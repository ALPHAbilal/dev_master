"""Explicit live Claude Agent SDK smoke test; never run as part of normal tests."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from tutor_v2 import (
    ClaudeAgentAdapter,
    Database,
    EventRecorder,
    Router,
    TutorConfig,
    WakeupBuilder,
    WorkspaceService,
)


async def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = TutorConfig(
            root / "state.sqlite", root / "workspace", root / "archive", "sdk-smoke",
            codebase_root=root,
        )
        (root / "run.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
        db = Database(config.database_path)
        try:
            workspace = WorkspaceService(db, config)
            workspace.initialize(
                target="run.py", document_id="learner", display_name="solution.py",
                language="python", content="answer = 42\n",
            )
            decision = Router(db, config).commit_map({
                "kind": "return.map", "target": "run.py", "mode": "initial",
                "continues_after": None, "objective_covered": True,
                "units": [{
                    "slug": "main", "file": "run.py", "lo": 1, "hi": 2,
                    "depth": 0, "parent": None, "axes": ["COMPREHEND"],
                }],
                "order": ["main"],
            })
            packet = WakeupBuilder(db, config).build(
                step="wakeup.probe", unit_id=decision.unit_id, axis=decision.axis,
            )
            print("SDK_SMOKE_STARTED", flush=True)
            text = await ClaudeAgentAdapter(
                config, workspace, EventRecorder(db, config, workspace),
            ).run(
                packet,
                "You are a connectivity smoke test. Call read_code_slice before replying. "
                "Then reply with exactly: SDK_SMOKE_OK",
            )
            print("MODEL_TEXT:", repr(text), flush=True)
        finally:
            db.close()


if __name__ == "__main__":
    asyncio.run(main())
