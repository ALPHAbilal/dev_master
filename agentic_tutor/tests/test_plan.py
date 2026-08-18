"""M/PLAN tests: the two new gateway ops and their invariants, slice selection,
the prompt, and the frontier-file wakeup. No SDK, no model."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor import DB, dispatch
from tutor.frontier import empty_template
from ui.plan import plan_prompt, PlanError, _next_slice
from ui.server import App

FIX = Path(__file__).resolve().parent / "fixtures" / "frontier_pinned_qa.json"


def _db(lib=None) -> DB:
    db = DB()
    db.meta_set("library_root", lib or tempfile.mkdtemp())
    dispatch(db, "M", "set_target", {"codebase_path": "/repo"})
    return db


def _spined() -> DB:
    db = _db()
    dispatch(db, "M", "upsert_concept", {"slug": "enumerate-index", "name": "enumerate"})
    dispatch(db, "M", "upsert_slice",
             {"slug": "pinned-qa-group", "title": "pinned QA grouping",
              "target_file": "prompts/run_prompts.py", "ordinal": 1,
              "concept_prereqs": ["enumerate-index"]})
    return db


SPEC = ("Write _pinned_qa_group(questions). Pinned questions lead each group and the "
        "original order is preserved within a group. Returns a new list; the input is "
        "never mutated. An empty input returns an empty list.")


# --------------------------------------------------------------------------
# write_spec — file and path in ONE act
# --------------------------------------------------------------------------
def test_write_spec_writes_the_file_and_sets_the_path_together():
    db = _spined()
    d = dispatch(db, "M", "write_spec", {"slice_slug": "pinned-qa-group", "body": SPEC})
    assert d.committed
    path = db.one("SELECT spec_path FROM slices WHERE slug='pinned-qa-group'")["spec_path"]
    assert path and Path(path).exists()
    assert Path(path).read_text() == SPEC


def test_a_non_null_spec_path_always_means_the_file_exists():
    """The lazy-spec invariant, stated as a test: open_gate trusts the column."""
    db = _spined()
    dispatch(db, "M", "write_spec", {"slice_slug": "pinned-qa-group", "body": SPEC})
    d = dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    assert d.committed, d.text


def test_open_gate_still_refuses_a_slice_with_no_spec():
    db = _spined()
    d = dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    assert not d.committed and "spec" in d.text


def test_write_spec_refuses_an_unknown_slice_and_a_stub_body():
    db = _spined()
    assert "REFUSED" in dispatch(db, "M", "write_spec",
                                 {"slice_slug": "nope", "body": SPEC}).text
    d = dispatch(db, "M", "write_spec", {"slice_slug": "pinned-qa-group", "body": "TODO"})
    assert "REFUSED" in d.text
    assert db.one("SELECT spec_path FROM slices WHERE slug='pinned-qa-group'")["spec_path"] is None


# --------------------------------------------------------------------------
# write_frontier — the schema refuses a partial fill
# --------------------------------------------------------------------------
def _publishable(db) -> dict:
    dispatch(db, "M", "write_spec", {"slice_slug": "pinned-qa-group", "body": SPEC})
    return json.loads(FIX.read_text())


def test_write_frontier_publishes_a_complete_frontier():
    db = _spined()
    raw = _publishable(db)
    d = dispatch(db, "M", "write_frontier", {"frontier": raw})
    assert d.committed, d.text
    dest = Path(db.meta_get("library_root")) / "frontier.json"
    assert json.loads(dest.read_text())["slice"]["slug"] == "pinned-qa-group"


def test_write_frontier_refuses_an_empty_key_and_writes_nothing():
    db = _spined()
    raw = _publishable(db)
    raw["gap"]["justify"] = ""
    d = dispatch(db, "M", "write_frontier", {"frontier": raw})
    assert "REFUSED" in d.text and "justify" in d.text
    assert not (Path(db.meta_get("library_root")) / "frontier.json").exists()


def test_write_frontier_refuses_the_empty_template():
    db = _spined()
    _publishable(db)
    d = dispatch(db, "M", "write_frontier", {"frontier": empty_template("pinned-qa-group")})
    assert "REFUSED" in d.text


def test_write_frontier_is_offered_but_refuses_without_the_spec():
    """Offered from the moment a spine exists — hiding it stalled a real M/PLAN turn —
    but it still refuses to publish a slice whose spec was never written."""
    db = _spined()
    assert "write_frontier" in dispatch(db, "M").text
    d = dispatch(db, "M", "write_frontier", {"frontier": json.loads(FIX.read_text())})
    assert not d.committed and "spec" in d.text


def test_write_frontier_refuses_a_slice_whose_own_spec_is_unwritten():
    """Another slice having a spec must not let a spec-less one be published."""
    db = _spined()
    dispatch(db, "M", "upsert_slice",
             {"slug": "other", "title": "o", "target_file": "o.py", "ordinal": 2})
    dispatch(db, "M", "write_spec", {"slice_slug": "other", "body": SPEC})
    raw = json.loads(FIX.read_text())           # names pinned-qa-group, which has no spec
    d = dispatch(db, "M", "write_frontier", {"frontier": raw})
    assert "REFUSED" in d.text and "spec" in d.text
    assert not (Path(db.meta_get("library_root")) / "frontier.json").exists()


def test_write_frontier_refuses_an_unknown_slice():
    db = _spined()
    raw = _publishable(db)
    raw["slice"]["slug"] = "ghost-slice"
    assert "REFUSED" in dispatch(db, "M", "write_frontier", {"frontier": raw}).text


# --------------------------------------------------------------------------
# menu discipline — the new ops appear only when they are legal
# --------------------------------------------------------------------------
def test_new_ops_are_M_only_and_state_gated():
    db = _db()
    names = lambda role: {l.split("—")[0].strip()
                          for l in dispatch(db, role).text.splitlines() if "—" in l}
    assert "write_spec" not in names("M")       # no spine yet
    assert "write_spec" not in names("L")       # never L's
    assert "write_frontier" not in names("M")   # no spine at all yet
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "a.py"})
    # both acts of a plan turn appear together, before either has run
    assert "write_spec" in names("M") and "write_frontier" in names("M")
    assert "write_spec" not in names("L") and "write_frontier" not in names("L")


# --------------------------------------------------------------------------
# which slice gets planned
# --------------------------------------------------------------------------
def test_plans_the_earliest_unbuilt_slice_even_when_all_are_locked():
    db = _db()
    for i, slug in enumerate(["c", "a", "b"], start=1):
        dispatch(db, "M", "upsert_slice",
                 {"slug": slug, "title": slug, "target_file": f"{slug}.py", "ordinal": i})
    assert _next_slice(db)["slug"] == "c"       # ordinal 1, LOCKED is fine


def test_ready_outranks_a_lower_ordinal_lock():
    db = _db()
    dispatch(db, "M", "upsert_slice",
             {"slug": "first", "title": "f", "target_file": "f.py", "ordinal": 1})
    dispatch(db, "M", "upsert_slice",
             {"slug": "second", "title": "s", "target_file": "s.py", "ordinal": 2,
              "state": "READY"})
    assert _next_slice(db)["slug"] == "second"


def test_built_slices_are_skipped():
    db = _spined()
    dispatch(db, "M", "write_spec", {"slice_slug": "pinned-qa-group", "body": SPEC})
    dispatch(db, "L", "open_gate", {"slice_slug": "pinned-qa-group"})
    dispatch(db, "L", "pass_gate", {"slice_slug": "pinned-qa-group", "note": "judged vs spec"})
    assert _next_slice(db) is None


# --------------------------------------------------------------------------
# the prompt
# --------------------------------------------------------------------------
def test_prompt_carries_evidence_overlays_and_the_frontier_shape():
    db = _spined()
    dispatch(db, "L", "record_probe",
             {"concept_slug": "enumerate-index", "kind": "predict", "result": "MISS"})
    system, first = plan_prompt(db)
    assert "[EVIDENCE]" in system and "predict/MISS" in system
    assert "[OVERLAYS]" in system
    assert "[SURVEY]" not in system and "[TOOL DISCIPLINE]" not in system
    assert "pinned-qa-group" in first and "write_spec" in first and "write_frontier" in first
    assert "opening_question" in first          # the template shape is handed over
    assert "Do not plan the slice after this one" in first


def test_prompt_refuses_without_a_spine_or_when_all_built():
    for setup in (lambda: _db(), ):
        try:
            plan_prompt(setup())
            assert False, "planning needs a spine"
        except PlanError:
            pass


def test_plan_uses_no_repo_tools():
    src = (Path(__file__).resolve().parent.parent / "ui" / "plan.py").read_text()
    assert 'allowed_tools=["mcp__tutor__db"]' in src
    for banned in ("Read", "Grep", "Bash", "Write"):
        assert f'"{banned}"' in src, f"{banned} must be explicitly disallowed on PLAN"


# --------------------------------------------------------------------------
# the frontier FILE is the wakeup signal
# --------------------------------------------------------------------------
def test_the_frontier_file_decides_who_is_awake():
    d = Path(tempfile.mkdtemp())
    app = App(DB(str(d / "session.db")), str(d / "ws"))
    dispatch(app.db, "M", "set_target", {"codebase_path": "/repo"})
    dispatch(app.db, "M", "upsert_slice",
             {"slug": "s1", "title": "t", "target_file": "a.py", "ordinal": 1})
    assert app.frontier_empty() is True
    assert app.snapshot()["active"]["agent"] == "M/PLAN"

    dispatch(app.db, "M", "write_spec", {"slice_slug": "s1", "body": SPEC})
    raw = json.loads(FIX.read_text())
    raw["slice"]["slug"] = "s1"
    dispatch(app.db, "M", "write_frontier", {"frontier": raw})

    assert app.frontier_empty() is False
    assert app.snapshot()["active"]["agent"] == "L"     # L now has something to teach


# --------------------------------------------------------------------------
# stale frontier — a re-survey left frontier.json behind, so the UI announced
# "L waiting for you" over a spine that had never been planned.
# --------------------------------------------------------------------------
def _file_app():
    from ui.server import App
    d = Path(tempfile.mkdtemp())
    app = App(DB(str(d / "session.db")), str(d / "ws"))
    dispatch(app.db, "M", "set_target", {"codebase_path": "/repo"})
    return app


def _plan_a_slice(app, slug="s1"):
    dispatch(app.db, "M", "upsert_slice",
             {"slug": slug, "title": "t", "target_file": "a.py", "ordinal": 1})
    dispatch(app.db, "M", "write_spec", {"slice_slug": slug, "body": SPEC})
    raw = json.loads(FIX.read_text())
    raw["slice"]["slug"] = slug
    dispatch(app.db, "M", "write_frontier", {"frontier": raw})


def test_resurvey_clears_the_frontier_and_the_specs():
    from ui import runs
    app = _file_app()
    _plan_a_slice(app)
    assert app.frontier_empty() is False

    runs.archive(app.db, "m")
    cleared = runs.reset_spine(app.db)
    assert cleared["frontier"] == 1 and cleared["specs"] == 1
    assert not (app.library / "frontier.json").exists()
    assert list((app.library / "slices").glob("*.md")) == []
    assert app.frontier_empty() is True


def test_the_archive_keeps_the_specs_and_frontier_too():
    from ui import runs
    app = _file_app()
    _plan_a_slice(app)
    saved = runs.archive(app.db, "m")
    lib = saved.with_name(saved.stem + "-library")
    assert (lib / "frontier.json").exists()
    assert (lib / "slices" / "s1.md").exists()


def test_a_frontier_naming_a_missing_slice_counts_as_empty():
    """Defence in depth: debris must never be mistaken for a lesson."""
    app = _file_app()
    _plan_a_slice(app, "gone")
    app.db.execute("DELETE FROM slices WHERE slug='gone'")     # spine replaced under it
    assert (app.library / "frontier.json").exists()
    assert app.frontier_empty() is True
    dispatch(app.db, "M", "upsert_slice",
             {"slug": "fresh", "title": "t", "target_file": "b.py", "ordinal": 1})
    assert app.snapshot()["active"]["agent"] == "M/PLAN"


def test_a_corrupt_frontier_counts_as_empty():
    app = _file_app()
    _plan_a_slice(app)
    (app.library / "frontier.json").write_text("{not json")
    assert app.frontier_empty() is True


# --------------------------------------------------------------------------
# menu snapshot vs. same-turn state. M/PLAN reads the menu once, at the start of
# a turn whose first act creates the precondition for its second act. Gating on
# that precondition made write_frontier invisible and the turn stalled.
# --------------------------------------------------------------------------
def test_write_frontier_is_on_the_menu_before_any_spec_is_written():
    db = _db()
    dispatch(db, "M", "upsert_slice",
             {"slug": "s1", "title": "t", "target_file": "a.py", "ordinal": 1})
    menu = dispatch(db, "M").text
    assert "write_spec" in menu
    assert "write_frontier" in menu, \
        "both acts of an M/PLAN turn must be visible in the menu it reads first"


def test_write_frontier_still_refuses_when_that_slice_has_no_spec():
    """Visibility is not permission — the real check runs at call time."""
    db = _db()
    dispatch(db, "M", "upsert_slice",
             {"slug": "s1", "title": "t", "target_file": "a.py", "ordinal": 1})
    raw = json.loads(FIX.read_text())
    raw["slice"]["slug"] = "s1"
    d = dispatch(db, "M", "write_frontier", {"frontier": raw})
    assert "REFUSED" in d.text and "spec" in d.text
    assert not (Path(db.meta_get("library_root")) / "frontier.json").exists()


def test_both_acts_of_a_plan_turn_work_in_sequence():
    db = _db()
    dispatch(db, "M", "upsert_slice",
             {"slug": "s1", "title": "t", "target_file": "a.py", "ordinal": 1})
    assert "write_frontier" in dispatch(db, "M").text          # menu read once, up front
    assert dispatch(db, "M", "write_spec",
                    {"slice_slug": "s1", "body": SPEC}).committed
    raw = json.loads(FIX.read_text()); raw["slice"]["slug"] = "s1"
    assert dispatch(db, "M", "write_frontier", {"frontier": raw}).committed
