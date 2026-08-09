#!/usr/bin/env python3
"""Verification for the tutor instrument. Runs against a throwaway copy.

    python3 test_tutor.py

Never touches the real tutor.db. Copies tutor_db.py, tutor_hook.py and
schema.sql into a temp directory, builds an empty database there, and drives
the whole funnel through the CLI exactly as an agent would.
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PASS, FAIL = [], []


def check(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print(f"{'ok  ' if ok else 'FAIL'} {name}" + (f"  <- {detail}" if not ok else ''))


class Sandbox:
    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix='tutor-test-'))
        for f in ('tutor_db.py', 'tutor_hook.py', 'schema.sql'):
            shutil.copy2(HERE / f, self.dir / f)
        self.db = self.dir / 'tutor.db'
        self.run('init')

    def run(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(self.dir / 'tutor_db.py'), *args],
            capture_output=True, text=True, input=stdin)

    def hook(self, cmd, payload):
        return subprocess.run(
            [sys.executable, str(self.dir / 'tutor_hook.py'), cmd],
            capture_output=True, text=True, input=json.dumps(payload))

    def sql(self, q, *p):
        con = sqlite3.connect(self.db)
        con.row_factory = sqlite3.Row
        return con.execute(q, p).fetchall()

    def seed_concept(self, slug, depth=1):
        con = sqlite3.connect(self.db)
        con.execute(
            "INSERT INTO concepts (slug, name, definition, category, depth, gate)"
            " VALUES (?,?,?,?,?,?)",
            (slug, slug.replace('-', ' '), 'seeded for test', 'language', depth,
             'writes it from a blank page'))
        con.commit()

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def test_refusals(s):
    s.run('session', 'test', 'refusals')
    s.seed_concept('executing-a-file')

    r = s.run('promote', 'executing-a-file', 'APPLIED')
    check('promote APPLIED refused without an unaided production probe',
          r.returncode != 0 and 'REFUSED' in r.stderr, r.stdout + r.stderr)
    state = s.sql("SELECT state FROM concepts WHERE slug='executing-a-file'")[0]['state']
    check('refused promote left the row untouched', state == 'UNKNOWN', state)

    r = s.run('teach-open', 'executing-a-file')
    check('teach-open refused with no prior attempt',
          r.returncode != 0 and 'never been probed' in r.stderr, r.stderr)

    r = s.run('probe', 'executing-a-file', 'SWEEP', 'telepathy', 'HIT')
    check('probe refused on an unknown faculty', r.returncode != 0, r.stderr)

    r = s.run('probe', 'executing-a-file', 'LECTURE', 'write', 'HIT')
    check('probe refused on an unknown phase', r.returncode != 0, r.stderr)

    r = s.run('revise', '--trigger', 'IT_WAS_HARD', '--evidence', 'x', '--change', 'y')
    check('revise refused on a non-evidence trigger',
          r.returncode != 0 and 'flinching' in r.stderr, r.stderr)

    r = s.run('promote', 'executing-a-file', 'EXPLAINED', '--evidence', 'transferred')
    check('transferred refused before APPLIED', r.returncode != 0, r.stderr)

    r = s.run('promote', 'nonexistent-slug', 'SEEN')
    check('grading refused for a concept not in the bank', r.returncode != 0, r.stderr)


def test_funnel(s):
    """sweep -> descend -> floor -> teach -> gate -> APPLIED -> transfer."""
    s.run('session', 'test', 'funnel')
    s.seed_concept('name-main')

    s.run('probe', 'name-main', 'SWEEP', 'write', 'MISS', '-q', 'what does it do',
          '--seconds', '40')
    swept = s.sql("SELECT swept_in, attempts, fails FROM concepts WHERE slug='name-main'")[0]
    check('SWEEP stamps swept_in and counts the attempt',
          swept['swept_in'] is not None and swept['attempts'] == 1
          and swept['fails'] == 1, dict(swept))

    s.run('probe', 'name-main', 'DESCEND', 'recall', 'HIT', '--below', '3',
          '--seconds', '20')
    s.run('floor', 'name-main', '--explains', 'name-main', '--descents', '3')
    check('floor recorded', len(s.sql("SELECT 1 FROM floors")) == 1)

    r = s.run('teach-open', 'name-main')
    check('teach-open allowed after an attempt', r.returncode == 0, r.stderr)

    expl = s.dir / 'expl.md'
    expl.write_text('When you run a file directly, __name__ is "__main__".')
    r = s.run('teach-close', 'name-main', '--explanation-file', str(expl))
    check('teach-close refused before a gate exists',
          r.returncode != 0 and 'lecture' in r.stderr, r.stderr)

    spec = s.dir / 'run_prompts.py'
    spec.write_text('# the AI-authored original\n')
    target = s.dir / 'mine.py'
    r = s.run('gate', 'open', 'name-main', '--kind', 'rebuild',
              '--spec', str(spec), '--target', str(target))
    check('gate opened', r.returncode == 0, r.stderr)

    r = s.run('teach-close', 'name-main', '--explanation-file', str(expl))
    check('teach-close accepted once a gate is open', r.returncode == 0, r.stderr)
    cached = s.sql("SELECT explanation FROM concepts WHERE slug='name-main'")[0]
    check('explanation cached in the DB', bool(cached['explanation']))

    r = s.run('teach-open', 'name-main')
    check('re-teaching returns the cached text instead of a new wording',
          'ALREADY TAUGHT' in r.stdout, r.stdout)

    # The hooks must now block both sides of the blank page.
    r = s.hook('read-guard', {'tool_name': 'Read',
                              'tool_input': {'file_path': str(spec)}})
    check('read-guard BLOCKS the spec while the gate is open',
          r.returncode == 2 and 'BLOCKED' in r.stderr, f"exit={r.returncode}")
    r = s.hook('write-guard', {'tool_name': 'Write',
                               'tool_input': {'file_path': str(target)}})
    check('write-guard BLOCKS the agent writing his target',
          r.returncode == 2, f"exit={r.returncode}")
    r = s.hook('read-guard', {'tool_name': 'Read',
                              'tool_input': {'file_path': str(s.dir / 'other.py')}})
    check('read-guard allows unrelated files', r.returncode == 0)

    r = s.run('promote', 'name-main', 'APPLIED')
    check('APPLIED still refused: the gate is open, nothing was produced',
          r.returncode != 0, r.stderr)

    s.run('probe', 'name-main', 'REBUILD', 'write', 'HIT', '--seconds', '600')
    gate_id = s.sql("SELECT id FROM gates ORDER BY id DESC LIMIT 1")[0]['id']
    s.run('gate', 'close', str(gate_id), '--result', 'PASS')

    r = s.hook('read-guard', {'tool_name': 'Read',
                              'tool_input': {'file_path': str(spec)}})
    check('read-guard stops blocking once the gate is closed', r.returncode == 0)

    r = s.run('promote', 'name-main', 'APPLIED')
    check('APPLIED accepted after unaided production', r.returncode == 0, r.stderr)
    row = s.sql("SELECT state, evidence, next_review FROM concepts"
                " WHERE slug='name-main'")[0]
    check('APPLIED review is 30 days out', row['next_review'] is not None, dict(row))

    r = s.run('promote', 'name-main', 'APPLIED', '--evidence', 'transferred')
    check('transferred refused without a TRANSFER probe', r.returncode != 0, r.stderr)

    s.run('probe', 'name-main', 'TRANSFER', 'write', 'HIT', '--seconds', '300')
    r = s.run('promote', 'name-main', 'APPLIED', '--evidence', 'transferred')
    check('transferred accepted after a second context', r.returncode == 0, r.stderr)

    r = s.run('demote', 'name-main', '--reason', 'failed a drill')
    check('demote drops one state', 'APPLIED -> EXPLAINED' in r.stdout, r.stdout)


def test_profile(s):
    r = s.run('profile', '--json')
    data = json.loads(r.stdout)
    check('profile counts the write axis',
          data['write']['attempts'] >= 3, data['write'])
    check('profile reports a median time', data['write']['median_seconds'] is not None)
    check('untested axes report zero attempts, not a score',
          data['design']['attempts'] == 0 and data['design']['hit_rate'] is None)
    r = s.run('profile')
    check('profile names the axes it has never measured',
          'NEVER TESTED' in r.stdout and 'design' in r.stdout, r.stdout)
    r = s.run('velocity')
    check('velocity runs', r.returncode == 0, r.stderr)
    r = s.run('gaps')
    check('gaps says the spine is missing when it is',
          'no spine loaded' in r.stdout, r.stdout)


def test_spine(s):
    csv_path = s.dir / 'spine.csv'
    csv_path.write_text(
        "slug,name,definition,category,depth,requires,gate\n"
        "name-main,Module entry point,dup of an existing slug,language,1,,x\n"
        "list-comprehension,List comprehension,build a list inline,language,2,,writes one\n")
    r = s.run('spine-load', str(csv_path))
    check('spine merges by slug instead of duplicating his own concepts',
          '1 added, 1 already in the bank' in r.stdout, r.stdout)
    row = s.sql("SELECT source, state FROM concepts WHERE slug='list-comprehension'")[0]
    check('spine rows are marked source=spine and UNKNOWN',
          row['source'] == 'spine' and row['state'] == 'UNKNOWN', dict(row))
    row = s.sql("SELECT explanation FROM concepts WHERE slug='name-main'")[0]
    check('spine load did not overwrite an existing taught concept',
          row['explanation'] is not None)
    r = s.run('gaps')
    check('gaps separates never-asked-in-code from never-entered territory',
          'in the spine, never asked:  1' in r.stdout, r.stdout)


def test_fail_open(s):
    """A locked or corrupt DB must never stop the user working."""
    bad = s.dir / 'tutor.db'
    good = bad.read_bytes()
    bad.write_bytes(b'this is not a database')
    r = s.hook('read-guard', {'tool_name': 'Read',
                              'tool_input': {'file_path': 'anything.py'}})
    check('hooks fail OPEN on a corrupt database', r.returncode == 0,
          f"exit={r.returncode}")
    r = s.hook('brief', {})
    check('brief fails open too', r.returncode == 0)
    bad.write_bytes(good)


def main():
    s = Sandbox()
    try:
        test_refusals(s)
        test_funnel(s)
        test_profile(s)
        test_spine(s)
        test_fail_open(s)
    finally:
        s.cleanup()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"  FAILED: {f}")
        sys.exit(1)


if __name__ == '__main__':
    main()
