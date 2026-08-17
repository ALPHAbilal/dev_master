"""Routing tests: frontier load/validate, Part E block selection, F2 framing,
and the PreToolUse gate wall."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor import DB, dispatch
from tutor.frontier import load, validate, empty_template, FrontierError
from tutor.routing import build_l_block, gate_wall_decision
from tutor.hooks import pretooluse_decision

FIX = Path(__file__).resolve().parent / "fixtures" / "frontier_pinned_qa.json"


def _db_with_slice():
    db = DB()
    dispatch(db, "M", "upsert_concept",
             {"slug": "enumerate-index", "name": "enumerate", "state": "LOCKED"})
    dispatch(db, "M", "upsert_slice",
             {"slug": "pinned-qa-group", "title": "pinned QA grouping",
              "target_file": "soufiane_prompts/prompts/run_prompts.py",
              "spec_path": "library/slices/pinned-qa-group.md",
              "concept_prereqs": ["enumerate-index"], "ordinal": 1})
    return db


# --------------------------------------------------------------------------
# frontier load / validate
# --------------------------------------------------------------------------
def test_frontier_loads_and_exposes_slice():
    f = load(FIX)
    assert f.slice_slug == "pinned-qa-group"
    assert f.target_file.endswith("run_prompts.py")
    assert f.gap["concept"] == "enumerate-index"


def test_empty_template_is_rejected():
    try:
        validate(empty_template("x"))
        assert False, "empty template must fail validation"
    except FrontierError:
        pass


def test_partial_gap_is_rejected():
    raw = load(FIX).data
    raw["gap"]["justify"] = ""            # blank a required gap key
    try:
        validate(raw)
        assert False
    except FrontierError as e:
        assert "gap.justify" in str(e)


# --------------------------------------------------------------------------
# Part E: block selection
# --------------------------------------------------------------------------
def test_first_turn_shows_opening_question_not_continue():
    db = _db_with_slice()
    f = load(FIX)
    block = build_l_block(db, f, is_first_turn=True)
    assert "OPEN WITH (guess-first)" in block
    assert "done-when:" not in block                 # continue framing withheld
    assert "HELD (do not use): enumerate" in block   # vocab door surfaced


def test_later_turn_shows_continue_framing():
    db = _db_with_slice()
    f = load(FIX)
    block = build_l_block(db, f, is_first_turn=False)
    assert "done-when:" in block and "OPEN WITH" not in block
    assert "if stuck, descend ONE step" in block


def test_teaching_block_gone_once_concept_owned():
    db = _db_with_slice()
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    block = build_l_block(db, load(FIX), is_first_turn=False)
    assert "[GAP]" not in block                       # gap closed -> no teaching block


def test_open_gate_replaces_teaching_with_wall():
    db = _db_with_slice()
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    block = build_l_block(db, load(FIX), is_first_turn=False)
    assert "[GATE — OPEN]" in block and "[GAP]" not in block


def test_subhole_forces_hold_block():
    db = _db_with_slice()
    dispatch(db, "L", "raise_subhole",
             {"slice_slug": "pinned-qa-group", "concept_slug": "list-iteration",
              "evidence": "failed to index"})
    # frontier still says gap, but DB subhole cell is set -> but has_subhole reads the
    # frontier json, so simulate M having written it into the frontier:
    f = load(FIX)
    f.data["subhole"] = {"concept": "list-iteration", "evidence": "failed to index", "plan": None}
    block = build_l_block(db, f, is_first_turn=False)
    assert "[SUBHOLE — HOLD]" in block and "[GAP]" not in block


# --------------------------------------------------------------------------
# the gate wall (PreToolUse)
# --------------------------------------------------------------------------
def test_gate_wall_allows_when_no_gate():
    db = _db_with_slice()
    dec, _ = gate_wall_decision(db, "Write",
                                {"file_path": "soufiane_prompts/prompts/run_prompts.py"})
    assert dec == "allow"


def test_gate_wall_denies_writing_target_when_open():
    db = _db_with_slice()
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    out = pretooluse_decision(db, {"tool_name": "Write",
                                   "tool_input": {"file_path": "run_prompts.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_gate_wall_denies_reading_spec_when_open():
    db = _db_with_slice()
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    out = pretooluse_decision(db, {"tool_name": "Read",
                                   "tool_input": {"file_path": "library/slices/pinned-qa-group.md"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_gate_wall_allows_unrelated_file_when_open():
    db = _db_with_slice()
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    out = pretooluse_decision(db, {"tool_name": "Read",
                                   "tool_input": {"file_path": "some/other/notes.md"}})
    assert out == {}
