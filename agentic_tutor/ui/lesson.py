"""lesson — one L turn: the tutor answers the learner (build order steps 4 + 6).

This is the piece the docs call "L alone, driven through the ContextManager"
(tutor-sdk-mapping.md §5 step 4) plus the slice-level orchestration around it
(step 6). The design decisions are all inherited, not invented here:

  history    WE own it (§3). A `ContextManager("L")` per slice; every model call is
             stateless — cm.render() IS the prompt. F1: a new slice drops the old
             manager. F2: build_l_block(is_first_turn) picks opening vs continue.
             F7: cm.collapse() swaps finished db() runs for their receipts.
  frontier   L teaches ONLY what library/frontier.json says (G1 rule 2). No usable
             frontier = L has nothing to teach; that is an error event, not a guess.
  vocab      seed_vocab() plants the frontier's lists at slice start (code's job,
             never L's); from then on the TABLE is the truth.
  gate wall  make_hooks(db) — PreToolUse denies spec-read / target-write while a
             gate is OPEN. The one interception that must be an SDK hook.
  rollover   code does it, never an agent: when the slice comes back BUILT, the
             frontier is archived and removed, which is exactly the wakeup signal
             that makes M/PLAN owe the next turn.
"""
from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Callable

from tutor.context_manager import ContextManager, Turn
from tutor.db import DB
from tutor.frontier import Frontier, FrontierError, load as load_frontier
from tutor.library import seed_vocab
from tutor.routing import build_l_block

from .agentrun import cost_line, drive
from .runner import Event
from .survey import DEFAULT_MODEL, SurveyError
from .trace import TurnTrace

MAX_LESSON_TURNS = 30

# L's constant core (MAP.md v2). Deliberately short: everything situational is
# rented context — the STEP block, the menu, post-commit steering. Only laws that
# hold on EVERY turn live here.
L_CORE = """You are the tutor — the only agent the learner sees. Code routes the
learning map; you judge quality. You never decide what comes next — your db() rows do.

1. The [STEP] block below is your only working orders. Do exactly that step —
   never the next one, never your own curriculum. Every judged answer becomes
   a db row IN THE SAME TURN; a step without its row did not happen.
2. He attempts before you explain. Before any code of his runs, his PREDICTION
   is on the table; reality vs prediction is the lesson, and HE reconciles it.
3. Never write, complete, or fix his code beyond what the step explicitly allows.
4. Vocabulary door: never use a HELD term. If HE uses one, probe the behavior
   it names before promoting the word.
5. If a supposedly-owned prerequisite is failing: db raise_subhole and HOLD —
   do not answer him until the frontier updates.
6. While a [GATE] block is present: he writes the target file himself, spec
   hidden, your hands off. He produces, or it did not happen.
7. Bookkeeping is invisible: pushes, probes, levels, step names, HIT/MISS never
   appear in the chat. He sees the journey — what he builds, why, what is next.
8. No praise without evidence. Short, direct. Name gaps he cannot see."""


class LessonError(SurveyError):
    """This L turn could not run. History and the frontier are unchanged."""


def load_current_frontier(db: DB) -> Frontier:
    """The published handoff, or a refusal that names whose turn it actually is."""
    path = Path(db.meta_get("library_root", "library")) / "frontier.json"
    if not path.exists():
        raise LessonError("no frontier published — M/PLAN owes a turn before L can teach")
    try:
        return load_frontier(path)
    except (FrontierError, ValueError) as e:
        raise LessonError(f"the published frontier is unusable ({e}) — re-run M/PLAN") from e


def tools_block(db: DB) -> str:
    """Pre-seeded menu: L never spends turns discovering its own API."""
    from tutor.operations import menu_for
    lines = ["[TOOLS] db() ops live now (args, * = required; check=true = validate only):"]
    for op in menu_for(db, "L"):
        args = ", ".join(f + ("*" if f in op.required else "") for f in op.schema)
        lines.append(f"  {op.name}({args}) — {op.summary}")
    return "\n".join(lines)


