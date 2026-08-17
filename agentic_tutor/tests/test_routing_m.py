"""M routing tests: the deterministic wakeup picker, the three injected sets,
per-turn tools, and the [EVIDENCE] pointer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor import DB, dispatch
from tutor.routing_m import (M_CORE, build_m_block, mark_probes_seen,
                             pick_m_turn, tools_for_turn)


def _db():
    return DB()


def _adopted_db():
    db = DB()
    dispatch(db, "M", "set_target", {"codebase_path": "/repo"})
    dispatch(db, "M", "upsert_concept", {"slug": "enumerate-index", "name": "enumerate"})
    dispatch(db, "M", "upsert_slice",
             {"slug": "pinned-qa-group", "title": "pinned QA grouping",
              "target_file": "run_prompts.py",
              "concept_prereqs": ["enumerate-index"], "ordinal": 1})
    return db


# --------------------------------------------------------------------------
# wakeup picker — a cell's state IS the signal
# --------------------------------------------------------------------------
def test_no_target_means_no_session_not_a_wakeup():
    assert pick_m_turn(_db(), frontier_empty=True) is None


def test_adopted_but_empty_spine_wakes_survey():
    db = DB()
    dispatch(db, "M", "set_target", {"codebase_path": "/repo"})
    # the target row exists (adoption wrote it) but no map has been drawn yet
    assert pick_m_turn(db, frontier_empty=True) == "SURVEY"


def test_survey_stops_being_due_once_the_spine_exists():
    assert pick_m_turn(_adopted_db(), frontier_empty=True) == "PLAN"


def test_filled_subhole_cell_wakes_subhole():
    db = _adopted_db()
    dispatch(db, "L", "raise_subhole",
             {"slice_slug": "pinned-qa-group", "concept_slug": "enumerate-index",
              "evidence": "wrote qa[i] inside `for i in qa`"})
    assert pick_m_turn(db, frontier_empty=True) == "SUBHOLE"


def test_empty_frontier_wakes_plan():
    assert pick_m_turn(_adopted_db(), frontier_empty=True) == "PLAN"


def test_filled_frontier_no_subhole_means_no_wakeup():
    assert pick_m_turn(_adopted_db(), frontier_empty=False) is None


def test_subhole_outranks_empty_frontier():
    db = _adopted_db()
    dispatch(db, "L", "raise_subhole",
             {"slice_slug": "pinned-qa-group", "concept_slug": "enumerate-index",
              "evidence": "e"})
    # even with an empty frontier, the mid-slice correction comes first
    assert pick_m_turn(db, frontier_empty=True) == "SUBHOLE"


# --------------------------------------------------------------------------
# the injected sets
# --------------------------------------------------------------------------
def test_survey_block_carries_map_not_specs():
    block = build_m_block(_db(), "SURVEY", codebase_path="/repo")
    assert "[SURVEY]" in block and "/repo" in block
    assert "[TOOL DISCIPLINE]" in block
    assert "spec_path` NULL" in block            # lazy specs are in the instructions
    assert "[EVIDENCE]" not in block             # survey has no learner evidence


def test_survey_without_codebase_path_refuses():
    try:
        build_m_block(_db(), "SURVEY")
        assert False, "SURVEY must demand a codebase_path"
    except ValueError:
        pass


def test_plan_block_carries_evidence_and_overlays_no_repo_discipline():
    db = _adopted_db()
    dispatch(db, "L", "record_probe",
             {"concept_slug": "enumerate-index", "kind": "predict", "result": "HIT",
              "pushes": 1, "self_corrected": True})
    block = build_m_block(db, "PLAN")
    assert "[EVIDENCE]" in block and "enumerate-index predict/HIT" in block
    assert "[OVERLAYS]" in block and "pinned-qa-group [LOCKED]" in block
    assert "[TOOL DISCIPLINE]" not in block      # no repo tools on PLAN
    assert "[SURVEY]" not in block


def test_subhole_block_carries_cell_and_discipline():
    db = _adopted_db()
    dispatch(db, "L", "raise_subhole",
             {"slice_slug": "pinned-qa-group", "concept_slug": "enumerate-index",
              "evidence": "wrote qa[i] inside `for i in qa`"})
    block = build_m_block(db, "SUBHOLE")
    assert "[SUBHOLE]" in block and "qa[i]" in block
    assert "[TOOL DISCIPLINE]" in block          # subhole research turns get repo tools
    assert "clear_subhole" in block


def test_unknown_turn_raises():
    try:
        build_m_block(_db(), "TEACH")
        assert False
    except ValueError:
        pass


# --------------------------------------------------------------------------
# tools per turn + evidence pointer
# --------------------------------------------------------------------------
def test_tools_match_turn():
    assert "Grep" in tools_for_turn("SURVEY") and "Read" in tools_for_turn("SURVEY")
    assert tools_for_turn("PLAN") == ("Write",)   # spec authoring only; db always live
    assert "WebSearch" in tools_for_turn("SUBHOLE")


def test_evidence_pointer_advances():
    db = _adopted_db()
    dispatch(db, "L", "record_probe",
             {"concept_slug": "enumerate-index", "kind": "predict", "result": "MISS"})
    assert "predict/MISS" in build_m_block(db, "PLAN")
    mark_probes_seen(db)                          # M's turn ended
    assert "no probes since" in build_m_block(db, "PLAN")
    dispatch(db, "L", "record_probe",
             {"concept_slug": "enumerate-index", "kind": "produce", "result": "HIT"})
    assert "produce/HIT" in build_m_block(db, "PLAN")


def test_core_is_constant_and_short():
    assert "planner" in M_CORE and "SLICE" in M_CORE
    assert len(M_CORE.splitlines()) < 25          # the router carries the situation
