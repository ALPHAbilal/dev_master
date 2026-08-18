"""UI tests: codebase adoption (folder + zip), the read-only state snapshot,
the active-agent indicator, and the pure HTTP router. No socket, no SDK, no model."""
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor import DB, dispatch
from ui import session, state
from ui.runner import Event, ScriptedRunner
from ui.server import App, handle


def _codebase(files=None) -> str:
    d = Path(tempfile.mkdtemp())
    for rel, body in (files or {"app.py": "print(1)\n", "lib/util.py": "x=1\n"}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return str(d)


def _app(runner=None) -> App:
    return App(DB(), tempfile.mkdtemp(), runner=runner)


def _zip_bytes(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in entries.items():
            z.writestr(name, body)
    return buf.getvalue()


# --------------------------------------------------------------------------
# adoption — nothing is hardcoded; nothing else works until this happens
# --------------------------------------------------------------------------
def test_nothing_is_adopted_by_default():
    db = DB()
    assert session.is_adopted(db) is False
    assert session.current_root(db) is None
    assert state.snapshot(db)["adopted"] is False


def test_adopt_folder_sets_target_through_the_gateway():
    db, root = DB(), _codebase()
    got = session.adopt_folder(db, root)
    assert Path(got) == Path(root).resolve()
    assert session.is_adopted(db)
    # committed through set_target, not a side door
    assert db.one("SELECT codebase_path FROM target WHERE id=1")["codebase_path"] == got


def test_adopt_rejects_missing_and_non_dir_and_empty():
    db = DB()
    for bad in ("/nope/does/not/exist", __file__):
        try:
            session.adopt_folder(db, bad)
            assert False, f"should refuse {bad}"
        except session.SessionError:
            pass
    empty = tempfile.mkdtemp()
    try:
        session.adopt_folder(db, empty)
        assert False, "should refuse an empty folder"
    except session.SessionError:
        pass
    assert not session.is_adopted(db)      # a refusal commits nothing


def test_adopt_zip_extracts_and_descends_wrapper():
    db, ws = DB(), tempfile.mkdtemp()
    blob = _zip_bytes({"proj-main/app.py": "print(1)\n", "proj-main/lib/u.py": "x=1\n"})
    root = session.adopt_zip(db, blob, ws, "proj.zip")
    assert Path(root).name == "proj-main"          # the wrapper folder is descended into
    assert (Path(root) / "app.py").exists()
    assert session.is_adopted(db)


def test_zip_slip_members_are_skipped():
    db, ws = DB(), tempfile.mkdtemp()
    blob = _zip_bytes({"../escaped.py": "bad\n", "ok.py": "good\n"})
    root = session.adopt_zip(db, blob, ws, "z.zip")
    assert (Path(root) / "ok.py").exists()
    assert not (Path(ws).parent / "escaped.py").exists()


def test_bad_zip_refuses():
    db = DB()
    try:
        session.adopt_zip(db, b"not a zip at all", tempfile.mkdtemp())
        assert False
    except session.SessionError:
        pass


# --------------------------------------------------------------------------
# the active-agent indicator — it must agree with the real picker
# --------------------------------------------------------------------------
def test_active_is_none_before_adoption():
    who = state.who_is_active(DB(), frontier_empty=True)
    assert who["agent"] is None and who["learner_waits"] is True


def test_active_is_survey_right_after_adoption():
    db = DB()
    session.adopt_folder(db, _codebase())
    who = state.who_is_active(db, frontier_empty=True)
    # adoption writes the target row, but the map is not drawn — SURVEY is still due
    assert who["agent"] == "M/SURVEY"
    assert "reading your codebase" in who["activity"]


def test_active_is_l_once_surveyed_and_the_frontier_is_filled():
    db = DB()
    session.adopt_folder(db, _codebase())
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    who = state.who_is_active(db, frontier_empty=False)
    assert who["agent"] == "L" and who["learner_waits"] is False


def test_active_shows_subhole_and_learner_waits():
    db = DB()
    session.adopt_folder(db, _codebase())
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    dispatch(db, "L", "raise_subhole",
             {"slice_slug": "s1", "concept_slug": "c", "evidence": "e"})
    who = state.who_is_active(db, frontier_empty=False)
    assert who["agent"] == "M/SUBHOLE" and who["learner_waits"] is True


# --------------------------------------------------------------------------
# the snapshot — read-only, live off the DB
# --------------------------------------------------------------------------
def test_snapshot_reports_spine_specs_and_gate():
    db = DB()
    root = _codebase()
    session.adopt_folder(db, root)
    dispatch(db, "M", "upsert_slice",
             {"slug": "s1", "title": "first slice", "target_file": "app.py", "ordinal": 1})
    snap = state.snapshot(db)
    assert snap["spine"][0]["slug"] == "s1"
    assert snap["spine"][0]["has_spec"] is False       # lazy specs surface honestly
    assert snap["gate"] is None
    assert any(f["path"] == "app.py" for f in snap["files"])


def test_file_tree_marks_the_gated_file_as_his():
    db = DB()
    root = _codebase()
    session.adopt_folder(db, root)
    spec = Path(tempfile.mkdtemp()) / "s1.md"
    spec.write_text("# spec\n")
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py",
                                       "spec_path": str(spec)})
    dispatch(db, "L", "open_gate", {"slice_slug": "s1"})
    tree = {f["path"]: f for f in session.file_tree(db)}
    assert tree["app.py"]["gated"] is True
    assert tree["lib/util.py"]["gated"] is False
    assert state.snapshot(db)["gate"]["target_file"] == "app.py"


