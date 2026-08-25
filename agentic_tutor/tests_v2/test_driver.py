"""Step 2 tests: the turn driver runs the loop to the next learner input and no further."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    ArchiveService, Database, DriverState, EventRecorder, JourneyArchiveService,
    LearnerModelService, Router, SemanticGraphService, SessionRunner, TurnDriver,
    TurnOrchestrator, TutorConfig, WakeupBuilder, WorkspaceService,
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
    orchestrator = TurnOrchestrator(
        db, config, Router(db, config),
        graph=SemanticGraphService(db, config),
        archive=JourneyArchiveService(db, config),
        unit_archive=ArchiveService(db, config, workspace, events),
        learner_model=LearnerModelService(db, config),
    )
    session = SessionRunner(config, WakeupBuilder(db, config), orchestrator, _make_agent())
    return temp, db, config, session


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
        "learner_diff": {"can": ["read a loader"], "cant": [], "misconceptions": []},
        "handoff": {"next_unit": "loader", "dive_depth": 0, "why": "done", "watch": "nothing"},
    })]


def _make_agent():
    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does load(path) do?"]
        if step == "wakeup.teach":
            return ["load reads the file at path and returns its parsed contents."]
        if step == "wakeup.grade":
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                                "category": "correct-deep", "evidence_ref": "events:1",
                                "hidden_gap": None})]
        if step == "wakeup.distill":
            return _distill_blocks()
        raise AssertionError(f"unexpected step {step}")
    return run


def test_advance_stops_at_the_probe_then_completes_after_the_answer():
    temp, db, config, session = _setup()
    try:
        driver = TurnDriver(session)
        mapped = session.run_mapping()
        jid = mapped.journey_id

        # The driver runs point-next and stops holding a live question for the learner.
        state = driver.advance(journey_id=jid, decision=mapped.decision)
        assert isinstance(state, DriverState)
        assert state.status == "awaiting_learner"
        assert state.turn_id and state.question == "What does load(path) do?"
        assert state.unit_id == mapped.decision.unit_id and state.axis == "COMPREHEND"

        # The learner answers with the driver-minted turn id; single COMPREHEND axis → OWNED,
        # so the driver distills, finishes the root, and reports the ladder done.
        graded = session.run_grade(journey_id=jid, unit_id=state.unit_id, axis=state.axis,
                                   turn_id=state.turn_id, question=state.question,
                                   answer="It reads the file then returns its contents.")
        done = driver.advance(journey_id=jid, decision=graded.decision)
        assert done.status == "done"

        # Distill really ran on the way to done: the proof artifact was sealed.
        assert (config.archive_root / "loader" / "manifest.json").is_file()
        assert db.one("SELECT COUNT(*) AS n FROM journey_events "
                      "WHERE event_type='unit_distilled'", ()) == {"n": 1}
    finally:
        db.close()
        temp.cleanup()


def _two_unit_map_blocks():
    units = [
        {"slug": "loader", "file": "run.py", "lo": 1, "hi": 2, "depth": 0, "parent": None,
         "axes": ["COMPREHEND"]},
        {"slug": "reader", "file": "run.py", "lo": 5, "hi": 6, "depth": 0, "parent": None,
         "axes": ["COMPREHEND"]},
    ]
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": units,
                        "order": ["loader", "reader"]})]


def _two_unit_agent():
    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _two_unit_map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["Explain this unit."]
        if step == "wakeup.grade":
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                                "category": "correct-deep", "evidence_ref": "events:1",
                                "hidden_gap": None})]
        if step == "wakeup.distill":
            unit = wakeup.get("unit", {})
            slug = unit.get("slug", "loader")
            blocks = json.loads(_distill_blocks()[0])
            blocks["unit"] = slug
            blocks["title"] = slug
            blocks["handoff"]["next_unit"] = slug
            return [json.dumps(blocks)]
        raise AssertionError(f"unexpected step {step}")
    return run


def test_driver_mints_a_distinct_turn_id_per_question():
    temp, db, config, session = _setup()
    try:
        session.agent_run = _two_unit_agent()
        driver = TurnDriver(session)
        mapped = session.run_mapping()
        jid = mapped.journey_id

        first = driver.advance(journey_id=jid, decision=mapped.decision)
        assert first.status == "awaiting_learner"

        # Owning the first unit distills + finishes it, then points the second unit and stops.
        graded = session.run_grade(journey_id=jid, unit_id=first.unit_id, axis=first.axis,
                                   turn_id=first.turn_id, question=first.question, answer="ok")
        second = driver.advance(journey_id=jid, decision=graded.decision)
        assert second.status == "awaiting_learner"
        assert second.unit_id != first.unit_id
        assert first.turn_id != second.turn_id
    finally:
        db.close()
        temp.cleanup()
