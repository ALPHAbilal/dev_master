"""Stage 4 tests: additive conversation, probe, and journey recorders."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tutor_v2 import (
    ConversationRecorder, Database, InvariantError, JourneyRecorder, ProbeRecorder,
    Router, TutorConfig, ValidationError, WorkspaceService,
)


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1")
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(
        target="run.py", document_id="learner-main", display_name="solution.py", language="python"
    )
    return temp, db, config, Router(db, config)


def _map(slug, axes):
    unit = {"slug": slug, "file": "run.py", "lo": 1, "hi": 10, "depth": 0, "parent": None, "axes": axes}
    return {"kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
            "objective_covered": True, "units": [unit], "order": [slug]}


def test_journey_start_is_idempotent_and_resolves_children_to_root():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map("main", ["RATIONALE"]))
        router.record_resume_question(unit_id=pointed.unit_id, question="Why?")
        gap = {"slug": "child", "why": "prereq", "axis": "COMPREHEND", "anchor": {"kind": "conceptual"}}
        child = router.route_grade(unit_id=pointed.unit_id, stamp={
            "kind": "return.grade", "axis": "RATIONALE", "verdict": "MISSING",
            "category": "misconception", "evidence_ref": "e:1", "hidden_gap": gap})

        recorder = JourneyRecorder(db, config)
        journey_id = recorder.start(pointed.unit_id)
        assert recorder.start(pointed.unit_id) == journey_id  # idempotent
        # A dived child resolves to the root's journey.
        assert recorder.journey_for_unit(child.unit_id) == journey_id
    finally:
        db.close()
        temp.cleanup()


def test_conversation_sequences_increment_and_status_updates():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map("main", ["COMPREHEND"]))
        journey_id = JourneyRecorder(db, config).start(pointed.unit_id)
        convo = ConversationRecorder(db, config)
        first = convo.record(journey_id=journey_id, unit_id=pointed.unit_id, role="tutor",
                             message_kind="question", content="What does it do?", turn_id="t1")
        second = convo.record(journey_id=journey_id, unit_id=pointed.unit_id, role="learner",
                              message_kind="answer", content="It loads config.", turn_id="t1",
                              status="AWAITING_EVALUATION")
        rows = convo.list_for_journey(journey_id)
        assert [r["sequence"] for r in rows] == [1, 2]
        assert rows[0]["id"] == first and rows[1]["id"] == second
        convo.set_turn_status(journey_id=journey_id, turn_id="t1", status="EVALUATED")
        assert {r["status"] for r in convo.list_for_journey(journey_id)} == {"EVALUATED"}
    finally:
        db.close()
        temp.cleanup()


def test_probe_recorder_writes_and_sequences_turns():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map("main", ["COMPREHEND"]))
        probes = ProbeRecorder(db, config)
        turn = probes.next_turn(pointed.unit_id)
        assert turn == 1
        probe_id = probes.record(turn=turn, unit_id=pointed.unit_id, axis="COMPREHEND", step="probe",
                                 question="What does it do?", learner_answer="Loads config.",
                                 verdict="SOLID", category="correct-deep")
        assert probe_id > 0
        assert probes.next_turn(pointed.unit_id) == 2
        with pytest.raises(ValidationError):
            probes.record(turn=2, unit_id=pointed.unit_id, axis="COMPREHEND", step="bogus",
                          question="q", learner_answer="a", verdict="SOLID", category="correct-deep")
    finally:
        db.close()
        temp.cleanup()


def test_journey_events_and_revision_counter():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map("main", ["COMPREHEND"]))
        recorder = JourneyRecorder(db, config)
        journey_id = recorder.start(pointed.unit_id)
        recorder.record_event(journey_id=journey_id, unit_id=pointed.unit_id, event_type="journey_started")
        recorder.record_event(journey_id=journey_id, unit_id=pointed.unit_id, event_type="axis_started",
                              axis="COMPREHEND")
        events = db.query("SELECT event_type FROM journey_events WHERE journey_id=? ORDER BY id", (journey_id,))
        assert [e["event_type"] for e in events] == ["journey_started", "axis_started"]
        assert recorder.bump_revision(journey_id) == 1
        assert recorder.bump_revision(journey_id) == 2
        recorder.set_state(journey_id, "OWNED", completed=True)
        row = recorder.get(journey_id)
        assert row["state"] == "OWNED" and row["completed_at"] is not None
    finally:
        db.close()
        temp.cleanup()


def test_journey_for_unit_requires_started_journey():
    temp, db, config, router = _setup()
    try:
        pointed = router.commit_map(_map("main", ["COMPREHEND"]))
        with pytest.raises(InvariantError):
            JourneyRecorder(db, config).journey_for_unit(pointed.unit_id)
    finally:
        db.close()
        temp.cleanup()
