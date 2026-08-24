"""The runnable session layer: wires real agent calls to the orchestrator.

This is the missing entrypoint that turns the composed engine + orchestrator into
something you can actually run. It builds the scoped wakeup for each step, invokes the
agent through a single seam, and forwards the returned text to the orchestrator. It adds
no learning logic: it chooses no verdict, no route, and no next step — it only sequences
existing operations and moves model text across the boundary.

The agent seam is a plain callable ``(wakeup, instruction) -> list[str]``. In production
``agent_run_from_adapter`` wraps ``ClaudeAgentAdapter.run`` (async) into that shape; in
tests a deterministic fake is passed, so the session is fully runnable without the SDK.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from .config import TutorConfig
from .errors import ValidationError
from .orchestrator import TurnOrchestrator, TurnResult
from .packets import WakeupBuilder
from .routing import RouteDecision
from .sdk_runtime import ClaudeAgentAdapter

AgentRun = Callable[[dict[str, Any], str], list[str]]

# Minimal non-empty per-agent instruction placeholders. Real deployments pass the
# authored agent role prompts; the session only requires each to be non-blank.
DEFAULT_INSTRUCTIONS: dict[str, str] = {
    "wakeup.map": "You are the MAPPER. Return exactly one return.map JSON object.",
    "wakeup.probe": "You are the TEACHER. Ask one probing question for the active axis.",
    "wakeup.teach": "You are the TEACHER. Explain the active axis concisely.",
    "wakeup.test": "You are the TEACHER. Pose one harder proof task for the active axis.",
    "wakeup.grade": "You are the JUDGE. Return exactly one return.grade JSON object.",
    "wakeup.distill": "You are the DISTILLER. Return exactly one return.distill JSON object.",
}


def agent_run_from_adapter(adapter: ClaudeAgentAdapter) -> AgentRun:
    """Adapt the async ``ClaudeAgentAdapter.run`` into the synchronous session seam."""
    def run(wakeup: dict[str, Any], instruction: str) -> list[str]:
        return asyncio.run(adapter.run(wakeup, instruction))
    return run


class SessionRunner:
    """Runs full turns: build wakeup → invoke agent → forward to the orchestrator."""

    def __init__(
        self,
        config: TutorConfig,
        wakeups: WakeupBuilder,
        orchestrator: TurnOrchestrator,
        agent_run: AgentRun,
        *,
        instructions: dict[str, str] | None = None,
    ) -> None:
        self.config = config
        self.wakeups = wakeups
        self.orchestrator = orchestrator
        self.agent_run = agent_run
        self.instructions = {**DEFAULT_INSTRUCTIONS, **(instructions or {})}

    # -- mapping ------------------------------------------------------------------

    def run_mapping(self) -> TurnResult:
        wakeup = self.wakeups.build(step="wakeup.map")
        blocks = self._invoke("wakeup.map", wakeup)
        return self.orchestrator.commit_map(blocks)

    # -- teaching / questioning (non-graded) --------------------------------------

    def run_question(
        self, *, journey_id: int, unit_id: int, axis: str, turn_id: str,
        step: str = "wakeup.probe", save_resume_question: bool = False,
    ) -> str:
        """Run TEACHER for a probe/test and record its text as the turn's question."""
        if step not in {"wakeup.probe", "wakeup.test"}:
            raise ValidationError("run_question is for probe/test steps only")
        wakeup = self.wakeups.build(step=step, unit_id=unit_id, axis=axis)
        blocks = self._invoke(step, wakeup)
        question = self._join(blocks)
        self.orchestrator.present_question(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id,
            question=question, step=step, save_resume_question=save_resume_question,
        )
        return question

    def run_teaching(self, *, journey_id: int, unit_id: int, axis: str, turn_id: str) -> list[int]:
        wakeup = self.wakeups.build(step="wakeup.teach", unit_id=unit_id, axis=axis)
        blocks = self._invoke("wakeup.teach", wakeup)
        return self.orchestrator.present_teaching(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id, blocks=blocks)

    # -- grading (atomic) ---------------------------------------------------------

    def run_grade(
        self, *, journey_id: int, unit_id: int, axis: str, turn_id: str, question: str,
        answer: str, step: str = "probe",
    ) -> TurnResult:
        wakeup = self.wakeups.build(
            step="wakeup.grade", unit_id=unit_id, axis=axis,
            transient={"learner_answer": answer},
        )
        blocks = self._invoke("wakeup.grade", wakeup)
        return self.orchestrator.submit_answer(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id,
            question=question, answer=answer, grade_blocks=blocks, step=step,
        )

    # -- lifecycle pass-throughs (no agent call) ----------------------------------

    def finish_child(self, *, child_unit_id: int) -> TurnResult:
        return self.orchestrator.finish_child(child_unit_id=child_unit_id)

    def finish_root(self, *, root_unit_id: int) -> TurnResult:
        return self.orchestrator.finish_root(root_unit_id=root_unit_id)

    def park(self, *, unit_id: int) -> TurnResult:
        return self.orchestrator.park(unit_id=unit_id)

    def resume(self) -> TurnResult:
        return self.orchestrator.resume()

    # -- internals ----------------------------------------------------------------

    def _invoke(self, step: str, wakeup: dict[str, Any]) -> list[str]:
        instruction = self.instructions.get(step, "")
        if not instruction.strip():
            raise ValidationError(f"no agent instruction configured for {step}")
        blocks = self.agent_run(wakeup, instruction)
        if not isinstance(blocks, list) or any(not isinstance(item, str) for item in blocks):
            raise ValidationError("agent runner must return a list of text blocks")
        return blocks

    @staticmethod
    def _join(blocks: list[str]) -> str:
        joined = "\n\n".join(block.strip() for block in blocks if block.strip())
        if not joined:
            raise ValidationError("agent produced no question text")
        return joined
