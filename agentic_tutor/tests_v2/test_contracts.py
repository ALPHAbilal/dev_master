"""Stage 3 tests: schemas validate shapes before any state service can mutate."""
from __future__ import annotations

from tutor_v2 import (
    ValidationError,
    validate_action_event,
    validate_archive_manifest,
    validate_continuation,
    validate_return,
    validate_wakeup,
)


def _fails(fn, value):
    try:
        fn(value)
        assert False, "expected contract rejection"
    except ValidationError:
        pass


def test_wakeup_requires_right_agent_known_step_and_closed_shape():
    packet = {"step": "wakeup.probe", "agent": "TEACHER", "session_id": "s1", "context": {"source": "x"}, "capabilities": ["read_code_slice"], "unit_id": 1, "axis": "RATIONALE"}
    assert validate_wakeup(packet) == packet
    wrong_agent = {**packet, "agent": "JUDGE"}
    _fails(validate_wakeup, wrong_agent)
    _fails(validate_wakeup, {**packet, "unscoped_db_dump": True})


def test_return_map_enforces_dependency_order_and_mappable_axes():
    stamp = {
        "kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
        "objective_covered": False,
        "units": [{"slug": "main", "file": "run.py", "lo": 1, "hi": 9, "depth": 0, "parent": None, "axes": ["COMPREHEND", "RATIONALE"]}],
        "order": ["main"],
    }
    assert validate_return(stamp) == stamp
    _fails(validate_return, {**stamp, "order": ["wrong"]})
    bad_axis = {**stamp, "units": [{**stamp["units"][0], "axes": ["made-up"]}]}
    _fails(validate_return, bad_axis)


def test_return_grade_has_machine_route_signal_and_evidence():
    stamp = {"kind": "return.grade", "axis": "RATIONALE", "verdict": "SHAKY", "category": "working-code-wrong-reasoning", "evidence_ref": "events:12", "hidden_gap": {"slug": "lookup", "why": "wrong complexity reason", "axis": "RATIONALE", "anchor": {"kind": "conceptual"}}, "map_text": {"title": "dict lookup cost", "summary": "Reasoning gap on RATIONALE"}}
    assert validate_return(stamp) == stamp
    _fails(validate_return, {**stamp, "category": "freeform guess"})
    _fails(validate_return, {**stamp, "evidence_ref": ""})


def test_return_grade_map_text_matches_category_emission():
    base = {"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
            "category": "correct-deep", "evidence_ref": "events:1", "hidden_gap": None,
            "map_text": {"title": "load reads a file", "summary": "Proved COMPREHEND"}}
    # A node-emitting category with a valid map_text passes.
    assert validate_return(base) == base
    # A node-emitting category with map_text=null is rejected.
    _fails(validate_return, {**base, "map_text": None})
    # A non-emitting category carrying a non-null map_text is rejected.
    _fails(validate_return, {**base, "category": "off-topic"})
    # A non-emitting category with map_text=null passes.
    ok = {**base, "category": "off-topic", "map_text": None}
    assert validate_return(ok) == ok


def test_return_distill_requires_complete_owned_or_parked_contract():
    stamp = {
        "kind": "return.distill", "unit": "main", "title": "Main — first proof",
        "logical_document": {"id": "learner-main", "display_name": "solution.py"},
        "final_verdict": "OWNED", "axes_tested": ["RATIONALE"], "tests": [],
        "evidence": ["events:12"], "event_log": "events.jsonl", "workspace_snapshot": "workspace-snapshot.py",
        "resume_at": None, "learner_diff": {"can": ["reason about entry points"], "cant": [], "misconceptions": []},
        "handoff": {"next_unit": "loop", "dive_depth": 0, "why": "main owned", "watch": "judgment"},
    }
    assert validate_return(stamp) == stamp
    _fails(validate_return, {**stamp, "final_verdict": "OWNED", "resume_at": {"axis": "RATIONALE", "note": "bad"}})
    parked = {**stamp, "final_verdict": "PARKED", "resume_at": {"axis": "RATIONALE", "note": "continue after answer"}}
    assert validate_return(parked) == parked


def test_action_continuation_and_archive_contracts_reject_ambiguous_data():
    action = {"unit_id": 1, "document_id": "learner-main", "kind": "command", "payload": {"command": "pytest -q"}, "result": {"exit": 0}}
    assert validate_action_event(action) == action
    _fails(validate_action_event, {**action, "kind": "shell"})
    continuation = {"next_step": "wakeup.probe", "awaiting": "learner_answer", "outstanding_question_ref": "events:12", "context_refs": ["events:12"]}
    assert validate_continuation(continuation) == continuation
    _fails(validate_continuation, {**continuation, "outstanding_question_ref": None})
    manifest = {
        "unit": "main", "title": "Main", "logical_document": {"id": "learner-main", "display_name": "solution.py"},
        "final_verdict": "OWNED", "axes_tested": [], "tests": [], "evidence": [], "event_ids": [1, 2],
        "event_log": "events.jsonl", "workspace_snapshot": "workspace-snapshot.py", "workspace_hash": "abc", "workspace_checkpoints": [], "resume_at": None,
    }
    assert validate_archive_manifest(manifest) == manifest
    _fails(validate_archive_manifest, {**manifest, "event_ids": [1, 1]})
