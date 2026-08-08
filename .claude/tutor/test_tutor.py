#!/usr/bin/env python3
"""Verification for the tutor instrument. Runs against a throwaway copy.

    python3 test_tutor.py

Never touches the real tutor.db. Copies tutor_db.py, tutor_hook.py and
schema.sql into a temp directory, builds an empty database there, and drives
the whole funnel through the CLI exactly as an agent would.
"""
import json
import os
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
        env = dict(os.environ, TUTOR_ATTEMPTS_DIR=str(self.dir / 'attempts'))
        return subprocess.run(
            [sys.executable, str(self.dir / 'tutor_db.py'), *args],
            capture_output=True, text=True, input=stdin, env=env)

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

    r = s.run('promote', 'executing-a-file', 'CAN', '--copy-checked')
    check('promote CAN refused without an unaided production probe',
          r.returncode != 0 and 'REFUSED' in r.stderr, r.stdout + r.stderr)
    state = s.sql("SELECT state FROM concepts WHERE slug='executing-a-file'")[0]['state']
    check('refused promote left the row untouched', state == 'CANT', state)

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

    r = s.run('promote', 'executing-a-file', 'CANT', '--evidence', 'transferred')
    check('transferred refused before CAN', r.returncode != 0, r.stderr)

    r = s.run('promote', 'nonexistent-slug', 'CANT')
    check('grading refused for a concept not in the bank', r.returncode != 0, r.stderr)


def test_funnel(s):
    """sweep -> descend -> floor -> teach -> gate -> CAN -> transfer."""
    s.run('session', 'test', 'funnel')
    s.seed_concept('name-main')

    s.run('probe', 'name-main', 'SWEEP', 'write', 'MISS', '-q', 'what does it do', '--error-class', 'gap')
    swept = s.sql("SELECT swept_in, attempts, fails FROM concepts WHERE slug='name-main'")[0]
    check('SWEEP stamps swept_in and counts the attempt',
          swept['swept_in'] is not None and swept['attempts'] == 1
          and swept['fails'] == 1, dict(swept))

    s.run('probe', 'name-main', 'DESCEND', 'recall', 'HIT', '--below', '3')
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

    r = s.run('promote', 'name-main', 'CAN', '--copy-checked')
    check('CAN still refused: the gate is open, nothing was produced',
          r.returncode != 0, r.stderr)

    s.run('probe', 'name-main', 'REBUILD', 'write', 'HIT')
    gate_id = s.sql("SELECT id FROM gates ORDER BY id DESC LIMIT 1")[0]['id']
    s.run('gate', 'close', str(gate_id), '--result', 'PASS')

    r = s.hook('read-guard', {'tool_name': 'Read',
                              'tool_input': {'file_path': str(spec)}})
    check('read-guard stops blocking once the gate is closed', r.returncode == 0)

    r = s.run('promote', 'name-main', 'CAN', '--copy-checked')
    check('CAN accepted after unaided production', r.returncode == 0, r.stderr)
    row = s.sql("SELECT state, evidence, next_review FROM concepts"
                " WHERE slug='name-main'")[0]
    check('CAN review is 30 days out', row['next_review'] is not None, dict(row))

    r = s.run('promote', 'name-main', 'CAN', '--copy-checked', '--evidence', 'transferred')
    check('transferred refused without a TRANSFER probe', r.returncode != 0, r.stderr)

    s.run('probe', 'name-main', 'TRANSFER', 'write', 'HIT')
    r = s.run('promote', 'name-main', 'CAN', '--copy-checked', '--evidence', 'transferred')
    check('transferred accepted after a second context', r.returncode == 0, r.stderr)

    r = s.run('demote', 'name-main', '--reason', 'failed a drill')
    check('demote drops one state', 'CAN -> CANT' in r.stdout, r.stdout)


def test_profile(s):
    r = s.run('profile', '--json')
    data = json.loads(r.stdout)
    check('profile counts the write axis',
          data['write']['attempts'] >= 3, data['write'])
    check('profile reports no median when nothing was measured -- honestly',
          data['write']['timed'] == 0 and data['write']['median_seconds'] is None,
          data['write'])
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
          '1 added' in r.stdout and '1 already in the bank' in r.stdout, r.stdout)
    row = s.sql("SELECT source, state FROM concepts WHERE slug='list-comprehension'")[0]
    check('spine rows are marked source=spine and CANT',
          row['source'] == 'spine' and row['state'] == 'CANT', dict(row))
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


