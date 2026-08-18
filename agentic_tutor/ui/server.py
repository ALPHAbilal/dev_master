"""server — a stdlib-only local web app. No framework, no npm, no dependencies.

Routes (all JSON except the page itself):

    GET  /                 the one page
    GET  /api/state        the whole snapshot (state.snapshot)
    POST /api/adopt        {"kind":"folder","path":...}  -> adopt in place
    POST /api/adopt-zip    raw zip bytes (?name=foo.zip) -> extract to the workspace
    POST /api/say          {"text": ...}                 -> one learner turn

`handle(app, method, path, body)` is pure Python and fully testable without a socket;
the HTTPRequestHandler is a thin shell over it, exactly like gateway.dispatch is to
make_db_tool. The UI holds NO state of its own: every response is read live off the DB.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from tutor import frontier
from tutor.db import DB
from . import runs, session, state
from .runner import Event, Runner, ScriptedRunner, default_script

PAGE = Path(__file__).resolve().parent / "app.html"
DEV_PAGE = Path(__file__).resolve().parent / "dev.html"


@dataclass
class App:
    """Everything one tutoring session needs. One App = one learner = one DB."""

    db: DB
    workspace: str
    runner: Runner = None                       # type: ignore[assignment]
    transcript: list[dict] = field(default_factory=list)
    running: str | None = None                  # the agent EXECUTING right now, or None
    model: str = ""                             # pinned agent model; "" = survey default
    trace: list = field(default_factory=list)   # operator record: every turn, verbatim
    _auto_done: set = field(default_factory=set)  # autowake one-shot tokens (loop guard)

    def __post_init__(self):
        if self.runner is None:
            self.runner = _pick_runner(self)
        # where specs + frontier.json live for this session; the ops read it from meta
        if self.db.path != ":memory:":
            self.db.meta_set("library_root", str(Path(self.db.path).resolve().parent / "library"))

    @property
    def library(self) -> Path:
        return Path(self.db.meta_get("library_root", "library"))

    def frontier_empty(self) -> bool:
        """The wakeup signal (Part C): no usable frontier = M/PLAN owes a turn.

        The FILE is the fact, not a flag we keep — the same rule the design gives. But a
        frontier naming a slice that no longer exists is not a lesson, it is debris: it
        once made the interface announce "L waiting for you" over a spine that had never
        been planned. A frontier counts only if its slice is still on the spine.
        """
        f = self.library / "frontier.json"
        if not f.exists():
            return True
        try:
            slug = json.loads(f.read_text())["slice"]["slug"]
        except (ValueError, KeyError, TypeError, OSError):
            return True
        return self.db.one("SELECT 1 FROM slices WHERE slug=?", (slug,)) is None

    def frontier_data(self) -> dict | None:
        """The published frontier, raw. None when there is none, or it is unusable.

        Reading it here and not in `state` is the same split `frontier_empty` already
        obeys: the App knows where the library lives, `state` stays pure and testable
        with a dict. A frontier that fails the schema is reported as absent — the UI
        must never render a half-filled handoff as if L could teach from it.
        """
        f = self.library / "frontier.json"
        if not f.exists():
            return None
        try:
            return frontier.load(f).data
        except (frontier.FrontierError, ValueError, OSError):
            return None

    def snapshot(self) -> dict:
        snap = state.snapshot(self.db, self.frontier_empty(), self.running,
                              self.frontier_data())
        snap["transcript"] = self.transcript
        snap["runner"] = self.runner.name
        snap["model"] = self.model or _default_model()
        snap["runs"] = runs.history(self.db)
        return snap

    def autowake(self) -> None:
        """Fire the owed agent turn WITHOUT waiting for a keystroke (Part C, live).

        Called on every state poll; a pure no-op unless an agent actually owes a turn:
          frontier empty + spine exists  -> M/PLAN plans the next slice, automatically
          frontier published, L silent   -> L opens: greets, frames the slice, asks
        Each wakeup fires ONCE per state (token set) so a failing turn can never loop.
        Only the live SDK runner autowakes — the scripted runner has nothing to say.
        """
        if self.running or not getattr(self.runner, "emit", None):
            return
        if not session.is_adopted(self.db):
            return
        if self.db.one("SELECT 1 FROM slices LIMIT 1") is None:
            return                                  # survey is a deliberate, manual act

        if self.frontier_empty():
            built = self.db.one("SELECT COUNT(*) AS c FROM slices WHERE state='BUILT'")["c"]
            token = f"plan:{built}"
            if token in self._auto_done:
                return
            self._auto_done.add(token)
            self.emit(Event("handoff", "Session open — no frontier published, so M/PLAN "
                                       "is waking automatically to plan the next slice.",
                            "system"))
            self._start("M/PLAN", self._run_plan)
            return

        data = self.frontier_data()
        if not data:
            return

        from tutor.routing_m import pick_m_turn
        if pick_m_turn(self.db, False, data) == "REGAP":
            gap = (data.get("gap") or {}).get("concept")
            token = f"regap:{data['slice']['slug']}:{gap}"
            if token in self._auto_done:
                return
            self._auto_done.add(token)
            self.emit(Event("handoff", f"Gap {gap} closed — M is aiming the next gap "
                                       f"on this slice.", "system"))
            self._start("M/REGAP", lambda: self._run_plan(frontier=data))
            return

        token = f"greet:{data['slice']['slug']}:{(data.get('gap') or {}).get('concept')}"
        if token in self._auto_done or self._l_spoke_since_handoff():
            return
        self._auto_done.add(token)
        opener = ("(session opened — the learner has not typed yet. Greet him first: in a "
                  "few short lines say what he is building and why (the why-this-slice), "
                  "where things stand, run any [REVIEW] block, then the current step. "
                  "Do not wait for him.)")
        self._start("L", lambda: self.runner.turn(opener))

    def _l_spoke_since_handoff(self) -> bool:
        """Has L already opened this frontier? Scan back to the last handoff marker."""
        for ev in reversed(self.transcript):
            if ev.get("kind") == "say" and ev.get("agent") == "L":
                return True
            if ev.get("kind") == "handoff":
                return False
        return bool(self.transcript)

    def _start(self, label: str, fn) -> None:
        def work():
            try:
                fn()
            finally:
                self.running = None
        self.running = label
        threading.Thread(target=work, daemon=True).start()

    def _run_plan(self, frontier: dict | None = None) -> None:
        from .plan import run_plan_sync
        run_plan_sync(self.db, self.emit, self.model or _default_model(),
                      self.trace, frontier)

    def emit(self, ev) -> None:
        """Append one event to the LEARNER's transcript.

        M's prose never arrives here — agentrun.drive() only forwards `say` events for
        learner-facing agents. What does arrive from an M turn is the handoff notice and
        the receipts, i.e. that it happened and what it changed. The full turn lives in
        `trace`.
        """
        self.transcript.append(ev.as_dict())


def _pick_runner(app: App):
    """The live L runner when the SDK is installed; the script otherwise.

    Never silent: which one is active is in every snapshot (`runner`), and the page
    prints it in the composer footer. Tests pass a runner explicitly, so this choice
    only governs a real `python -m ui` launch.
    """
    try:
        import claude_agent_sdk                                # noqa: F401
    except ImportError:
        return ScriptedRunner(app.db, default_script())
    from .runner import SdkRunner
    return SdkRunner(app.db, model=app.model, trace=app.trace, emit=app.emit)


def _default_model() -> str:
    """Read lazily so the module still imports with no SDK installed."""
    from .survey import DEFAULT_MODEL
    return DEFAULT_MODEL


@dataclass
class Response:
    status: int
    body: dict | bytes
    content_type: str = "application/json"


# --------------------------------------------------------------------------
# the pure router
# --------------------------------------------------------------------------
def handle(app: App, method: str, path: str, body: bytes = b"", query: dict | None = None) -> Response:
    query = query or {}

    if method == "GET" and path == "/":
        return Response(200, PAGE.read_bytes(), "text/html; charset=utf-8")

    if method == "GET" and path == "/api/state":
        app.autowake()                     # the poll IS the session-open signal
        return Response(200, app.snapshot())

    if method == "POST" and path == "/api/adopt":
        return _adopt(app, _json(body))

    if method == "POST" and path == "/api/adopt-zip":
        name = (query.get("name") or ["upload.zip"])[0]
        try:
            root = session.adopt_zip(app.db, body, app.workspace, name)
        except session.SessionError as e:
            return Response(400, {"error": str(e)})
        return Response(200, {"root": root, "state": app.snapshot()})

    if method == "POST" and path == "/api/say":
        return _say(app, _json(body))

    if method == "POST" and path == "/api/survey":
        return _survey(app)

    if method == "POST" and path == "/api/plan":
        return _plan(app)

    if method == "GET" and path == "/dev":
        return Response(200, DEV_PAGE.read_bytes(), "text/html; charset=utf-8")

    if method == "GET" and path == "/api/dev":
        # the operator's facts: EVERYTHING the learner page firewalls away.
        # Read-only, straight off the DB — no shaping, no redaction.
        return Response(200, {
            "active": state.who_is_active(app.db, app.frontier_empty(), app.running,
                                          app.frontier_data()),
            "probes": [dict(r) for r in app.db.query("SELECT * FROM probes ORDER BY id DESC")],
            "mappings": [dict(r) for r in app.db.query("SELECT * FROM mappings ORDER BY id DESC")],
            "vocab": [dict(r) for r in app.db.query("SELECT * FROM vocab ORDER BY term")],
            "gates": [dict(r) for r in app.db.query("SELECT * FROM gates ORDER BY rowid DESC")],
            "concepts": [dict(r) for r in app.db.query("SELECT * FROM concepts ORDER BY slug")],
            "slices": [dict(r) for r in app.db.query("SELECT * FROM slices ORDER BY ordinal")],
            "meta": [dict(r) for r in app.db.query("SELECT * FROM meta ORDER BY key")],
            "frontier": app.frontier_data(),
            "autowake_tokens": sorted(app._auto_done),
        })

    if method == "GET" and path == "/api/trace":
        # the operator record: every turn, verbatim. Kept out of /api/state because it
        # is large and the learner's page polls state every second while a turn runs.
        return Response(200, {"turns": [t.as_dict() for t in app.trace]})

    return Response(404, {"error": f"no route: {method} {path}"})


def _plan(app: App) -> Response:
    """Run one M/PLAN turn. Cold every time — that IS the F1 wipe for this agent."""
    if not session.is_adopted(app.db):
        return Response(409, {"error": "adopt a codebase first"})
    if app.running:
        return Response(409, {"error": f"{app.running} is already running"})
    if app.db.one("SELECT 1 FROM slices LIMIT 1") is None:
        return Response(409, {"error": "no spine yet — run the survey first"})

    from tutor.routing_m import pick_m_turn
    from .plan import run_plan_sync
    model = app.model or _default_model()
    data = app.frontier_data()
    regap = (data if not app.frontier_empty()
             and pick_m_turn(app.db, False, data) == "REGAP" else None)

    def work():
        try:
            run_plan_sync(app.db, app.emit, model, app.trace, regap)
        finally:
            app.running = None

    app.running = "M/REGAP" if regap else "M/PLAN"
    threading.Thread(target=work, daemon=True).start()
    return Response(200, {"started": True, "state": app.snapshot()})


def _survey(app: App) -> Response:
    """Launch M/SURVEY in a background thread; the page polls /api/state for the feed.

    A re-survey archives the current spine first, then clears it. Never a silent
    overwrite: the previous map stays on disk so two runs can be compared.
    """
    if not session.is_adopted(app.db):
        return Response(409, {"error": "adopt a codebase first"})
    if app.running:
        return Response(409, {"error": f"{app.running} is already running"})

    model = app.model or _default_model()
    if app.db.one("SELECT 1 FROM slices LIMIT 1"):
        try:
            saved = runs.archive(app.db, model)
        except runs.ArchiveError as e:
            return Response(409, {"error": str(e)})
        cleared = runs.reset_spine(app.db)
        app.emit(Event("handoff",
                       f"Previous spine archived to runs/{saved.name} "
                       f"({cleared['slices']} slices, {cleared['concepts']} concepts, "
                       f"{cleared['specs']} specs, {cleared['frontier']} frontier) "
                       f"and cleared. Starting a fresh survey.", "system"))

    from .survey import run_survey_sync

    def work():
        try:
            # emits as it streams, not at the end
            run_survey_sync(app.db, app.emit, app.model or _default_model(), app.trace)
        finally:
            app.running = None                  # the indicator must never stay stuck on

    app.running = "M/SURVEY"
    threading.Thread(target=work, daemon=True).start()
    return Response(200, {"started": True, "state": app.snapshot()})


def _adopt(app: App, payload: dict) -> Response:
    path = (payload.get("path") or "").strip()
    if not path:
        return Response(400, {"error": "a folder path is required"})
    try:
        root = session.adopt_folder(app.db, path)
    except session.SessionError as e:
        return Response(400, {"error": str(e)})
    return Response(200, {"root": root, "state": app.snapshot()})


def _say(app: App, payload: dict) -> Response:
    text = (payload.get("text") or "").strip()
    if not text:
        return Response(400, {"error": "say something first"})
    if not session.is_adopted(app.db):
        return Response(409, {"error": "adopt a codebase before starting"})
    if app.running:
        return Response(409, {"error": f"{app.running} is already running"})
    app.transcript.append({"kind": "learner", "text": text, "agent": "you"})

    # A live L turn runs like the M turns: background thread, `running` set, events
    # streamed straight into the transcript by the runner's emit sink while the page
    # polls. The scripted runner has no sink and stays synchronous.
    if getattr(app.runner, "emit", None):
        def work():
            try:
                app.runner.turn(text)
            finally:
                app.running = None
        app.running = "L"
        threading.Thread(target=work, daemon=True).start()
        return Response(200, {"started": True, "state": app.snapshot()})

    for ev in app.runner.turn(text):
        app.transcript.append(ev.as_dict())
    return Response(200, {"state": app.snapshot()})


def _json(body: bytes) -> dict:
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


# --------------------------------------------------------------------------
# the socket shell
# --------------------------------------------------------------------------
def serve(app: App, port: int = 8765) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _run(self, method: str):
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            r = handle(app, method, parsed.path, body, parse_qs(parsed.query))
            payload = r.body if isinstance(r.body, bytes) else json.dumps(r.body).encode()
            self.send_response(r.status)
            self.send_header("Content-Type", r.content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self._run("GET")

        def do_POST(self):
            self._run("POST")

        def log_message(self, *a):
            pass                                # the terminal stays quiet

    print(f"tutor  →  http://127.0.0.1:{port}   (ctrl-c to stop)")
    # threading: an agent turn runs on a worker thread while the page keeps polling
    # /api/state for its output. A single-threaded server would block the whole feed.
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
