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

from tutor.db import DB
from . import runs, session, state
from .runner import Event, Runner, ScriptedRunner, default_script

PAGE = Path(__file__).resolve().parent / "app.html"


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

    def __post_init__(self):
        if self.runner is None:
            self.runner = ScriptedRunner(self.db, default_script())
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

    def snapshot(self) -> dict:
        snap = state.snapshot(self.db, self.frontier_empty(), self.running)
        snap["transcript"] = self.transcript
        snap["runner"] = self.runner.name
        snap["model"] = self.model or _default_model()
        snap["runs"] = runs.history(self.db)
        return snap

    def emit(self, ev) -> None:
        """Append one event to the LEARNER's transcript.

        M's prose never arrives here — agentrun.drive() only forwards `say` events for
        learner-facing agents. What does arrive from an M turn is the handoff notice and
        the receipts, i.e. that it happened and what it changed. The full turn lives in
        `trace`.
        """
        self.transcript.append(ev.as_dict())


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

    from .plan import run_plan_sync
    model = app.model or _default_model()

    def work():
        try:
            run_plan_sync(app.db, app.emit, model, app.trace)
        finally:
            app.running = None

    app.running = "M/PLAN"
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
    app.transcript.append({"kind": "learner", "text": text, "agent": "you"})
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