def test_secrets_never_reach_the_tree():
    db = DB()
    root = _codebase({"app.py": "x\n", ".env": "API_KEY=sk-real\n",
                      "server.pem": "-----BEGIN KEY-----\n", ".env.production": "K=1\n"})
    session.adopt_folder(db, root)
    assert [f["path"] for f in session.file_tree(db)] == ["app.py"]


def test_a_folder_of_only_secrets_is_not_adoptable():
    db = DB()
    try:
        session.adopt_folder(db, _codebase({".env": "API_KEY=sk-real\n"}))
        assert False, "a folder with nothing but secrets has nothing to survey"
    except session.SessionError:
        pass


def test_ignored_dirs_stay_out_of_the_tree():
    db = DB()
    root = _codebase({"app.py": "x\n", ".git/config": "junk\n", "__pycache__/a.pyc": "junk\n"})
    session.adopt_folder(db, root)
    paths = [f["path"] for f in session.file_tree(db)]
    assert paths == ["app.py"]


# --------------------------------------------------------------------------
# the pure router
# --------------------------------------------------------------------------
def test_state_route_returns_snapshot():
    r = handle(_app(), "GET", "/api/state")
    assert r.status == 200 and r.body["adopted"] is False


def test_adopt_route_happy_and_sad():
    app = _app()
    r = handle(app, "POST", "/api/adopt", json.dumps({"path": _codebase()}).encode())
    assert r.status == 200 and r.body["state"]["adopted"] is True

    bad = handle(_app(), "POST", "/api/adopt", json.dumps({"path": "/nope"}).encode())
    assert bad.status == 400 and "no such folder" in bad.body["error"]

    blank = handle(_app(), "POST", "/api/adopt", b"{}")
    assert blank.status == 400


def test_say_is_refused_before_a_codebase_exists():
    r = handle(_app(), "POST", "/api/say", json.dumps({"text": "hi"}).encode())
    assert r.status == 409


def test_say_appends_learner_then_runner_events():
    app = _app(ScriptedRunner(None, [[Event("say", "what do you think it does?", "L")]]))
    app.runner.db = app.db
    handle(app, "POST", "/api/adopt", json.dumps({"path": _codebase()}).encode())
    r = handle(app, "POST", "/api/say", json.dumps({"text": "it groups them"}).encode())
    t = r.body["state"]["transcript"]
    assert [x["kind"] for x in t] == ["learner", "say"]
    assert t[0]["text"] == "it groups them"
    assert t[1]["agent"] == "L"


def test_empty_say_refused():
    app = _app()
    handle(app, "POST", "/api/adopt", json.dumps({"path": _codebase()}).encode())
    assert handle(app, "POST", "/api/say", json.dumps({"text": "   "}).encode()).status == 400


def test_unknown_route_404s():
    assert handle(_app(), "GET", "/nope").status == 404


