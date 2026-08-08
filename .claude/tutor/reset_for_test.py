#!/usr/bin/env python3
"""Empty the tutor database for an end-to-end test of v2.

Deletes every ROW. Keeps every TABLE, index and constraint, so what you are
testing afterwards is the real schema, not a fixture.

    python3 .claude/tutor/reset_for_test.py --yes
    python3 .claude/tutor/reset_for_test.py --yes --keep-learner

Refuses without --yes. Always writes a timestamped backup first, so a reset is
never the thing that loses work.

Restore the last real state:
    cp .claude/tutor_versions/v2_restore_2026-08-05/tutor.db .claude/tutor/tutor.db
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / 'tutor.db'
ATTEMPTS = HERE.parent.parent / 'attempts'

TABLES = ('probes', 'attempts', 'assumptions', 'gates', 'floors',
          'ladder_log', 'concepts', 'sessions', 'learners')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yes', action='store_true', help='required; this deletes rows')
    ap.add_argument('--keep-learner', action='store_true',
                    help='keep the learners table so brief() still has rules')
    ap.add_argument('--keep-attempts', action='store_true',
                    help='leave the attempts/ folder on disk alone')
    a = ap.parse_args()
    if not a.yes:
        sys.exit("refused: pass --yes. This empties the tutor database.")
    if not DB.exists():
        sys.exit(f"no database at {DB}")

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = DB.with_name(f"tutor.db.pre_reset.bak-{stamp}")
    sqlite3.connect(DB).close()          # checkpoint WAL before copying
    shutil.copy(DB, bak)
    print(f"backup     {bak.name}")

    con = sqlite3.connect(DB)
    before = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}

    tables = [t for t in TABLES if not (a.keep_learner and t == 'learners')]
    con.execute("PRAGMA foreign_keys = OFF")
    for t in tables:
        con.execute(f"DELETE FROM {t}")
    # so the next run starts at id 1 and the test reads like a first run
    con.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)"
                % ','.join('?' * len(tables)), tables)
    con.execute("UPDATE meta SET value='FLOOR' WHERE key='phase'")
    con.commit()
    con.execute("VACUUM")
    con.commit()

    after = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    print(f"deleted    {sum(before.values()) - sum(after.values())} rows")
    for t in TABLES:
        if before[t] or after[t]:
            print(f"  {t:<12} {before[t]:>4} -> {after[t]}")

    kept = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"tables     {len(kept)} intact: {', '.join(sorted(kept))}")
    print("integrity ", con.execute("PRAGMA integrity_check").fetchone()[0])
    print("phase     ", con.execute(
        "SELECT value FROM meta WHERE key='phase'").fetchone()[0])
    con.close()

    if ATTEMPTS.exists() and not a.keep_attempts:
        n = sum(1 for _ in ATTEMPTS.rglob('*') if _.is_file())
        shutil.rmtree(ATTEMPTS)
        print(f"attempts   removed {n} archived file(s) from {ATTEMPTS.name}/")

    print("\nEMPTY. To drive the full v2 funnel from zero:")
    print("  learner add bilal .claude/tutor_versions/v2_restore_2026-08-05/"
          "learner_rules.txt")
    print("  learner use bilal")
    print("  session <model> 'v2 end-to-end test'")


if __name__ == '__main__':
    main()
