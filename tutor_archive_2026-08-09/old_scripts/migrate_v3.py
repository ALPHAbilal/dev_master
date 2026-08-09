#!/usr/bin/env python3
"""v1 -> v2 tutor migration.  Additive only: no row is deleted, no id changes,
no v1 value is overwritten in place.  Idempotent -- safe to run twice.

What it does, and which POSTMORTEM failure each answers:

  F1  concepts.parked        depth 3+ leaves the ladder, stays in the bank
  F6  concepts.state_v1      v1 state preserved verbatim before collapse
  F6  concepts.state         collapsed to CANT | CAN
  F4  probes.error_class     gap|syntax|typo|bleed|fatigue|none
  F5  probes.seconds         already exists; enforcement moves to tutor_db.py
  F3  attempts table         every submitted artifact, immutable, diffed
  F8  phase in meta          the learner's one choice, four times total
  F2  assumptions table      prerequisites the agent declared, and the vetoes
"""
import sqlite3, sys, os, shutil, datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tutor.db')

DDL = [
    # ---- F1: park the unreachable tail instead of ranking it every session
    "ALTER TABLE concepts ADD COLUMN parked INTEGER NOT NULL DEFAULT 0",
    # ---- F6: keep v1's four-state value forever, before collapsing the live one
    "ALTER TABLE concepts ADD COLUMN state_v1 TEXT",
    # ---- F4: a MISS is not one thing
    "ALTER TABLE probes ADD COLUMN error_class TEXT",
    # ---- F3: the learner's actual output, kept
    """CREATE TABLE IF NOT EXISTS attempts (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  INTEGER NOT NULL REFERENCES sessions(id),
        concept_id  INTEGER REFERENCES concepts(id),
        phase       TEXT NOT NULL,          -- FLOOR|READ|BUILD_V1|BUILD_V2
        slug        TEXT NOT NULL,          -- what was being attempted
        n           INTEGER NOT NULL,       -- 1,2,3... per (phase,slug)
        src_path    TEXT NOT NULL,          -- the file the learner edits
        stored_path TEXT NOT NULL,          -- the immutable copy
        sha         TEXT NOT NULL,
        bytes       INTEGER NOT NULL,
        lines       INTEGER NOT NULL,
        diff_prev   TEXT,                   -- unified diff vs attempt n-1
        added       INTEGER,                -- lines added vs prev
        removed     INTEGER,                -- lines removed vs prev
        result      TEXT,                   -- HIT|MISS|PARTIAL, set at grade time
        seconds     INTEGER,                -- wall clock since previous attempt
        taken_at    TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_attempts_slug ON attempts(phase, slug, n)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_sha ON attempts(phase, slug, n)",
    # ---- F2: assumptions must be stated so they can be vetoed
    """CREATE TABLE IF NOT EXISTS assumptions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  INTEGER NOT NULL REFERENCES sessions(id),
        teaching    TEXT NOT NULL,          -- the rung about to be taught
        assumed     TEXT NOT NULL,          -- comma-separated slugs assumed owned
        vetoed      TEXT,                   -- what the learner said he does NOT have
        declared_at TEXT NOT NULL
    )""",
]

STATE_MAP = {'APPLIED': 'CAN', 'EXPLAINED': 'CANT', 'SEEN': 'CANT', 'UNKNOWN': 'CANT'}


def has_col(con, table, col):
    return col in [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def main():
    if not os.path.exists(DB):
        sys.exit(f"no db at {DB}")
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = f"{DB}.pre_v2tutor.bak-{stamp}"
    shutil.copy(DB, bak)
    print(f"backup     {os.path.basename(bak)}")

    con = sqlite3.connect(DB)
    before = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
              for t in ('concepts', 'probes', 'sessions', 'ladder_log', 'floors')}

    applied = 0
    for stmt in DDL:
        try:
            con.execute(stmt)
            applied += 1
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e) or 'already exists' in str(e):
                continue
            raise
    print(f"ddl        {applied} applied, {len(DDL) - applied} already present")

    # F6 -- preserve, then collapse. Never overwrite an existing state_v1.
    con.execute("UPDATE concepts SET state_v1 = state WHERE state_v1 IS NULL")
    moved = 0
    for old, new in STATE_MAP.items():
        cur = con.execute("UPDATE concepts SET state=? WHERE state=?", (new, old))
        moved += cur.rowcount
    print(f"states     {moved} collapsed -> CAN/CANT (v1 value kept in state_v1)")

    # F1 -- park depth 3+. Reversible: parked=0 puts it back on the ladder.
    cur = con.execute("UPDATE concepts SET parked=1 WHERE depth >= 3 AND parked=0")
    print(f"parked     {cur.rowcount} concepts at depth 3+ off the ladder")

    # F8 -- the phase pointer. FLOOR is where v1 actually left him.
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('phase','FLOOR')")
    con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','2')")
    con.execute("UPDATE meta SET value='2' WHERE key='schema_version'")

    con.commit()

    after = {t: con.execute(f"select count(*) from {t}").fetchone()[0]
             for t in ('concepts', 'probes', 'sessions', 'ladder_log', 'floors')}
    ok = before == after
    print(f"rowcounts  {'UNCHANGED' if ok else 'CHANGED'}  {before} -> {after}")
    print("integrity ", con.execute("pragma integrity_check").fetchone()[0])
    print("live       ", dict(con.execute(
        "select state, count(*) from concepts where parked=0 group by state")))
    print("parked     ", dict(con.execute(
        "select state, count(*) from concepts where parked=1 group by state")))
    print("phase      ", con.execute("select value from meta where key='phase'").fetchone()[0])
    con.close()
    if not ok:
        sys.exit("ABORT: row counts changed, restore from " + bak)


if __name__ == '__main__':
    main()