def test_page_is_served():
    r = handle(_app(), "GET", "/")
    assert r.status == 200 and b"<title>tutor</title>" in r.body


# --------------------------------------------------------------------------
# the indicator must never claim work that is not happening
# --------------------------------------------------------------------------
def test_due_is_not_running():
    db = DB()
    session.adopt_folder(db, _codebase())
    who = state.who_is_active(db, frontier_empty=True, running=None)
    assert who["agent"] == "M/SURVEY"
    assert who["status"] == "due"
    assert "has not run yet" in who["activity"]


def test_running_is_only_reported_when_actually_running():
    db = DB()
    session.adopt_folder(db, _codebase())
    who = state.who_is_active(db, frontier_empty=True, running="M/SURVEY")
    assert who["status"] == "running"
    assert "reading your codebase" in who["activity"]


def test_running_survey_keeps_its_label_after_it_writes_its_first_slice():
    """Regression: writing a slice flipped the picker to PLAN mid-run and the header
    relabelled a still-running SURVEY as 'M/PLAN due'."""
    db = DB()
    session.adopt_folder(db, _codebase())
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    who = state.who_is_active(db, frontier_empty=True, running="M/SURVEY")
    assert who["agent"] == "M/SURVEY" and who["status"] == "running"


def test_the_button_follows_the_wakeup():
    db = DB()
    session.adopt_folder(db, _codebase())
    assert state.who_is_active(db, True)["start_label"] == "Run the survey"
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    assert state.who_is_active(db, True)["start_label"] == "Plan the next slice"


def test_l_waiting_is_not_a_running_state():
    db = DB()
    session.adopt_folder(db, _codebase())
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    who = state.who_is_active(db, frontier_empty=False)
    assert who["status"] == "waiting" and who["learner_waits"] is False


def test_survey_route_refuses_before_adoption_and_when_busy():
    app = _app()
    assert handle(app, "POST", "/api/survey").status == 409       # nothing adopted
    handle(app, "POST", "/api/adopt", json.dumps({"path": _codebase()}).encode())
    app.running = "M/SURVEY"
    r = handle(app, "POST", "/api/survey")
    assert r.status == 409 and "already running" in r.body["error"]


def test_survey_prompt_is_refused_once_a_spine_exists():
    from ui.survey import survey_prompt, SurveyError
    db = DB()
    session.adopt_folder(db, _codebase())
    system, first = survey_prompt(db)
    assert "[SURVEY]" in system and "spec_path` NULL" in system
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    try:
        survey_prompt(db)
        assert False, "a second survey is a spine repair, not a survey"
    except SurveyError:
        pass


# --------------------------------------------------------------------------
# archive-before-resurvey — a second survey must never silently overwrite the first
# --------------------------------------------------------------------------
def _file_app():
    d = Path(tempfile.mkdtemp())
    return App(DB(str(d / "session.db")), str(d / "ws"))


def test_archive_snapshots_and_reset_clears_only_the_map():
    from ui import runs
    app = _file_app()
    session.adopt_folder(app.db, _codebase())
    dispatch(app.db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "a.py"})
    dispatch(app.db, "M", "upsert_concept", {"slug": "c1", "name": "c"})
    dispatch(app.db, "L", "record_probe", {"kind": "predict", "result": "HIT"})

    saved = runs.archive(app.db, "claude-haiku-4-5")
    assert saved.exists()
    cleared = runs.reset_spine(app.db)
    assert cleared == {"slices": 1, "concepts": 1, "gates": 0, "specs": 0, "frontier": 0}
    assert app.db.one("SELECT 1 FROM slices") is None
    assert session.is_adopted(app.db)                       # target survives
    assert app.db.one("SELECT 1 FROM probes")               # evidence survives


def test_history_lists_archived_runs_with_their_sizes():
    from ui import runs
    app = _file_app()
    session.adopt_folder(app.db, _codebase())
    dispatch(app.db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "a.py"})
    runs.archive(app.db, "model-a")
    h = runs.history(app.db)
    assert len(h) == 1 and h[0]["slices"] == 1 and h[0]["label"] == "model-a"


