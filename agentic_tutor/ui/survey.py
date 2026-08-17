"""survey — actually RUN M/SURVEY. The first live agent turn in the system.

This is where the design stops being pure functions and talks to a model. It is
deliberately the smallest possible loop:

    system prompt = routing_m.M_CORE + build_m_block(db, "SURVEY", root)
    tools         = routing_m.tools_for_turn("SURVEY") + the one db() gateway
    cwd           = the adopted codebase, so Read/Grep land on the target repo
    then          = drain the stream, turning each message into a UI Event

Everything the agent is allowed to do is decided by code it cannot see: the injected
block, the role-filtered menu (`dispatch(db, "M", ...)` never exposes L's ops), and
the gate wall. The model chooses only WHAT to write, never WHETHER it may.

`run_survey` is async and streams; `run_survey_sync` wraps it for the plain HTTP
server. The SDK import is lazy so the package still loads (and tests still run)
on a machine with no SDK.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Iterator

from tutor.db import DB
from tutor.gateway import dispatch
from tutor.routing_m import M_CORE, build_m_block, tools_for_turn

from .runner import Event
from .session import current_root

MAX_TURNS = 60          # a survey that needs more than this has lost the plot


class SurveyError(Exception):
    """The survey could not run. The spine is unchanged."""


def survey_prompt(db: DB) -> tuple[str, str]:
    """(system_prompt, first_message) — pure, testable without the SDK."""
    root = current_root(db)
    if not root:
        raise SurveyError("no codebase adopted yet")
    if db.one("SELECT 1 FROM slices LIMIT 1"):
        raise SurveyError("this codebase is already surveyed; a re-survey is a spine repair")
    system = M_CORE + "\n\n" + build_m_block(db, "SURVEY", root)
    first = ("Survey this codebase now, following the [SURVEY] block exactly. "
             "Grep to locate, Read only what Grep proved matters, then write the "
             "spine through db(). Leave every spec_path NULL.")
    return system, first


async def run_survey(db: DB, emit: Callable[[Event], None]) -> None:
    """Run the one survey turn, emitting UI Events as it goes."""
    try:
        from claude_agent_sdk import (ClaudeAgentOptions, AssistantMessage, TextBlock,
                                      ToolUseBlock, ResultMessage, query,
                                      create_sdk_mcp_server)
    except ImportError as e:
        raise SurveyError(
            "claude-agent-sdk is not installed in the interpreter running the server. "
            "Install it (pip install claude-agent-sdk) and restart.") from e

    system, first = survey_prompt(db)
    root = current_root(db)

    from tutor.gateway import make_db_tool
    db_tool = make_db_tool(db, "M", on_commit=lambda r: emit(Event("receipt", r, "M/SURVEY")))
    server = create_sdk_mcp_server("tutor", tools=[db_tool])

    options = ClaudeAgentOptions(
        system_prompt=system,
        cwd=root,                                   # Read/Grep land on the TARGET repo
        allowed_tools=list(tools_for_turn("SURVEY")) + ["mcp__tutor__db"],
        mcp_servers={"tutor": server},
        permission_mode="acceptEdits",
        max_turns=MAX_TURNS,
    )

    emit(Event("handoff", f"M/SURVEY started on {root}", "M/SURVEY"))
    async for msg in query(prompt=first, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    emit(Event("say", block.text.strip(), "M/SURVEY"))
                elif isinstance(block, ToolUseBlock):
                    emit(Event("tool", _describe_tool(block), "M/SURVEY"))
        elif isinstance(msg, ResultMessage):
            emit(Event("handoff", _result_line(db, msg), "M/SURVEY"))


def run_survey_sync(db: DB) -> list[Event]:
    """Blocking wrapper for the plain HTTP server. Returns everything emitted."""
    events: list[Event] = []
    try:
        asyncio.run(run_survey(db, events.append))
    except SurveyError as e:
        events.append(Event("error", str(e), "M/SURVEY"))
    except Exception as e:                                   # surface, never swallow
        events.append(Event("error", f"survey failed: {type(e).__name__}: {e}", "M/SURVEY"))
    return events


# --------------------------------------------------------------------------
# rendering the stream for a human
# --------------------------------------------------------------------------
def _describe_tool(block) -> str:
    """One readable line per tool call — this IS the feedback the screen was missing."""
    name = getattr(block, "name", "?").replace("mcp__tutor__", "")
    a = getattr(block, "input", {}) or {}
    if name == "Grep":
        return f"grep  {a.get('pattern','?')}" + (f"  in {a['path']}" if a.get("path") else "")
    if name == "Read":
        return f"read  {a.get('file_path','?')}"
    if name == "db":
        op = a.get("op")
        return f"db()  {op or 'menu'}" + (f"  {a['args'].get('slug','')}" if a.get("args") else "")
    if name in ("WebSearch", "WebFetch"):
        return f"web   {a.get('query') or a.get('url','?')}"
    return f"{name}  {str(a)[:80]}"


def _result_line(db: DB, msg) -> str:
    n_slices = len(db.query("SELECT 1 FROM slices"))
    n_concepts = len(db.query("SELECT 1 FROM concepts"))
    cost = getattr(msg, "total_cost_usd", None)
    tail = f"  (${cost:.3f})" if isinstance(cost, (int, float)) else ""
    return (f"M/SURVEY finished: {n_slices} slices, {n_concepts} concepts on the spine. "
            f"Specs stay unwritten until M/PLAN reaches each slice.{tail}")
