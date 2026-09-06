"""Control plane: the multi-tenant registry + session resolver above the engine.

The engine (``tutor_v2``) is a single-session worker: every stone is already scoped by
``session_id``. This module adds the thin layer the frontend needs — many codebases per
user, each an independent session — WITHOUT changing the engine. A ``codebase`` is an
imported repo; a ``session`` is one ``(user, codebase)`` pairing whose id IS the engine
``session_id``. ``ControlPlane.open`` resolves a request to a fully-wired ``AppContext`` by
building the right ``TutorConfig`` and calling the existing ``build_session``.

Isolation is total: two codebases (or two users on their own codebases) never share engine
state, so their agent workflows run independently and concurrently. Migration to Supabase is
mechanical — these rows become Postgres rows keyed by ``user_id`` under row-level security.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import TutorConfig
from .db import Database
from .errors import ValidationError
from .factory import AppContext, build_session
from .session import AgentRun


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nonblank(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    return value


class SessionRegistry:
    """Reads/writes the codebases + sessions tables. No engine or agent logic."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_codebase(self, *, user_id: str, name: str, root_path: str) -> str:
        """Register a new codebase owned by ``user_id``; returns its id."""
        _nonblank(user_id, "user_id"); _nonblank(name, "name"); _nonblank(root_path, "root_path")
        codebase_id = str(uuid.uuid4())
        with self.db.transaction():
            self.db.connection.execute(
                "INSERT INTO codebases(id,user_id,name,root_path,created_at) VALUES(?,?,?,?,?)",
                (codebase_id, user_id, name, root_path, _now()))
        return codebase_id

    def get_codebase(self, *, codebase_id: str) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM codebases WHERE id=?", (codebase_id,))

    def list_codebases(self, *, user_id: str) -> list[dict[str, Any]]:
        """The user's codebases with their session id (if opened) and current unit count."""
        rows = self.db.query(
            "SELECT id,name,root_path,created_at FROM codebases WHERE user_id=? ORDER BY created_at,id",
            (user_id,))
        out: list[dict[str, Any]] = []
        for row in rows:
            session = self.db.one(
                "SELECT id FROM sessions WHERE user_id=? AND codebase_id=?", (user_id, row["id"]))
            session_id = session["id"] if session else None
            unit_count = 0
            if session_id is not None:
                unit_count = int(self.db.one(
                    "SELECT COUNT(*) AS n FROM units WHERE session_id=?", (session_id,))["n"])
            out.append({**row, "session_id": session_id, "unit_count": unit_count})
        return out

    def get_or_create_session(self, *, user_id: str, codebase_id: str) -> str:
        """Resolve the ``(user, codebase)`` session id, creating it once if needed."""
        codebase = self.get_codebase(codebase_id=codebase_id)
        if codebase is None:
            raise ValidationError("codebase does not exist")
        if codebase["user_id"] != user_id:
            raise ValidationError("codebase belongs to a different user")
        existing = self.db.one(
            "SELECT id FROM sessions WHERE user_id=? AND codebase_id=?", (user_id, codebase_id))
        if existing is not None:
            return str(existing["id"])
        session_id = f"s-{uuid.uuid4()}"
        with self.db.transaction():
            self.db.connection.execute(
                "INSERT INTO sessions(id,user_id,codebase_id,created_at) VALUES(?,?,?,?)",
                (session_id, user_id, codebase_id, _now()))
        return session_id


@dataclass(frozen=True, slots=True)
class ControlPlane:
    """Resolves a ``(user, codebase)`` request into a wired, isolated engine session."""

    state_root: Path
    agent_run: AgentRun

    def _registry_db(self) -> Database:
        return Database(self.state_root / "tutor.sqlite")

    def registry(self) -> SessionRegistry:
        return SessionRegistry(self._registry_db())

    def create_codebase(self, *, user_id: str, name: str, root_path: str) -> str:
        return self.registry().create_codebase(user_id=user_id, name=name, root_path=root_path)

    def list_codebases(self, *, user_id: str) -> list[dict[str, Any]]:
        return self.registry().list_codebases(user_id=user_id)

    def config_for(self, *, session_id: str, codebase_root: str, user_id: str) -> TutorConfig:
        state = self.state_root
        return TutorConfig(
            database_path=state / "tutor.sqlite",
            workspace_root=state / "projects" / session_id / "workspace",
            archive_root=state / "projects" / session_id / "archive",
            session_id=session_id,
            codebase_root=Path(codebase_root),
            learner_id=user_id,
        )

    def open(self, *, user_id: str, codebase_id: str) -> AppContext:
        """Return a fully-wired AppContext for this user's session on ``codebase_id``."""
        registry = self.registry()
        codebase = registry.get_codebase(codebase_id=codebase_id)
        if codebase is None:
            raise ValidationError("codebase does not exist")
        session_id = registry.get_or_create_session(user_id=user_id, codebase_id=codebase_id)
        config = self.config_for(session_id=session_id, codebase_root=codebase["root_path"],
                                 user_id=user_id)
        return build_session(config, self.agent_run)
