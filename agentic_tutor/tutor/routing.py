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
        step = gap_step(db, gap)
        parts.append(_step_block(db, gap, step))

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


# --------------------------------------------------------------------------
# the gap-loop step machine (MAP.md ②–⑧). CODE routes; the model only judges.
# --------------------------------------------------------------------------
STEPS = ("PROBE", "STUDY", "COMPLETE", "PRODUCE", "NAME", "VARY", "ABSTRACT")


def gap_step(db: DB, gap: dict) -> str:
    """Which map step this concept is at — a pure function of its probe rows.

    entry probe (level 3/4/5) routes the entry point; each produce MISS drops one
    level; a produce HIT advances to NAME -> VARY (2 HITs) -> ABSTRACT (close).
    """
    c = gap["concept"]
    entry = db.one("SELECT level FROM probes WHERE concept_slug=? AND kind='entry' "
                   "ORDER BY id DESC LIMIT 1", (c,))
    if not entry:
        return "PROBE"
    ev = _counts(db, c)
    if ev["produce_hits"] >= 1:
        if _held_terms(db, gap):
            return "NAME"
        if ev["vary_hits"] < 2:
            return "VARY"
        return "ABSTRACT"
    level = max(3, min(5, (entry["level"] or 4) - ev["produce_misses"]))
    if level == 3:
        if ev["predict_hits"] == 0:
            return "STUDY"
        return "COMPLETE" if ev["complete_hits"] == 0 else "PRODUCE"
    if level == 4:
        return "COMPLETE" if ev["complete_hits"] == 0 else "PRODUCE"
    return "PRODUCE"


def _counts(db: DB, concept: str) -> dict:
    row = db.one(
        "SELECT COALESCE(SUM(kind='predict' AND result='HIT'),0)  AS predict_hits, "
        "       COALESCE(SUM(kind='complete' AND result='HIT'),0) AS complete_hits, "
        "       COALESCE(SUM(kind='produce' AND result='HIT'),0)  AS produce_hits, "
        "       COALESCE(SUM(kind='produce' AND result='MISS'),0) AS produce_misses, "
        "       COALESCE(SUM(kind='vary' AND result='HIT'),0)     AS vary_hits "
        "FROM probes WHERE concept_slug=?", (concept,))
    return dict(row)


def _held_terms(db: DB, gap: dict) -> list[str]:
    hold = gap.get("vocab_hold") or []
    if not hold:
        return []
    q = "SELECT term FROM vocab WHERE state='hold' AND term IN (%s)" % ",".join("?" * len(hold))
    return [r["term"] for r in db.query(q, tuple(hold))]


def _step_block(db: DB, gap: dict, step: str) -> str:
    """ONE step's working orders — never the whole frontier. Rented context."""
    c, lines = gap["concept"], []
    head = f"[GAP {gap['concept']} — STEP {step}]"
    wfa = ("  judging aid — predicted wrong turns (let stand, record `reveals`): "
           + _wfa(gap.get("worth_failing_at"))) if gap.get("worth_failing_at") else ""
    ladder = _join(gap.get("simplify_ladder"))

    if step == "PROBE":
        lines = [head,
                 f"  OPEN WITH (guess-first): {gap['opening_question']}",
                 f"  connect to owned: {_join(gap.get('connect_to'))}",
                 "  Judge his footing from the answer, then record the entry:",
                 "    db record_probe kind=entry level=3 (nothing to stand on: he will",
                 "    STUDY a worked example) / 4 (partial: fill-the-holes) / 5 (near-",
                 "    complete: straight to fresh production). Result=HIT if any footing."]
    elif step == "STUDY":
        lines = [head,
                 "  Show ONE small worked example of the pattern (build it from these",
                 f"  rungs, smallest first): {ladder}",
                 "  ACTIVE study: before he may run anything, he PREDICTS the output",
                 "  line by line and says why each line does what it does. Only then run.",
                 "  Judge the prediction: db record_probe kind=predict HIT/MISS.",
                 wfa]
    elif step == "COMPLETE":
        lines = [head,
                 "  Give the SAME pattern with holes punched in it — he fills the holes.",
                 f"  Draw the material from the rungs: {ladder}",
                 "  Shrink the scaffold each rep. Never fill a hole for him.",
                 "  Judge: db record_probe kind=complete HIT/MISS.",
                 wfa]
    elif step == "PRODUCE":
        lines = [head,
                 f"  Blank page, FRESH instance sized by done-when: {gap['done_when']}",
                 "  Before he runs it he must state his PREDICTION of the output.",
                 "  Reality vs prediction is the lesson — he reconciles the diff, not you.",
                 "  You show NO code at this step. Judge: db record_probe kind=produce",
                 "  HIT/MISS (a MISS drops him one level automatically — do not improvise).",
                 wfa]
    elif step == "NAME":
        lines = [head,
                 "  His attempt did the teaching; now hand over the words and the residue:",
                 f"  {gap['just_tell']}",
                 "  Promote each vocab term he has now earned: db promote_vocab state=shown.",
                 "  Keep it short — then move on."]
    elif step == "VARY":
        need = 2 - _counts(db, c)["vary_hits"]
        lines = [head,
                 f"  {need} more varied round(s): SAME concept, DIFFERENT surface each",
                 "  time (change the data shape / the context, not the difficulty).",
                 "  Interleave: pick tasks where he must CHOOSE this tool among owned",
                 f"  ones — owned triggers he knows: {_owned_triggers(db, c)}",
                 "  Judge each round: db record_probe kind=vary HIT/MISS.",
                 wfa]
    elif step == "ABSTRACT":
        lines = [head,
                 "  He writes the rule as HIS one-liner: 'when I see __, I reach for __",
                 f"  because __'. Seed only if he stalls: {gap['mapping_seed']}",
                 "  Then: db store_mapping (trigger/solution/why = HIS words, his wrong",
                 "  turn as provenance), then db close_gap. The gate refuses shortcuts."]
    return "\n".join(l for l in lines if l)


