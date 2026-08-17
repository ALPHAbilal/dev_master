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

from .agentrun import cost_line, drive
from .runner import Event
from .session import current_root
from .trace import TurnTrace

MAX_TURNS = 60          # a survey that needs more than this has lost the plot

# Pinned, never inherited. An unpinned turn runs on whatever the CLI defaults to that
# day, so two surveys of the same repo are not comparable — and per the design doc
# M/SURVEY is "the turn whose errors cost the most". Pin it, print it, change it here.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class SurveyError(Exception):
    """The survey could not run. The spine is unchanged."""


def survey_prompt(db: DB) -> tuple[str, str]:
    """(system_prompt, first_message) — pure, testable without the SDK."""
    root = current_root(db)
    if not root:
        raise SurveyError("no codebase adopted yet")
    if db.one("SELECT 1 FROM slices LIMIT 1"):
        # The caller archives and clears before re-surveying (see server._survey), so a
        # spine still standing here means that step was skipped.
        raise SurveyError("a spine already exists — archive and clear it before "
                          "re-surveying, or the two maps will be merged")
    system = M_CORE + "\n\n" + build_m_block(db, "SURVEY", root)
    first = ("Survey this codebase now, following the [SURVEY] block exactly. "
             "Grep to locate, Read only what Grep proved matters, then write the "
             "spine through db(). Leave every spec_path NULL.")
    return system, first


async def run_survey(db: DB, emit: Callable[[Event], None],
                     model: str = DEFAULT_MODEL, trace: list | None = None) -> None:
    """Run the one survey turn, emitting UI Events as it goes."""
    try:
        from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server
    except ImportError as e:
        raise SurveyError(
            "claude-agent-sdk is not installed in the interpreter running the server. "
            "Install it (pip install claude-agent-sdk) and restart.") from e

    system, first = survey_prompt(db)
    root = current_root(db)
    tr = TurnTrace(
        agent="M/SURVEY", model=model, system_prompt=system, first_message=first,
        tools_allowed=list(tools_for_turn("SURVEY")) + ["db"],
        context_note="Cold. One-shot turn — the survey runs once per codebase and "
                     "keeps no history (F1 is trivial here: there is no prior turn).")
    if trace is not None:
        trace.append(tr)

    from tutor.gateway import make_db_tool

    def on_commit(r: str) -> None:
        tr.receipt(r)
        emit(Event("receipt", r, "M/SURVEY"))

    db_tool = make_db_tool(db, "M", on_commit=on_commit)
    server = create_sdk_mcp_server("tutor", tools=[db_tool])

    options = ClaudeAgentOptions(
        system_prompt=system,
        cwd=root,                                   # Read/Grep land on the TARGET repo
        allowed_tools=list(tools_for_turn("SURVEY")) + ["mcp__tutor__db"],
        # allowed_tools alone does NOT contain the agent: without this it inherits the
        # HOST project's settings — its CLAUDE.md, its skills, its permissions — and
        # will happily run Bash or invoke a local skill. M/SURVEY must see only the
        # target codebase and the block we injected, so load no settings at all and
        # name the escape hatches explicitly.
        setting_sources=[],
        disallowed_tools=["Bash", "Skill", "Task", "Agent", "Write", "Edit",
                          "MultiEdit", "NotebookEdit", "SlashCommand"],
        mcp_servers={"tutor": server},
        permission_mode="acceptEdits",
        max_turns=MAX_TURNS,
        model=model,
    )

    emit(Event("handoff", f"M/SURVEY started on {root}  ·  model: {model}", "M/SURVEY"))
    result = await drive("M/SURVEY", first, options, emit, tr)
    line = _result_line(db, result)
    tr.finish(line)
    emit(Event("handoff", line, "M/SURVEY"))


def run_survey_sync(db: DB, emit: Callable[[Event], None],
                    model: str = DEFAULT_MODEL, trace: list | None = None) -> None:
    """Blocking wrapper for the plain HTTP server.

    `emit` is called DURING the run, not after it. Buffering the events and returning
    them at the end leaves the screen empty for the whole survey, which is the same
    "nothing is happening" problem the status field exists to prevent.
    """
    try:
        asyncio.run(run_survey(db, emit, model, trace))
    except SurveyError as e:
        emit(Event("error", str(e), "M/SURVEY"))
    except Exception as e:                                   # surface, never swallow
        emit(Event("error", f"survey failed: {type(e).__name__}: {e}", "M/SURVEY"))


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
    bits = [f"M/SURVEY finished: {n_slices} slices, {n_concepts} concepts on the spine.",
            "Specs stay unwritten until M/PLAN reaches each slice."]
    # cost/turns come from the CLI's own accounting; we only format them
    if cost_line(msg):
        bits.append(cost_line(msg))
    return "  ·  ".join(bits)
