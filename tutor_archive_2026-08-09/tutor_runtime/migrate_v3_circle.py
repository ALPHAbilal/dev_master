#!/usr/bin/env python3
"""v3 CIRCLE migration — additive and reversible.

Adds the structures the v3 "circle" tutor needs WITHOUT touching v2 rows:

  1. concepts.verb        which of the 9 engineer-verbs a concept trains
  2. targets              the anchor(s) the learner builds by hand (DATA, not code)
  3. verb_coverage view   owned/total per verb, for the circle-map furniture

Run:  python3 .claude/tutor/migrate_v3_circle.py
Idempotent: safe to run twice. Nothing is dropped; v2 keeps working.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

DB = Path(__file__).resolve().parent / "tutor.db"

# The nine verbs of the circle (knowledge.md:448). `implement` is v2's `write`;
# `understand` folds v2's `read`. These become the legal `probes.faculty` values
# too (enforced in tutor_db.py, not here).
VERBS = ("understand", "decompose", "reason", "design",
         "implement", "debug", "evaluate", "communicate", "improve")

# First-pass backfill of concepts.verb from the existing category. Corrected by
# hand afterwards; this only makes the column non-empty so routing can see it.
CATEGORY_TO_VERB = {
    "language": "implement",
    "stdlib":   "implement",
    "failure":  "debug",
    "arch":     "design",
    "api":      "design",
    "pattern":  "reason",
}


def col_exists(con, table, col):
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    if not DB.exists():
        sys.exit(f"no db at {DB}")
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")

    # 1. concepts.verb -------------------------------------------------------
    if not col_exists(con, "concepts", "verb"):
        con.execute("ALTER TABLE concepts ADD COLUMN verb TEXT")
        print("+ concepts.verb added")
    else:
        print("= concepts.verb already present")

    filled = 0
    for cat, verb in CATEGORY_TO_VERB.items():
        cur = con.execute(
            "UPDATE concepts SET verb = ? WHERE category = ? AND (verb IS NULL OR verb = '')",
            (verb, cat))
        filled += cur.rowcount
    print(f"  backfilled verb on {filled} concepts (category -> verb; correct by hand)")

    # 2. targets -------------------------------------------------------------
    # The anchor is DATA and the process is agnostic to it. Captured by INTAKE
    # in session 1; read generically by every phase. `codebase` and `target` are
    # BOTH inputs, so a different repo needs zero code change.
    con.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            learner           TEXT NOT NULL,
            name              TEXT NOT NULL,   -- e.g. 'soufiane pipeline'
            codebase_path     TEXT,            -- the repo SCAN reads (agnostic)
            inputs            TEXT,            -- what the built thing takes in
            outputs           TEXT,            -- what it produces
            size              TEXT,            -- one script | several | large
            scripts           TEXT,            -- comma-sep files that make it up
            decomposition     TEXT,            -- JSON: slices, filled over time
            phase             TEXT NOT NULL DEFAULT 'SCAN',
                                               -- SCAN -> UNLOCK -> BUILD
            unlock_gate       TEXT NOT NULL DEFAULT 'open',
                                               -- open until every ladder concept owned
            created_at        TEXT NOT NULL,
            updated_at        TEXT
        )""")
    print("= targets table ready")

    # 3. verb_coverage view — the circle-map data ----------------------------
    con.execute("DROP VIEW IF EXISTS verb_coverage")
    con.execute("""
        CREATE VIEW verb_coverage AS
        SELECT verb,
               COUNT(*)                                        AS total,
               SUM(CASE WHEN state='CAN' THEN 1 ELSE 0 END)    AS owned,
               SUM(CASE WHEN parked=1 THEN 1 ELSE 0 END)       AS parked
        FROM concepts
        WHERE verb IS NOT NULL
        GROUP BY verb""")
    print("= verb_coverage view ready")

    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('v3_circle_migrated', ?)",
                (now(),))
    con.commit()

    print("\ncircle coverage now:")
    for r in con.execute("SELECT verb, owned, total, parked FROM verb_coverage ORDER BY total DESC"):
        print(f"  {r[0]:<12} owned {r[1] or 0:>3}/{r[2]:<3}  parked {r[3] or 0}")
    never = [v for v in VERBS
             if not con.execute("SELECT 1 FROM verb_coverage WHERE verb=?", (v,)).fetchone()]
    if never:
        print("  NEVER POPULATED (no concept trains them yet): " + ", ".join(never))
    con.close()


if __name__ == "__main__":
    main()
