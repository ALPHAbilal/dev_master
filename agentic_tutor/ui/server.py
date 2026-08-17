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
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from tutor.db import DB
from . import session, state
from .runner import Runner, ScriptedRunner, default_script

PAGE = Path(__file__).resolve().parent / "app.html"


@dataclass
class App:
    """Everything one tutoring session needs. One App = one learner = one DB."""

    db: DB
    workspace: str
    runner: Runner = None                       # type: ignore[assignment]
    transcript: list[dict] = field(default_factory=list)
    running: str | None = None                  # the agent EXECUTING right now, or None

    def __post_init__(self):
        if self.runner is None:
            self.runner = ScriptedRunner(self.db, default_script())

    def snapshot(self) -> dict:
        snap = state.snapshot(self.db, self.runner.frontier_empty(), self.running)
        snap["transcript"] = self.transcript
        snap["runner"] = self.runner.name
        return snap

    def emit(self, ev) -> None:
        """Append one agent event. The page polls, so this is the live feed."""
        self.transcript.append(ev.as_dict())


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

    return Response(404, {"error": f"no route: {method} {path}"})


def _survey(app: App) -> Response:
    """Launch M/SURVEY in a background thread; the page polls /api/state for the feed."""
    if not session.is_adopted(app.db):
        return Response(409, {"error": "adopt a codebase first"})
    if app.running:
        return Response(409, {"error": f"{app.running} is already running"})

    from .survey import run_survey_sync

    def work():
        try:
            for ev in run_survey_sync(app.db):
                app.emit(ev)
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
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
