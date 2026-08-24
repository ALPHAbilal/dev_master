"""Composite journey archival and the unified archive reader.

``JourneyArchiveService`` writes episode checkpoints and the final composite journey
index without changing what the existing per-unit ``ArchiveService.seal()`` means. It
coordinates: a park creates an immutable episode checkpoint; ownership finalizes the
composite journey. ``ArchiveReader`` reads both the new composite format and legacy
per-unit archives, returning the same snapshot shape the live ``JourneyReader`` uses, so
the UI has one read contract (proposal §10–12).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from .config import TutorConfig
from .db import Database
from .errors import ValidationError
from .journey_reader import JourneyReader

ARCHIVE_FORMAT_VERSION = 1


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid4().hex}"
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True)
class EpisodeReceipt:
    directory: Path
    episode_number: int
    kind: str


@dataclass(frozen=True, slots=True)
class JourneyArchiveReceipt:
    directory: Path
    manifest_path: Path


class JourneyArchiveService:
    """Writes episode checkpoints and the composite journey manifest atomically."""

    def __init__(self, db: Database, config: TutorConfig, reader: JourneyReader | None = None) -> None:
        self.db = db
        self.config = config
        self.reader = reader or JourneyReader(db, config)

    def _root_slug(self, journey_id: int) -> str:
        row = self.db.one(
            "SELECT u.slug AS slug FROM journeys j JOIN units u ON u.id=j.root_unit_id WHERE j.id=?",
            (journey_id,),
        )
        if not row:
            raise ValidationError("journey does not exist")
        return str(row["slug"])

    def _journey_dir(self, journey_id: int) -> Path:
        return self.config.archive_root / self._root_slug(journey_id)

    def next_episode_number(self, journey_id: int) -> int:
        """The next 1-based episode index, from the episode directories already written."""
        episodes_dir = self._journey_dir(journey_id) / "episodes"
        if not episodes_dir.is_dir():
            return 1
        return sum(1 for path in episodes_dir.glob("*-*") if path.is_dir()) + 1

    def checkpoint_episode(self, *, journey_id: int, episode_number: int, kind: str) -> EpisodeReceipt:
        """Write an immutable point-in-time snapshot of the journey for one episode."""
        if kind not in {"parked", "owned"}:
            raise ValidationError("episode kind must be parked or owned")
        if episode_number < 1:
            raise ValidationError("episode_number must be positive")
        snapshot = self.reader.read(journey_id)
        directory = self._journey_dir(journey_id) / "episodes" / f"{episode_number:04d}-{kind}"
        if directory.exists():
            # Idempotent: a repeated checkpoint keeps the original immutable snapshot.
            return EpisodeReceipt(directory, episode_number, kind)
        self._write_dir(directory, {
            "snapshot.json": _json_bytes(snapshot),
            "conversation.jsonl": self._conversation_jsonl(snapshot),
        })
        return EpisodeReceipt(directory, episode_number, kind)

    def finalize(self, journey_id: int) -> JourneyArchiveReceipt:
        """Write the composite journey manifest that indexes the whole root journey."""
        snapshot = self.reader.read(journey_id)
        directory = self._journey_dir(journey_id)
        episodes_dir = directory / "episodes"
        episodes = sorted(p.name for p in episodes_dir.glob("*-*")) if episodes_dir.exists() else []
        manifest = {
            "format_version": ARCHIVE_FORMAT_VERSION,
            "kind": "composite-journey",
            "root_slug": self._root_slug(journey_id),
            "journey": snapshot["journey"],
            "episodes": episodes,
            "snapshot": snapshot,
        }
        self._write_dir(directory, {
            "journey-manifest.json": _json_bytes(manifest),
            "conversation.jsonl": self._conversation_jsonl(snapshot),
            "graph.json": _json_bytes({
                "nodes": snapshot["semantic_nodes"], "edges": snapshot["semantic_edges"],
            }),
        }, merge=True)
        return JourneyArchiveReceipt(directory, directory / "journey-manifest.json")

    def _conversation_jsonl(self, snapshot: dict[str, Any]) -> bytes:
        lines = [json.dumps(message, sort_keys=True) for message in snapshot["conversation"]]
        return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")

    def _write_dir(self, directory: Path, files: dict[str, bytes], *, merge: bool = False) -> None:
        """Atomically materialize ``files`` into ``directory`` via a staging swap.

        With ``merge`` the new files are added over any existing directory content
        (used to lay the composite index beside already-written episodes); otherwise
        the directory is created fresh and must not already exist.
        """
        if merge and directory.exists():
            for name, content in files.items():
                _atomic_write(directory / name, content)
            return
        directory.parent.mkdir(parents=True, exist_ok=True)
        staging = directory.parent / f".{directory.name}.staging-{uuid4().hex}"
        try:
            staging.mkdir()
            for name, content in files.items():
                _atomic_write(staging / name, content)
            os.replace(staging, directory)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise


class ArchiveReader:
    """Read composite journeys and legacy per-unit archives into the projection shape."""

    def __init__(self, config: TutorConfig) -> None:
        self.config = config

    def read_journey(self, root_slug: str) -> dict[str, Any]:
        """Return the archived journey snapshot, marked as an archive source."""
        manifest_path = self.config.archive_root / root_slug / "journey-manifest.json"
        if not manifest_path.is_file():
            raise ValidationError(f"no composite journey archive for {root_slug}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format_version") != ARCHIVE_FORMAT_VERSION:
            raise ValidationError("unsupported journey archive format version")
        snapshot = dict(manifest["snapshot"])
        snapshot["source"] = "archive"
        return snapshot

    def read_unit_archive(self, unit_slug: str) -> dict[str, Any]:
        """Read a legacy per-unit ``ArchiveService`` manifest, unchanged in meaning."""
        manifest_path = self.config.archive_root / unit_slug / "manifest.json"
        if not manifest_path.is_file():
            raise ValidationError(f"no per-unit archive for {unit_slug}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def list_journeys(self) -> list[str]:
        root = self.config.archive_root
        if not root.is_dir():
            return []
        return sorted(p.name for p in root.iterdir()
                      if (p / "journey-manifest.json").is_file())
