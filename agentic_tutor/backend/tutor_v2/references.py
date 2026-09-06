"""Highlight references ("pins") for asides: validation + a per-thread file store.

A learner may attach many highlights to a side-question, drawn from three sources: the
codebase (a real file+range), a test/editor tab (an *unsaved*, learner-supplied snapshot),
or the conversation (a pointer to another message). ``ReferenceValidator`` turns the raw
client list into a closed, normalized shape and rejects anything unsafe. ``PinStore`` then
freezes each normalized pin to a file under the thread's directory and writes a manifest,
so the aside agent is handed *paths + descriptions* and reads content through a tool —
never the raw blobs inlined into its prompt.

This module is read-only with respect to the engine stones and the workspace: validating a
pin never initializes, writes, or checkpoints a workspace, and never touches units/axes/
stack/probes/meta. The only writes are the pin files + manifest under the aside store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import TutorConfig
from .db import Database
from .errors import ValidationError

_KINDS = frozenset({"code", "test", "convo"})
MAX_REFS = 32
MAX_LABEL = 256              # unicode code points
MAX_SNIPPET_BYTES = 16_384
MAX_TEXT_BYTES = 65_536


def _string(value: Any, label: str, *, max_len: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    if max_len is not None and len(value) > max_len:
        raise ValidationError(f"{label} exceeds {max_len} characters")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError(f"{label} must be a positive integer")
    return value


class ReferenceValidator:
    """Validates and normalizes a raw client ref list into closed, locatable pins."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def validate(self, refs: Any, *, journey_id: int) -> list[dict[str, Any]]:
        """Return the normalized pins, or raise ValidationError. Order is preserved."""
        if refs is None:
            return []
        if not isinstance(refs, list):
            raise ValidationError("refs must be a list")
        if len(refs) > MAX_REFS:
            raise ValidationError(f"at most {MAX_REFS} references are allowed")
        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(refs):
            normalized.append(self._one(raw, index=index, journey_id=journey_id))
        return normalized

    # -- per-ref -----------------------------------------------------------------

    def _one(self, raw: Any, *, index: int, journey_id: int) -> dict[str, Any]:
        where = f"refs[{index}]"
        if not isinstance(raw, dict):
            raise ValidationError(f"{where} must be an object")
        if set(raw) != {"kind", "label", "snippet", "source"}:
            raise ValidationError(f"{where} must have exactly kind, label, snippet, source")
        kind = raw["kind"]
        if kind not in _KINDS:
            raise ValidationError(f"{where}.kind must be one of code, test, convo")
        label = _string(raw["label"], f"{where}.label", max_len=MAX_LABEL)
        snippet = _string(raw["snippet"], f"{where}.snippet")
        if len(snippet.encode("utf-8")) > MAX_SNIPPET_BYTES:
            raise ValidationError(f"{where}.snippet exceeds {MAX_SNIPPET_BYTES} bytes")
        source = raw["source"]
        if not isinstance(source, dict):
            raise ValidationError(f"{where}.source must be an object")
        if kind == "code":
            src = self._code_source(source, snippet, where=where)
        elif kind == "test":
            src = self._test_source(source, snippet, where=where)
        else:
            src = self._convo_source(source, snippet, where=where, journey_id=journey_id)
        return {"id": f"pin_{index + 1:02d}", "kind": kind,
                "label": label, "snippet": snippet, "source": src}

    def _code_source(self, source: dict[str, Any], snippet: str, *, where: str) -> dict[str, Any]:
        if set(source) != {"file", "lo", "hi"}:
            raise ValidationError(f"{where}.source (code) must have exactly file, lo, hi")
        file = _string(source["file"], f"{where}.source.file")
        lo = _positive_int(source["lo"], f"{where}.source.lo")
        hi = _positive_int(source["hi"], f"{where}.source.hi")
        if hi < lo:
            raise ValidationError(f"{where}.source.hi must be >= lo")
        root = self._codebase_root()
        candidate = (root / file).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValidationError(f"{where}.source.file escapes the codebase root")
        if candidate.is_symlink() or not candidate.is_file():
            raise ValidationError(f"{where}.source.file is not a readable file")
        lines = candidate.read_text(encoding="utf-8").splitlines()
        if hi > len(lines):
            raise ValidationError(f"{where}.source range exceeds the file")
        if "\n".join(lines[lo - 1:hi]) != snippet:
            raise ValidationError(f"{where}.snippet does not match the code at file:lo-hi")
        return {"file": candidate.relative_to(root).as_posix(), "lo": lo, "hi": hi}

    def _test_source(self, source: dict[str, Any], snippet: str, *, where: str) -> dict[str, Any]:
        # A learner-supplied, unsaved editor tab. Not verified against disk; stored verbatim.
        if set(source) != {"editor_id", "text"}:
            raise ValidationError(f"{where}.source (test) must have exactly editor_id, text")
        editor_id = _string(source["editor_id"], f"{where}.source.editor_id")
        text = source["text"]
        if not isinstance(text, str) or not text:
            raise ValidationError(f"{where}.source.text must be a non-empty string")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValidationError(f"{where}.source.text exceeds {MAX_TEXT_BYTES} bytes")
        if snippet not in text:
            raise ValidationError(f"{where}.snippet is not part of the editor text")
        return {"editor_id": editor_id, "text": text}

    def _convo_source(self, source: dict[str, Any], snippet: str, *, where: str,
                      journey_id: int) -> dict[str, Any]:
        if set(source) != {"message_id"}:
            raise ValidationError(f"{where}.source (convo) must have exactly message_id")
        message_id = _positive_int(source["message_id"], f"{where}.source.message_id")
        row = self.db.one(
            "SELECT content FROM conversation_messages WHERE id=? AND journey_id=?",
            (message_id, journey_id))
        if not row:
            raise ValidationError(f"{where}.source.message_id is not in this journey")
        if snippet not in row["content"]:
            raise ValidationError(f"{where}.snippet is not part of the referenced message")
        return {"message_id": message_id}

    def _codebase_root(self) -> Path:
        if self.config.codebase_root is None:
            raise ValidationError("codebase_root is required to validate a code reference")
        root = self.config.codebase_root.resolve()
        if not root.is_dir():
            raise ValidationError("configured codebase_root is not a directory")
        return root


