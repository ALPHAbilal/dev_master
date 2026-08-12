# Tutor Context Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deterministic context router: after every learner answer, code (not AI judgment) computes from ALL system variables — phase, bucket state, per-concept teaching context — exactly which assessment questions the agent must answer, which bucket-key definitions it needs, and what the next teaching move is; delivered through DB command outputs, never through fat hooks.

**Architecture:** Three new modules around the existing `tutor_db.py`: (1) registry tables in SQLite holding every bucket key, form question, gap type, and teaching angle with `applies_when` conditions; (2) a pure-code router that filters the registry against current state and computes the next move; (3) a per-concept `concept_context/<slug>/` folder (gaps, angles, log) that is relocated to `passed_context/` when the concept passes, with the bucket wiped when the chain completes. The agent's channel is command output: `turn-brief` prints the computed slice, `assess` records the agent's forced answers and prints the updated slice. Hooks shrink to a one-line pointer.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, argparse, pathlib, unittest). No new dependencies — the tutor must run anywhere, any language being taught, any repo size.

## Global Constraints

- Language-agnostic and scale-agnostic: nothing hardcodes Python-the-taught-language or concept count; per-turn context cost is constant regardless of bank size.
- All valid values (gap types, angles, keys, questions) live in DB tables, seeded idempotently — extending the taxonomy is a DB row, never a prompt edit.
- All writes go through `tutor_db.py`; invalid writes are refused with a non-zero exit and a reason (existing house rule).
- Routing is deterministic pure code: same state in, same slice out.
- Existing behavior must not break: all current `tutor_db.py` commands, the phase-guard hook contract, and `PROGRESS.md` regeneration stay working.
- Test runner: `python3 -m unittest discover -s .claude/tutor/tests -v` (stdlib unittest, no pytest dependency).
- New files live under `.claude/tutor/`; tests under `.claude/tutor/tests/`.

## File Structure

- Create: `.claude/tutor/context_store.py` — per-concept teaching context folder lifecycle (gaps.json, angles.json, log.json; pass-relocation; bucket wipe). All functions take an explicit `base` path so tests never touch real state.
- Create: `.claude/tutor/router.py` — registry seed data + condition evaluator + `compute_slice()` (pure) + state assembly.
- Create: `.claude/tutor/tests/__init__.py`, `tests/test_context_store.py`, `tests/test_router.py`.
- Modify: `.claude/tutor/schema.sql` — five new tables: `gap_types`, `angles`, `bucket_keys`, `form_questions`, `assessments`.
- Modify: `.claude/tutor/tutor_db.py` — register subcommands `registry-seed`, `turn-brief`, `assess`, `concept-pass`; add to `DISPATCH` and `WRITES`.
- Modify: `.claude/tutor/tutor_hook.py` — `bucket_status_message()` slims to a pointer at `turn-brief`.
- Create: `.claude/skills/tutor_v3/phases/machinery/11-context-router.md` — how any phase uses the loop.

---

### Task 1: Registry schema + idempotent seed

**Files:**
- Modify: `.claude/tutor/schema.sql` (append at end, before the final `INSERT OR IGNORE INTO meta` lines is fine — file is `CREATE TABLE IF NOT EXISTS` throughout, order-independent)
- Create: `.claude/tutor/router.py` (seed data + seed function only in this task)
- Test: `.claude/tutor/tests/test_router.py` (seed tests only in this task)

**Interfaces:**
- Produces: tables `gap_types(slug, description)`, `angles(slug, description, ord)`, `bucket_keys(name, description, value_type, applies_when)`, `form_questions(slug, question, answers, applies_when, ord)`, `assessments(...)`; function `router.seed_registry(conn)` — idempotent, safe to re-run.

- [ ] **Step 1: Create the tests package and write the failing seed test**

Create empty `.claude/tutor/tests/__init__.py`, then `.claude/tutor/tests/test_router.py`:

```python
import sqlite3
import sys
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

import router  # noqa: E402


def fresh_db():
    conn = sqlite3.connect(':memory:')
    conn.executescript((TUTOR / 'schema.sql').read_text())
    return conn


class TestSeed(unittest.TestCase):
    def test_seed_populates_registry(self):
        conn = fresh_db()
        router.seed_registry(conn)
        gaps = {r[0] for r in conn.execute("SELECT slug FROM gap_types")}
        self.assertEqual(gaps, {'model', 'reason', 'application', 'tradeoff'})
        angles = [r[0] for r in conn.execute("SELECT slug FROM angles ORDER BY ord")]
        self.assertEqual(angles, ['mechanical', 'practical', 'reasoning'])
        self.assertGreaterEqual(
            conn.execute("SELECT COUNT(*) FROM form_questions").fetchone()[0], 4)
        self.assertGreaterEqual(
            conn.execute("SELECT COUNT(*) FROM bucket_keys").fetchone()[0], 6)

    def test_seed_is_idempotent(self):
        conn = fresh_db()
        router.seed_registry(conn)
        router.seed_registry(conn)
        n = conn.execute("SELECT COUNT(*) FROM gap_types").fetchone()[0]
        self.assertEqual(n, 4)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest discover -s .claude/tutor/tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'router'` (or missing tables).

- [ ] **Step 3: Append the new tables to schema.sql**

Append to `.claude/tutor/schema.sql`:

