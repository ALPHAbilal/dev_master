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


def test_sdk_runner_says_it_is_not_built_rather_than_pretending():
    from ui.runner import SdkRunner
    ev = SdkRunner(DB()).turn("hello")
    assert ev[0].kind == "error" and "not built yet" in ev[0].text
