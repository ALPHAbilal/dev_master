"""agentrun — the one place a model is actually driven.

Both M turns (and L, when it lands) go through `drive()`. It owns the stream loop so
every agent is observed identically: the same trace record, the same separation between
what the learner sees and what the operator sees.

The split it enforces:

    trace   gets EVERYTHING, verbatim — prompt, tools, args, results, prose.
    emit    gets only what belongs in the LEARNER's transcript. For M that is nothing
            but a one-line notice, because M never talks to the learner. For L it is
            the actual teaching.

That rule lives here rather than in each runner, so a new agent cannot forget it.
"""
from __future__ import annotations

from typing import Callable

from .runner import Event
from .trace import TurnTrace

# agents whose prose the learner may read. M is invisible by design.
LEARNER_FACING = {"L"}


async def drive(agent: str, prompt: str, options, emit: Callable[[Event], None],
                tr: TurnTrace) -> object | None:
    """Run one agent turn to completion. Returns the SDK ResultMessage, if any."""
    from claude_agent_sdk import (AssistantMessage, TextBlock, ToolUseBlock, UserMessage,
                                  ToolResultBlock, ResultMessage, query)

    visible = agent in LEARNER_FACING
    last_result = None

    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    tr.text(block.text.strip())
                    if visible:
                        emit(Event("say", block.text.strip(), agent))
                elif isinstance(block, ToolUseBlock):
                    tr.tool(_short(getattr(block, "name", "?")),
                            getattr(block, "input", {}) or {})
        elif isinstance(msg, UserMessage):
            for block in getattr(msg, "content", []) or []:
                if isinstance(block, ToolResultBlock):
                    tr.result(_text_of(block))
        elif isinstance(msg, ResultMessage):
            last_result = msg
    return last_result


def _short(name: str) -> str:
    return name.replace("mcp__tutor__", "")


def _text_of(block) -> str:
    c = getattr(block, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
    return str(c or "")


def cost_line(msg) -> str:
    """Formats the CLI's own accounting. We do not compute cost."""
    if msg is None:
        return ""
    bits = []
    cost = getattr(msg, "total_cost_usd", None)
    if isinstance(cost, (int, float)):
        bits.append(f"${cost:.3f} (CLI-reported)")
    turns = getattr(msg, "num_turns", None)
    if isinstance(turns, int):
        bits.append(f"{turns} turns")
    return " · ".join(bits)