```sql
-- ---- v3: context router registry -------------------------------------------
-- The master mind lives HERE, in data, never fully in the AI's context.
-- Adding a gap type / angle / key / question is a row, not a prompt edit.
-- `applies_when` is a JSON condition evaluated by router.py (pure code):
--   {"always": true} | {"phase_in": [...]} | {"has_context": true}
--   {"open_gaps_min": 1} | {"open_misconceptions_min": 1}
--   {"current_angle": true} | {"angles_unexplored_min": 1}
-- Every present field must match (AND semantics).

CREATE TABLE IF NOT EXISTS gap_types (
    slug        TEXT PRIMARY KEY,   -- model|reason|application|tradeoff (+ future rows)
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS angles (
    slug        TEXT PRIMARY KEY,   -- mechanical|practical|reasoning (+ future rows)
    description TEXT NOT NULL,
    ord         INTEGER NOT NULL    -- default teaching order
);

CREATE TABLE IF NOT EXISTS bucket_keys (
    name         TEXT PRIMARY KEY,  -- dotted path inside bucket / context files
    description  TEXT NOT NULL,     -- one line: what it is, when to write it
    value_type   TEXT NOT NULL,     -- string|array|object|timestamp
    applies_when TEXT NOT NULL DEFAULT '{"always": true}'
);

CREATE TABLE IF NOT EXISTS form_questions (
    slug         TEXT PRIMARY KEY,
    question     TEXT NOT NULL,     -- what the AGENT must answer about the learner's answer
    answers      TEXT,              -- comma-separated valid answers; NULL = free text
    applies_when TEXT NOT NULL DEFAULT '{"always": true}',
    ord          INTEGER NOT NULL DEFAULT 0
);

-- Every answered form. This is the gap-detection audit trail: what the agent
-- concluded from each learner answer, with the evidence quoted.
CREATE TABLE IF NOT EXISTS assessments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER REFERENCES sessions(id),
    slug         TEXT NOT NULL,     -- concept under teaching
    hole         TEXT NOT NULL,     -- none|explicit|implicit
    gap_type     TEXT,              -- REQUIRED when hole != none; FK-checked in code
    demonstrated INTEGER,           -- REQUIRED when hole == none: 1 demonstrated, 0 claimed
    angle        TEXT,              -- angle being taught when this answer happened
    angle_result TEXT,              -- pass|partial|fail
    evidence     TEXT NOT NULL,     -- the learner's words, verbatim-ish
    ts           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assessments_slug ON assessments(slug);
```

- [ ] **Step 4: Create router.py with the seed data and seed function**

Create `.claude/tutor/router.py`:

```python
#!/usr/bin/env python3
"""Deterministic context router for the tutor.

The registry (bucket keys, form questions, gap types, angles) lives in the DB.
This module seeds it and computes, from current state, the exact slice the
agent needs THIS turn: which questions to answer, which keys exist for it,
and the next teaching move. Pure code — same state in, same slice out.
"""
import json

GAP_TYPES = [
    ('model', "doesn't know what the thing IS or what it produces"),
    ('reason', "knows what it does, not WHY it is built this way"),
    ('application', "knows what/why, not WHEN to reach for it"),
    ('tradeoff', "doesn't see the cost/benefit against the alternatives"),
]

ANGLES = [
    ('mechanical', "what it does: inputs, outputs, observable behavior — run it, show it", 1),
    ('practical', "where the REAL codebase uses it and what breaks without it", 2),
    ('reasoning', "why this choice: trade-offs, alternatives, when NOT to use it", 3),
]

FORM_QUESTIONS = [
    ('assess-hole',
     "Does the learner's latest answer reveal a hole — explicit ('I don't know') "
     "or implicit (their words show a wrong model)?",
     'none,explicit,implicit', '{"always": true}', 1),
    ('assess-gap',
     "If a hole: which gap type is it? (required with --gap when --hole != none)",
     'model,reason,application,tradeoff', '{"always": true}', 2),
    ('assess-demonstrated',
     "If no hole: did he DEMONSTRATE it (correct prediction/production) or just "
     "claim it? A claim is a hint, not evidence.",
     'demonstrated,claimed', '{"always": true}', 3),
    ('assess-angle-result',
     "Which angle were you teaching, and what result did this answer show for it?",
     'pass,partial,fail', '{"current_angle": true}', 4),
    ('assess-misconception',
     "Does this answer resurface a known OPEN misconception? If yes, also run: "
     "misconception hit <slug>.",
     None, '{"open_misconceptions_min": 1}', 5),
]

BUCKET_KEYS = [
    ('primary_concept', "slug of the concept the bucket is resolving", 'string',
     '{"always": true}'),
    ('chain', "discovery chain: [{concept, name, blocked_by, status}] — status is "
     "needs_teaching|teaching|passed", 'array', '{"always": true}'),
    ('status', "bucket lifecycle: in_progress|ready_archive|archived", 'string',
     '{"always": true}'),
    ('context.gaps', "concept_context/<slug>/gaps.json: [{gap, evidence, status "
     "open|closed, opened_at, closed_at}] — open a gap ONLY via `assess`, close "
     "ONLY via `assess --close-gap` after a probe proves it is gone", 'array',
     '{"has_context": true}'),
    ('context.angles', "concept_context/<slug>/angles.json: [{angle, result, ts}] "
     "— one row per teaching pass; latest row per angle is its current result",
     'array', '{"has_context": true}'),
    ('context.log', "concept_context/<slug>/log.json: [{ts, event, detail}] — the "
     "temporary teaching memory for this concept; wiped to passed_context/ on pass",
     'array', '{"has_context": true}'),
]


def seed_registry(conn):
    """Idempotent: INSERT OR REPLACE every registry row."""
    conn.executemany(
        "INSERT OR REPLACE INTO gap_types(slug, description) VALUES (?,?)", GAP_TYPES)
    conn.executemany(
        "INSERT OR REPLACE INTO angles(slug, description, ord) VALUES (?,?,?)", ANGLES)
    conn.executemany(
        "INSERT OR REPLACE INTO form_questions(slug, question, answers, applies_when, ord) "
        "VALUES (?,?,?,?,?)", FORM_QUESTIONS)
    conn.executemany(
        "INSERT OR REPLACE INTO bucket_keys(name, description, value_type, applies_when) "
        "VALUES (?,?,?,?)", BUCKET_KEYS)
    conn.commit()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s .claude/tutor/tests -v`
Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add .claude/tutor/schema.sql .claude/tutor/router.py .claude/tutor/tests/
git commit -m "tutor: add context-router registry tables and idempotent seed

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Concept context store (temporary per-concept memory + lifecycle)

