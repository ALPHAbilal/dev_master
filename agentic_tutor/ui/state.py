"""state — the DB rendered for the interface. Read-only, always.

One function per panel the learner sees. Every value is read live off the DB, so a
panel can never show a state the gateway did not actually commit.

  who_is_active(db, frontier_empty) -> which agent holds the turn RIGHT NOW.
      Delegated to `routing_m.pick_m_turn` — the same picker the orchestrator obeys,
      so the indicator cannot disagree with what will actually run. M outranks L:
      whenever M has a wakeup, L is waiting on it.

  snapshot(db, frontier_empty) -> the whole UI payload in one read.

No writes, no SDK, no HTTP.
"""
from __future__ import annotations

import json

from tutor.db import DB
from tutor.routing_m import pick_m_turn
from . import session

# what the learner is told each agent is doing — plain language, no internal jargon
ACTIVITY = {
    "SURVEY": "reading your codebase and drawing the map",
    "PLAN": "planning the next slice",
    "REGAP": "aiming the next gap on this slice",
    "SUBHOLE": "re-planning around a shaky prerequisite",
    "L": "teaching",
    None: "waiting for you",
}

# Which M turns still have no runner, and what would have to be built to give them one.
# Surfaced verbatim in the UI so a stalled session explains itself.
MISSING_RUNNER = {
    "SUBHOLE": ("M/SUBHOLE has no runner yet (build order step 6). L is holding on a "
                "shaky prerequisite that nothing can re-plan."),
}

# M turns that can actually be launched, and the button that launches them.
RUNNABLE = {"SURVEY": "Run the survey", "PLAN": "Plan the next slice",
            "REGAP": "Aim the next gap"}
ROUTE = {"SURVEY": "/api/survey", "PLAN": "/api/plan", "REGAP": "/api/plan"}


def who_is_active(db: DB, frontier_empty: bool, running: str | None = None,
                  frontier: dict | None = None) -> dict:
    """Who holds the turn, and — critically — whether anything is actually EXECUTING.

    `status` is the honest bit and must never be faked:
      running  — a turn is executing right now
      due      — this agent owes a turn but nothing has started it
      waiting  — L has the turn and is waiting on the learner
      idle     — no codebase yet
    A `due` agent is NOT working. Showing motion for a turn nobody launched is the
    interface lying about the system, which is the one thing it may never do.
    """
    if not session.is_adopted(db):
        return {"agent": None, "label": "no codebase yet", "status": "idle",
                "activity": "waiting for a codebase", "learner_waits": True}
    # What is ACTUALLY executing outranks what the picker predicts. A running SURVEY
    # writes slices, which immediately makes the picker say "PLAN is due" — reporting
    # that while SURVEY is still working would swap the label mid-run and claim the
    # wrong agent. Only the orchestrator clears `running`.
    if running:
        key = running.split("/")[-1] if running.startswith("M/") else "L"
        return {"agent": running, "label": running, "status": "running",
                "activity": ACTIVITY.get(key, "working"), "learner_waits": True,
                "startable": False}
    turn = pick_m_turn(db, frontier_empty, frontier)
    if turn:
        # Only SURVEY has a runner today. Saying "due" and greying the composer with no
        # explanation strands the learner: nothing to press, nothing to type, no reason
        # given. Name the missing piece instead.
        return {
            "agent": f"M/{turn}", "label": f"M/{turn}", "status": "due",
            "activity": f"has not run yet — it would be {ACTIVITY[turn]}",
            "learner_waits": True,
            "startable": turn in RUNNABLE,
            "blocked_by": None if turn in RUNNABLE else MISSING_RUNNER[turn],
            "resurveyable": _has_spine(db),
            "start_label": RUNNABLE.get(turn, ""),
            "start_route": ROUTE.get(turn, ""),
        }
    return {"agent": "L", "label": "L", "status": "waiting",
            "activity": "waiting for you", "learner_waits": False,
            "startable": False, "blocked_by": None, "resurveyable": _has_spine(db)}


def _has_spine(db: DB) -> bool:
    """A spine exists, so 'run the survey' means re-survey: archive, clear, redraw."""
    return db.one("SELECT 1 FROM slices LIMIT 1") is not None


