"""routing — the deterministic context router (docs/tutor-simulation.md Part E).

Two pure functions, both `state -> text-or-nothing`:

  build_l_block(db, frontier, is_first_turn)  -> the block injected into L's prompt.
      ALWAYS: the active slice + vocab lists.
      CONDITIONAL: the GATE-WALL notice (only while a gate is OPEN),
                   the TEACHING block (only while the gap is unclosed),
                   the SUBHOLE-HOLD notice (only while a subhole is unresolved).
      F2: the teaching block opens with the opening-question on turn 1, and switches
          to a continue framing (done-when + road + ladder) afterwards.
      NEVER: other slices, other concepts, the full bank, table dumps.

  gate_wall_decision(db, tool_name, tool_input) -> ('allow'|'deny', reason)
      While a gate is OPEN: deny reading the spec file and deny writing the target file.

Every block is a pure function of state; empty => omitted. No LLM decides routing.
"""
from __future__ import annotations

import json

from .db import DB
from .frontier import Frontier

# tools that touch files — the gate wall inspects these
_READ_TOOLS = {"Read", "Grep", "Glob"}
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


# --------------------------------------------------------------------------
# the L routing block (injected by ContextManager.render — we own history, so
# this is NOT a UserPromptSubmit hook; see tutor-sdk-mapping.md §3)
# --------------------------------------------------------------------------
def build_l_block(db: DB, frontier: Frontier, is_first_turn: bool) -> str:
    parts: list[str] = [_slice_block(frontier)]

    if frontier.has_subhole:                       # F4: hold until M re-plans
        parts.append(_subhole_hold_block(frontier))
        return "\n\n".join(p for p in parts if p)

    gate = _open_gate_for(db, frontier.slice_slug)
    if gate:                                        # the wall is live -> gate framing only
        parts.append(_gate_block(frontier, gate))
        return "\n\n".join(p for p in parts if p)

    gap = frontier.gap
    if gap and not _concept_owned(db, gap["concept"]):
        parts.append(_teaching_block(gap, is_first_turn))

    parts.append(_vocab_block(db, gap))
    return "\n\n".join(p for p in parts if p)


def _slice_block(f: Frontier) -> str:
    sl = f.slice
    lines = ["[SLICE] " + sl["slug"],
             f"  building: {sl['target_file']}",
             f"  spec: {sl['spec']}"]
    if sl.get("why_this_slice"):
        lines.append(f"  why this slice: {sl['why_this_slice']}")
    return "\n".join(lines)


def _teaching_block(gap: dict, is_first_turn: bool) -> str:
    lines = [f"[GAP] {gap['concept']}  (road: {gap['road']})"]
    if is_first_turn:
        lines.append(f"  OPEN WITH (guess-first): {gap['opening_question']}")
        if gap.get("connect_to"):
            lines.append(f"  connect to owned: {_join(gap['connect_to'])}")
    else:
        lines.append(f"  done-when: {gap['done_when']}")
        lines.append(f"  road reminder: {_road_hint(gap['road'])}")
        if gap.get("simplify_ladder"):
            lines.append(f"  if stuck, descend ONE step: {_join(gap['simplify_ladder'])}")
    if gap.get("worth_failing_at"):
        lines.append("  let-stand + record `reveals`: " + _wfa(gap["worth_failing_at"]))
    if gap.get("just_tell"):
        lines.append(f"  just tell (lane 6): {gap['just_tell']}")
    lines.append(f"  justify (hard close): {gap['justify']}")
    lines.append(f"  mapping seed: {gap['mapping_seed']}")
    return "\n".join(lines)


def _gate_block(f: Frontier, gate: dict) -> str:
    return ("[GATE — OPEN] the wall is live.\n"
            f"  he writes {f.target_file} himself; spec is hidden; you write nothing into it.\n"
            f"  when it is in the file, judge it and pass_gate (or fail_gate).")


def _subhole_hold_block(f: Frontier) -> str:
    sh = f.subhole
    return ("[SUBHOLE — HOLD] a shaky prereq was handed to M.\n"
            f"  concept: {sh.get('concept')} — do NOT answer the learner until the frontier updates.")


def _vocab_block(db: DB, gap: dict | None) -> str:
    # single source of truth: the vocab TABLE. The frontier's vocab lists are seed
    # input only — library.seed_vocab() plants them at slice start; the door and this
    # block read the table exclusively, so a mid-slice promotion is never shadowed
    # by a stale frontier line.
    ok = _terms_by_status(db, ("shown", "proved"))
    hold = _terms_by_status(db, ("hold",))
    lines = ["[VOCAB]"]
    lines.append(f"  ok to use: {_join(ok) or '(none)'}")
    lines.append(f"  HELD (do not use): {_join(hold) or '(none)'}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# the gate wall (the one true PreToolUse hook)
# --------------------------------------------------------------------------
def gate_wall_decision(db: DB, tool_name: str, tool_input: dict) -> tuple[str, str]:
    """('allow'|'deny', reason). Denies spec-read and target-write while a gate is OPEN.

    Joins to slices for the paths — gates stores no copies, so the wall can never
    enforce a stale target_file/spec_path.
    """
    gate = db.one(
        "SELECT g.slice_slug, s.target_file, s.spec_path FROM gates g "
        "JOIN slices s ON s.slug = g.slice_slug WHERE g.state='OPEN'")
    if not gate:
        return ("allow", "")
    path = _path_of(tool_input)
    if not path:
        return ("allow", "")
    if tool_name in _WRITE_TOOLS and _same_file(path, gate["target_file"]):
        return ("deny", f"gate is OPEN: {gate['target_file']} is his to write, not yours.")
    if tool_name in _READ_TOOLS and gate["spec_path"] and _same_file(path, gate["spec_path"]):
        return ("deny", "gate is OPEN: the spec is hidden while he writes.")
    return ("allow", "")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _open_gate_for(db: DB, slice_slug: str) -> dict | None:
    return db.one("SELECT * FROM gates WHERE slice_slug=? AND state='OPEN'", (slice_slug,))


def _concept_owned(db: DB, slug: str) -> bool:
    row = db.one("SELECT state FROM concepts WHERE slug=?", (slug,))
    return bool(row) and row["state"] == "OWNED"


def _terms_by_status(db: DB, statuses: tuple[str, ...]) -> list[str]:
    q = "SELECT term FROM vocab WHERE status IN (%s) ORDER BY term" % ",".join("?" * len(statuses))
    return [r["term"] for r in db.query(q, statuses)]


def _path_of(tool_input: dict) -> str:
    return (tool_input.get("file_path") or tool_input.get("path")
            or tool_input.get("notebook_path") or "")


def _same_file(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a, b = a.replace("\\", "/"), b.replace("\\", "/")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a) or a.split("/")[-1] == b.split("/")[-1]


def _road_hint(road: str) -> str:
    return {
        "intuition-train": "he guesses; let listed mistakes stand; nudge, never fix; cap 4 pushes.",
        "fast-map": "show the solution cleanly, then he applies it once, fresh.",
        "slow-solve": "he proves it fully; you only verify the proof.",
    }.get(road, road)


def _join(v) -> str:
    if isinstance(v, str):
        return v
    return "; ".join(str(x) for x in (v or []))


def _wfa(items) -> str:
    out = []
    for it in items or []:
        if isinstance(it, dict):
            out.append(f"{it.get('turn','?')} -> reveals: {it.get('reveals','?')}")
        else:
            out.append(str(it))
    return " | ".join(out)