def lesson_prompt(db: DB, cm: ContextManager, frontier: Frontier,
                  learner_text: str) -> str:
    """Append his message, collapse, render. Pure — testable without the SDK.

    The routing block is injected HERE by render(), not by a UserPromptSubmit hook:
    we own history, so injection is a rendering concern (tutor-sdk-mapping.md §3).
    First turn of a session additionally carries ⓪: due reviews + his last session
    note; every turn carries the step block and the live op menu.
    """
    # F2 is decided BEFORE his message lands: this UI's turn 1 begins with the
    # learner speaking, so appending first would make every turn a continue turn.
    first = cm.is_first_turn
    cm.append_learner(learner_text)
    cm.collapse()
    parts = []
    if first:
        from tutor.routing import review_block
        note = db.meta_get("last_session_note", "")
        if note:
            parts.append(f"[LAST SESSION — his own summary] {note}")
        rb = review_block(db)
        if rb:
            parts.append(rb)
    parts.append(build_l_block(db, frontier, first))
    parts.append(tools_block(db))
    block = "\n\n".join(parts)
    return cm.render(opening_block=block, continue_block=block)


async def run_lesson(db: DB, cm: ContextManager, learner_text: str,
                     emit: Callable[[Event], None],
                     model: str = DEFAULT_MODEL, trace: list | None = None) -> None:
    try:
        from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server
    except ImportError as e:
        raise LessonError(
            "claude-agent-sdk is not installed in the interpreter running the server. "
            "Install it (pip install claude-agent-sdk) and restart.") from e

    frontier = load_current_frontier(db)
    prompt = lesson_prompt(db, cm, frontier, learner_text)

    tr = TurnTrace(
        agent="L", model=model, system_prompt=L_CORE, first_message=prompt,
        tools_allowed=["db", "Read", "Grep", "Glob"],
        context_note="Orchestrator-owned history: this prompt IS ContextManager.render() "
                     "— the collapsed slice history plus the routed frontier block. The "
                     "model call itself is stateless; F1 wipes at the slice boundary.")
    if trace is not None:
        trace.append(tr)

    from tutor.gateway import make_db_tool
    from tutor.hooks import make_hooks

    def on_commit(r: str) -> None:
        cm.append(Turn("receipt", f"✓ {r}"))
        tr.receipt(r)
        emit(Event("receipt", r, "L"))

    server = create_sdk_mcp_server("tutor", tools=[make_db_tool(db, "L", on_commit=on_commit)])
    root = db.one("SELECT codebase_path FROM target WHERE id=1")
    options = ClaudeAgentOptions(
        system_prompt=L_CORE,
        allowed_tools=["mcp__tutor__db", "Read", "Grep", "Glob"],
        setting_sources=[],                        # never inherit the host project
        disallowed_tools=["Bash", "Skill", "Task", "Agent", "Write", "Edit",
                          "MultiEdit", "NotebookEdit", "SlashCommand",
                          "WebFetch", "WebSearch"],
        mcp_servers={"tutor": server},
        hooks=make_hooks(db),                      # the gate wall, live mid-turn
        permission_mode="acceptEdits",
        max_turns=MAX_LESSON_TURNS,
        cwd=root["codebase_path"] if root else None,
        model=model,
    )

    def see(ev: Event) -> None:
        if ev.kind == "say":                       # his tutor's words are history too
            cm.append_assistant(ev.text)
        emit(ev)

    result = await drive("L", prompt, options, see, tr)
    tr.finish(cost_line(result) or "L turn finished")
    _rollover_if_built(db, frontier, emit)


def run_lesson_sync(db: DB, cm: ContextManager, learner_text: str,
                    emit: Callable[[Event], None],
                    model: str = DEFAULT_MODEL, trace: list | None = None) -> None:
    try:
        asyncio.run(run_lesson(db, cm, learner_text, emit, model, trace))
    except LessonError as e:
        emit(Event("error", str(e), "L"))
    except Exception as e:                                   # surface, never swallow
        emit(Event("error", f"lesson turn failed: {type(e).__name__}: {e}", "L"))


def _rollover_if_built(db: DB, frontier: Frontier, emit: Callable[[Event], None]) -> None:
    """CODE does the rollover, never an agent (Part C lifecycle).

    When pass_gate marked the slice BUILT, archive the spent frontier and remove it.
    Its absence IS the wakeup signal that makes M/PLAN owe the next planning turn.
    """
    row = db.one("SELECT state FROM slices WHERE slug=?", (frontier.slice_slug,))
    if not row or row["state"] != "BUILT":
        return
    lib = Path(db.meta_get("library_root", "library"))
    src = lib / "frontier.json"
    if src.exists():
        dest = lib / "archive"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest / f"frontier-{frontier.slice_slug}.json"))
    emit(Event("handoff",
               f"Slice {frontier.slice_slug} is BUILT — frontier archived. "
               f"M/PLAN owes the next planning turn.", "system"))
