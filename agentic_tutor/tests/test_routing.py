"""Routing tests: frontier load/validate, Part E block selection, F2 framing,
and the PreToolUse gate wall."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tempfile

from tutor import DB, dispatch
from tutor.frontier import load, validate, empty_template, FrontierError
from tutor.library import seed_vocab
from tutor.routing import build_l_block, gate_wall_decision
from tutor.hooks import pretooluse_decision

FIX = Path(__file__).resolve().parent / "fixtures" / "frontier_pinned_qa.json"


def _spec_file() -> str:
    """A real spec file on disk — open_gate refuses a slice whose spec doesn't exist."""
    f = tempfile.NamedTemporaryFile("w", suffix="-pinned-qa-group.md", delete=False)
    f.write("# spec: pinned QA grouping\n")
    f.close()
    return f.name


def _db_with_slice(spec_path: str | None = None):
    db = DB()
    dispatch(db, "M", "upsert_concept",
             {"slug": "enumerate-index", "name": "enumerate", "state": "LOCKED"})
    args = {"slug": "pinned-qa-group", "title": "pinned QA grouping",
            "target_file": "soufiane_prompts/prompts/run_prompts.py",
            "concept_prereqs": ["enumerate-index"], "ordinal": 1}
    if spec_path:
        args["spec_path"] = spec_path
    dispatch(db, "M", "upsert_slice", args)
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
    seed_vocab(db, f)          # slice start: frontier lists are planted into the TABLE
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


def _db_gate_open(spec_path: str):
    """A db whose slice's gap is closed and gate is OPEN (spec file must exist)."""
    db = _db_with_slice(spec_path)
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    d = dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    assert d.committed, d.text
    return db


def test_open_gate_replaces_teaching_with_wall():
    db = _db_gate_open(_spec_file())
    block = build_l_block(db, load(FIX), is_first_turn=False)
    assert "[GATE — OPEN]" in block and "[GAP]" not in block


def test_open_gate_refused_without_spec():
    db = _db_with_slice()                              # spec_path NULL — lazy spec unwritten
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": "w"})
    dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    d = dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    assert not d.committed and "spec" in d.text
    assert db.one("SELECT 1 FROM gates WHERE state='OPEN'") is None


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
    db = _db_gate_open(_spec_file())
    out = pretooluse_decision(db, {"tool_name": "Write",
                                   "tool_input": {"file_path": "run_prompts.py"}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_gate_wall_denies_reading_spec_when_open():
    spec = _spec_file()
    db = _db_gate_open(spec)
    out = pretooluse_decision(db, {"tool_name": "Read", "tool_input": {"file_path": spec}})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_gate_wall_reads_live_slice_row_not_a_copy():
    # the wall joins slices — a spine correction mid-gate is enforced immediately
    db = _db_gate_open(_spec_file())
    dispatch(db, "M", "upsert_slice",
             {"slug": "pinned-qa-group", "title": "pinned QA grouping",
              "target_file": "soufiane_prompts/prompts/renamed.py", "ordinal": 1})
    dec, _ = gate_wall_decision(db, "Write", {"file_path": "renamed.py"})
    assert dec == "deny"


def test_gate_wall_allows_unrelated_file_when_open():
    db = _db_gate_open(_spec_file())
    out = pretooluse_decision(db, {"tool_name": "Read",
                                   "tool_input": {"file_path": "some/other/notes.md"}})
    assert out == {}
