"""Stage 5 tests: minimal packets and non-leaking capability/context scopes."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tutor_v2 import CapabilityPolicy, Database, Router, TutorConfig, WakeupBuilder, WorkspaceService


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    codebase = root / "codebase"
    codebase.mkdir()
    (codebase / "run.py").write_text("def main():\n    return 42\n\nprint(main())\n", encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1", codebase_root=codebase)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(target="run.py", document_id="learner-main", display_name="solution.py", language="python")
    router = Router(db, config)
    decision = router.commit_map({
        "kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
        "objective_covered": True,
        "units": [{"slug": "main", "file": "run.py", "lo": 1, "hi": 2, "depth": 0, "parent": None, "axes": ["COMPREHEND"]}],
        "order": ["main"],
    })
    return temp, db, config, router, decision


def test_policy_is_closed_and_step_scoped():
    policy = CapabilityPolicy()
    assert policy.permits("wakeup.probe", "read_code_slice")
    assert not policy.permits("wakeup.probe", "write_workspace")
    assert "read_event_trace" in policy.for_step("wakeup.distill")


def test_probe_packet_injects_only_current_slice_axis_profile_and_budget():
    temp, db, config, _, decision = _setup()
    try:
        packet = WakeupBuilder(db, config).build(step="wakeup.probe", unit_id=decision.unit_id, axis=decision.axis)
        assert packet["agent"] == "TEACHER"
        assert packet["capabilities"] == ["read_code_slice", "read_axis_evidence", "read_probe_history"]
        assert packet["context"]["source"] == {
            "role": "code", "file": "run.py", "lo": 1, "hi": 2,
            "text": "def main():\n    return 42", "highlight": True,
        }
        assert packet["context"]["axis"]["name"] == "COMPREHEND"
        assert packet["context"]["hop_budget"] == 2
        assert "events" not in packet["context"] and "archive" not in packet["context"]
    finally:
        db.close()
        temp.cleanup()


def test_grade_packet_accepts_only_current_evidence_and_resume_has_same_shape():
    temp, db, config, _, decision = _setup()
    try:
        builder = WakeupBuilder(db, config)
        transient = {"learner_answer": "main prevents import side effects", "question_ref": "events:1"}
        normal = builder.build(step="wakeup.grade", unit_id=decision.unit_id, axis=decision.axis, transient=transient)
        resumed = builder.build_resumed(
            continuation={"next_step": "wakeup.grade", "awaiting": "none", "outstanding_question_ref": None, "context_refs": ["events:1"]},
            unit_id=decision.unit_id, axis=decision.axis, transient=transient,
        )
        assert resumed == normal
        assert "continuation" not in resumed["context"] and "resum" not in str(resumed["context"]).lower()
    finally:
        db.close()
        temp.cleanup()