def _owned_triggers(db: DB, exclude: str) -> str:
    rows = db.query(
        "SELECT m.trigger FROM mappings m JOIN concepts c ON c.slug=m.concept_slug "
        "WHERE c.state='OWNED' AND m.concept_slug != ? AND m.polarity='positive' "
        "ORDER BY m.id DESC LIMIT 3", (exclude,))
    return "; ".join(r["trigger"] for r in rows) or "(none yet)"


# --------------------------------------------------------------------------
# ⓪ REACTIVATE — the review block for the session's first turn
# --------------------------------------------------------------------------
def review_block(db: DB, limit: int = 3) -> str:
    """Due cold recalls, oldest first. Empty string when nothing is due."""
    rows = db.query(
        "SELECT c.slug, m.trigger FROM concepts c "
        "LEFT JOIN mappings m ON m.concept_slug=c.slug AND m.polarity='positive' "
        "WHERE c.state='OWNED' AND c.review_due IS NOT NULL "
        "AND c.review_due <= datetime('now') ORDER BY c.review_due LIMIT ?", (limit,))
    if not rows:
        return ""
    body = "\n".join(f"  - {r['slug']}" + (f" (his trigger was: {r['trigger']})"
                                           if r["trigger"] else "") for r in rows)
    return ("[REVIEW — do this FIRST, before the slice]\n"
            "Cold recall, unannounced as such: pose one small task per concept below,\n"
            "from memory, no example shown. Judge each: db record_review HIT/MISS.\n"
            "A MISS demotes it — the tool handles that; you just move on.\n" + body)


# --------------------------------------------------------------------------
# post-tool-use steering — the mid-turn injection channel (hooks.posttooluse_note)
# --------------------------------------------------------------------------
def post_commit_guidance(db: DB, gap: dict | None, op: str = "record_probe") -> str | None:
    """One line for L right after a db commit: where the map now stands."""
    if op == "store_mapping":
        return "mapping stored — now db close_gap. If it refuses, the text names what is missing."
    if op == "close_gap":
        return ("gap CLOSED. Stop teaching: do not open the next concept yourself — "
                "the planner owes the next handoff. Tell the learner what he now owns, briefly.")
    if op == "pass_gate":
        return ("slice BUILT. Close the session: ask HIM to summarize what he built and "
                "what rule he keeps (then db session_note with HIS words).")
    if op == "record_review":
        return "review recorded — continue the remaining reviews, or open the slice work."
    if op != "record_probe" or not gap:
        return None
    row = db.one("SELECT result, pushes, kind FROM probes WHERE concept_slug=? "
                 "ORDER BY id DESC LIMIT 1", (gap["concept"],))
    if not row:
        return None
    if row["pushes"] >= 4:
        return "push cap hit (4): stop pushing. Record where he is and end the attempt."
    step = gap_step(db, gap)
    what = {
        "PROBE":    "record the entry probe (level 3/4/5) before anything else.",
        "STUDY":    "next: a worked example — he predicts line by line BEFORE it runs.",
        "COMPLETE": "next: the pattern with holes — he fills them, you never do.",
        "PRODUCE":  "next: fresh blank-page instance — demand his prediction before he runs.",
        "NAME":     "he earned the words — give the residue + promote the vocab, briefly.",
        "VARY":     "next: a varied round — same concept, different surface.",
        "ABSTRACT": "next: his one-line rule, then store_mapping + close_gap.",
    }[step]
    return f"{row['kind']}/{row['result']} recorded — map step is now {step}: {what}"


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
    q = "SELECT term FROM vocab WHERE state IN (%s) ORDER BY term" % ",".join("?" * len(statuses))
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
