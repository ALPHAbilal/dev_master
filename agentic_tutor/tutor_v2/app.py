"""FastAPI surface: the URL the React client on Vercel hits.

This is a thin translation of :class:`ApiHandlers` into HTTP — every route unpacks a request,
calls exactly one handler, and returns its ``dict``. No learning logic lives here; the handler
(and the engine beneath it) owns all of that. Kept deliberately separate from ``api.py`` so the
package never hard-depends on FastAPI: import this module only from the server entrypoint. It
runs on a persistent host (see the plan's Deployment Topology), never as a Vercel function,
because the engine is stateful (SQLite + workspace files + long agent turns).
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .api import ApiHandlers
from .errors import (
    CapabilityUnavailableError, InvariantError, StaleWorkspaceRevisionError, ValidationError,
)
from .factory import AppContext


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


class ParkBody(BaseModel):
    unit_id: int


class WorkspaceBody(BaseModel):
    expected_revision: int
    content: str


# Client errors (bad input / stale revision) map to 4xx; the engine's invariant failures are
# server bugs and surface as 500 via the default handler.
_CLIENT_ERRORS = (ValidationError, StaleWorkspaceRevisionError, CapabilityUnavailableError)


def create_app(context: AppContext, *, allow_origins: list[str] | None = None) -> FastAPI:
    """Build the FastAPI app over a wired session. Pure HTTP translation of ApiHandlers."""
    handlers = ApiHandlers(context)
    app = FastAPI(title="tutor_v2", version="1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["*"],
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

    @app.post("/session")
    def init_session(body: InitBody) -> dict[str, Any]:
        return _guard(lambda: handlers.init_session(**body.model_dump()))

    @app.post("/session/map")
    def start_map() -> dict[str, Any]:
        return _guard(handlers.start_map)

    @app.get("/journey/{journey_id}")
    def poll(journey_id: int, since: int | None = None) -> dict[str, Any]:
        return _guard(lambda: handlers.poll(journey_id, since_revision=since))

    @app.post("/journey/{journey_id}/answer")
    def answer(journey_id: int, body: AnswerBody) -> dict[str, Any]:
        return _guard(lambda: handlers.answer(journey_id, **body.model_dump()))

    @app.post("/journey/{journey_id}/park")
    def park(journey_id: int, body: ParkBody) -> dict[str, Any]:
        return _guard(lambda: handlers.park(journey_id, unit_id=body.unit_id))

    @app.post("/session/resume")
    def resume() -> dict[str, Any]:
        return _guard(handlers.resume)

    @app.post("/workspace")
    def workspace_write(body: WorkspaceBody) -> dict[str, Any]:
        return _guard(lambda: handlers.workspace_write(**body.model_dump()))

    return app