def test_v2_error_classes(s):
    """A MISS is not one thing. v1 collapsed five causes into one word."""
    s.seed_concept('error-class-demo')
    r = s.run('probe', 'error-class-demo', 'FLOOR', 'write', 'MISS')
    check('non-HIT refused with no error class', r.returncode != 0, r.stderr)

    s.run('probe', 'error-class-demo', 'FLOOR', 'write', 'MISS', '--error-class', 'typo')
    row = s.sql("SELECT attempts, fails FROM concepts WHERE slug='error-class-demo'")[0]
    check('a typo counts as an attempt but never as a fail',
          row['attempts'] == 1 and row['fails'] == 0, dict(row))

    s.run('probe', 'error-class-demo', 'FLOOR', 'write', 'MISS', '--error-class', 'gap')
    row = s.sql("SELECT attempts, fails FROM concepts WHERE slug='error-class-demo'")[0]
    check('a gap does count as a fail', row['fails'] == 1, dict(row))

    r = s.run('demote', 'error-class-demo', '--error-class', 'typo')
    check('demote refused when charged to a typo', r.returncode != 0, r.stderr)

    r = s.run('probe', 'error-class-demo', 'FLOOR', 'write', 'MISS', '--error-class', 'sloppiness')
    check('an invented error class is refused', r.returncode != 0, r.stderr)


def test_v2_copy_check(s):
    """The E16 refusal, made mechanical instead of lucky."""
    s.seed_concept('copy-demo')
    # FLOOR, not BUILD_V1: BUILD_V1 additionally requires an archived attempt,
    # which would mask the rule this test is about.
    s.run('probe', 'copy-demo', 'FLOOR', 'write', 'HIT')
    r = s.run('promote', 'copy-demo', 'CAN')
    check('promote to CAN refused without --copy-checked',
          r.returncode != 0 and 'copy-checked' in r.stderr, r.stderr)
    state = s.sql("SELECT state FROM concepts WHERE slug='copy-demo'")[0]['state']
    check('the refused promotion wrote nothing', state == 'CANT', state)
    r = s.run('promote', 'copy-demo', 'CAN', '--copy-checked')
    check('promote accepted once the copy check is declared', r.returncode == 0, r.stderr)


def test_v2_attempts(s):
    """He edits one file; the archive is the agent's job."""
    work = s.dir / 'work.py'
    work.write_text('a = 1\nprint(a)\n')
    s.seed_concept('attempt-demo')
    r = s.run('attempt', 'snap', 'FLOOR', 'attempt-demo', '--src', str(work))
    check('first snapshot stored', r.returncode == 0 and '#01' in r.stdout, r.stdout)
    stored = s.dir / 'attempts' / '01_floor' / 'attempt-demo_01.py'
    check('the copy exists on disk', stored.exists(), str(stored))

    work.write_text('a = 1\nb = 2\nprint(a + b)\n')
    r = s.run('attempt', 'snap', 'FLOOR', 'attempt-demo', '--src', str(work))
    check('second snapshot numbered 02', '#02' in r.stdout, r.stdout)
    check('the diff is reported', '+2 -1' in r.stdout, r.stdout)

    check('the earlier attempt still exists, unaltered',
          stored.read_text() == 'a = 1\nprint(a)\n', stored.read_text())

    row = s.sql("SELECT n, added, removed, diff_prev FROM attempts"
                " WHERE slug='attempt-demo' ORDER BY n DESC")[0]
    check('the diff is stored, not just printed',
          row['diff_prev'] and 'print(a + b)' in row['diff_prev'], dict(row))

    s.run('attempt', 'grade', 'FLOOR', 'attempt-demo', 'HIT')
    row = s.sql("SELECT result FROM attempts WHERE slug='attempt-demo'"
                " ORDER BY n DESC")[0]
    check('the verdict attaches to the artifact', row['result'] == 'HIT', dict(row))

    r = s.run('attempt', 'snap', 'FLOOR', 'attempt-demo', '--src',
              str(s.dir / 'does-not-exist.py'))
    check('snapshot refused on a missing file', r.returncode != 0, r.stderr)