**Files:**
- Create: `.claude/tutor/context_store.py`
- Test: `.claude/tutor/tests/test_context_store.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent).
- Produces (all take `base: Path` = the project dir, e.g. `.claude/tutor/projects/dev_master`):
  - `ctx_dir(base, slug) -> Path` — `base/concept_context/<slug>`
  - `has_context(base, slug) -> bool`
  - `init_context(base, slug) -> None` — creates dir + empty gaps/angles/log json files
  - `read_context(base, slug) -> dict` — `{'gaps': [...], 'angles': [...], 'log': [...]}` (empty lists when absent)
  - `open_gap(base, slug, gap, evidence) -> None` — appends `{gap, evidence, status:'open', opened_at, closed_at:None}`; if same gap already open, appends evidence to that row instead of duplicating
  - `close_gap(base, slug, gap, evidence) -> bool` — marks latest open row of that gap closed with closing evidence; False if none open
  - `log_angle(base, slug, angle, result) -> None` — appends `{angle, result, ts}`
  - `append_log(base, slug, event, detail) -> None`
  - `open_gaps(ctx) -> list[str]` — gap slugs with an open row (pure, takes the dict)
  - `angle_results(ctx) -> dict[str, str]` — latest result per angle (pure)
  - `pass_concept(base, slug) -> Path` — moves `concept_context/<slug>` to `passed_context/<slug>_<YYYYmmdd_HHMMSS>`; returns destination; raises `RuntimeError` naming each open gap if any remain

- [ ] **Step 1: Write the failing tests**

Create `.claude/tutor/tests/test_context_store.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

TUTOR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TUTOR))

import context_store as cs  # noqa: E402


class TestContextStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_and_has_context(self):
        self.assertFalse(cs.has_context(self.base, 'uuid'))
        cs.init_context(self.base, 'uuid')
        self.assertTrue(cs.has_context(self.base, 'uuid'))
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(ctx, {'gaps': [], 'angles': [], 'log': []})

    def test_gap_open_dedup_and_close(self):
        cs.init_context(self.base, 'uuid')
        cs.open_gap(self.base, 'uuid', 'model', "said uuid4 makes 12 chars")
        cs.open_gap(self.base, 'uuid', 'model', "did not know .hex output")
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(len(ctx['gaps']), 1)          # deduped, evidence merged
        self.assertIn('.hex', ctx['gaps'][0]['evidence'])
        self.assertEqual(cs.open_gaps(ctx), ['model'])
        self.assertTrue(cs.close_gap(self.base, 'uuid', 'model', "predicted hex output correctly"))
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(cs.open_gaps(ctx), [])
        self.assertFalse(cs.close_gap(self.base, 'uuid', 'model', "again"))

    def test_angle_results_latest_wins(self):
        cs.init_context(self.base, 'uuid')
        cs.log_angle(self.base, 'uuid', 'mechanical', 'fail')
        cs.log_angle(self.base, 'uuid', 'mechanical', 'pass')
        ctx = cs.read_context(self.base, 'uuid')
        self.assertEqual(cs.angle_results(ctx), {'mechanical': 'pass'})

    def test_pass_refuses_open_gaps_then_relocates(self):
        cs.init_context(self.base, 'uuid')
        cs.open_gap(self.base, 'uuid', 'reason', "no idea why 8 chars")
        with self.assertRaises(RuntimeError):
            cs.pass_concept(self.base, 'uuid')
        cs.close_gap(self.base, 'uuid', 'reason', "explained readability tradeoff unprompted")
        dest = cs.pass_concept(self.base, 'uuid')
        self.assertFalse(cs.has_context(self.base, 'uuid'))
        self.assertTrue(dest.exists())
        self.assertTrue(str(dest).startswith(str(self.base / 'passed_context')))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s .claude/tutor/tests -v`
Expected: `ModuleNotFoundError: No module named 'context_store'`.

- [ ] **Step 3: Implement context_store.py**

Create `.claude/tutor/context_store.py`:

```python
#!/usr/bin/env python3
"""Per-concept TEMPORARY teaching memory.

While a concept is being taught, everything the tutor learns about teaching it
(gaps detected, angles tried, session log) lives in concept_context/<slug>/.
On pass the folder is relocated to passed_context/ and the working copy is
gone — the bucket stays lean no matter how many thousands of concepts exist.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

FILES = ('gaps', 'angles', 'log')


def now():
    return datetime.now().isoformat(timespec='seconds')


def ctx_dir(base: Path, slug: str) -> Path:
    return Path(base) / 'concept_context' / slug


def has_context(base, slug) -> bool:
    return ctx_dir(base, slug).is_dir()


def _read(base, slug, name):
    p = ctx_dir(base, slug) / f'{name}.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            return []
    return []


def _write(base, slug, name, data):
    d = ctx_dir(base, slug)
    d.mkdir(parents=True, exist_ok=True)
    (d / f'{name}.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def init_context(base, slug):
    for name in FILES:
        if not (ctx_dir(base, slug) / f'{name}.json').exists():
            _write(base, slug, name, [])


def read_context(base, slug) -> dict:
    return {name: _read(base, slug, name) for name in FILES}


def open_gap(base, slug, gap, evidence):
    gaps = _read(base, slug, 'gaps')
    for row in gaps:
        if row['gap'] == gap and row['status'] == 'open':
            row['evidence'] += f' | {evidence}'
            _write(base, slug, 'gaps', gaps)
            return
    gaps.append({'gap': gap, 'evidence': evidence, 'status': 'open',
                 'opened_at': now(), 'closed_at': None})
    _write(base, slug, 'gaps', gaps)


def close_gap(base, slug, gap, evidence) -> bool:
    gaps = _read(base, slug, 'gaps')
    for row in gaps:
        if row['gap'] == gap and row['status'] == 'open':
            row.update(status='closed', closed_at=now())
            row['evidence'] += f' | CLOSED: {evidence}'
            _write(base, slug, 'gaps', gaps)
            return True
    return False


def log_angle(base, slug, angle, result):
    angles = _read(base, slug, 'angles')
    angles.append({'angle': angle, 'result': result, 'ts': now()})
    _write(base, slug, 'angles', angles)


def append_log(base, slug, event, detail):
    log = _read(base, slug, 'log')
    log.append({'ts': now(), 'event': event, 'detail': detail})
    _write(base, slug, 'log', log)


def open_gaps(ctx: dict) -> list:
    return [r['gap'] for r in ctx.get('gaps', []) if r['status'] == 'open']


def angle_results(ctx: dict) -> dict:
    out = {}
    for row in ctx.get('angles', []):     # later rows overwrite: latest wins
        out[row['angle']] = row['result']
    return out


def pass_concept(base, slug) -> Path:
    ctx = read_context(base, slug)
    still_open = open_gaps(ctx)
    if still_open:
        raise RuntimeError(
            f"REFUSED: gaps still open on '{slug}': {', '.join(still_open)}. "
            f"Close each with `assess {slug} --close-gap <gap>` backed by a probe.")
    src = ctx_dir(base, slug)
    dest_root = Path(base) / 'passed_context'
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.move(str(src), str(dest))
    return dest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s .claude/tutor/tests -v`
Expected: all 6 tests PASS (2 from Task 1 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add .claude/tutor/context_store.py .claude/tutor/tests/test_context_store.py
git commit -m "tutor: per-concept teaching context with pass-relocation lifecycle

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: The router — computed questions, filtered keys, next move

**Files:**
- Modify: `.claude/tutor/router.py` (add condition evaluator + `compute_slice` + `render_slice`)
- Test: `.claude/tutor/tests/test_router.py` (add router tests)

**Interfaces:**
- Consumes: registry rows from Task 1; `open_gaps`/`angle_results` shapes from Task 2.
- Produces:
  - `matches(cond: dict, state: dict) -> bool` — condition evaluator (AND semantics)
  - `load_registry(conn) -> dict` — `{'questions': [...], 'keys': [...], 'gap_types': {slug: desc}, 'angles': [(slug, desc)] ordered}`
  - `compute_slice(state, registry) -> dict` — `{'questions': [...], 'keys': [...], 'next_move': str, 'summary': str}`
  - `render_slice(slice_) -> str` — the printable turn brief
  - The `state` dict contract (assembled by the CLI in Task 4): `{'phase': str, 'slug': str|None, 'has_context': bool, 'open_gaps': [str], 'angle_results': {str: str}, 'current_angle': str|None, 'open_misconceptions': int}`

- [ ] **Step 1: Write the failing router tests**

Append to `.claude/tutor/tests/test_router.py`:

```python
def _registry(conn=None):
    conn = conn or fresh_db()
    router.seed_registry(conn)
    return router.load_registry(conn)


def _state(**over):
    base = {'phase': 'READ', 'slug': 'uuid', 'has_context': True,
            'open_gaps': [], 'angle_results': {}, 'current_angle': None,
            'open_misconceptions': 0}
    base.update(over)
    return base


class TestConditions(unittest.TestCase):
    def test_always(self):
        self.assertTrue(router.matches({'always': True}, _state()))

    def test_and_semantics(self):
        cond = {'has_context': True, 'open_gaps_min': 1}
        self.assertFalse(router.matches(cond, _state(open_gaps=[])))
        self.assertTrue(router.matches(cond, _state(open_gaps=['model'])))

    def test_current_angle_and_misconceptions(self):
        self.assertFalse(router.matches({'current_angle': True}, _state()))
        self.assertTrue(router.matches({'current_angle': True},
                                       _state(current_angle='mechanical')))
        self.assertTrue(router.matches({'open_misconceptions_min': 1},
                                       _state(open_misconceptions=2)))


class TestComputeSlice(unittest.TestCase):
    def setUp(self):
        self.reg = _registry()

    def test_questions_filtered_by_state(self):
        s = router.compute_slice(_state(), self.reg)
        slugs = [q['slug'] for q in s['questions']]
        self.assertIn('assess-hole', slugs)
        self.assertNotIn('assess-angle-result', slugs)   # no current angle
        self.assertNotIn('assess-misconception', slugs)  # none open
        s2 = router.compute_slice(_state(current_angle='practical',
                                         open_misconceptions=1), self.reg)
        slugs2 = [q['slug'] for q in s2['questions']]
        self.assertIn('assess-angle-result', slugs2)
        self.assertIn('assess-misconception', slugs2)

    def test_keys_filtered_by_context(self):
        names = [k['name'] for k in
                 router.compute_slice(_state(has_context=False), self.reg)['keys']]
        self.assertIn('primary_concept', names)
        self.assertNotIn('context.gaps', names)
        names2 = [k['name'] for k in router.compute_slice(_state(), self.reg)['keys']]
        self.assertIn('context.gaps', names2)

    def test_next_move_priorities(self):
        # 1. no context yet -> init + first angle
        m = router.compute_slice(_state(has_context=False), self.reg)['next_move']
        self.assertIn('mechanical', m)
        # 2. open gap outranks unexplored angles
        m = router.compute_slice(_state(open_gaps=['reason'],
                                        angle_results={'mechanical': 'pass'}),
                                 self.reg)['next_move']
        self.assertIn("gap 'reason'", m)
        # 3. no gaps -> next unexplored angle
        m = router.compute_slice(_state(angle_results={'mechanical': 'pass'}),
                                 self.reg)['next_move']
        self.assertIn("'practical'", m)
        # 4. failed angle must be re-taught before pass
        m = router.compute_slice(
            _state(angle_results={'mechanical': 'pass', 'practical': 'fail',
                                  'reasoning': 'pass'}), self.reg)['next_move']
        self.assertIn("'practical'", m)
        # 5. everything pass, nothing open -> concept-pass
        m = router.compute_slice(
            _state(angle_results={'mechanical': 'pass', 'practical': 'pass',
                                  'reasoning': 'pass'}), self.reg)['next_move']
        self.assertIn('concept-pass uuid', m)

    def test_render_is_plain_text(self):
        text = router.render_slice(router.compute_slice(_state(), self.reg))
        self.assertIn('NEXT MOVE', text)
        self.assertIn('assess-hole', text)
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python3 -m unittest discover -s .claude/tutor/tests -v`
Expected: Task 1/2 tests PASS; new tests FAIL with `AttributeError: module 'router' has no attribute 'matches'`.

- [ ] **Step 3: Implement the router functions**

Append to `.claude/tutor/router.py`:

```python
# ---- condition evaluator ----------------------------------------------------
# AND semantics: every field present in the condition must hold in the state.
# Unknown condition fields fail closed (return False) so a typo in a seed row
# hides a key instead of spraying it into every turn.

_CHECKS = {
    'always': lambda v, s: bool(v),
    'phase_in': lambda v, s: s.get('phase') in v,
    'has_context': lambda v, s: s.get('has_context', False) == v,
    'open_gaps_min': lambda v, s: len(s.get('open_gaps', [])) >= v,
    'open_misconceptions_min': lambda v, s: s.get('open_misconceptions', 0) >= v,
    'current_angle': lambda v, s: bool(s.get('current_angle')) == v,
    'angles_unexplored_min': lambda v, s: v <= sum(
        1 for a, _ in s.get('_angle_order', []) if a not in s.get('angle_results', {})),
}


def matches(cond: dict, state: dict) -> bool:
    for field, want in cond.items():
        check = _CHECKS.get(field)
        if check is None or not check(want, state):
            return False
    return True


def load_registry(conn) -> dict:
    return {
        'questions': [
            {'slug': r[0], 'question': r[1], 'answers': r[2],
             'applies_when': json.loads(r[3])}
            for r in conn.execute(
                "SELECT slug, question, answers, applies_when FROM form_questions "
                "ORDER BY ord")],
        'keys': [
            {'name': r[0], 'description': r[1], 'value_type': r[2],
             'applies_when': json.loads(r[3])}
            for r in conn.execute(
                "SELECT name, description, value_type, applies_when FROM bucket_keys")],
        'gap_types': dict(conn.execute("SELECT slug, description FROM gap_types")),
        'angles': [(r[0], r[1]) for r in
                   conn.execute("SELECT slug, description FROM angles ORDER BY ord")],
    }


def _next_move(state, registry) -> str:
    slug = state.get('slug')
    angle_order = registry['angles']
    results = state.get('angle_results', {})
    if not slug:
        return ("no active concept in the bucket — nothing to teach. "
                "Resolve the bucket chain first (bucket-show).")
    if not state.get('has_context'):
        first = angle_order[0][0] if angle_order else 'mechanical'
        return (f"no teaching context for '{slug}' yet — it is created by your "
                f"first `assess`. Teach angle '{first}' ({dict(angle_order).get(first, '')}) "
                f"and assess his next answer.")
    gaps = state.get('open_gaps', [])
    unexplored = [a for a, _ in angle_order if a not in results]
    failed = [a for a, _ in angle_order if results.get(a) in ('fail', 'partial')]
    if gaps:
        g = gaps[0]
        desc = registry['gap_types'].get(g, '')
        via = state.get('current_angle') or (unexplored[0] if unexplored
                                             else angle_order[0][0])
        return (f"gap '{g}' is OPEN ({desc}). Teach it via angle '{via}', then "
                f"probe with a test that would FAIL if the gap persists. Close it "
                f"with: assess {slug} --close-gap {g} --evidence \"<what he did>\".")
    if unexplored:
        a = unexplored[0]
        return (f"angle '{a}' not yet explored — teach it: "
                f"{dict(angle_order).get(a, '')}. Log the result on your next assess "
                f"with --angle {a} --angle-result pass|partial|fail.")
    if failed:
        a = failed[0]
        return (f"angle '{a}' last resulted '{results[a]}' — re-teach it from a "
                f"different example in the real code, then re-assess with "
                f"--angle {a}.")
    return (f"all angles pass and no open gaps — run: concept-pass {slug}. "
            f"Context relocates to passed_context/ and the chain advances.")


def compute_slice(state: dict, registry: dict) -> dict:
    state = dict(state, _angle_order=registry['angles'])
    questions = [q for q in registry['questions']
                 if matches(q['applies_when'], state)]
    keys = [k for k in registry['keys'] if matches(k['applies_when'], state)]
    results = state.get('angle_results', {})
    summary = (f"phase={state.get('phase')} concept={state.get('slug')} | "
               f"open_gaps={state.get('open_gaps', [])} | "
               f"angles={{{', '.join(f'{a}:{r}' for a, r in results.items()) or '-'}}}")
    return {'questions': questions, 'keys': keys,
            'next_move': _next_move(state, registry), 'summary': summary}


def render_slice(s: dict) -> str:
    lines = ["== TURN BRIEF (computed — this is your working context) ==",
             s['summary'], "",
             "ANSWER THIS FORM about the learner's latest answer (via `assess`):"]
    for q in s['questions']:
        ans = f"  [{q['answers']}]" if q['answers'] else ''
        lines.append(f"  {q['slug']}: {q['question']}{ans}")
    lines.append("")
    lines.append("KEYS you may touch right now (nothing else exists for you):")
    for k in s['keys']:
        lines.append(f"  {k['name']} ({k['value_type']}): {k['description']}")
    lines.append("")
    lines.append(f"NEXT MOVE: {s['next_move']}")
    return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s .claude/tutor/tests -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/tutor/router.py .claude/tutor/tests/test_router.py
git commit -m "tutor: deterministic router computes questions, keys, next move from state

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: CLI wiring — turn-brief, assess, concept-pass, registry-seed

**Files:**
- Modify: `.claude/tutor/tutor_db.py` — handler functions near the other bucket functions; parser registrations inside `build_parser()` (after the `bucket-archive` line at `tutor_db.py:2583`); entries in `DISPATCH` and `WRITES` (around `tutor_db.py:2789-2846`)

**Interfaces:**
- Consumes: `router.seed_registry/load_registry/compute_slice/render_slice` (Tasks 1+3); `context_store` functions (Task 2); existing helpers in tutor_db.py: `detect_project_id()`, `read_bucket()`, `write_bucket()`, `bucket_path()`, and its DB connection helper (find it: `grep -n "def con\|sqlite3.connect" .claude/tutor/tutor_db.py` — reuse the existing one, do not open a second pattern).
- Produces CLI commands:
  - `registry-seed` — applies schema + seeds registry
  - `turn-brief` — prints `render_slice(compute_slice(assembled_state))`
  - `assess <slug> --hole none|explicit|implicit [--gap G] [--demonstrated|--claimed] [--angle A --angle-result R] [--close-gap G] --evidence "..."` — validates, writes assessment row + context files, prints the UPDATED slice
  - `concept-pass <slug>` — refuses on open gaps / unexplored / failed angles; relocates context; advances chain; marks bucket `ready_archive` when all passed

- [ ] **Step 1: Read the existing patterns you must reuse**

Run: `grep -n "def bucket_show\|def bucket_archive\|def connect\|def _con\|sqlite3.connect\|def now(" .claude/tutor/tutor_db.py`
Read those functions. Reuse the file's own connection helper and `now()`; match its print style (plain text, two-space indents).

- [ ] **Step 2: Add the handler functions**

Add to `tutor_db.py`, next to `bucket_show`/`bucket_archive` (imports `import router` and `import context_store` go at the top with the other imports; `sys.path` already contains the tutor dir when run as a script since both modules sit beside `tutor_db.py`):

```python
def _project_base():
    return PROJECTS_DIR / detect_project_id()


def _assemble_state(conn, slug=None):
    """Everything the router needs, gathered from ALL system variables."""
    bucket = read_bucket()
    slug = slug or bucket.get('primary_concept')
    phase = conn.execute("SELECT value FROM meta WHERE key='phase'").fetchone()
    phase = phase[0] if phase else 'FLOOR'
    base = _project_base()
    ctx = context_store.read_context(base, slug) if (
        slug and context_store.has_context(base, slug)) else {}
    open_mis = conn.execute(
        "SELECT COUNT(*) FROM misconceptions WHERE state='OPEN'").fetchone()[0]
    angles = context_store.angle_results(ctx) if ctx else {}
    current = None
    if ctx:
        rows = ctx.get('angles', [])
        if rows and rows[-1]['result'] in ('partial', 'fail'):
            current = rows[-1]['angle']       # still working that angle
    return {'phase': phase, 'slug': slug,
            'has_context': bool(ctx),
            'open_gaps': context_store.open_gaps(ctx) if ctx else [],
            'angle_results': angles, 'current_angle': current,
            'open_misconceptions': open_mis}


def registry_seed(args):
    conn = connect()                       # use the file's real helper name
    conn.executescript(SCHEMA.read_text())
    router.seed_registry(conn)
    print("registry seeded: gap_types, angles, form_questions, bucket_keys")


def turn_brief(args):
    conn = connect()
    state = _assemble_state(conn, getattr(args, 'slug', None))
    print(router.render_slice(router.compute_slice(state, router.load_registry(conn))))


def assess(args):
    conn = connect()
    reg = router.load_registry(conn)
    if args.hole not in ('none', 'explicit', 'implicit'):
        sys.exit(f"REFUSED: --hole must be none|explicit|implicit, got '{args.hole}'")
    if args.hole != 'none' and not args.gap:
        sys.exit("REFUSED: a hole needs a gap type. Add --gap "
                 f"{{{'|'.join(reg['gap_types'])}}} — which KIND of hole is it?")
    if args.gap and args.gap not in reg['gap_types']:
        sys.exit(f"REFUSED: unknown gap '{args.gap}'. Valid: {', '.join(reg['gap_types'])}")
    if args.hole == 'none' and args.demonstrated is None and not args.close_gap:
        sys.exit("REFUSED: no hole claimed — was it --demonstrated or --claimed? "
                 "A claim is a hint; only demonstration is evidence.")
    if args.angle and args.angle not in dict(reg['angles']):
        sys.exit(f"REFUSED: unknown angle '{args.angle}'. "
                 f"Valid: {', '.join(a for a, _ in reg['angles'])}")
    if args.angle and args.angle_result not in ('pass', 'partial', 'fail'):
        sys.exit("REFUSED: --angle needs --angle-result pass|partial|fail")

    base = _project_base()
    context_store.init_context(base, args.slug)
    sid = current_session_id(conn)         # reuse the file's real helper for this
    conn.execute(
        "INSERT INTO assessments(session_id, slug, hole, gap_type, demonstrated, "
        "angle, angle_result, evidence, ts) VALUES (?,?,?,?,?,?,?,?,?)",
        (sid, args.slug, args.hole, args.gap,
         args.demonstrated, args.angle, args.angle_result, args.evidence, now()))
    conn.commit()

    if args.hole != 'none':
        context_store.open_gap(base, args.slug, args.gap, args.evidence)
    if args.close_gap:
        if not context_store.close_gap(base, args.slug, args.close_gap, args.evidence):
            sys.exit(f"REFUSED: no open gap '{args.close_gap}' on '{args.slug}'")
    if args.angle:
        context_store.log_angle(base, args.slug, args.angle, args.angle_result)
    context_store.append_log(base, args.slug, 'assess',
                             f"hole={args.hole} gap={args.gap} "
                             f"angle={args.angle}:{args.angle_result} | {args.evidence}")
    print(f"assessed '{args.slug}'.\n")
    turn_brief(argparse.Namespace(slug=args.slug))     # the updated slice IS the reply


def concept_pass(args):
    conn = connect()
    base = _project_base()
    state = _assemble_state(conn, args.slug)
    reg = router.load_registry(conn)
    unexplored = [a for a, _ in reg['angles'] if a not in state['angle_results']]
    failed = [a for a, r in state['angle_results'].items() if r != 'pass']
    if state['open_gaps']:
        sys.exit(f"REFUSED: open gaps on '{args.slug}': {', '.join(state['open_gaps'])}")
    if unexplored:
        sys.exit(f"REFUSED: angles never explored on '{args.slug}': {', '.join(unexplored)}")
    if failed:
        sys.exit(f"REFUSED: angles not at pass on '{args.slug}': {', '.join(failed)}")
    dest = context_store.pass_concept(base, args.slug)
    bucket = read_bucket()
    for entry in bucket.get('chain', []):
        if entry['concept'] == args.slug:
            entry['status'] = 'passed'
    if all(e.get('status') == 'passed' for e in bucket.get('chain', [])):
        bucket['status'] = 'ready_archive'   # existing hook archives + wipes it
    write_bucket(bucket)
    print(f"'{args.slug}' PASSED. context -> {dest}")
    print(f"bucket: {bucket.get('status')}")
```

Two names above are placeholders for the file's real helpers and MUST be replaced during implementation with what Step 1's grep found: `connect()` (the DB connection helper) and `current_session_id(conn)` (however existing commands like `probe` obtain the session id — copy that exact mechanism).

- [ ] **Step 3: Register parsers, DISPATCH, WRITES**

In `build_parser()` after the `bucket-archive` line (`tutor_db.py:2583`):

```python
    sub.add_parser('registry-seed', help='create + seed the context-router registry')
    s = sub.add_parser('turn-brief', help='computed context slice for THIS turn')
    s.add_argument('slug', nargs='?', default=None)
    s = sub.add_parser('assess', help='answer the computed form about his latest answer')
    s.add_argument('slug')
    s.add_argument('--hole', required=True)
    s.add_argument('--gap', default=None)
    s.add_argument('--demonstrated', dest='demonstrated', action='store_const', const=1)
    s.add_argument('--claimed', dest='demonstrated', action='store_const', const=0)
    s.add_argument('--angle', default=None)
    s.add_argument('--angle-result', default=None)
    s.add_argument('--close-gap', default=None)
    s.add_argument('--evidence', required=True)
    s = sub.add_parser('concept-pass', help='close a concept: relocate context, advance chain')
    s.add_argument('slug')
```

In `DISPATCH`:

```python
    'registry-seed': registry_seed,
    'turn-brief': turn_brief,
    'assess': assess,
    'concept-pass': concept_pass,
```

In `WRITES` add: `'assess', 'concept-pass', 'registry-seed'`.

- [ ] **Step 4: Seed and smoke-test against the real project**

```bash
python3 .claude/tutor/tutor_db.py registry-seed
python3 .claude/tutor/tutor_db.py turn-brief
```

Expected: turn-brief prints the slice for the live bucket (`concept=uuid`, `has_context` false → next move says "teach angle 'mechanical'"), and does NOT print `assess-angle-result` or `assess-misconception` unless applicable. Then:

```bash
python3 .claude/tutor/tutor_db.py assess uuid --hole implicit --gap model \
  --evidence "said uuid4 generates 12 characters; did not know str output" \
  --angle mechanical --angle-result partial
python3 .claude/tutor/tutor_db.py turn-brief
```

Expected: second brief shows `open_gaps=['model']`, `angles={mechanical:partial}`, next move targets the model gap. Also verify a refusal exits non-zero: `python3 .claude/tutor/tutor_db.py assess uuid --hole implicit --evidence x; echo "exit=$?"` → prints REFUSED, exit=1. Finally re-run the unit suite: `python3 -m unittest discover -s .claude/tutor/tests -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/tutor/tutor_db.py
git commit -m "tutor: wire turn-brief/assess/concept-pass CLI onto the context router

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Slim the hook — pointer, not payload

**Files:**
- Modify: `.claude/tutor/tutor_hook.py:57-78` (`bucket_status_message`)

**Interfaces:**
- Consumes: nothing new — the hook keeps reading the bucket file only to decide IF a pointer is needed.
- Produces: hook messages that never carry bucket detail, only the instruction to run `turn-brief`. The `ready_archive` auto-archive block at `tutor_hook.py:320-349` stays untouched.

- [ ] **Step 1: Replace the message bodies**

In `bucket_status_message` replace the `in_progress` branches (both the "almost done" and "active" variants, `tutor_hook.py:70-75`) with a single return:

```python
            return ("📌 BUCKET ACTIVE — before tutoring this turn run:\n"
                    "   python3 .claude/tutor/tutor_db.py turn-brief\n"
                    "   (computed brief: the form to answer, the keys that exist "
                    "for you, and the next move)")
```

Leave the `complete`/`ready_archive` branch as is. Do not add any new state reads to the hook — detail now lives in command output by design.

- [ ] **Step 2: Verify the hook still runs clean**

Run: `echo '{}' | python3 .claude/tutor/tutor_hook.py` (check first how the hook is invoked: `grep -n "tutor_hook" .claude/settings.json .claude/settings.local.json` and mimic that invocation with a minimal stdin payload). Expected: exits 0, output contains the `turn-brief` pointer, no traceback.

- [ ] **Step 3: Commit**

```bash
git add .claude/tutor/tutor_hook.py
git commit -m "tutor: hook carries a pointer to turn-brief, not bucket payload

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Machinery doc — how any phase runs the loop

**Files:**
- Create: `.claude/skills/tutor_v3/phases/machinery/11-context-router.md`

**Interfaces:**
- Consumes: the CLI surface from Task 4.
- Produces: the one page an agent in ANY phase follows to run the assess loop; phase files keep governing WHAT to teach, this governs HOW state flows.

- [ ] **Step 1: Write the doc**

Create `.claude/skills/tutor_v3/phases/machinery/11-context-router.md`:

```markdown
# CONTEXT ROUTER — the assess loop (any phase)

The bucket's teaching intelligence is COMPUTED, not remembered. You never
need the full schema of keys, gap types, or angles: the DB hands you the
exact slice for this moment, every time you touch it.

## The loop, every learner answer

1. `python3 .claude/tutor/tutor_db.py turn-brief`
   You get: the FORM (which questions to answer about his answer), the KEYS
   that exist for you right now, and the NEXT MOVE. Nothing else exists.
2. Judge his answer against the form, then record it in one call:
   `assess <slug> --hole none|explicit|implicit [--gap <type>]
        [--demonstrated|--claimed] [--angle <a> --angle-result pass|partial|fail]
        [--close-gap <type>] --evidence "<his words>"`
   The command REFUSES incoherent answers (a hole without a gap type, an
   unknown angle) and prints the UPDATED slice — that output is your next
   instruction. Follow its NEXT MOVE.
3. When the slice says so — and only then — run `concept-pass <slug>`.
   It refuses while gaps are open or angles are unexplored/failed. On pass,
   the concept's context folder relocates to `passed_context/` and the chain
   advances; when the whole chain has passed, the bucket archives and wipes.

## Rules

- Gaps open ONLY through `assess`, and close ONLY through `--close-gap`
  backed by a probe that would have FAILED if the gap persisted (LAW 0.3).
- A claim is a hint; demonstration is evidence (`--claimed` vs `--demonstrated`).
- Angles are taught in the order the brief offers them; a `fail`/`partial`
  angle is re-taught from a DIFFERENT example in the real code.
- Never write bucket or context files by hand — the commands are the only pen.
```

- [ ] **Step 2: Verify the referenced commands all exist**

Run: `python3 .claude/tutor/tutor_db.py turn-brief && python3 .claude/tutor/tutor_db.py concept-pass uuid; echo "exit=$?"`
Expected: turn-brief prints; concept-pass REFUSES (uuid still has open work) with exit=1 — proving the doc's promises are enforced, not prose.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/tutor_v3/phases/machinery/11-context-router.md
git commit -m "tutor: document the assess loop for all phases

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Gap Registry per concept → `gaps.json` + `assessments` table (Tasks 1, 2, 4) ✓
- Gap categorization taxonomy → `gap_types` table, extensible by row (Task 1) ✓
- Temporary concept context, emptied on pass, relocated to passed context → `context_store.pass_concept` (Task 2) ✓ ; bucket wipe on chain completion reuses the existing `ready_archive` hook path (Task 4) ✓
- Bucket keys defined with descriptions, discoverable → `bucket_keys` table + filtered rendering (Tasks 1, 3) ✓
- Questions-form itself computed per turn from all variables → `form_questions.applies_when` + `compute_slice` (Tasks 1, 3) ✓
- Deterministic code decides what the AI sees; no massive hook context → router is pure code (Task 3); hook slimmed to a pointer (Task 5); channel is command output (Task 4) ✓
- Language/scale agnostic → stdlib only, constant per-turn slice, taxonomy in DB rows ✓

**Placeholder scan:** Two intentional adapt-on-site names in Task 4 (`connect()`, `current_session_id()`) are explicitly flagged with the grep that resolves them — the file's real helpers must be discovered at execution time since they exist but weren't fully read. No other TBDs.

**Type consistency:** `state` dict contract defined once (Task 3 Interfaces) and consumed by `_assemble_state` (Task 4); `context_store` signatures in Task 2 match every call site in Task 4; `render_slice`/`compute_slice`/`load_registry` names consistent across Tasks 3, 4, 6.
