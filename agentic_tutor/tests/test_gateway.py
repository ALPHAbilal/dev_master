"""Gateway dispatch tests: menu disclosure, role filtering, validation, and the
full slice trace from docs/tutor-simulation.md Turns 0-5 driven through db()."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor import DB, dispatch, menu_for


# --------------------------------------------------------------------------
# menu disclosure (F6)
# --------------------------------------------------------------------------
def test_menu_is_role_filtered():
    db = DB()
    l_menu = {o.name for o in menu_for(db, "L")}
    m_menu = {o.name for o in menu_for(db, "M")}
    assert "record_probe" in l_menu and "record_probe" not in m_menu
    assert "upsert_slice" in m_menu and "upsert_slice" not in l_menu
    assert "list_ready_slices" in l_menu and "list_ready_slices" in m_menu  # both


def test_menu_hides_pass_gate_until_a_gate_is_open():
    db = DB()
    _seed_slice(db)
    assert "pass_gate" not in {o.name for o in menu_for(db, "L")}
    assert "open_gate" in {o.name for o in menu_for(db, "L")}
    dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    names = {o.name for o in menu_for(db, "L")}
    assert "pass_gate" in names and "open_gate" not in names   # flipped by state


def test_describe_returns_schema_not_commit():
    db = DB()
    d = dispatch(db, "L", "record_probe")            # op, no args -> schema
    assert not d.committed and "kind" in d.text and "result" in d.text


def test_no_op_returns_menu_text():
    db = DB()
    d = dispatch(db, "L")
    assert "operations available" in d.text and "record_probe" in d.text


# --------------------------------------------------------------------------
# validation + refusal (nothing commits on bad input)
# --------------------------------------------------------------------------
def test_missing_required_arg_is_refused():
    db = DB()
    d = dispatch(db, "L", "record_probe", {"kind": "predict"})   # no result
    assert not d.committed and d.text.startswith("REFUSED")
    assert db.query("SELECT * FROM probes") == []


def test_role_cannot_call_other_agents_op():
    db = DB()
    d = dispatch(db, "L", "upsert_slice", {"slug": "x", "title": "t", "target_file": "f.py"})
    assert not d.committed and "not available to agent L" in d.text


def test_mapping_without_why_is_refused():
    db = DB()
    dispatch(db, "M", "upsert_concept", {"slug": "enumerate-index", "name": "enumerate"})
    d = dispatch(db, "L", "store_mapping",
                 {"concept_slug": "enumerate-index", "trigger": "t", "solution": "s", "why": ""})
    assert not d.committed and "why" in d.text


def test_close_gap_refused_without_mapping():
    db = DB()
    dispatch(db, "M", "upsert_concept", {"slug": "enumerate-index", "name": "enumerate"})
    d = dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    assert not d.committed and "no positive mapping" in d.text


# --------------------------------------------------------------------------
# the full slice trace (sim Turns 0-5)
# --------------------------------------------------------------------------
def _seed_slice(db):
    """M's Turn 0: the concept + the slice that needs it."""
    dispatch(db, "M", "upsert_concept",
             {"slug": "enumerate-index", "name": "enumerate", "state": "LOCKED"})
    dispatch(db, "M", "upsert_slice",
             {"slug": "pinned-qa-group", "title": "pinned QA grouping",
              "target_file": "soufiane_prompts/prompts/run_prompts.py",
              "spec_path": "library/slices/pinned-qa-group.md",
              "concept_prereqs": ["enumerate-index"], "ordinal": 1})


def test_full_slice_trace_reaches_built():
    db = DB()
    _seed_slice(db)

    # Turn 2: probe the mistake (PARTIAL, no push)
    d = dispatch(db, "L", "record_probe",
                 {"concept_slug": "enumerate-index", "kind": "predict",
                  "result": "PARTIAL", "pushes": 0, "reveals": "no pairing primitive"})
    assert d.committed and d.receipt.startswith("probe:")

    # Turn 3: self-corrected HIT, promote the word, deposit the mapping, close the gap
    dispatch(db, "L", "record_probe",
             {"concept_slug": "enumerate-index", "kind": "produce",
              "result": "HIT", "pushes": 1, "self_corrected": True})
    dispatch(db, "L", "promote_vocab", {"term": "enumerate", "status": "proved"})
    dispatch(db, "L", "store_mapping",
             {"concept_slug": "enumerate-index",
              "trigger": "looping and I also need the position",
              "solution": "enumerate(seq) -> (index, item)",
              "why": "avoids range(len)+re-index",
              "provenance": "reached for range(len) first, self-corrected on 1 nudge"})
    d = dispatch(db, "L", "close_gap", {"concept_slug": "enumerate-index"})
    assert d.committed
    # closing the last prereq flips the slice READY and the consequence says so
    assert "gate-when fires" in d.text
    assert db.one("SELECT state FROM slices WHERE slug='pinned-qa-group'")["state"] == "READY"

    # Turn 4: the gate — open, then pass; slice goes BUILT
    d = dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    assert "Wall active" in d.text
    dispatch(db, "L", "record_probe",
             {"concept_slug": "pinned-qa-group", "kind": "build", "result": "HIT"})
    d = dispatch(db, "L", "pass_gate", {"slice_slug": "pinned-qa-group"})
    assert d.committed and "BUILT" in d.text
    assert db.one("SELECT state FROM slices WHERE slug='pinned-qa-group'")["state"] == "BUILT"
    assert db.one("SELECT state FROM gates WHERE slice_slug='pinned-qa-group'")["state"] == "PASSED"


def test_push_cap_consequence():
    db = DB()
    _seed_slice(db)
    d = dispatch(db, "L", "record_probe",
                 {"concept_slug": "enumerate-index", "kind": "produce",
                  "result": "MISS", "pushes": 4})
    assert "Cap hit" in d.text


# --------------------------------------------------------------------------
# subhole handoff (F4)
# --------------------------------------------------------------------------
def test_subhole_roundtrip():
    db = DB()
    _seed_slice(db)
    d = dispatch(db, "L", "raise_subhole",
                 {"slice_slug": "pinned-qa-group", "concept_slug": "list-iteration",
                  "evidence": "failed to index a list"})
    assert d.committed and "HOLD" in d.text
    row = db.one("SELECT subhole_concept FROM slices WHERE slug='pinned-qa-group'")
    assert row["subhole_concept"] == "list-iteration"
    # M clears it
    assert "clear_subhole" in {o.name for o in menu_for(db, "M")}
    d = dispatch(db, "M", "clear_subhole",
                 {"slice_slug": "pinned-qa-group", "plan_note": "taught list-iteration"})
    assert d.committed
    row = db.one("SELECT subhole_concept FROM slices WHERE slug='pinned-qa-group'")
    assert row["subhole_concept"] is None
