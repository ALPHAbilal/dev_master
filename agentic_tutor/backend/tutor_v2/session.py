"""The runnable session layer: wires real agent calls to the orchestrator.

This is the missing entrypoint that turns the composed engine + orchestrator into
something you can actually run. It builds the scoped wakeup for each step, invokes the
agent through a single seam, and forwards the returned text to the orchestrator. It adds
no learning logic: it chooses no verdict, no route, and no next step — it only sequences
existing operations and moves model text across the boundary.

The agent seam is a plain callable ``(wakeup, instruction) -> AgentOutput | list[str]``. In
production ``agent_run_from_adapter`` wraps ``ClaudeAgentAdapter.run`` (async) into that shape;
in tests a deterministic fake is passed, so the session is fully runnable without the SDK. A
seam that returns a bare ``list[str]`` is normalized to ``AgentOutput(blocks, [])``, so every
legacy fake keeps working. Tool calls returned alongside the text are captured best-effort
via ``TurnOrchestrator.record_tool_calls``; a capture failure never fails the turn.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .aside_instructions import build_aside_instruction
from .config import TutorConfig
from .contracts import WAKEUP_AGENTS
from .domain import AgentOutput
from .errors import ValidationError
from .orchestrator import AsideResult, TurnOrchestrator, TurnResult
from .packets import WakeupBuilder
from .routing import RouteDecision
from .sdk_runtime import ClaudeAgentAdapter

_logger = logging.getLogger(__name__)

AgentRun = Callable[[dict[str, Any], str], "AgentOutput | list[str]"]

# Minimal non-empty per-agent instruction placeholders. Real deployments pass the
# authored agent role prompts; the session only requires each to be non-blank.
DEFAULT_INSTRUCTIONS: dict[str, str] = {
    "wakeup.map": "You are the MAPPER. Return exactly one return.map JSON object.",
    "wakeup.probe": "You are the TEACHER. Ask one probing question for the active axis.",
    "wakeup.teach": "You are the TEACHER. Explain the active axis concisely.",
    "wakeup.test": "You are the TEACHER. Pose one harder proof task for the active axis.",
    "wakeup.grade": (
        "You are the JUDGE. Return exactly one return.grade JSON object. When the category "
        "emits a map node (correct-deep, working-code-wrong-reasoning, misconception, "
        "different-prereq, sibling-hole), include map_text:{title,summary} naming the concept "
        "the verdict establishes; otherwise map_text:null."
    ),
    "wakeup.distill": "You are the DISTILLER. Return exactly one return.distill JSON object.",
}


def agent_run_from_adapter(adapter: ClaudeAgentAdapter) -> AgentRun:
    """Adapt the async ``ClaudeAgentAdapter.run`` into the synchronous session seam."""
    def run(wakeup: dict[str, Any], instruction: str) -> AgentOutput:
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
        output = self._invoke("wakeup.map", wakeup)
        result = self.orchestrator.commit_map(output.blocks)
        # No journey existed yet, so capture lands after commit, keyed to the created journey.
        self._record_tools(result.journey_id, None, "map:0", "wakeup.map", output)
        return result

    # -- teaching / questioning (non-graded) --------------------------------------

    def run_question(
        self, *, journey_id: int, unit_id: int, axis: str, turn_id: str,
        step: str = "wakeup.probe", save_resume_question: bool = False,
    ) -> str:
        """Run TEACHER for a probe/test and record its text as the turn's question."""
        if step not in {"wakeup.probe", "wakeup.test"}:
            raise ValidationError("run_question is for probe/test steps only")
        wakeup = self.wakeups.build(step=step, unit_id=unit_id, axis=axis)
        output = self._invoke(step, wakeup)
        question = self._join(output.blocks)
        self.orchestrator.present_question(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id,
            question=question, step=step, save_resume_question=save_resume_question,
        )
        self._record_tools(journey_id, unit_id, turn_id, step, output)
        return question

    def run_teaching(self, *, journey_id: int, unit_id: int, axis: str, turn_id: str) -> list[int]:
        wakeup = self.wakeups.build(step="wakeup.teach", unit_id=unit_id, axis=axis)
        output = self._invoke("wakeup.teach", wakeup)
        result = self.orchestrator.present_teaching(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id, blocks=output.blocks)
        self._record_tools(journey_id, unit_id, turn_id, "wakeup.teach", output)
        return result

    # -- grading (atomic) ---------------------------------------------------------

    def run_grade(
        self, *, journey_id: int, unit_id: int, axis: str, turn_id: str, question: str,
        answer: str, step: str = "probe", refs: Any = None,
    ) -> TurnResult:
        # A graded answer may carry highlight pins as additional evidence for the JUDGE.
        # They are validated up front, ride in the grade packet's current_evidence, and are
        # stored on the durable answer message — the verdict/route/probe schema is unchanged.
        normalized = self.orchestrator.references.validate(refs, journey_id=journey_id)
        transient: dict[str, Any] = {"learner_answer": answer}
        if normalized:
            transient["refs"] = normalized
        wakeup = self.wakeups.build(
            step="wakeup.grade", unit_id=unit_id, axis=axis, transient=transient,
        )
        output = self._invoke("wakeup.grade", wakeup)
        result = self.orchestrator.submit_answer(
            journey_id=journey_id, unit_id=unit_id, axis=axis, turn_id=turn_id,
            question=question, answer=answer, grade_blocks=output.blocks, step=step,
            refs=normalized,
        )
        self._record_tools(journey_id, unit_id, turn_id, "wakeup.grade", output)
        return result

    # -- distill (agent call, then seal) ------------------------------------------

    def run_distill(self, *, unit_id: int, axis: str | None = None) -> TurnResult:
        """Run the DISTILLER for a finished unit and commit its sealed proof.

        The Router's all-solid exit carries ``axis=None`` (distill is not axis-scoped, and the
        DISTILLER's capabilities do not include axis evidence); a fatigue-switch exit carries
        the current axis. Either way the wakeup packet still needs some firing axis to build its
        context, so a representative one is resolved when the caller does not supply it.
        """
        resolved_axis = axis or self._representative_axis(unit_id)
        wakeup = self.wakeups.build(step="wakeup.distill", unit_id=unit_id, axis=resolved_axis)
        output = self._invoke("wakeup.distill", wakeup)
        journey_id = self.orchestrator.journeys.journey_for_unit(unit_id)
        self._record_tools(journey_id, unit_id, f"distill:{unit_id}", "wakeup.distill", output)
        return self.orchestrator.commit_distill(output.blocks, unit_id=unit_id)

    def _representative_axis(self, unit_id: int) -> str:
        row = self.orchestrator.db.one(
            "SELECT axis FROM axes WHERE unit_id=? ORDER BY ordinal LIMIT 1", (unit_id,)
        )
        if not row:
            raise ValidationError("cannot distill a unit that has no axes")
        return str(row["axis"])

    # -- aside (off-record side question; never grades or advances) ----------------

    def run_aside(
        self, *, journey_id: int, unit_id: int, request_id: str, question: str,
        refs: Any = None, thread_id: str | None = None, origin_message_id: int | None = None,
    ) -> AsideResult:
        """Record the off-record question, run the ASIDE agent, and record its reply.

        Idempotent by ``request_id``: a completed turn short-circuits with no agent call; a
        durable PENDING turn (e.g. a prior invocation crashed) is safely re-run. The agent's
        prose reply is recorded inertly — it is never parsed for a verdict or a route.
        """
        begin = self.orchestrator.begin_aside(
            journey_id=journey_id, unit_id=unit_id, request_id=request_id, question=question,
            refs=refs, thread_id=thread_id, origin_message_id=origin_message_id)
        if begin.status == "COMPLETE":
            return begin
        packet = self.wakeups.build_aside(journey_id=journey_id, request_id=begin.request_id)
        instruction = build_aside_instruction(list(packet["context"]["unit"]["axes"]))
        output = self._invoke_with("wakeup.aside", packet, instruction)
        result = self.orchestrator.commit_aside(
            journey_id=journey_id, request_id=request_id, aside_blocks=output.blocks)
        self._record_tools(journey_id, unit_id, f"aside:{request_id}", "wakeup.aside", output)
        return result

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

    def _invoke(self, step: str, wakeup: dict[str, Any]) -> AgentOutput:
        return self._invoke_with(step, wakeup, self.instructions.get(step, ""))

    def _invoke_with(self, step: str, wakeup: dict[str, Any], instruction: str) -> AgentOutput:
        """Invoke the agent seam with an explicit instruction (aside assembles its own)."""
        if not instruction.strip():
            raise ValidationError(f"no agent instruction configured for {step}")
        result = self.agent_run(wakeup, instruction)
        if isinstance(result, list):  # legacy fakes return bare text blocks
            result = AgentOutput(result, [])
        if (not isinstance(result, AgentOutput)
                or any(not isinstance(item, str) for item in result.blocks)):
            raise ValidationError("agent runner must return text blocks (list or AgentOutput)")
        return result

    def _record_tools(self, journey_id: int, unit_id: int | None, turn_id: str,
                      step: str, output: AgentOutput) -> None:
        """Best-effort tool-call capture: a failure to record must never fail the turn."""
        if not output.tool_calls:
            return
        try:
            self.orchestrator.record_tool_calls(
                journey_id=journey_id, unit_id=unit_id, turn_id=turn_id, step=step,
                agent=WAKEUP_AGENTS[step], tool_calls=output.tool_calls)
        except Exception:  # observability, never authority
            _logger.warning("tool-call capture failed for turn %s", turn_id, exc_info=True)

    @staticmethod
    def _join(blocks: list[str]) -> str:
        joined = "\n\n".join(block.strip() for block in blocks if block.strip())
        if not joined:
            raise ValidationError("agent produced no question text")
        return joined
