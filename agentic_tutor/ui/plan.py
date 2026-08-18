"""plan — run M/PLAN, the per-slice planning turn.

Same agent as M/SURVEY, same gateway, same three-step menu. Only three things differ,
and each is a deliberate consequence of the design:

  injected   [EVIDENCE] + [OVERLAYS] instead of [SURVEY] — M/PLAN reads what the
             learner actually did, not the codebase. No [TOOL DISCIPLINE]: this turn
             has no repo tools to discipline.
  tools      db() ONLY. It writes the spec through `write_spec` (file + spec_path in
             one act) and publishes through `write_frontier` (schema-gated). It gets
             no Read/Grep — the map is already drawn and re-reading the repo here is
             how a planner drifts into surveying.
  context    NONE. M/PLAN wakes cold every slice (F1). A fresh stateless query() per
             invocation IS that wipe — there is no history to manage, so wiring a
             ContextManager here would be ceremony, not fidelity.

Its output is two files: `library/slices/<slug>.md` and `library/frontier.json`.
Until the frontier exists, L has nothing to teach.
"""
from __future__ import annotations

import asyncio
import json
from typing import Callable

from tutor.db import DB
from tutor.routing_m import M_CORE, build_m_block, mark_probes_seen
from tutor.frontier import empty_template

from .agentrun import cost_line, drive
from .runner import Event
from .survey import DEFAULT_MODEL, SurveyError
from .trace import TurnTrace

MAX_PLAN_TURNS = 40


class PlanError(SurveyError):
    """The planning turn could not run. The frontier is unchanged."""


def regap_prompt(db: DB, frontier: dict) -> tuple[str, str]:
    """(system, first) for M/REGAP: same slice, next gap. Pure, testable."""
    sl = frontier.get("slice") or {}
    unowned = [p for p in sl.get("concept_prereqs") or []
               if not (r := db.one("SELECT state FROM concepts WHERE slug=?", (p,)))
               or r["state"] != "OWNED"]
    if not unowned:
        raise PlanError("REGAP called but every prereq is owned — the gate should open instead")
    system = M_CORE + "\n\n" + build_m_block(db, "REGAP")
    first = (
        f"The gap `{(frontier.get('gap') or {}).get('concept')}` on slice `{sl.get('slug')}` "
        f"just CLOSED, but the slice still has unowned prereqs: {', '.join(unowned)}.\n\n"
        "One act: db(op=\"write_frontier\") — republish the frontier with the SAME slice "
        "block, untouched, and a NEW gap block for ONE of those prereqs (the evidence above "
        "tells you which road and size fit him now). Fill every gap key. Do not touch the "
        "spec. Then stop.\n\nUse this exact shape:\n\n"
        + json.dumps(empty_template(sl.get("slug", "")), indent=2)
    )
    return system, first


def plan_prompt(db: DB) -> tuple[str, str]:
    """(system_prompt, first_message) — pure, testable without the SDK."""
    if db.one("SELECT 1 FROM slices LIMIT 1") is None:
        raise PlanError("no spine yet — run the survey before planning a slice")
    target = _next_slice(db)
    if not target:
        raise PlanError("every slice is BUILT — there is nothing left to plan")

    system = M_CORE + "\n\n" + build_m_block(db, "PLAN")
    first = (
        "Plan exactly one slice now — the earliest one not yet BUILT.\n\n"
        f"That slice is `{target['slug']}` ({target['title']}), which the learner will "
        f"write into {target['target_file']}.\n"
        f"Its concept prereqs: {', '.join(_prereqs(target)) or '(none)'}.\n\n"
        "Two acts, in this order:\n"
        "1. db(op=\"write_spec\", args={slice_slug, body}) — the spec HE reads: what the "
        "function must do, its inputs and outputs, the edge cases that matter. Describe "
        "the behaviour, never the implementation. No code he could copy.\n"
        "2. db(op=\"write_frontier\", args={frontier}) — the handoff L teaches from. "
        "Fill EVERY key; the schema refuses a partial frontier. Use this exact shape:\n\n"
        + json.dumps(empty_template(target["slug"]), indent=2) +
        "\n\nThen stop. One slice, then observe. Do not plan the slice after this one."
    )
    return system, first