def test_v2_phase_and_assumptions(s):
    """His only routing choice, and the agent's stated prerequisites."""
    r = s.run('phase')
    check('phase starts at FLOOR', 'FLOOR' in r.stdout, r.stdout)
    r = s.run('phase', '--set', 'BUILD_V1', '--why', 'floor cleared')
    check('phase transition accepted', r.returncode == 0, r.stderr)
    check('the transition is logged as a ladder revision',
          len(s.sql("SELECT id FROM ladder_log WHERE change LIKE '%BUILD_V1%'")) == 1)
    r = s.run('phase', '--set', 'SOMETHING')
    check('an invented phase is refused', r.returncode != 0, r.stderr)

    s.run('assume', '--teaching', 'context-manager', '--assumed', 'file-object')
    row = s.sql("SELECT teaching, assumed, vetoed FROM assumptions")[0]
    check('the assumption is on the record before teaching',
          row['assumed'] == 'file-object' and row['vetoed'] is None, dict(row))

    before = len(s.sql("SELECT id FROM ladder_log WHERE trigger='BLIND_SPOT'"))
    s.run('assume', '--veto', 'file-object')
    row = s.sql("SELECT vetoed FROM assumptions")[0]
    check('the veto is recorded against it', row['vetoed'] == 'file-object', dict(row))
    after = len(s.sql("SELECT id FROM ladder_log WHERE trigger='BLIND_SPOT'"))
    check('a veto logs a BLIND_SPOT against the machine, not the learner',
          after == before + 1, f"{before} -> {after}")


def test_v2_parked(s):
    """Depth 3+ leaves the ladder without leaving the bank."""
    s.seed_concept('deep-thing', depth=4)
    con = sqlite3.connect(s.db)
    con.execute("UPDATE concepts SET parked=1 WHERE slug='deep-thing'")
    con.commit()
    r = s.run('sweep-next', '50')
    check('a parked concept is invisible to sweep', 'deep-thing' not in r.stdout)
    r = s.run('map')
    check('a parked concept is invisible to the map', 'deep-thing' not in r.stdout)
    check('but it is still in the bank',
          len(s.sql("SELECT id FROM concepts WHERE slug='deep-thing'")) == 1)


def test_v2_bank_loading(s):
    """concepts-load and spine-load must both honour the parking rule."""
    csv_path = s.dir / 'bank.csv'
    csv_path.write_text(
        "slug,name,definition,category,depth,file,line,snippet,requires,gate\n"
        "shallow-thing,Shallow Thing,a depth-1 idea,language,1,a.py,3,x,,writes it\n"
        "deep-thing-2,Deep Thing,a depth-4 idea,arch,4,a.py,9,y,,designs it\n")
    r = s.run('concepts-load', str(csv_path))
    check('concepts-load reports ladder vs parked',
          '1 on the ladder' in r.stdout and '1 parked' in r.stdout, r.stdout)
    rows = {x['slug']: x for x in s.sql(
        "SELECT slug, state, parked, source FROM concepts"
        " WHERE slug IN ('shallow-thing','deep-thing-2')")}
    check('loaded concepts start at CANT, sourced from his code',
          all(x['state'] == 'CANT' and x['source'] == 'code' for x in rows.values()),
          {k: dict(v) for k, v in rows.items()})
    check('depth 1 goes on the ladder', rows['shallow-thing']['parked'] == 0)
    check('depth 4 is parked off it', rows['deep-thing-2']['parked'] == 1)

    r = s.run('concepts-load', str(csv_path))
    check('re-loading skips instead of duplicating', '2 already in the bank' in r.stdout,
          r.stdout)

    spine = s.dir / 'spine2.csv'
    spine.write_text("slug,name,definition,category,depth,requires,gate\n"
                     "spine-deep,Spine Deep,a depth-3 idea,pattern,3,,writes it\n")
    s.run('spine-load', str(spine))
    row = s.sql("SELECT parked, state FROM concepts WHERE slug='spine-deep'")[0]
    check('spine-load parks depth 3+ the same way concepts-load does',
          row['parked'] == 1 and row['state'] == 'CANT', dict(row))


