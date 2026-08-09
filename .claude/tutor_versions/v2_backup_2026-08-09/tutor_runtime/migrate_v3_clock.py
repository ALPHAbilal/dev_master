#!/usr/bin/env python3
"""Make the clock a subtraction instead of a question. Additive and idempotent.

    python3 .claude/tutor/migrate_v3_clock.py

Adds:
    probes.clock   how `seconds` was obtained (measured|batch|away|unmeasured)
    asks           a running clock, opened when a question goes on screen

Changes NO id and NO historical value. Existing probe rows keep their seconds
exactly as recorded and are labelled honestly: every one of them came from the
learner's own estimate, so none of them is `measured`.
"""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / 'tutor.db'


def cols(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def main():
    if not DB.exists():
        sys.exit(f"no database at {DB}")
    con = sqlite3.connect(DB)
    before = con.execute("SELECT COUNT(*) FROM probes").fetchone()[0]

    if 'clock' not in cols(con, 'probes'):
        con.execute("ALTER TABLE probes ADD COLUMN clock TEXT NOT NULL"
                    " DEFAULT 'unmeasured'")
        # Everything already in the table was self-reported, then divided.
        # `self-reported` is kept as its own label so the fiction stays visible
        # in the record instead of being laundered into `measured`.
        n = con.execute(
            "UPDATE probes SET clock = 'self-reported' WHERE seconds IS NOT NULL"
        ).rowcount
        print(f"probes.clock added; {n} existing rows labelled 'self-reported'")
    else:
        print("probes.clock already present")

    con.execute("""CREATE TABLE IF NOT EXISTS asks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL REFERENCES sessions(id),
        slugs      TEXT NOT NULL,
        phase      TEXT,
        faculty    TEXT,
        asked_at   TEXT NOT NULL,
        closed_at  TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_asks_open ON asks(closed_at)")
    print("asks table present")

    con.commit()
    after = con.execute("SELECT COUNT(*) FROM probes").fetchone()[0]
    print(f"probes {before} -> {after} (must be unchanged)")
    for r in con.execute("SELECT clock, COUNT(*) FROM probes GROUP BY 1"):
        print(f"  clock={r[0]:<14} {r[1]}")
    print("integrity ", con.execute("PRAGMA integrity_check").fetchone()[0])
    con.close()


if __name__ == '__main__':
    main()
