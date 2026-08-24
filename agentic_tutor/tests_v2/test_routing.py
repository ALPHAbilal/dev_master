"""Stage 4 tests: deterministic routing, child dives, siblings, and returns."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import Database, Router, TutorConfig, WorkspaceService


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
    return {
        "kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
        "objective_covered": True, "units": units, "order": [unit["slug"] for unit in units],
    }


def _unit(slug, axes):
    return {"slug": slug, "file": "run.py", "lo": 1, "hi": 10, "depth": 0, "parent": None, "axes": axes}


def _grade(axis, verdict, category, gap=None):
    return {
        "kind": "return.grade", "axis": axis, "verdict": verdict, "category": category,
        "evidence_ref": "events:1", "hidden_gap": gap,
    }


def test_mapper_order_points_first_unit_then_owned_root_advances_to_next():
    temp, db, _, router = _setup()
    try:
        first = router.commit_map(_map([_unit("first", ["COMPREHEND"]), _unit("second", ["RATIONALE"])]))
        assert first.next_step == "wakeup.probe" and first.highlight and first.axis == "COMPREHEND"
        router.record_resume_question(unit_id=first.unit_id, question="What does first do?")
        owned = router.route_grade(unit_id=first.unit_id, stamp=_grade("COMPREHEND", "SOLID", "correct-deep"))
        assert owned.next_step == "wakeup.distill"
        next_root = router.finish_owned_unit(unit_id=first.unit_id)
        assert next_root.next_step == "wakeup.probe" and next_root.axis == "RATIONALE"
        assert db.one("SELECT state FROM units WHERE slug='first'") == {"state": "OWNED"}
    finally:
        db.close()
        temp.cleanup()


def test_second_shaky_creates_conceptual_child_and_replays_parent_question():
    temp, db, _, router = _setup()
    try:
        parent = router.commit_map(_map([_unit("main", ["RATIONALE"])]))
        router.record_resume_question(unit_id=parent.unit_id, question="Why is the loop inside main?")
        first = router.route_grade(unit_id=parent.unit_id, stamp=_grade("RATIONALE", "SHAKY", "shaky"))
        assert first.next_step == "wakeup.probe" and first.unit_id == parent.unit_id
        gap = {"slug": "iteration-basics", "why": "The learner thinks values execute themselves.", "axis": "COMPREHEND", "anchor": {"kind": "conceptual"}}
        child = router.route_grade(unit_id=parent.unit_id, stamp=_grade("RATIONALE", "SHAKY", "shaky", gap))
        assert child.next_step == "wakeup.probe" and child.axis == "COMPREHEND" and not child.highlight
        child_row = db.one("SELECT parent_id,anchor_kind,file,lo,hi,state FROM units WHERE id=?", (child.unit_id,))
        assert child_row["parent_id"] == parent.unit_id and child_row["anchor_kind"] == "conceptual"
        assert child_row["state"] == "POINTED"
        child_done = router.route_grade(unit_id=child.unit_id, stamp=_grade("COMPREHEND", "SOLID", "correct-deep"))
        assert child_done.next_step == "wakeup.distill"
        resumed = router.finish_owned_unit(unit_id=child.unit_id)
        assert resumed.unit_id == parent.unit_id and resumed.resume_question == "Why is the loop inside main?"
        assert resumed.next_step == "wakeup.probe"
    finally:
        db.close()
        temp.cleanup()


def test_code_anchored_gap_highlights_its_own_range_and_sibling_stays_queued():
    temp, db, _, router = _setup()
    try:
        parent = router.commit_map(_map([_unit("main", ["RATIONALE"])]))
        router.record_resume_question(unit_id=parent.unit_id, question="Why this structure?")
        code_gap = {"slug": "lookup-cost", "why": "Needs the lookup cost prerequisite.", "axis": "RATIONALE", "anchor": {"kind": "code", "file": "run.py", "lo": 20, "hi": 24}}
        child = router.route_grade(unit_id=parent.unit_id, stamp=_grade("RATIONALE", "MISSING", "misconception", code_gap))
        assert child.highlight
        assert db.one("SELECT file,lo,hi,anchor_kind FROM units WHERE id=?", (child.unit_id,)) == {"file": "run.py", "lo": 20, "hi": 24, "anchor_kind": "code"}
        # Finish the child, then let the parent queue a sibling rather than opening it.
        router.route_grade(unit_id=child.unit_id, stamp=_grade("RATIONALE", "SOLID", "correct-deep"))
        router.finish_owned_unit(unit_id=child.unit_id)
        sibling = {"slug": "ordering", "why": "Related ordering detail.", "axis": "JUDGMENT", "anchor": {"kind": "conceptual"}}
        decision = router.route_grade(unit_id=parent.unit_id, stamp=_grade("RATIONALE", "SHAKY", "sibling-hole", sibling))
        assert decision.next_step == "wakeup.teach"
        pending = json.loads(db.one("SELECT pending_json FROM stack WHERE is_top=1")["pending_json"])
        assert pending == [sibling]
    finally:
        db.close()
        temp.cleanup()


def test_parent_cannot_be_graded_while_child_is_top():
    temp, db, _, router = _setup()
    try:
        parent = router.commit_map(_map([_unit("main", ["RATIONALE"])]))
        router.record_resume_question(unit_id=parent.unit_id, question="Question")
        gap = {"slug": "child", "why": "Need a prerequisite.", "axis": "COMPREHEND", "anchor": {"kind": "conceptual"}}
        router.route_grade(unit_id=parent.unit_id, stamp=_grade("RATIONALE", "MISSING", "misconception", gap))
        try:
            router.route_grade(unit_id=parent.unit_id, stamp=_grade("RATIONALE", "SOLID", "correct-deep"))
            assert False, "only deepest frame may be graded"
        except Exception as error:
            assert "deepest" in str(error)
    finally:
        db.close()
        temp.cleanup()
