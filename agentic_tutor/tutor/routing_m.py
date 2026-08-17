"""routing_m — Agent M's turn picker + context router (docs/tutor-simulation.md G2/G2a).

M is ONE agent that wakes in three named turns — not three agents (the doc is
explicit: "There is no separate 'scanner agent'"). Same core, same gateway; only
the injected instruction set and the live tool list differ:

  pick_m_turn(db, frontier_empty)  -> 'SURVEY' | 'SUBHOLE' | 'PLAN' | None
      All wakeups are deterministic — a cell's state IS the signal, no agent decides:
        no `target` row                       -> SURVEY   (first turn of the project)
        a filled `slices.subhole_*` cell      -> SUBHOLE  (mid-slice course correction)
        empty frontier                        -> PLAN     (a slice closed; plan the next)

  build_m_block(db, turn, codebase_path)  -> the block injected into M's prompt
      SURVEY : [SURVEY] + [TOOL DISCIPLINE]           (repo tools are live)
      SUBHOLE: [SUBHOLE] + [EVIDENCE] + [TOOL DISCIPLINE]
      PLAN   : [EVIDENCE] + [OVERLAYS]                (db() only + Write for the spec)

  tools_for_turn(turn)  -> the file/web tools live on that turn (db is always live).
      Tool discipline is rented context: injected only on turns where those tools
      exist (the G3/H1 lesson), never core prose.

Injection happens via ContextManager.render — we own history, so this is NOT a
UserPromptSubmit hook, exactly like build_l_block. Pure Python, no SDK.
"""
from __future__ import annotations

import json

from .db import DB

# the meta key marking the last probes row M has seen ([EVIDENCE] = rows after it)
_SEEN_KEY = "m_last_probe_id"

# G2 — the constant core, every planning turn (~12 lines; the router carries the rest)
M_CORE = """You are the planner. You never talk to the learner; you never see transcripts.
Your inputs are probes rows and the overlays. Your output is the library.

1. Unit of progress = the SLICE. Pick the earliest READY slice on the spine;
   state why in why-this-slice — the learner will read it.
2. For each unowned concept-prereq, write one GAP block. Roads: fast-map (one
   right answer / a name), intuition-train (guessable shape), slow-solve (needs
   proof). Not the same road 3x in a row.
3. Fill every teaching-support key: opening-question, connect-to, simplify-ladder,
   worth-failing-at (+reveals), just-tell, justify, done-when, mapping-seed,
   vocab-ok/vocab-hold. The schema rejects a frontier with any empty key.
4. Size by the ZPD meter: 0 pushes = raise, 1-2 self-corrected = hold,
   4 = shrink (insert a smaller slice; don't soften roads).
5. If evidence contradicts a prerequisite edge, fix the DAG.
6. Never plan past the next slice. One step, then observe."""


# --------------------------------------------------------------------------
# the wakeup picker — a pure function of state, no agent decides
# --------------------------------------------------------------------------
def pick_m_turn(db: DB, frontier_empty: bool) -> str | None:
    # No target = no codebase adopted yet. M has nothing to survey; this is not a
    # wakeup, it is the absence of a session.
    if db.one("SELECT 1 FROM target WHERE id=1") is None:
        return None
    # The map is the SPINE, so "not surveyed yet" means no slices — NOT "no target row".
    # Whoever adopts the codebase writes the target row (the UI does), so keying SURVEY
    # off that row would skip the survey forever: the row exists before M ever runs.
    if db.one("SELECT 1 FROM slices LIMIT 1") is None:
        return "SURVEY"
    if db.one("SELECT 1 FROM slices WHERE subhole_concept IS NOT NULL"):
        return "SUBHOLE"
    if frontier_empty:
        return "PLAN"
    return None


# --------------------------------------------------------------------------
# the injected block — mirrors build_l_block: pure state -> text
# --------------------------------------------------------------------------
def build_m_block(db: DB, turn: str, codebase_path: str | None = None) -> str:
    if turn == "SURVEY":
        if not codebase_path:
            raise ValueError("SURVEY needs the codebase_path to survey")
        return "\n\n".join([_survey_block(codebase_path), _tool_discipline_block()])
    if turn == "SUBHOLE":
        return "\n\n".join([_subhole_block(db), _evidence_block(db),
                            _tool_discipline_block()])
    if turn == "PLAN":
        return "\n\n".join([_evidence_block(db), _overlays_block(db)])
    raise ValueError(f"unknown M turn: {turn}")


def tools_for_turn(turn: str) -> tuple[str, ...]:
    """File/web tools live on this turn. db() is always live (role-filtered inside)."""
    return {
        "SURVEY": ("Read", "Grep", "WebSearch", "WebFetch"),
        "SUBHOLE": ("Read", "Grep", "WebSearch", "WebFetch"),
        "PLAN": ("Write",),        # M/PLAN authors the spec file in the same act
    }[turn]


def mark_probes_seen(db: DB) -> None:
    """Advance the [EVIDENCE] pointer — the orchestrator calls this after an M turn."""
    row = db.one("SELECT MAX(id) AS m FROM probes")
    db.meta_set(_SEEN_KEY, row["m"] or 0)