async def run_plan(db: DB, emit: Callable[[Event], None],
                   model: str = DEFAULT_MODEL, trace: list | None = None,
                   frontier: dict | None = None) -> None:
    try:
        from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server
    except ImportError as e:
        raise PlanError(
            "claude-agent-sdk is not installed in the interpreter running the server. "
            "Install it (pip install claude-agent-sdk) and restart.") from e

    # frontier given = REGAP (same slice, next gap); absent = PLAN (next slice)
    system, first = regap_prompt(db, frontier) if frontier else plan_prompt(db)
    label = "M/REGAP" if frontier else "M/PLAN"
    tr = TurnTrace(
        agent=label, model=model, system_prompt=system, first_message=first,
        tools_allowed=["db"],
        context_note="Cold. M/PLAN wakes with no memory of the last slice (F1). Its only "
                     "inputs are the [EVIDENCE] probe rows and [OVERLAYS] above — a fresh "
                     "stateless call IS the wipe, so no ContextManager is involved.")
    if trace is not None:
        trace.append(tr)

    from tutor.gateway import make_db_tool

    def on_commit(r: str) -> None:
        tr.receipt(r)
        emit(Event("receipt", r, label))

    db_tool = make_db_tool(db, "M", on_commit=on_commit)
    server = create_sdk_mcp_server("tutor", tools=[db_tool])

    options = ClaudeAgentOptions(
        system_prompt=system,
        allowed_tools=["mcp__tutor__db"],          # db() only — no repo tools this turn
        setting_sources=[],                        # never inherit the host project
        disallowed_tools=["Bash", "Skill", "Task", "Agent", "Write", "Edit",
                          "MultiEdit", "NotebookEdit", "SlashCommand", "Read", "Grep"],
        mcp_servers={"tutor": server},
        permission_mode="acceptEdits",
        max_turns=MAX_PLAN_TURNS,
        model=model,
    )

    emit(Event("handoff", f"{label} started  ·  model: {model}", label))
    result = await drive(label, first, options, emit, tr)
    line = _result_line(db, result)
    tr.finish(line)
    emit(Event("handoff", line, label))
    mark_probes_seen(db)                           # this turn has consumed the evidence


def run_plan_sync(db: DB, emit: Callable[[Event], None],
                  model: str = DEFAULT_MODEL, trace: list | None = None,
                  frontier: dict | None = None) -> None:
    try:
        asyncio.run(run_plan(db, emit, model, trace, frontier))
    except PlanError as e:
        emit(Event("error", str(e), "M/PLAN"))
    except Exception as e:                                   # surface, never swallow
        emit(Event("error", f"planning failed: {type(e).__name__}: {e}", "M/PLAN"))


# --------------------------------------------------------------------------
def _next_slice(db: DB) -> dict | None:
    """The earliest slice not yet BUILT. READY first, then LOCKED by ordinal.

    A LOCKED slice is normal here: nothing is OWNED before the first lesson, so on a
    fresh spine every slice is LOCKED and slice 1 is still the right thing to plan.
    """
    return db.one("SELECT * FROM slices WHERE state != 'BUILT' "
                  "ORDER BY (state='READY') DESC, COALESCE(ordinal, 999), slug LIMIT 1")


def _prereqs(row: dict) -> list:
    try:
        v = json.loads(row["concept_prereqs"]) if row["concept_prereqs"] else []
    except (ValueError, TypeError):
        return []
    return v if isinstance(v, list) else []


def _result_line(db: DB, msg) -> str:
    from pathlib import Path
    root = Path(db.meta_get("library_root", "library"))
    published = (root / "frontier.json").exists()
    bits = ["M/PLAN finished — frontier published; L can teach this slice." if published
            else "M/PLAN ended WITHOUT publishing a frontier — L still has nothing to "
                 "teach. Run it again; the spec it wrote is kept."]
    if cost_line(msg):
        bits.append(cost_line(msg))
    return "  ·  ".join(bits)