class PinStore:
    """Freezes normalized pins to files under the thread's dir and writes a manifest.

    Layout:  <aside store>/<thread_id>/manifest.json
             <aside store>/<thread_id>/pins/<pin id>.txt

    The manifest is the pointer surface handed to the agent: one entry per pin with a
    short description and a relative path. The agent reads a pin via ``read`` (path-scoped).
    """

    def __init__(self, config: TutorConfig) -> None:
        self.config = config

    def _thread_dir(self, thread_id: str) -> Path:
        if "/" in thread_id or "\\" in thread_id or thread_id in {"", ".", ".."}:
            raise ValidationError("invalid thread_id")
        return (self._base() / thread_id).resolve()

    def _base(self) -> Path:
        return (self.config.archive_root.parent / "asides").resolve()

    def materialize(self, *, thread_id: str, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Write each pin's snippet to a file; return the manifest (also written to disk)."""
        thread_dir = self._thread_dir(thread_id)
        pins_dir = thread_dir / "pins"
        pins_dir.mkdir(parents=True, exist_ok=True)
        manifest: list[dict[str, Any]] = []
        for ref in refs:
            rel = f"pins/{ref['id']}.txt"
            (thread_dir / rel).write_text(ref["snippet"], encoding="utf-8")
            manifest.append({"id": ref["id"], "kind": ref["kind"],
                             "description": self._describe(ref), "path": rel})
        (thread_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def manifest(self, *, thread_id: str) -> list[dict[str, Any]]:
        """Return the thread's manifest (pointer surface for the agent), or [] if none."""
        manifest_path = self._thread_dir(thread_id) / "manifest.json"
        if not manifest_path.is_file():
            return []
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def read(self, *, thread_id: str, rel_path: str) -> str:
        """Read one materialized pin file, refusing any path that escapes the thread dir."""
        thread_dir = self._thread_dir(thread_id)
        target = (thread_dir / rel_path).resolve()
        if target != thread_dir and thread_dir not in target.parents:
            raise ValidationError("pin path escapes the thread directory")
        if target.is_symlink() or not target.is_file():
            raise ValidationError("pin file does not exist")
        return target.read_text(encoding="utf-8")

    @staticmethod
    def _describe(ref: dict[str, Any]) -> str:
        source, kind = ref["source"], ref["kind"]
        if kind == "code":
            return f"{ref['label']} — {source['file']}:{source['lo']}-{source['hi']}"
        if kind == "test":
            return f"{ref['label']} — editor tab {source['editor_id']} (unsaved)"
        return f"{ref['label']} — conversation message #{source['message_id']}"
