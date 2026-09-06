"""Stage 5/6 tests: atomic graded turns and journey-fact recording."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tutor_v2 import (
    ConversationRecorder, Database, JourneyRecorder, ProbeRecorder, Router,
    TurnOrchestrator, TutorConfig, WorkspaceService,
)
from tutor_v2.contracts import MAP_NODE_CATEGORIES


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1")
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(
        target="run.py", document_id="learner-main", display_name="solution.py", language="python"
    )
    return temp, db, config, Router(db, config)


def _map(units):
    return {"kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
            "objective_covered": True, "units": units, "order": [u["slug"] for u in units]}


def _unit(slug, axes):
    return {"slug": slug, "file": "run.py", "lo": 1, "hi": 10, "depth": 0, "parent": None, "axes": axes}


def _grade(axis, verdict, category, gap=None):
    map_text = ({"title": f"{category} on {axis}", "summary": f"Verdict {verdict}"}
                if category in MAP_NODE_CATEGORIES else None)
    return [json.dumps({"kind": "return.grade", "axis": axis, "verdict": verdict,
                        "category": category, "evidence_ref": "events:1", "hidden_gap": gap,
                        "map_text": map_text})]


def _map_blocks(units):
    return [json.dumps(_map(units))]


def test_commit_map_starts_journey_and_points_root():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        result = orch.commit_map(_map_blocks([_unit("main", ["COMPREHEND"])]))
        assert result.decision.next_step == "wakeup.probe" and result.decision.highlight
        assert result.projection_revision == 1
        events = db.query("SELECT event_type FROM journey_events WHERE journey_id=? ORDER BY id",
                          (result.journey_id,))
        assert [e["event_type"] for e in events] == ["journey_started", "axis_started"]
    finally:
        db.close()
        temp.cleanup()


def test_graded_turn_commits_route_probe_and_lifecycle_together():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        mapped = orch.commit_map(_map_blocks([_unit("main", ["COMPREHEND"]), _unit("next", ["RATIONALE"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                              question="What does it do?", save_resume_question=True)
        result = orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                                    question="What does it do?", answer="Loads config safely.",
                                    grade_blocks=_grade("COMPREHEND", "SOLID", "correct-deep"))
        assert result.decision.next_step == "wakeup.distill"
        # Axis went SOLID, one probe row, answer_evaluated fact, and EVALUATED status — all committed.
        assert db.one("SELECT verdict FROM axes WHERE unit_id=? AND axis='COMPREHEND'", (unit_id,)) == {"verdict": "SOLID"}
        assert db.one("SELECT COUNT(*) AS n FROM probes WHERE unit_id=?", (unit_id,)) == {"n": 1}
        assert db.one("SELECT status FROM conversation_messages WHERE turn_id='t1' AND role='learner'") == {"status": "EVALUATED"}
        kinds = {e["event_type"] for e in db.query("SELECT event_type FROM journey_events WHERE journey_id=?", (jid,))}
        assert "answer_evaluated" in kinds
    finally:
        db.close()
        temp.cleanup()


def test_probe_failure_rolls_back_the_route_atomically():
    temp, db, config, router = _setup()
    try:
        class ExplodingProbes(ProbeRecorder):
            def record(self, **kwargs):
                raise RuntimeError("simulated probe write failure")

        orch = TurnOrchestrator(db, config, router, probes=ExplodingProbes(db, config))
        mapped = orch.commit_map(_map_blocks([_unit("main", ["COMPREHEND"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                              question="What does it do?", save_resume_question=True)
        with pytest.raises(RuntimeError, match="probe write failure"):
            orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                               question="What does it do?", answer="Loads config.",
                               grade_blocks=_grade("COMPREHEND", "SOLID", "correct-deep"))
        # The route rolled back: axis stayed UNGRADED, no probe row, and the answer is recoverable.
        assert db.one("SELECT verdict FROM axes WHERE unit_id=? AND axis='COMPREHEND'", (unit_id,)) == {"verdict": "UNGRADED"}
        assert db.one("SELECT COUNT(*) AS n FROM probes WHERE unit_id=?", (unit_id,)) == {"n": 0}
        assert db.one("SELECT status FROM conversation_messages WHERE turn_id='t1' AND role='learner'") == {"status": "AWAITING_EVALUATION"}
    finally:
        db.close()
        temp.cleanup()


def test_child_dive_records_detour_started_then_completion_and_resume():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        mapped = orch.commit_map(_map_blocks([_unit("main", ["RATIONALE"])]))
        jid, parent_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=parent_id, axis="RATIONALE", turn_id="t1",
                              question="Why this structure?", save_resume_question=True)
        gap = {"slug": "prereq", "why": "needs a prerequisite", "axis": "COMPREHEND",
               "anchor": {"kind": "conceptual"}}
        dive = orch.submit_answer(journey_id=jid, unit_id=parent_id, axis="RATIONALE", turn_id="t1",
                                  question="Why this structure?", answer="I'm not sure.",
                                  grade_blocks=_grade("RATIONALE", "MISSING", "misconception", gap))
        child_id = dive.decision.unit_id
        assert child_id != parent_id
        assert any(e["event_type"] == "detour_started"
                   for e in db.query("SELECT event_type FROM journey_events WHERE journey_id=?", (jid,)))
        # Finish the child: parent resumes at its exact question.
        orch.present_question(journey_id=jid, unit_id=child_id, axis="COMPREHEND", turn_id="t2",
                              question="What is iteration?")
        orch.submit_answer(journey_id=jid, unit_id=child_id, axis="COMPREHEND", turn_id="t2",
                           question="What is iteration?", answer="Repeated evaluation.",
                           grade_blocks=_grade("COMPREHEND", "SOLID", "correct-deep"))
        resumed = orch.finish_child(child_unit_id=child_id)
        assert resumed.decision.unit_id == parent_id
        assert resumed.decision.resume_question == "Why this structure?"
        types = [e["event_type"] for e in db.query("SELECT event_type FROM journey_events WHERE journey_id=? ORDER BY id", (jid,))]
        assert "detour_completed" in types and "parent_resumed" in types
    finally:
        db.close()
        temp.cleanup()


def test_park_and_resume_move_journey_state_and_record_facts():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        mapped = orch.commit_map(_map_blocks([_unit("main", ["RATIONALE"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="RATIONALE", turn_id="t1",
                              question="Why?", save_resume_question=True)
        gap = {"slug": "p", "why": "prereq", "axis": "COMPREHEND", "anchor": {"kind": "conceptual"}}
        orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="RATIONALE", turn_id="t1",
                           question="Why?", answer="tired", grade_blocks=_grade("RATIONALE", "SHAKY", "fatigue-switch", gap))
        parked = orch.park(unit_id=unit_id)
        assert db.one("SELECT state FROM journeys WHERE id=?", (jid,)) == {"state": "PARKED"}
        assert parked.decision is None
        resumed = orch.resume()
        assert resumed.decision.next_step == "wakeup.probe"
        assert db.one("SELECT state FROM journeys WHERE id=?", (jid,)) == {"state": "LIVE"}
        types = {e["event_type"] for e in db.query("SELECT event_type FROM journey_events WHERE journey_id=?", (jid,))}
        assert {"journey_parked", "journey_resumed"} <= types
    finally:
        db.close()
        temp.cleanup()