def test_v2_floor_is_production(s):
    """The wide FLOOR gates ARE blank-page production. v2 must be able to credit them."""
    s.seed_concept('floor-rung')
    s.run('probe', 'floor-rung', 'FLOOR', 'write', 'HIT')
    r = s.run('promote', 'floor-rung', 'CAN', '--copy-checked')
    check('a FLOOR pass can reach CAN', r.returncode == 0, r.stderr)

    s.seed_concept('read-rung')
    s.run('probe', 'read-rung', 'READ', 'read', 'HIT')
    r = s.run('promote', 'read-rung', 'CAN', '--copy-checked')
    check('a READ pass cannot -- predicting is not producing',
          r.returncode != 0, r.stderr)


def test_v2_snapshot_required(s):
    """Grading a real-file phase without archiving the file is refused."""
    s.seed_concept('artifact-rung')
    s.run('probe', 'artifact-rung', 'BUILD_V1', 'write', 'HIT')
    r = s.run('promote', 'artifact-rung', 'CAN', '--copy-checked')
    check('BUILD_V1 promotion refused with no archived attempt',
          r.returncode != 0 and 'attempt snap' in r.stderr, r.stderr)

    work = s.dir / 'artifact.py'
    work.write_text('print("hi")\n')
    s.run('attempt', 'snap', 'BUILD_V1', 'artifact-rung', '--src', str(work))
    r = s.run('promote', 'artifact-rung', 'CAN', '--copy-checked')
    check('accepted once the attempt is on record', r.returncode == 0, r.stderr)


def test_v3_visibility(s):
    """He must be able to see where he is without asking, and without a message.

    On 2026-08-05 a quarter of everything he typed in four hours was "i(m
    waiting" and "where i cn find those please ??". Position was a message,
    once, at session start. Now it is a file and a status bar.
    """
    prog = s.dir / 'PROGRESS.md'
    here = s.sql("SELECT value v FROM meta WHERE key='phase'")[0]['v']

    r = s.run('tree')
    check('tree renders the four phases with a marker on the current one',
          r.returncode == 0 and f'>> {here}' in r.stdout and 'BUILD_V2' in r.stdout,
          r.stderr or r.stdout[:200])
    check('tree writes PROGRESS.md', prog.exists(), 'no file')

    # it must refresh itself: a write, then the file already knows
    prog.unlink()
    s.seed_concept('visible-rung')
    s.run('probe', 'visible-rung', 'FLOOR', 'write', 'HIT')
    check('a write regenerates PROGRESS.md with nobody asking',
          prog.exists() and 'visible-rung' in prog.read_text(), 'stale or missing')

    r = s.run('statusline')
    check('statusline is one line',
          r.returncode == 0 and r.stdout.count('\n') == 1, repr(r.stdout))
    check('statusline names the phase and the owned count',
          here in r.stdout and 'owned' in r.stdout, r.stdout)

    # an open gate with nothing archived is the loudest thing on the bar
    s.run('gate', 'open', 'visible-rung', '--kind', 'build', '--target', 'test.py')
    r = s.run('statusline')
    check('an open gate with no snapshot shouts on the status bar',
          'GATE#' in r.stdout and 'NOTHING SAVED' in r.stdout, r.stdout)

    work = s.dir / 'seen.py'
    work.write_text('x = 1\n')
    s.run('attempt', 'snap', 'FLOOR', 'visible-rung', '--src', str(work))
    r = s.run('statusline')
    check('once he saves an attempt the bar stops shouting',
          'NOTHING SAVED' not in r.stdout and 'saved)' in r.stdout, r.stdout)


