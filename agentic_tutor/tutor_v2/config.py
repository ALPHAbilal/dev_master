"""Configuration owned by the backend, with no UI or SDK dependency."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TutorConfig:
    """Locations and identity for exactly one local tutoring session."""

    database_path: Path
    workspace_root: Path
    archive_root: Path
    session_id: str
    codebase_root: Path | None = None
    learner_id: str = "local-learner"

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id must not be blank")
        if not self.learner_id.strip():
            raise ValueError("learner_id must not be blank")

    @classmethod
    def in_project(cls, project_root: Path, session_id: str) -> "TutorConfig":
        """Return conventional paths without creating files or directories."""
        state_root = project_root / ".claude" / "tutor"
        return cls(
            database_path=state_root / "tutor.sqlite",
            workspace_root=state_root / "projects" / session_id / "workspace",
            archive_root=state_root / "projects" / session_id / "archive",
            session_id=session_id,
            codebase_root=project_root,
        )
