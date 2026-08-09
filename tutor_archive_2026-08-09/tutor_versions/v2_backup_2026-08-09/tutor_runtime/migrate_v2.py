#!/usr/bin/env python3
"""Schema v1 -> v2. Additive only: no existing row is rewritten, no id changes.

    python3 migrate_v2.py [--db tutor.db]

Idempotent. Every ALTER is guarded by a PRAGMA table_info check, so running it
twice is a no-op. Takes a backup before touching anything.
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

ADD_COLUMNS = [
    # table,      column,        definition
    ('concepts', 'source', "TEXT NOT NULL DEFAULT 'code'"),
    ('concepts', 'explanation', "TEXT"),
    ('concepts', 'taught_in', "INTEGER REFERENCES sessions(id)"),
    ('probes', 'faculty', "TEXT NOT NULL DEFAULT 'write'"),
    ('probes', 'seconds', "INTEGER"),
]

NEW_TABLES = {
    'gates': """
CREATE TABLE IF NOT EXISTS gates (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    kind       TEXT NOT NULL,   -- rebuild|build|transfer
    spec_path  TEXT,            -- file the learner must NOT read while open
    target     TEXT,            -- file the learner writes
    opened_at  TEXT NOT NULL,
    closed_at  TEXT,
    result     TEXT             -- PASS|FAIL|ABANDONED
)""",
    'learners': """
CREATE TABLE IF NOT EXISTS learners (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    rules      TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)""",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_gates_open ON gates(closed_at)",
    "CREATE INDEX IF NOT EXISTS idx_probes_faculty ON probes(faculty)",
    "CREATE INDEX IF NOT EXISTS idx_concepts_source ON concepts(source)",
]

# The rules that used to live in first person inside SKILL.md.
DEFAULT_RULES = """Never answer before I attempt. No praise without evidence.
My self-report is a hint; my code is evidence.
Short, direct, no softening. Name gaps I cannot see.
Assume nothing. Ask. Assuming I know something I don't is the failure that
killed every previous attempt. When unsure whether I have a prerequisite, probe
it - do not proceed on the assumption, and do not teach it unasked either.
I learn by building with AI, then rebuilding by hand. AI-written code in this
repo is spec, never credit. The ladder outranks my enthusiasm: reordering is
cheap, removing is not."""


def columns(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def migrate(db_path):
    db = Path(db_path)
    if not db.exists():
        sys.exit(f"no database at {db}")

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = db.with_suffix(f'.db.bak-{stamp}')
    shutil.copy2(db, backup)
    print(f"backup: {backup.name}")

    con = sqlite3.connect(db)
    before = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ('sessions', 'concepts', 'probes', 'floors', 'ladder_log')}

    added = []
    for table, col, ddl in ADD_COLUMNS:
        if col not in columns(con, table):
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            added.append(f"{table}.{col}")

    created = []
    for name, ddl in NEW_TABLES.items():
        existed = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,)).fetchone()
        con.execute(ddl)
        if not existed:
            created.append(name)

    for ddl in INDEXES:
        con.execute(ddl)

    if not con.execute("SELECT 1 FROM learners").fetchone():
        con.execute(
            "INSERT INTO learners (name, rules, active, created_at) VALUES (?,?,1,?)",
            ('bilal', DEFAULT_RULES, datetime.now().isoformat(timespec='seconds')))
        created.append("learners:bilal (active)")

    con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version','2')")
    con.commit()

    after = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in before}
    if before != after:
        sys.exit(f"ROW COUNTS CHANGED {before} -> {after}; restore {backup.name}")

    print(f"columns added: {added or 'none (already v2)'}")
    print(f"tables created: {created or 'none (already v2)'}")
    print(f"row counts unchanged: {after}")


if __name__ == '__main__':
    args = sys.argv[1:]
    path = args[args.index('--db') + 1] if '--db' in args else HERE / 'tutor.db'
    migrate(path)
