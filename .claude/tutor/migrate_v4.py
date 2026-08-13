#!/usr/bin/env python3
"""v3 -> v4. Additive columns, one backfill, then the dead tables go.

Re-runnable: every ALTER is guarded by a PRAGMA table_info check and every DROP
by a sqlite_master check, so running this twice is a no-op the second time.

What changes:
  probes    gains rung|hole_kind|terms|question|answer; rung backfilled from
            faculty, because v4 tests a RUNG (predict/perturb/produce/transfer)
            and v3's faculty was the closest thing it had.
  assessments  every row is copied into probes and the table is dropped. A
            judgment about an answer IS a probe; two tables meant two places to
            look and the last session looked in neither.
  angles    dropped. The stack replaced the angle carousel.
  meta      phase renamed into the v4 six, schema_version = 4.

    python3 migrate_v4.py [path/to/tutor.db]
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / 'tutor.db'

# v4 columns added to probes, in order. `question`/`answer` already exist on a
# v3 database but are listed so a stranger schema still converges.
PROBE_COLS = (('rung', 'TEXT'), ('hole_kind', 'TEXT'), ('terms', 'TEXT'),
              ('question', 'TEXT'), ('answer', 'TEXT'))

# v3 named its phases after what the learner was doing; v4 names them after what
# the tutor is doing, and there is now exactly one of them.
PHASE_RENAME = {'FLOOR': 'SCAN', 'BUILD_V1': 'BUILD', 'BUILD_V2': 'SOLO',
                'CAPSTONE': 'SOLO', 'INTAKE': 'SCAN', 'UNLOCK': 'DRILL'}

V4_PHASES = {'SCAN', 'READ', 'DRILL', 'ASSEMBLE', 'BUILD', 'SOLO'}


def has_table(con, name):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone() is not None


def has_column(con, table, col):
    return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})"))


def add_columns(con):
    added = []
    for col, typ in PROBE_COLS:
        if not has_column(con, 'probes', col):
            con.execute(f"ALTER TABLE probes ADD COLUMN {col} {typ}")
            added.append(col)
    return added


def backfill_rung(con):
    """faculty -> rung, only where rung is still empty."""
    if not has_column(con, 'probes', 'faculty'):
        return 0
    return con.execute(
        "UPDATE probes SET rung = faculty WHERE rung IS NULL").rowcount


def fold_assessments(con):
    """Copy every assessment into probes, then drop the table.

    hole -> result: a hole of any kind is a MISS, no hole is a HIT. v3 also
    stored `demonstrated`, which only ever distinguished a HIT from a claim; a
    claim is not evidence, so it becomes PARTIAL.
    """
    if not has_table(con, 'assessments'):
        return 0
    phase = get_meta(con, 'phase') or 'DRILL'
    rows = con.execute(
        "SELECT session_id, slug, hole, gap_type, demonstrated, evidence, ts"
        " FROM assessments ORDER BY id").fetchall()
    for sid, slug, hole, gap, demo, evidence, ts in rows:
        cid = con.execute("SELECT id FROM concepts WHERE slug=?", (slug,)).fetchone()
        if hole and hole != 'none':
            result = 'MISS'
        elif demo:
            result = 'HIT'
        else:
            result = 'PARTIAL'
        con.execute(
            "INSERT INTO probes(session_id, concept_id, phase, depth_below,"
            " question, answer, result, asked_at, hole_kind, rung)"
            " VALUES (?,?,?,0,?,?,?,?,?,?)",
            (sid or 1, cid[0] if cid else None, phase,
             f'[migrated from assessments: {slug}]', evidence, result,
             ts or now(), gap, 'predict'))
    con.execute("DROP TABLE assessments")
    return len(rows)


def drop_dead(con):
    dropped = []
    for t in ('angles', 'gap_types', 'bucket_keys', 'form_questions'):
        if has_table(con, t):
            con.execute(f"DROP TABLE {t}")
            dropped.append(t)
    return dropped


def get_meta(con, key):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", (key, value))


def migrate_phase(con):
    old = get_meta(con, 'phase')
    new = PHASE_RENAME.get(old, old)
    if new not in V4_PHASES:
        new = 'SCAN'                    # unknown or missing: start at the top
    set_meta(con, 'phase', new)
    return old, new


def now():
    return datetime.now().isoformat(timespec='seconds')


def migrate(db=DB):
    con = sqlite3.connect(str(db))
    try:
        con.executescript((HERE / 'schema.sql').read_text(encoding='utf-8'))
        added = add_columns(con)
        rungs = backfill_rung(con)
        folded = fold_assessments(con)
        dropped = drop_dead(con)
        old, new = migrate_phase(con)
        set_meta(con, 'schema_version', '4')
        set_meta(con, 'v4_migrated', now())
        con.commit()
    finally:
        con.close()
    return {'columns_added': added, 'rungs_backfilled': rungs,
            'assessments_folded': folded, 'tables_dropped': dropped,
            'phase': f'{old} -> {new}'}


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else DB
    for k, v in migrate(db).items():
        print(f"= {k}: {v}")
    print(f"= {db} is at schema_version 4")


if __name__ == '__main__':
    main()
