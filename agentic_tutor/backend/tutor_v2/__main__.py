"""Persistent, single-worker HTTP entrypoint: python -m tutor_v2."""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from .app import create_app
from .db import Database
from .registry import ControlPlane
from .sdk_runtime import ClaudeAgentAdapter, RuntimeSettings, DEFAULT_MODEL
from .services import EventRecorder, WorkspaceService
from .session import agent_run_from_adapter


def build_app():
    state = Path(os.getenv("STATE_ROOT", "./state")).resolve()
    state.mkdir(parents=True, exist_ok=True)

    def run(wakeup, instruction):
        db = Database(state / "tutor.sqlite")
        try:
            row = db.one("SELECT s.id,s.user_id,c.root_path FROM sessions s JOIN codebases c "
                         "ON c.id=s.codebase_id WHERE s.id=?", (wakeup["session_id"],))
            if row is None:
                raise RuntimeError("Agent session does not exist")
            config = plane.config_for(session_id=row["id"], user_id=row["user_id"],
                                      codebase_root=row["root_path"])
            workspace = WorkspaceService(db, config)
            adapter = ClaudeAgentAdapter(config, workspace, EventRecorder(db, config, workspace),
                settings=RuntimeSettings(model=os.getenv("TUTOR_MODEL", DEFAULT_MODEL)))
            return agent_run_from_adapter(adapter)(wakeup, instruction)
        finally:
            db.close()

    plane = ControlPlane(state, run)
    source = os.getenv("CODEBASE_ROOT")
    return create_app(plane, source_root=Path(source) if source else None)


def main():
    uvicorn.run(build_app(), host=os.getenv("HOST", "0.0.0.0"),
                port=int(os.getenv("PORT", "8000")), workers=1)


if __name__ == "__main__":
    main()