def snapshot(db: DB, frontier_empty: bool = True, running: str | None = None,
             frontier_raw: dict | None = None) -> dict:
    return {
        "adopted": session.is_adopted(db),
        "root": session.current_root(db),
        "active": who_is_active(db, frontier_empty, running, frontier_raw),
        "frontier": frontier(frontier_raw),
        "spine": spine(db),
        "concepts": concepts(db),
        "vocab": vocab(db),
        "gate": open_gate(db),
        "evidence": recent_probes(db),
        "files": session.file_tree(db),
    }


def frontier(raw: dict | None) -> dict | None:
    """The published handoff, shaped for the page. Pure — the App reads the file.

    Split in two, and nothing is withheld — both halves ship:

      `now`  the glance view: which slice L is teaching, into which file, which
             concept is open. Small enough for the sidebar.
      `full` the raw file, byte for byte, rendered in the Inspector. This is the
             tracing view: it carries `opening_question`, `simplify_ladder`,
             `worth_failing_at` and `just_tell`, so what L was handed can be read
             against what L actually did. The sidebar is a summary of it, not a
             redaction of it — a full frontier in a 20rem column is unreadable.

    None means no usable frontier: L has nothing to teach and M/PLAN owes a turn.
    """
    if not raw:
        return None
    sl = raw.get("slice") or {}
    gap = raw.get("gap") or None
    sub = raw.get("subhole") or {}
    return {
        "now": {
            "slug": sl.get("slug", ""),
            "title": sl.get("title") or sl.get("slug", ""),
            "target_file": sl.get("target_file", ""),
            "why": sl.get("why_this_slice", ""),
            "prereqs": sl.get("concept_prereqs") or [],
            # the concept under the microscope; None = skip-gap slice, every prereq owned
            "concept": (gap or {}).get("concept") or None,
            "road": (gap or {}).get("road") or "",
            "done_when": (gap or {}).get("done_when") or "",
            "vocab_ok": (gap or {}).get("vocab_ok") or [],
            "vocab_hold": (gap or {}).get("vocab_hold") or [],
            "subhole": sub.get("concept") or None,
            "skip_gap": gap is None,
        },
        "full": raw,
    }


def spine(db: DB) -> list[dict]:
    rows = db.query("SELECT slug,title,target_file,spec_path,state,ordinal,concept_prereqs,"
                    "subhole_concept FROM slices ORDER BY COALESCE(ordinal, 999), slug")
    return [{
        "slug": r["slug"],
        "title": r["title"],
        "target_file": r["target_file"],
        "ordinal": r["ordinal"],
        "state": r["state"],
        # lazy specs: NULL means M/PLAN has not authored it yet, so the gate cannot open
        "has_spec": bool(r["spec_path"]),
        "prereqs": _json_list(r["concept_prereqs"]),
        "subhole": r["subhole_concept"],
    } for r in rows]


def concepts(db: DB) -> list[dict]:
    rows = db.query("SELECT slug,name,state,requires FROM concepts ORDER BY state DESC, slug")
    return [{"slug": r["slug"], "name": r["name"], "state": r["state"],
             "requires": _json_list(r["requires"])} for r in rows]


def vocab(db: DB) -> dict:
    rows = db.query("SELECT term,state FROM vocab ORDER BY term")
    out: dict[str, list[str]] = {"ok": [], "hold": []}
    for r in rows:
        if r["state"] in ("shown", "proved"):
            out["ok"].append(r["term"])
        elif r["state"] == "hold":
            out["hold"].append(r["term"])
    return out


def open_gate(db: DB) -> dict | None:
    r = db.one("SELECT g.slice_slug, s.title, s.target_file, g.opened_at FROM gates g "
               "JOIN slices s ON s.slug=g.slice_slug WHERE g.state='OPEN'")
    if not r:
        return None
    return {"slice": r["slice_slug"], "title": r["title"],
            "target_file": r["target_file"], "opened_at": r["opened_at"]}


def recent_probes(db: DB, limit: int = 12) -> list[dict]:
    rows = db.query("SELECT id,concept_slug,kind,result,pushes,self_corrected,reveals "
                    "FROM probes ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]


def _json_list(v) -> list:
    if not v:
        return []
    try:
        parsed = json.loads(v)
    except (ValueError, TypeError):
        return []
    return parsed if isinstance(parsed, list) else []
