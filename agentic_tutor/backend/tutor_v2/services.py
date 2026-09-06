"""Code-owned services for mutable tutor state.

No service imports an agent SDK. Agents later receive narrow adapters around these
methods; they never receive the database connection or filesystem paths directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import uuid4

from .config import TutorConfig
from .contracts import validate_action_event, validate_archive_manifest
from .db import Database
from .domain import Handoff, Workspace
from .errors import StaleWorkspaceRevisionError, ValidationError


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValidationError("value must be JSON serializable") from error


def _json_object(value: str, label: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValidationError(f"stored {label} is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise ValidationError(f"stored {label} must be a JSON object")
    return decoded


def _safe_filename(name: str) -> str:
    candidate = Path(name)
    if not name or candidate.name != name or name in {".", ".."}:
        raise ValidationError("display_name must be one safe filename")
    return name


def _safe_slug(slug: str) -> str:
    if not slug or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in slug):
        raise ValidationError("unit slug may contain only letters, digits, hyphen, and underscore")
    return slug


def _atomic_write(path: Path, content: bytes) -> None:
    """Durably replace one file without exposing a partial write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and Path(temporary_name).exists():
            Path(temporary_name).unlink()


@dataclass(frozen=True, slots=True)
class WorkspaceWrite:
    workspace: Workspace
    changed: bool