# --------------------------------------------------------------------------
# blocks
# --------------------------------------------------------------------------
def _survey_block(codebase_path: str) -> str:
    # G2a, verbatim in intent: the map, not the specs. Specs are lazy (DECIDED):
    # spec_path stays NULL; M/PLAN writes each spec knowing the evidence.
    return f"""[SURVEY] — you are looking at this codebase for the first and only time.
  target: {codebase_path}

You are not teaching. You are drawing the map every later turn navigates by.
Output = the spine in the DB. You write NO frontier; that is your next turn's job.

1. READ THE REAL CODE FIRST. Grep the entry points, then Read the files they
   reach. You may not invent a slice for code you have not read.
2. Cut the codebase into SLICES. A slice is ONE function or file the learner
   can write in one sitting, from a spec, behind a closed gate. Sizing test:
   a sayable name; <= 2 unowned concept-prereqs; judgeable PASS/FAIL.
   Too big => cut it. Too small => it is a line, not a slice.
3. ORDER them into a spine: dependency order, not file order. Slice N may only
   need concepts and slices from before it. The FIRST slice needs the fewest
   unowned concepts — it is where he starts cold.
4. For each slice name its concept-prereqs. A concept can be OWNED or not
   (`enumerate-index`), never a task (`write the loop`).
5. Build the concept DAG: every prereq becomes a concepts row with its edges.
   All start LOCKED — you have no evidence yet. Assume nothing about him.
   OWNED is never yours to grant (close_gap alone does).
6. RESEARCH (WebSearch/WebFetch) only for two questions: the standard NAME of
   a concept, and whether edge X->Y is a real prerequisite. Never tutorials.
7. Write slice ROWS only — leave `spec_path` NULL. You author no spec files:
   M/PLAN writes each spec lazily AND sets `spec_path` in the same act, so a
   non-NULL path always means the file exists. `open_gate` refuses a NULL spec.
8. Write it all through db(): set_target first, then upsert_slice / upsert_concept.
   Then STOP. One survey, then observe. You do not plan the first slice."""


def _tool_discipline_block() -> str:
    return """[TOOL DISCIPLINE]
 Grep  first, always. Pattern + path filter; never a bare pattern over the repo.
       You are locating, not reading. Cheap and wide.
 Read  only files Grep proved matter, and only the ranges it pointed at.
       A whole-file Read of something you have not located is a bug.
 Web   two questions only: the standard NAME of a concept, and whether a
       prerequisite edge is real. Two calls is a lot; five means you are drifting.
 db()  last. It is the only write. menu -> describe -> commit."""


def _evidence_block(db: DB) -> str:
    since = int(db.meta_get(_SEEN_KEY, 0))
    rows = db.query("SELECT * FROM probes WHERE id > ? ORDER BY id", (since,))
    if not rows:
        body = "  (no probes since your last turn)"
    else:
        body = "\n".join(
            f"  #{r['id']} {r['concept_slug']} {r['kind']}/{r['result']} "
            f"pushes={r['pushes']} self_corrected={r['self_corrected']}"
            + (f" reveals={r['reveals']}" if r["reveals"] else "")
            for r in rows)
    return f"[EVIDENCE] probes since your last turn (rows, never prose):\n{body}"


def _overlays_block(db: DB) -> str:
    slices = db.query("SELECT slug,state,ordinal FROM slices ORDER BY ordinal")
    concepts = db.query("SELECT slug,state FROM concepts ORDER BY slug")
    s_body = "\n".join(f"  {r['ordinal'] or '?'}. {r['slug']} [{r['state']}]"
                       for r in slices) or "  (none)"
    c_body = "\n".join(f"  {r['slug']} [{r['state']}]" for r in concepts) or "  (none)"
    return (f"[OVERLAYS]\n spine:\n{s_body}\n concepts:\n{c_body}\n"
            f" zpd meter: {_zpd_meter(db)}")


def _zpd_meter(db: DB) -> str:
    row = db.one("SELECT AVG(pushes) AS p, SUM(self_corrected) AS sc, COUNT(*) AS n "
                 "FROM probes WHERE id > ?", (int(db.meta_get(_SEEN_KEY, 0)),))
    if not row or not row["n"]:
        return "no fresh evidence"
    avg = row["p"] or 0
    if avg >= 4:
        return f"avg {avg:.1f} pushes over {row['n']} probes -> SHRINK (insert a smaller slice)"
    if avg == 0:
        return f"0 pushes over {row['n']} probes -> RAISE"
    return f"avg {avg:.1f} pushes, {row['sc'] or 0} self-corrected over {row['n']} -> HOLD"


def _subhole_block(db: DB) -> str:
    row = db.one("SELECT slug, subhole_concept, subhole_evidence FROM slices "
                 "WHERE subhole_concept IS NOT NULL")
    return f"""[SUBHOLE] — L hit a shaky prereq mid-slice and is HOLDING for you.
  slice: {row['slug']}
  concept: {row['subhole_concept']}
  evidence: {row['subhole_evidence']}
Keep the SLICE block untouched. Research the shaky concept, write its GAP block
under the existing keys, fill subhole-plan, then clear_subhole to release L.
Max 2 sub-gaps per slice — a third means you mis-sized: insert a smaller slice."""
