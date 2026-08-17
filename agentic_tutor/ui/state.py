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
    "SUBHOLE": "re-planning around a shaky prerequisite",
    "L": "teaching",
    None: "waiting for you",
}


def who_is_active(db: DB, frontier_empty: bool, running: str | None = None) -> dict:
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
    turn = pick_m_turn(db, frontier_empty)
    if turn:
        is_running = running == f"M/{turn}"
        return {
            "agent": f"M/{turn}", "label": f"M/{turn}",
            "status": "running" if is_running else "due",
            "activity": (ACTIVITY[turn] if is_running
                         else f"has not run yet — it would be {ACTIVITY[turn]}"),
            "learner_waits": True,
            "startable": turn == "SURVEY",
        }
    if running == "L":
        return {"agent": "L", "label": "L", "status": "running",
                "activity": ACTIVITY["L"], "learner_waits": True}
    return {"agent": "L", "label": "L", "status": "waiting",
            "activity": "waiting for you", "learner_waits": False}


def snapshot(db: DB, frontier_empty: bool = True, running: str | None = None) -> dict:
    return {
        "adopted": session.is_adopted(db),
        "root": session.current_root(db),
        "active": who_is_active(db, frontier_empty, running),
        "spine": spine(db),
        "concepts": concepts(db),
        "vocab": vocab(db),
        "gate": open_gate(db),
        "evidence": recent_probes(db),
        "files": session.file_tree(db),
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
    rows = db.query("SELECT term,status FROM vocab ORDER BY term")
    out: dict[str, list[str]] = {"ok": [], "hold": []}
    for r in rows:
        if r["status"] in ("shown", "proved"):
            out["ok"].append(r["term"])
        elif r["status"] == "hold":
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
