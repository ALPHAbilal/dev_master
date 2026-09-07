"""FastAPI surface: the URL the React client on Vercel hits.

This is a thin translation of :class:`ApiHandlers` into HTTP — every route unpacks a request,
calls exactly one handler, and returns its ``dict``. No learning logic lives here; the handler
(and the engine beneath it) owns all of that. Kept deliberately separate from ``api.py`` so the
package never hard-depends on FastAPI: import this module only from the server entrypoint. It
runs on a persistent host (see the plan's Deployment Topology), never as a Vercel function,
because the engine is stateful (SQLite + workspace files + long agent turns).
"""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from .api import ApiHandlers
from .errors import (
    CapabilityUnavailableError, InvariantError, StaleWorkspaceRevisionError, ValidationError,
)
from .factory import AppContext
from .registry import ControlPlane
from .auth import AuthenticationError, IdentityVerifier, verifier_from_env
from .streaming import SSE_HEADERS, ScanLog, journey_events, scan_events


class InitBody(BaseModel):
    target: str
    document_id: str
    display_name: str
    language: str


class AnswerBody(BaseModel):
    turn_id: str
    unit_id: int
    axis: str
    question: str
    answer: str
    refs: list[dict[str, Any]] | None = None


class AsideBody(BaseModel):
    model_config = {"extra": "forbid"}  # strict: an unknown field is a 400, not silently dropped
    request_id: str
    unit_id: int
    question: str = ""
    refs: list[dict[str, Any]] | None = None
    thread_id: str | None = None
    origin_message_id: int | None = None


class ParkBody(BaseModel):
    unit_id: int


class WorkspaceBody(BaseModel):
    expected_revision: int
    content: str


class CodebaseBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str
    source: str


@dataclass
class SessionSurface:
    context: AppContext
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    scan: ScanLog = field(default_factory=ScanLog)


# Client errors (bad input / stale revision) map to 4xx; the engine's invariant failures are
# server bugs and surface as 500 via the default handler.
_CLIENT_ERRORS = (ValidationError, StaleWorkspaceRevisionError, CapabilityUnavailableError)


