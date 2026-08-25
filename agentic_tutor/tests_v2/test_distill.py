"""Stage 10 tests: the DISTILL turn (seal the unit proof + apply the learner diff)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    ArchiveService, Database, EventRecorder, JourneyArchiveService, LearnerModelService,
    Router, SemanticGraphService, SessionRunner, TurnOrchestrator, TutorConfig, WakeupBuilder,
    WorkspaceService,
)

_SAMPLE = "def load(path):\n    return read(path)\n\n\ndef read(path):\n    return {}\n"


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    db = Database(config.database_path)
    workspace = WorkspaceService(db, config)
    workspace.initialize(target="run.py", document_id="learner-main",
                         display_name="solution.py", language="python")
    events = EventRecorder(db, config, workspace)
    router = Router(db, config)
    orchestrator = TurnOrchestrator(
        db, config, router,
        graph=SemanticGraphService(db, config),
        archive=JourneyArchiveService(db, config),
        unit_archive=ArchiveService(db, config, workspace, events),
        learner_model=LearnerModelService(db, config),
    )
    wakeups = WakeupBuilder(db, config)
    return temp, db, config, router, orchestrator, wakeups


def _map_blocks():
    unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6, "depth": 0, "parent": None,
            "axes": ["COMPREHEND"]}
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": [unit],
                        "order": ["loader"]})]


def _distill_blocks():
    return [json.dumps({
        "kind": "return.distill", "unit": "loader", "title": "Loader",
        "logical_document": {"id": "learner-main", "display_name": "solution.py"},
        "final_verdict": "OWNED", "axes_tested": ["COMPREHEND"],
        "tests": [{"axis": "COMPREHEND", "prompt": "what does load do?", "expected": "reads"}],
        "evidence": ["transcript:t1"], "event_log": "events.jsonl",
        "workspace_snapshot": "workspace-snapshot.py", "resume_at": None,
        "learner_diff": {"can": ["read a loader"], "cant": [],
                         "misconceptions": [{"belief": "load mutates path",
                                             "disproved_by": "transcript:t1"}]},
        "handoff": {"next_unit": "loader", "dive_depth": 0, "why": "done", "watch": "nothing"},
    })]


def _make_agent():
    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does load(path) do?"]
        if step == "wakeup.grade":
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                                "category": "correct-deep", "evidence_ref": "events:1",
                                "hidden_gap": None})]
        if step == "wakeup.distill":
            return _distill_blocks()
        raise AssertionError(f"unexpected step {step}")
    return run


def _drive_to_owned(session):
    mapped = session.run_mapping()
    jid, unit_id = mapped.journey_id, mapped.decision.unit_id
    question = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                    turn_id="t1", save_resume_question=True)
    result = session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                               turn_id="t1", question=question, answer="It reads then returns.")
    assert result.decision.next_step == "wakeup.distill"
    return jid, unit_id


def test_distill_seals_artifact_and_applies_learner_diff():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orchestrator, _make_agent())
        jid, unit_id = _drive_to_owned(session)

        distilled = session.run_distill(unit_id=unit_id)
        assert distilled.journey_id == jid

        # The per-unit proof artifact was sealed to disk.
        assert (config.archive_root / "loader" / "manifest.json").is_file()

        # The lifecycle fact exists.
        assert db.one(
            "SELECT COUNT(*) AS n FROM journey_events WHERE journey_id=? AND event_type='unit_distilled'",
            (jid,)) == {"n": 1}

        # The learner profile absorbed the diff (state-machine merge).
        profile = LearnerModelService(db, config).read()
        assert "read a loader" in profile["can"]
        assert any(m["belief"] == "load mutates path" and m.get("status") == "disproved"
                   for m in profile["misconceptions"])

        # finish_root still works after distill (unit state untouched by distill).
        session.finish_root(root_unit_id=unit_id)
    finally:
        db.close()
        temp.cleanup()


def test_distill_is_idempotent_on_replay():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orchestrator, _make_agent())
        _jid, unit_id = _drive_to_owned(session)
        session.run_distill(unit_id=unit_id)
        session.run_distill(unit_id=unit_id)  # replay
        assert db.one("SELECT COUNT(*) AS n FROM journey_events WHERE event_type='unit_distilled'",
                      ()) == {"n": 1}
    finally:
        db.close()
        temp.cleanup()


def test_distill_rejects_a_unit_the_router_did_not_finish():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orchestrator, _make_agent())
        mapped = session.run_mapping()
        unit_id = mapped.decision.unit_id  # POINTED, not OWNED
        raised = False
        try:
            orchestrator.commit_distill(_distill_blocks(), unit_id=unit_id)
        except Exception:
            raised = True
        assert raised, "distilling a non-finished unit must be refused"
    finally:
        db.close()
        temp.cleanup()


def test_learner_model_moves_proven_skill_out_of_cant():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        model = LearnerModelService(db, config)
        model.apply_diff({"can": [], "cant": ["reason about dict vs list"], "misconceptions": []})
        merged = model.apply_diff({"can": ["reason about dict vs list"], "cant": [],
                                   "misconceptions": []})
        assert "reason about dict vs list" in merged["can"]
        assert "reason about dict vs list" not in merged["cant"], "a proven skill must leave cant"
    finally:
        db.close()
        temp.cleanup()