def test_resurvey_archives_before_clearing():
    app = _file_app()
    handle(app, "POST", "/api/adopt", json.dumps({"path": _codebase()}).encode())
    dispatch(app.db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "a.py"})
    handle(app, "POST", "/api/survey")                      # SDK absent -> run errors out
    from ui import runs
    assert len(runs.history(app.db)) == 1, "the old spine must be archived first"
    assert app.db.one("SELECT 1 FROM slices") is None       # and then cleared
    assert any("archived" in t["text"] for t in app.transcript)


def test_in_memory_session_refuses_to_archive_rather_than_losing_the_spine():
    from ui import runs
    app = _app()
    handle(app, "POST", "/api/adopt", json.dumps({"path": _codebase()}).encode())
    dispatch(app.db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "a.py"})
    r = handle(app, "POST", "/api/survey")
    assert r.status == 409
    assert app.db.one("SELECT 1 FROM slices"), "a failed archive must clear nothing"


def test_spine_makes_the_session_resurveyable():
    db = DB()
    session.adopt_folder(db, _codebase())
    assert state.who_is_active(db, True)["resurveyable"] is False
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "a.py"})
    assert state.who_is_active(db, True)["resurveyable"] is True


def test_plan_is_launchable_now_that_it_has_a_runner():
    db = DB()
    session.adopt_folder(db, _codebase())
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    who = state.who_is_active(db, frontier_empty=True)
    assert who["agent"] == "M/PLAN"
    assert who["startable"] is True and who["blocked_by"] is None
    assert who["start_route"] == "/api/plan"


def test_subhole_still_reports_its_missing_runner():
    """The one M turn with no runner must still say so rather than dead-ending."""
    db = DB()
    session.adopt_folder(db, _codebase())
    dispatch(db, "M", "upsert_slice", {"slug": "s1", "title": "t", "target_file": "app.py"})
    dispatch(db, "L", "raise_subhole",
             {"slice_slug": "s1", "concept_slug": "c", "evidence": "e"})
    who = state.who_is_active(db, frontier_empty=False)
    assert who["agent"] == "M/SUBHOLE" and who["startable"] is False
    assert who["blocked_by"] and "step 6" in who["blocked_by"]


def test_survey_due_is_startable_so_has_no_blocker():
    db = DB()
    session.adopt_folder(db, _codebase())
    who = state.who_is_active(db, frontier_empty=True)
    assert who["startable"] is True and who["blocked_by"] is None


def test_model_is_pinned_not_inherited():
    from ui.survey import DEFAULT_MODEL
    src = (Path(__file__).resolve().parent.parent / "ui" / "survey.py").read_text()
    assert "model=model" in src, "the survey must pass an explicit model, never inherit"
    assert DEFAULT_MODEL.startswith("claude-")


def test_snapshot_reports_the_model_so_the_screen_never_guesses():
    app = _app()
    assert app.snapshot()["model"].startswith("claude-")
    app.model = "claude-opus-5"
    assert app.snapshot()["model"] == "claude-opus-5"


