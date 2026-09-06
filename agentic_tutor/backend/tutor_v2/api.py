"""Framework-neutral request handlers over a wired :class:`AppContext`.

Each handler wraps exactly one existing engine call (plus, for the write paths, the
:class:`TurnDriver` that already advances the loop) and returns a plain JSON-able ``dict``.
It adds no learning logic: it validates nothing the engine does not already validate, chooses
no verdict/route/axis, and mints no ids the driver does not already mint. It is the seam the
HTTP layer (``app.py``, FastAPI) is a thin translation of — and, crucially, the seam the tests
drive in-process without any network stack.

Contract with the client (the React app): every *write* returns the current ``DriverState``
(what to render: a live question, a parked journey, or a completed ladder) **plus** the
``projection_revision`` it should poll ``GET /journey/{id}`` from. The client echoes the
driver-minted ``turn_id`` back on the matching answer so probe and grade pair up.
"""
from __future__ import annotations

from typing import Any

from .driver import DriverState
from .factory import AppContext


class ApiHandlers:
    """Thin, framework-neutral wrappers around the wired session graph."""

    def __init__(self, context: AppContext) -> None:
        self.ctx = context

    # -- session setup ------------------------------------------------------------

    def init_session(self, *, target: str, document_id: str, display_name: str,
                     language: str) -> dict[str, Any]:
        """Initialize the learner-visible workspace for the file about to be taught."""
        workspace = self.ctx.workspace.initialize(
            target=target, document_id=document_id, display_name=display_name, language=language)
        return {"document_id": workspace.document_id, "display_name": workspace.display_name,
                "workspace_revision": workspace.revision}

    # -- write paths (each returns DriverState + projection_revision) --------------

    def start_map(self) -> dict[str, Any]:
        """Run the MAPPER, then advance to the first learner question."""
        mapped = self.ctx.session.run_mapping()
        state = self.ctx.driver.advance(journey_id=mapped.journey_id, decision=mapped.decision)
        return self._state_payload(state)

    def answer(self, journey_id: int, *, turn_id: str, unit_id: int, axis: str,
               question: str, answer: str, refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Grade one learner answer (with any attached highlight pins), then advance."""
        graded = self.ctx.session.run_grade(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id,
            question=question, answer=answer, refs=refs)
        state = self.ctx.driver.advance(journey_id=journey_id, decision=graded.decision)
        return self._state_payload(state)

    def aside(self, journey_id: int, *, request_id: str, unit_id: int, question: str,
              refs: list[dict[str, Any]] | None = None, thread_id: str | None = None,
              origin_message_id: int | None = None) -> dict[str, Any]:
        """Answer one off-record side question. Returns an aside acknowledgment — NOT a
        DriverState — so the client's live lesson state is left untouched."""
        result = self.ctx.session.run_aside(
            journey_id=journey_id, unit_id=unit_id, request_id=request_id, question=question,
            refs=refs, thread_id=thread_id, origin_message_id=origin_message_id)
        return {"operation": "aside", "journey_id": result.journey_id,
                "thread_id": result.thread_id, "request_id": result.request_id,
                "status": result.status.lower(), "learner_message_id": result.learner_message_id,
                "reply_message_id": result.reply_message_id,
                "projection_revision": result.projection_revision}

    def resume(self) -> dict[str, Any]:
        """Restore a parked journey, then advance to its resumed question."""
        resumed = self.ctx.session.resume()
        state = self.ctx.driver.advance(journey_id=resumed.journey_id, decision=resumed.decision)
        return self._state_payload(state)

    def park(self, journey_id: int, *, unit_id: int) -> dict[str, Any]:
        """Park the live stack; the journey pauses until ``resume``."""
        result = self.ctx.session.park(unit_id=unit_id)
        return {"status": "parked", "journey_id": result.journey_id,
                "projection_revision": result.projection_revision,
                "reason": "journey parked; resume to continue"}

    def workspace_write(self, *, expected_revision: int, content: str) -> dict[str, Any]:
        """Apply one optimistic-concurrency guarded learner edit to the workspace."""
        write = self.ctx.workspace.write(expected_revision=expected_revision, content=content)
        return {"changed": write.changed, "workspace_revision": write.workspace.revision,
                "revision_hash": write.workspace.revision_hash}

    # -- read path ----------------------------------------------------------------

    def poll(self, journey_id: int, *, since_revision: int | None = None) -> dict[str, Any]:
        """Revision-gated read; returns a fresh snapshot only when something changed."""
        update = self.ctx.feed.poll(journey_id, since_revision=since_revision)
        return {"journey_id": update.journey_id, "changed": update.changed,
                "revision": update.revision, "snapshot": update.snapshot}

    # -- shaping ------------------------------------------------------------------

    @staticmethod
    def _state_payload(state: DriverState) -> dict[str, Any]:
        return {
            "status": state.status, "journey_id": state.journey_id,
            "projection_revision": state.projection_revision, "turn_id": state.turn_id,
            "unit_id": state.unit_id, "axis": state.axis, "question": state.question,
            "step": state.step, "highlight": state.highlight,
            "resume_question": state.resume_question, "reason": state.reason,
        }