class WorkspaceService:
    """The only writer of the learner-visible logical document."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def initialize(
        self,
        *,
        target: str,
        document_id: str,
        display_name: str,
        language: str,
        content: str = "",
    ) -> Workspace:
        """Create or verify the one visible document for this session."""
        display_name = _safe_filename(display_name)
        if not target or not document_id or not language:
            raise ValidationError("target, document_id, and language are required")
        path = self.config.workspace_root / display_name
        encoded = content.encode("utf-8")
        digest = sha256(encoded).hexdigest()
        _atomic_write(path, encoded)
        with self.db.transaction():
            existing = self.db.connection.execute(
                "SELECT target,document_id,display_name,workspace_revision,workspace_hash "
                "FROM meta WHERE session_id=?", (self.config.session_id,)
            ).fetchone()
            if existing and (existing["target"] != target or existing["document_id"] != document_id):
                raise ValidationError("session is already initialized for another target or document")
            if existing:
                revision = int(existing["workspace_revision"])
                if existing["workspace_hash"] != digest:
                    revision += 1
                self.db.connection.execute(
                    "UPDATE meta SET display_name=?,language=?,workspace_path=?,workspace_revision=?,workspace_hash=?,updated_at=datetime('now') "
                    "WHERE session_id=?",
                    (display_name, language, str(path), revision, digest, self.config.session_id),
                )
            else:
                revision = 0
                self.db.connection.execute(
                    "INSERT INTO meta(session_id,target,document_id,display_name,language,workspace_path,workspace_revision,workspace_hash) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (self.config.session_id, target, document_id, display_name, language, str(path), revision, digest),
                )
        self._write_checkpoint(document_id, display_name, revision, encoded, digest)
        return Workspace(document_id, display_name, revision, digest)

    def read(self) -> tuple[Workspace, str]:
        row = self._meta()
        workspace = Workspace(
            document_id=row["document_id"],
            display_name=row["display_name"],
            revision=int(row["workspace_revision"]),
            revision_hash=row["workspace_hash"],
        )
        path = Path(row["workspace_path"])
        if not path.is_file():
            raise ValidationError("workspace metadata exists but document is missing")
        return workspace, path.read_text(encoding="utf-8")

    def write(self, *, expected_revision: int, content: str) -> WorkspaceWrite:
        """Apply one optimistic-concurrency guarded workspace edit."""
        with self.db.transaction():
            row = self._meta()
            actual_revision = int(row["workspace_revision"])
            if expected_revision != actual_revision:
                raise StaleWorkspaceRevisionError(
                    f"workspace revision is {actual_revision}, not {expected_revision}"
                )
            encoded = content.encode("utf-8")
            digest = sha256(encoded).hexdigest()
            changed = digest != row["workspace_hash"]
            if changed:
                _atomic_write(Path(row["workspace_path"]), encoded)
            revision = actual_revision + int(changed)
            self.db.connection.execute(
                "UPDATE meta SET workspace_revision=?,workspace_hash=?,updated_at=datetime('now') WHERE session_id=?",
                (revision, digest, self.config.session_id),
            )
            if changed:
                self._write_checkpoint(row["document_id"], row["display_name"], revision, encoded, digest)
        return WorkspaceWrite(
            Workspace(row["document_id"], row["display_name"], revision, digest), changed
        )

    def checkpoint(self) -> Workspace:
        """Return the current revision and guarantee its hidden evidence copy exists."""
        workspace, content = self.read()
        digest = sha256(content.encode("utf-8")).hexdigest()
        if digest != workspace.revision_hash:
            raise ValidationError("workspace file changed outside the guarded workspace service")
        self._write_checkpoint(
            workspace.document_id, workspace.display_name, workspace.revision,
            content.encode("utf-8"), digest,
        )
        return workspace

    def checkpoints_for_hashes(self, hashes: set[str]) -> list[dict[str, Any]]:
        """Return the internal snapshots referenced by test events, and no others."""
        if not hashes:
            return []
        workspace, _ = self.read()
        directory = self._revision_directory(workspace.document_id)
        matches: list[dict[str, Any]] = []
        for path in sorted(directory.glob("revision-*")):
            content = path.read_bytes()
            digest = sha256(content).hexdigest()
            if digest in hashes:
                revision_text = path.stem.removeprefix("revision-")
                matches.append({"revision": int(revision_text), "hash": digest, "file": path.name, "content": content})
        found = {entry["hash"] for entry in matches}
        missing = hashes - found
        if missing:
            raise ValidationError("a test event references a missing workspace checkpoint")
        return matches

    def _write_checkpoint(self, document_id: str, display_name: str, revision: int, content: bytes, digest: str) -> None:
        suffix = Path(display_name).suffix
        checkpoint = self._revision_directory(document_id) / f"revision-{revision:08d}{suffix}"
        if checkpoint.exists():
            if sha256(checkpoint.read_bytes()).hexdigest() != digest:
                raise ValidationError("workspace revision checkpoint hash collision")
            return
        _atomic_write(checkpoint, content)

    def _revision_directory(self, document_id: str) -> Path:
        return self.config.workspace_root / ".revisions" / document_id

    def _meta(self) -> dict:
        row = self.db.one("SELECT * FROM meta WHERE session_id=?", (self.config.session_id,))
        if not row or not row["document_id"] or not row["workspace_path"]:
            raise ValidationError("workspace is not initialized for this session")
        return row


class EventRecorder:
    """Append observable activity before policy or agent interpretation happens."""

    def __init__(self, db: Database, config: TutorConfig, workspace: WorkspaceService | None = None) -> None:
        self.db = db
        self.config = config
        self.workspace = workspace or WorkspaceService(db, config)

    def record(
        self,
        *,
        unit_id: int,
        document_id: str,
        kind: str,
        payload: dict[str, Any],
        axis: str | None = None,
        result: dict[str, Any] | None = None,
        revision_hash: str | None = None,
    ) -> int:
        if kind == "test":
            checkpoint = self.workspace.checkpoint()
            if revision_hash is not None and revision_hash != checkpoint.revision_hash:
                raise ValidationError("test event revision_hash does not match the current workspace")
            revision_hash = checkpoint.revision_hash
            payload = {**payload, "workspace_checkpoint": {
                "revision": checkpoint.revision, "hash": checkpoint.revision_hash,
            }}
        packet = validate_action_event({
            "unit_id": unit_id, "document_id": document_id, "kind": kind,
            "payload": payload, "axis": axis, "result": result,
            "revision_hash": revision_hash,
        })
        with self.db.transaction():
            self._assert_unit_ownership(packet["unit_id"])
            cursor = self.db.connection.execute(
                "INSERT INTO events(session_id,unit_id,axis,document_id,kind,payload_json,result_json,revision_hash) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    self.config.session_id, packet["unit_id"], packet.get("axis"), packet["document_id"],
                    packet["kind"], _json(packet["payload"]),
                    _json(packet["result"]) if packet.get("result") is not None else None,
                    packet.get("revision_hash"),
                ),
            )
        return int(cursor.lastrowid)

    def list_for_unit(self, unit_id: int) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM events WHERE session_id=? AND unit_id=? ORDER BY id",
            (self.config.session_id, unit_id),
        )
        for row in rows:
            row["payload"] = _json_object(row.pop("payload_json"), "event payload")
            row["result"] = _json_object(row.pop("result_json"), "event result") if row.get("result_json") else None
        return rows

    def _assert_unit_ownership(self, unit_id: int) -> None:
        row = self.db.one("SELECT session_id FROM units WHERE id=?", (unit_id,))
        if not row or row["session_id"] != self.config.session_id:
            raise ValidationError("event unit does not belong to this session")


@dataclass(frozen=True, slots=True)
class ArchiveReceipt:
    directory: Path
    event_ids: tuple[int, ...]
    workspace_hash: str
    checkpoint_hashes: tuple[str, ...]


class ArchiveService:
    """Seal a unit artifact before removing the corresponding live events."""

    def __init__(self, db: Database, config: TutorConfig, workspace: WorkspaceService, events: EventRecorder) -> None:
        self.db = db
        self.config = config
        self.workspace = workspace
        self.events = events

    def seal(
        self,
        *,
        unit_id: int,
        unit_slug: str,
        title: str,
        final_verdict: str,
        axes_tested: list[str],
        tests: list[dict[str, Any]],
        evidence: list[str],
        resume_at: dict[str, Any] | None = None,
    ) -> ArchiveReceipt:
        """Write a durable artifact and then move only its captured events out of SQLite.

        A repeated call after a crash uses the existing manifest's captured event ids,
        so it never drops later events that did not belong to the original archive.
        """
        unit_slug = _safe_slug(unit_slug)
        if not title.strip():
            raise ValidationError("archive title is required")
        workspace, content = self.workspace.read()
        events = self.events.list_for_unit(unit_id)
        target = self.config.archive_root / unit_slug
        if target.exists():
            manifest = _json_object((target / "manifest.json").read_text(encoding="utf-8"), "archive manifest")
            captured = tuple(int(event_id) for event_id in manifest["event_ids"])
            digest = str(manifest["workspace_hash"])
            checkpoint_hashes = tuple(item["hash"] for item in manifest["workspace_checkpoints"])
        else:
            captured = tuple(int(event["id"]) for event in events)
            digest = workspace.revision_hash or sha256(content.encode("utf-8")).hexdigest()
            checkpoint_hashes = tuple(sorted({event["revision_hash"] for event in events if event["kind"] == "test" and event["revision_hash"]}))
            checkpoints = self.workspace.checkpoints_for_hashes(set(checkpoint_hashes))
            manifest = {
                "unit": unit_slug,
                "title": title,
                "logical_document": {"id": workspace.document_id, "display_name": workspace.display_name},
                "final_verdict": final_verdict,
                "axes_tested": axes_tested,
                "tests": tests,
                "evidence": evidence,
                "event_ids": list(captured),
                "event_log": "events.jsonl",
                "workspace_snapshot": f"workspace-snapshot{Path(workspace.display_name).suffix}",
                "workspace_hash": digest,
                "workspace_checkpoints": [
                    {"revision": checkpoint["revision"], "hash": checkpoint["hash"],
                     "file": f"workspace-revisions/{checkpoint['file']}"}
                    for checkpoint in checkpoints
                ],
                "resume_at": resume_at,
            }
            validate_archive_manifest(manifest)
            self._write_artifact(target, manifest, events, content, checkpoints)

        with self.db.transaction():
            if captured:
                placeholders = ",".join("?" for _ in captured)
                self.db.connection.execute(
                    f"DELETE FROM events WHERE session_id=? AND unit_id=? AND id IN ({placeholders})",
                    (self.config.session_id, unit_id, *captured),
                )
        return ArchiveReceipt(target, captured, digest, checkpoint_hashes)

    def _write_artifact(self, target: Path, manifest: dict[str, Any], events: list[dict[str, Any]], content: str, checkpoints: list[dict[str, Any]]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.parent / f".{target.name}.staging-{uuid4().hex}"
        try:
            staging.mkdir()
            _atomic_write(staging / "manifest.json", (_json(manifest) + "\n").encode("utf-8"))
            event_lines = "".join(_json(event) + "\n" for event in events)
            _atomic_write(staging / "events.jsonl", event_lines.encode("utf-8"))
            snapshot = str(manifest["workspace_snapshot"])
            _atomic_write(staging / snapshot, content.encode("utf-8"))
            for checkpoint in checkpoints:
                _atomic_write(staging / "workspace-revisions" / checkpoint["file"], checkpoint["content"])
            os.replace(staging, target)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise


class HandoffService:
    """Read and replace the latest SQLite warm-start record."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def save(self, payload: dict[str, Any], *, parked_stack: bool = False) -> Handoff:
        encoded = _json(payload)
        with self.db.transaction():
            self.db.connection.execute(
                "INSERT INTO handoff(session_id,payload_json,parked_stack) VALUES(?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET payload_json=excluded.payload_json,parked_stack=excluded.parked_stack,updated_at=datetime('now')",
                (self.config.session_id, encoded, int(parked_stack)),
            )
        return Handoff(payload, parked_stack)

    def load(self) -> Handoff | None:
        row = self.db.one("SELECT payload_json,parked_stack FROM handoff WHERE session_id=?", (self.config.session_id,))
        if not row:
            return None
        return Handoff(_json_object(row["payload_json"], "handoff payload"), bool(row["parked_stack"]))


class StateReader:
    """Read scoped state projections for later packet builders and service calls."""

    def __init__(self, db: Database, config: TutorConfig) -> None:
        self.db = db
        self.config = config

    def session_summary(self) -> dict[str, Any]:
        meta = self.db.one("SELECT * FROM meta WHERE session_id=?", (self.config.session_id,))
        if not meta:
            raise ValidationError("session is not initialized")
        current = None
        if meta["current_unit_id"] is not None:
            current = self.db.one("SELECT * FROM units WHERE id=?", (meta["current_unit_id"],))
        return {"meta": meta, "current_unit": current}

    def unit_axes(self, unit_id: int) -> list[dict[str, Any]]:
        return self.db.query("SELECT * FROM axes WHERE unit_id=? ORDER BY axis", (unit_id,))
