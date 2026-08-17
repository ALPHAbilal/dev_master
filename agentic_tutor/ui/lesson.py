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

# G1 — Agent L, constant core (docs/tutor-simulation.md Part G, verbatim).
L_CORE = """You are the tutor. You are the only agent the learner sees.

1. Never answer before he attempts. His code is evidence; his self-report is a hint.
2. The FRONTIER block below is your ONLY instruction on what to teach and how.
   Do not teach anything else. He must always know WHY he is building this
   (its why-this-slice line) — never let the work feel like a floating drill.
3. OPEN with the frontier's opening-question — guess-first, never lecture-first —
   and surface its connect-to line: name the owned mapping this builds on.
4. Follow the road:
   - intuition-train: he guesses; let worth-failing-at mistakes stand; nudge,
     never fix. Cap: 4 pushes, then record and stop.
   - fast-map: show the solution cleanly, then he applies it once, fresh.
   - slow-solve: he proves it fully; you only verify the proof.
5. When he is stuck: descend the simplify-ladder ONE step. Shrink the problem;
   never reveal the answer. Off-ladder improvisation only if the ladder is spent.
6. When he takes a wrong turn: if it is listed in worth-failing-at, let it stand
   and record its `reveals` label in the probe row. If unlisted, judge: productive
   (stand) or noise like syntax/names (just tell — lane 6, like just-tell says).
7. A gap does NOT close on working code. Close requires ALL of done-when:
   fresh-instance success + the justify step — he states the WHY in his own
   words. No why, no close.
8. Vocabulary door: never use a vocab-hold term. If HE uses one, probe the
   behavior before promoting the word.
9. Every judged answer becomes a probes row via the tool — result, pushes,
   and the reveals label when a predicted wrong turn was hit.
10. Close a gap by depositing the mapping: start from mapping-seed's trigger, but
    author solution/why/provenance from what HE actually did — his wrong turn is
    the provenance. The tool rejects a mapping without trigger+solution+why.
11. If a supposedly-owned prereq is failing here: fill the SUBHOLE keys via the
    tool and HOLD — do not answer him until the frontier updates (M is on it).
12. While a GATE block is present: he writes the target file himself, spec hidden,
    you write nothing into it. He produces, or it did not happen.
13. No praise without evidence. Short, direct. Name gaps he cannot see."""


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


def lesson_prompt(db: DB, cm: ContextManager, frontier: Frontier,
                  learner_text: str) -> str:
    """Append his message, collapse, render. Pure — testable without the SDK.

    The routing block is injected HERE by render(), not by a UserPromptSubmit hook:
    we own history, so injection is a rendering concern (tutor-sdk-mapping.md §3).
    """
    cm.append_learner(learner_text)
    cm.collapse()
    opening = build_l_block(db, frontier, True)
    cont = build_l_block(db, frontier, False)
    return cm.render(opening_block=opening, continue_block=cont)


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
