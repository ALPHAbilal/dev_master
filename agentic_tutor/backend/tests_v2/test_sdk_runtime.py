"""Stage 6 tests: an SDK-free proof of the real adapter's security boundary."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tutor_v2 import (
    ClaudeAgentAdapter, DEFAULT_MODEL, Database, EventRecorder, Router,
    RuntimeSettings, TutorConfig, TutorToolGateway, WorkspaceService,
)
from tutor_v2.packets import WakeupBuilder
from tutor_v2.errors import CapabilityUnavailableError


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    codebase = root / "codebase"
    codebase.mkdir()
    (codebase / "run.py").write_text("def main():\n    return 42\n", encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1", codebase_root=codebase)
    db = Database(config.database_path)
    workspace = WorkspaceService(db, config)
    workspace.initialize(target="run.py", document_id="learner", display_name="solution.py", language="python", content="answer = 42\n")
    router = Router(db, config)
    decision = router.commit_map({
        "kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
        "objective_covered": True,
        "units": [{"slug": "main", "file": "run.py", "lo": 1, "hi": 2, "depth": 0, "parent": None, "axes": ["COMPREHEND"]}],
        "order": ["main"],
    })
    return temp, db, config, workspace, EventRecorder(db, config, workspace), decision


def test_launch_spec_is_haiku_unbounded_and_blocks_every_builtin_escape_hatch():
    temp, db, config, workspace, events, decision = _setup()
    try:
        wakeup = WakeupBuilder(db, config).build(step="wakeup.probe", unit_id=decision.unit_id, axis=decision.axis)
        spec = ClaudeAgentAdapter(config, workspace, events).launch_spec(wakeup, "Probe the learner.")
        assert spec.model == DEFAULT_MODEL == "claude-haiku-4-5-20251001"
        assert spec.max_turns is None and spec.max_budget_usd is None
        assert spec.allowed_tools == (
            "mcp__tutor__read_code_slice", "mcp__tutor__read_axis_evidence", "mcp__tutor__read_probe_history",
        )
        assert {"Bash", "Write", "Edit", "Task", "Agent"} <= set(spec.disallowed_tools)
    finally:
        db.close()
        temp.cleanup()


def test_gateway_only_executes_capabilities_granted_to_that_wakeup():
    temp, db, config, workspace, events, decision = _setup()
    try:
        wakeup = WakeupBuilder(db, config).build(step="wakeup.probe", unit_id=decision.unit_id, axis=decision.axis)
        gateway = TutorToolGateway(config, workspace, events, wakeup)
        assert gateway.call("read_code_slice", {})["text"] == "def main():\n    return 42"
        try:
            gateway.call("read_workspace", {})
            assert False, "probe must not gain workspace access"
        except CapabilityUnavailableError:
            pass
    finally:
        db.close()
        temp.cleanup()


def test_settings_can_change_model_later_without_creating_an_implicit_limit():
    settings = RuntimeSettings(model="example-model")
    assert settings.model == "example-model"
    assert settings.max_turns is None and settings.max_budget_usd is None