def test_survey_options_contain_the_agent():
    """Regression: a live run invoked Skill and Bash because host settings leaked in."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "survey.py").read_text()
    assert "setting_sources=[]" in src           # no host CLAUDE.md, skills, or perms
    for escape in ("Bash", "Skill", "Task", "Write"):
        assert f'"{escape}"' in src, f"{escape} must be explicitly disallowed"


def test_survey_emits_during_the_run_not_after_it():
    """The whole point of the feed: events must arrive while the survey is working."""
    from ui import survey as survey_mod
    seen = []

    async def fake_run(db, emit, model=None, trace=None):
        emit(Event("handoff", f"M/SURVEY started on {model}", "M/SURVEY"))
        assert seen, "the first event must already be delivered before the run ends"
        emit(Event("tool", "grep def ", "M/SURVEY"))

    original = survey_mod.run_survey
    survey_mod.run_survey = fake_run
    try:
        survey_mod.run_survey_sync(DB(), lambda e: seen.append(e))
    finally:
        survey_mod.run_survey = original
    assert [e.kind for e in seen] == ["handoff", "tool"]


def test_survey_errors_are_surfaced_not_swallowed():
    from ui import survey as survey_mod
    seen = []
    survey_mod.run_survey_sync(DB(), seen.append)     # no codebase adopted
    assert seen and seen[0].kind == "error"


def test_survey_prompt_points_the_agent_at_the_adopted_root():
    from ui.survey import survey_prompt
    db = DB()
    root = _codebase()
    session.adopt_folder(db, root)
    system, _ = survey_prompt(db)
    assert str(Path(root).resolve()) in system


def test_sdk_runner_refuses_to_teach_without_a_frontier():
    """No handoff = L has nothing to teach. The error names whose turn it is."""
    from ui.runner import SdkRunner
    db = DB()
    db.meta_set("library_root", tempfile.mkdtemp())
    ev = SdkRunner(db).turn("hello")
    assert ev[0].kind == "error" and "M/PLAN" in ev[0].text
    assert SdkRunner(db).frontier_empty() is True


# --------------------------------------------------------------------------
# the frontier panel — the file M publishes, rendered for the page
# --------------------------------------------------------------------------
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "frontier_pinned_qa.json"


def test_snapshot_reports_no_frontier_before_one_is_published():
    assert state.snapshot(DB())["frontier"] is None


def test_frontier_panel_summarises_the_slice_and_keeps_the_file_whole():
    raw = json.loads(_FIXTURE.read_text())
    f = state.frontier(raw)
    assert f["now"]["slug"] == "pinned-qa-group"
    assert f["now"]["target_file"] == "soufiane_prompts/prompts/run_prompts.py"
    assert f["now"]["concept"] == "enumerate-index"
    assert f["now"]["road"] == "intuition-train"
    assert f["now"]["skip_gap"] is False
    assert f["now"]["vocab_hold"] == ["enumerate"]
    assert "enumerate-index" in f["now"]["prereqs"]
    # the tracing half is the file itself, unedited
    assert f["full"] == raw
    assert f["full"]["gap"]["just_tell"] == raw["gap"]["just_tell"]


def test_frontier_panel_reports_a_skip_gap_slice_instead_of_a_blank_concept():
    raw = json.loads(_FIXTURE.read_text())
    raw.pop("gap")
    f = state.frontier(raw)
    assert f["now"]["skip_gap"] is True
    assert f["now"]["concept"] is None


def test_app_publishes_the_frontier_through_the_snapshot():
    db, root = DB(), _codebase()
    session.adopt_folder(db, root)
    app = App(db, tempfile.mkdtemp())
    lib = Path(tempfile.mkdtemp())
    db.meta_set("library_root", str(lib))
    assert app.snapshot()["frontier"] is None          # nothing published yet

    (lib / "frontier.json").write_text(_FIXTURE.read_text())
    assert app.snapshot()["frontier"]["now"]["slug"] == "pinned-qa-group"


def test_a_frontier_that_fails_the_schema_is_reported_as_absent():
    """A half-filled handoff is not a lesson. The panel must not render it as one."""
    db = DB()
    app = App(db, tempfile.mkdtemp())
    lib = Path(tempfile.mkdtemp())
    db.meta_set("library_root", str(lib))
    raw = json.loads(_FIXTURE.read_text())
    raw["slice"]["target_file"] = ""                   # the schema refuses this
    (lib / "frontier.json").write_text(json.dumps(raw))
    assert app.frontier_data() is None
    assert app.snapshot()["frontier"] is None

    (lib / "frontier.json").write_text("{not json")
    assert app.frontier_data() is None


# --------------------------------------------------------------------------
# the L turn (build order step 4) — pure parts, no SDK, no model
# --------------------------------------------------------------------------
def _published(db, raw=None):
    lib = Path(tempfile.mkdtemp())
    db.meta_set("library_root", str(lib))
    raw = raw or json.loads(_FIXTURE.read_text())
    (lib / "frontier.json").write_text(json.dumps(raw))
    return raw


def test_lesson_prompt_opens_with_the_opening_question_then_switches():
    from tutor.context_manager import ContextManager
    from tutor.frontier import validate
    from ui.lesson import lesson_prompt
    db = DB()
    f = validate(json.loads(_FIXTURE.read_text()))
    # the concept must exist and be unowned for the teaching block to render
    dispatch(db, "M", "upsert_concept",
             {"slug": "enumerate-index", "name": "enumerate", "state": "READY"})
    cm = ContextManager("L")
    p1 = lesson_prompt(db, cm, f, "hi, where do we start?")
    assert "OPEN WITH" in p1 and f.gap["opening_question"] in p1
    assert "[USER] hi, where do we start?" in p1
    cm.append_assistant("what does the loop hand you each step?")
    # the entry probe advances the step machine past PROBE (level 5 = produce)
    dispatch(db, "L", "record_probe",
             {"concept_slug": "enumerate-index", "kind": "entry",
              "result": "HIT", "level": 5})
    p2 = lesson_prompt(db, cm, f, "the item, I think")
    assert "OPEN WITH" not in p2 and "STEP PRODUCE" in p2   # the router moved on
    assert "what does the loop hand you each step?" in p2   # history survived


def test_lesson_refuses_an_unusable_frontier_and_names_the_planner():
    from ui.lesson import LessonError, load_current_frontier
    db = DB()
    raw = json.loads(_FIXTURE.read_text())
    raw["gap"]["opening_question"] = ""                     # schema-refused
    _published(db, raw)
    try:
        load_current_frontier(db)
        assert False, "should have raised"
    except LessonError as e:
        assert "re-run M/PLAN" in str(e)


def test_sdk_runner_wipes_history_at_the_slice_boundary():
    """F1: a new slug on the frontier drops the old ContextManager, and the
    frontier's vocab is seeded exactly at that fresh start (F3)."""
    from ui import lesson as lesson_mod
    from ui.runner import SdkRunner

    db = DB()
    raw = _published(db)
    calls = []
    r = SdkRunner(db)
    original = lesson_mod.run_lesson_sync
    lesson_mod.run_lesson_sync = lambda db_, cm, text, sink, model, trace: calls.append(cm)
    try:
        r.turn("first")
        first_cm = calls[0]
        r.turn("second")
        assert calls[1] is first_cm                         # same slice, same mind
        raw["slice"]["slug"] = "next-slice"
        _seen = json.dumps(raw)
        (Path(db.meta_get("library_root")) / "frontier.json").write_text(_seen)
        db.execute("INSERT INTO slices(slug,title,target_file,state) "
                   "VALUES('next-slice','next','x.py','READY')")
        r.turn("third")
        assert calls[2] is not first_cm                     # F1: the wipe
    finally:
        lesson_mod.run_lesson_sync = original
    assert db.one("SELECT state FROM vocab WHERE term='enumerate'")["state"] == "hold"