def create_app(control_plane: ControlPlane, *, verifier: IdentityVerifier | None = None,
               allow_origins: list[str] | None = None, stream_interval: float = 0.25,
               source_root: Path | None = None) -> FastAPI:
    """Authenticate each request and resolve its isolated session above the engine.

    One persistent process owns this pool. Writes serialize per session, while other
    tenants and SSE reads continue. Reusing contexts also preserves the driver's counter.
    """
    identity_verifier = verifier or verifier_from_env()
    sessions: dict[tuple[str, str], SessionSurface] = {}
    resolver_lock = asyncio.Lock()
    interval = max(0.02, stream_interval)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for surface in sessions.values():
            surface.context.db.close()

    app = FastAPI(title="tutor_v2", version="1.0", lifespan=lifespan)
    app.state.sessions = sessions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins if allow_origins is not None else [
            value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if value.strip()],
        allow_methods=["*"], allow_headers=["*"],
    )

    def _guard(call) -> Any:
        try:
            return call()
        except _CLIENT_ERRORS as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except InvariantError as exc:
            # An invariant breach is a server-side contract violation, not a bad request.
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    async def identity(authorization: str | None = Header(default=None),
                       x_user_id: str | None = Header(default=None)) -> str:
        try:
            return await run_in_threadpool(identity_verifier.verify, authorization, x_user_id)
        except AuthenticationError as exc:
            raise HTTPException(401, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc

    def owned_context(user_id: str, codebase_id: str) -> AppContext:
        registry = control_plane.registry()
        try:
            row = registry.get_codebase(codebase_id=codebase_id)
            if row is None or row["user_id"] != user_id:
                raise HTTPException(404, "Codebase not found")
        finally:
            registry.db.close()
        ctx = control_plane.open(user_id=user_id, codebase_id=codebase_id)
        # Restore the existing driver's monotonic counter at the composition boundary.
        # No minting/routing/grading logic is replaced; all writes still use ApiHandlers.
        rows = ctx.db.query("SELECT turn_id FROM conversation_messages WHERE journey_id IN "
                            "(SELECT id FROM journeys WHERE session_id=?)", (ctx.config.session_id,))
        ctx.driver._turn_seq = max((int(r["turn_id"][5:]) for r in rows
                                   if r["turn_id"].startswith("turn-") and r["turn_id"][5:].isdigit()), default=0)
        return ctx

    async def resolve(user_id: str, codebase_id: str) -> SessionSurface:
        async with resolver_lock:
            key = (user_id, codebase_id)
            if key not in sessions:
                ctx = await run_in_threadpool(lambda: _guard(lambda: owned_context(user_id, codebase_id)))
                sessions[key] = SessionSurface(ctx)
            return sessions[key]

    async def selected(user_id: str = Depends(identity),
                       x_codebase_id: str | None = Header(default=None)) -> SessionSurface:
        if not x_codebase_id:
            raise HTTPException(400, "X-Codebase-Id is required for session and journey routes")
        return await resolve(user_id, x_codebase_id)

    def require_journey(surface: SessionSurface, journey_id: int, unit_id: int | None = None) -> None:
        ctx = surface.context
        row = ctx.db.one("SELECT root_unit_id FROM journeys WHERE id=? AND session_id=?",
                         (journey_id, ctx.config.session_id))
        if not row:
            raise HTTPException(404, "Journey not found")
        if unit_id is not None:
            found = ctx.db.one(
                "WITH RECURSIVE tree(id) AS (SELECT ? UNION SELECT u.id FROM units u JOIN tree t "
                "ON u.parent_id=t.id WHERE u.session_id=?) SELECT id FROM tree WHERE id=?",
                (row["root_unit_id"], ctx.config.session_id, unit_id))
            if not found:
                raise HTTPException(404, "Unit not found in this journey")

    async def write(surface: SessionSurface, fn: Callable[[], Any], journey_id: int | None = None,
                    unit_id: int | None = None) -> Any:
        async with surface.write_lock:
            def invoke():
                if journey_id is not None:
                    require_journey(surface, journey_id, unit_id)
                return _guard(fn)
            # Await completion even after disconnect: don't release the session's write
            # lock while a synchronous model call is still mutating its engine context.
            task = asyncio.create_task(run_in_threadpool(invoke))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                finally:
                    raise

    @app.post("/codebases")
    async def create_codebase(body: CodebaseBody, user_id: str = Depends(identity)) -> dict[str, Any]:
        root = Path(body.source).expanduser().resolve()
        if not root.is_dir():
            raise HTTPException(400, "source must be a directory on the backend host")
        if source_root is not None and not root.is_relative_to(source_root.resolve()):
            raise HTTPException(400, "source must be inside CODEBASE_ROOT")
        async with resolver_lock:
            cid = await run_in_threadpool(lambda: _guard(lambda: control_plane.create_codebase(
                user_id=user_id, name=body.name, root_path=str(root))))
        return {"codebase_id": cid, "name": body.name}

    @app.get("/codebases")
    async def list_codebases(user_id: str = Depends(identity)) -> list[dict[str, Any]]:
        rows = await run_in_threadpool(lambda: _guard(lambda: control_plane.list_codebases(user_id=user_id)))
        return [{key: row[key] for key in ("id", "name", "session_id", "unit_count")} for row in rows]

    @app.post("/codebases/{codebase_id}/open")
    async def open_codebase(codebase_id: str, user_id: str = Depends(identity)) -> dict[str, str]:
        surface = await resolve(user_id, codebase_id)
        return {"session_id": surface.context.config.session_id}

    @app.post("/session")
    async def init_session(body: InitBody, surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        return await write(surface, lambda: ApiHandlers(surface.context).init_session(**body.model_dump()))

    @app.post("/session/map")
    async def start_map(surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        # Publish progress around the unchanged synchronous operation. Unit records are
        # read only after commit; no simulated model tokens or engine callbacks.
        if surface.scan.running or surface.write_lock.locked():
            raise HTTPException(409, "Session has a write in progress")
        surface.scan.begin()
        try:
            result = await write(surface, ApiHandlers(surface.context).start_map)
            rows = await run_in_threadpool(surface.context.db.query,
                "SELECT slug,file,lo,hi FROM units WHERE session_id=? ORDER BY ordinal,id",
                (surface.context.config.session_id,))
            surface.scan.publish("thinking", {"text": "Mapping committed; preparing lesson…"})
            for row in rows:
                surface.scan.publish("unit", row)
            surface.scan.publish("done", {"journey_id": result["journey_id"]})
            return result
        except BaseException:
            surface.scan.publish("thinking", {"text": "Scan failed; retry the request."})
            raise
        finally:
            surface.scan.running = False

    @app.get("/session/map/stream")
    async def map_stream(request: Request, surface: SessionSurface = Depends(selected)):
        return StreamingResponse(scan_events(request, surface.scan, interval),
                                 media_type="text/event-stream", headers=SSE_HEADERS)

    @app.get("/journey/{journey_id}/stream")
    async def journey_stream(journey_id: int, request: Request,
                             surface: SessionSurface = Depends(selected)):
        await run_in_threadpool(require_journey, surface, journey_id)
        return StreamingResponse(journey_events(request, surface.context, journey_id, interval),
                                 media_type="text/event-stream", headers=SSE_HEADERS)

    @app.get("/journey/{journey_id}")
    async def poll(journey_id: int, since: int | None = None,
                   surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        def read():
            require_journey(surface, journey_id)
            return _guard(lambda: ApiHandlers(surface.context).poll(journey_id, since_revision=since))
        return await run_in_threadpool(read)

    @app.post("/journey/{journey_id}/answer")
    async def answer(journey_id: int, body: AnswerBody,
                     surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        return await write(surface, lambda: ApiHandlers(surface.context).answer(journey_id, **body.model_dump()),
                           journey_id, body.unit_id)

    @app.post("/journey/{journey_id}/aside")
    async def aside(journey_id: int, body: AsideBody,
                    surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        return await write(surface, lambda: ApiHandlers(surface.context).aside(journey_id, **body.model_dump()),
                           journey_id, body.unit_id)

    @app.post("/journey/{journey_id}/park")
    async def park(journey_id: int, body: ParkBody,
                   surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        return await write(surface, lambda: ApiHandlers(surface.context).park(journey_id, unit_id=body.unit_id),
                           journey_id, body.unit_id)

    @app.post("/session/resume")
    async def resume(surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        return await write(surface, ApiHandlers(surface.context).resume)

    @app.post("/workspace")
    async def workspace_write(body: WorkspaceBody,
                              surface: SessionSurface = Depends(selected)) -> dict[str, Any]:
        return await write(surface, lambda: ApiHandlers(surface.context).workspace_write(**body.model_dump()))

    return app
