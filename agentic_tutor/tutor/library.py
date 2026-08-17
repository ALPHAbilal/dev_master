"""library — the CODE-owned library writes (never an agent's job).

Two anti-drift rules live here:

  seed_vocab(db, frontier)   The frontier's vocab-ok / vocab-hold lists are SEED
                             input only. At slice start the orchestrator plants them
                             into the vocab table; from then on the table is the single
                             truth (the door and build_l_block read it exclusively).
                             Never downgrades: a term already 'proved' stays proved.

  render_target_md(db)       library/target.md is GENERATED from the DB spine, never
                             hand-written by M — a render, not a second source of truth.
                             The orchestrator rewrites it after any spine write.
"""
from __future__ import annotations

import json

from .db import DB
from .frontier import Frontier

_RANK = {"unknown": 0, "hold": 1, "shown": 2, "proved": 3}


def seed_vocab(db: DB, frontier: Frontier) -> list[str]:
    """Plant the frontier's vocab lists into the vocab table (slice start).

    ok terms -> 'shown', hold terms -> 'hold'. Existing rows are only ever
    UPGRADED (by _RANK); seeding never takes a word back. Returns seeded terms.
    """
    gap = frontier.gap or {}
    seeded: list[str] = []
    for term, status in ([(t, "shown") for t in gap.get("vocab_ok", [])]
                         + [(t, "hold") for t in gap.get("vocab_hold", [])]):
        row = db.one("SELECT state FROM vocab WHERE term=?", (term,))
        if row and _RANK[row["state"]] >= _RANK[status]:
            continue
        db.execute(
            "INSERT INTO vocab(term,state) VALUES(?,?) "
            "ON CONFLICT(term) DO UPDATE SET state=excluded.state, "
            "updated_at=datetime('now')",
            (term, status))
        seeded.append(term)
    return seeded


def render_target_md(db: DB) -> str:
    """The human-readable spine, generated from target + slices. Returns markdown."""
    t = db.one("SELECT codebase_path FROM target WHERE id=1")
    lines = ["# target — the spine (GENERATED from the DB; do not edit)", ""]
    lines.append(f"codebase: {t['codebase_path'] if t else '(no target registered)'}")
    lines.append("")
    for r in db.query("SELECT * FROM slices ORDER BY ordinal"):
        prereqs = ", ".join(json.loads(r["concept_prereqs"]) if r["concept_prereqs"] else [])
        lines.append(f"{r['ordinal'] or '?'}. [{r['state']}] {r['slug']} — {r['title']}")
        lines.append(f"     file: {r['target_file']}   prereqs: {prereqs or '(none)'}")
    return "\n".join(lines) + "\n"