def test_rollover_archives_the_frontier_only_when_the_slice_is_built():
    from tutor.frontier import validate
    from ui.lesson import _rollover_if_built
    db = DB()
    _published(db)
    f = validate(json.loads(_FIXTURE.read_text()))
    lib = Path(db.meta_get("library_root"))
    seen = []
    db.execute("INSERT INTO slices(slug,title,target_file,state) "
               "VALUES('pinned-qa-group','t','run_prompts.py','READY')")
    _rollover_if_built(db, f, seen.append)
    assert (lib / "frontier.json").exists() and not seen    # not BUILT: nothing moves

    db.execute("UPDATE slices SET state='BUILT' WHERE slug='pinned-qa-group'")
    _rollover_if_built(db, f, seen.append)
    assert not (lib / "frontier.json").exists()             # code did the rollover
    assert (lib / "archive" / "frontier-pinned-qa-group.json").exists()
    assert seen and seen[0].kind == "handoff" and "M/PLAN" in seen[0].text


def test_say_runs_a_live_runner_in_the_background_with_running_set():
    from ui.runner import Event, Runner

    class FakeLive(Runner):
        name = "sdk"
        def __init__(self, app_holder):
            self.emit = None                                # set after App exists
        def turn(self, text):
            self.emit(Event("say", "echo: " + text, "L"))
            return []

    live = FakeLive(None)
    db, root = DB(), _codebase()
    session.adopt_folder(db, root)
    app = App(db, tempfile.mkdtemp(), runner=live)
    live.emit = app.emit
    r = handle(app, "POST", "/api/say", json.dumps({"text": "hello"}).encode())
    assert r.status == 200 and r.body.get("started") is True
    import time
    for _ in range(50):                                     # the thread is near-instant
        if any(t.get("text") == "echo: hello" for t in app.transcript):
            break
        time.sleep(0.02)
    assert any(t["kind"] == "learner" for t in app.transcript)
    assert any(t.get("text") == "echo: hello" for t in app.transcript)