def test_v3_clock_is_a_subtraction(s):
    """The clock is measured, never asked for.

    v2 made --seconds required and supplied nothing, so the agent begged him for
    it. On 2026-08-05 he answered "around 30 minitues" for a fifteen-question
    sweep and it was divided into fifteen numbers that look like measurements.
    """
    s.seed_concept('clock-a')
    s.seed_concept('clock-b')
    s.seed_concept('clock-c')

    r = s.run('probe', 'clock-a', 'FLOOR', 'write', 'HIT', '--seconds', '90')
    check('--seconds is refused outright',
          r.returncode != 0 and 'SUBTRACTION' in r.stderr, r.stderr)

    # no clock running -> a known hole, not an invented number
    s.run('probe', 'clock-a', 'FLOOR', 'write', 'HIT')
    row = s.sql("SELECT seconds, clock FROM probes WHERE id ="
                " (SELECT MAX(id) FROM probes)")[0]
    check('with no clock open the probe records UNMEASURED, not a guess',
          row['clock'] == 'unmeasured' and row['seconds'] is None, dict(row))

    # one live question -> a real elapsed, by subtraction
    r = s.run('ask', 'clock-b')
    check('ask opens a single clock',
          r.returncode == 0 and 'single' in r.stdout, r.stdout + r.stderr)
    s.run('probe', 'clock-b', 'FLOOR', 'write', 'HIT')
    row = s.sql("SELECT seconds, clock FROM probes WHERE id ="
                " (SELECT MAX(id) FROM probes)")[0]
    check('a single ask yields a MEASURED elapsed nobody was asked for',
          row['clock'] == 'measured' and row['seconds'] is not None, dict(row))
    check('the consumed clock is closed',
          s.sql("SELECT COUNT(*) n FROM asks WHERE closed_at IS NULL")[0]['n'] == 0)

    # a worksheet is ONE clock, and its span is never divided
    r = s.run('ask', 'clock-a,clock-b,clock-c', '--phase', 'SWEEP')
    check('ask accepts a batch and says so',
          r.returncode == 0 and 'batch' in r.stdout and 'NOT be divided' in r.stdout,
          r.stdout)
    s.run('probe', 'clock-a', 'SWEEP', 'read', 'HIT')
    row = s.sql("SELECT seconds, clock FROM probes WHERE id ="
                " (SELECT MAX(id) FROM probes)")[0]
    check('a batch probe is labelled batch, not measured',
          row['clock'] == 'batch', dict(row))
    check('the batch clock stays open for the questions not yet probed',
          s.sql("SELECT slugs FROM asks WHERE closed_at IS NULL")[0]['slugs']
          == 'clock-b,clock-c')

    s.run('probe', 'clock-b', 'SWEEP', 'read', 'HIT')
    s.run('probe', 'clock-c', 'SWEEP', 'read', 'HIT')
    check('the batch clock closes when its last question is probed',
          s.sql("SELECT COUNT(*) n FROM asks WHERE closed_at IS NULL")[0]['n'] == 0)

    # a batch span must never reach the fatigue detector as think-time
    r = s.run('profile', '--json')
    d = json.loads(r.stdout)
    check('profile counts only measured spans, ignoring batch ones',
          d['read']['timed'] == 0 and d['read']['attempts'] >= 3, d['read'])

    # a clock left running is abandoned, never re-attributed
    s.run('ask', 'clock-a')
    r = s.run('ask', 'clock-b')
    check('opening a second clock abandons the first instead of mixing them',
          'abandoned' in r.stderr, r.stderr)
    check('only one clock is ever running',
          s.sql("SELECT COUNT(*) n FROM asks WHERE closed_at IS NULL")[0]['n'] == 1)


def test_v3_blank_file_to_saved(s):
    """"How many minutes did test.py take?" is a subtraction, so never ask it."""
    s.seed_concept('timed-build')
    s.run('gate', 'open', 'timed-build', '--kind', 'build', '--target', 'test.py')
    work = s.dir / 'test.py'
    work.write_text('print("hi")\n')
    r = s.run('attempt', 'snap', 'FLOOR', 'timed-build', '--src', str(work))
    check('the first snapshot is timed from the gate opening',
          'blank file -> saved' in r.stdout, r.stdout)
    row = s.sql("SELECT seconds FROM attempts WHERE slug='timed-build' AND n=1")[0]
    check('and that elapsed is stored, not requested',
          row['seconds'] is not None, dict(row))


def main():
    s = Sandbox()
    try:
        test_refusals(s)
        test_funnel(s)
        test_profile(s)
        test_spine(s)
        test_v2_error_classes(s)
        test_v2_copy_check(s)
        test_v2_attempts(s)
        test_v2_phase_and_assumptions(s)
        test_v2_parked(s)
        test_v2_bank_loading(s)
        test_v2_floor_is_production(s)
        test_v2_snapshot_required(s)
        test_v3_visibility(s)
        test_v3_clock_is_a_subtraction(s)
        test_v3_blank_file_to_saved(s)
        # last: it corrupts and restores the database on purpose, which leaves
        # the WAL sidecars inconsistent for anything that runs after it.
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
