# Tutor v4 — Stack Implementation Plan

> **For agentic workers:** use superpowers:subagent-driven-development or
> superpowers:executing-plans. Steps are checkboxes.

**Goal:** Replace chain+angles+assess with a hole STACK, a four-value verdict,
an outgoing-question gate, and one phase variable.

**Architecture:** Holes nest, so FOCUS becomes a stack — only the top frame is
teachable, popping replays the parent's stored question. Every judgment is one
`probes` row. Every outgoing question passes a code check for unknown terms and
inference count before it reaches the learner.

**Tech Stack:** Python 3 stdlib only (sqlite3, json, argparse, pathlib,
unittest). No new deps.

## Global Constraints

- All writes go through `tutor_db.py`. Refusals exit non-zero with the reason.
- Hooks fail OPEN on any unexpected error; only positive matches block.
- Tests use tempdirs; every store function takes an explicit `base`.
- Absolute paths in all printed commands (relative cwd broke the last session).
- Do not delete `tutor.db`. Migrations are additive + a one-shot backfill.

---

### Task 1: Schema — stack, vocab, verdict merge

**Files:**
- Modify: `.claude/tutor/schema.sql`
- Create: `.claude/tutor/migrate_v4.py`
- Test: `.claude/tutor/tests/test_schema_v4.py`

**Interfaces:**
- Produces: tables `stack_frames`, `vocab`, `utterances`; `probes` gains
  `rung`, `hole_kind`, `terms`, `question`, `answer`; `concepts` gains
  `source='hole'` support.

- [ ] **Step 1: Write failing test** — assert the new tables exist, that
  `probes` has the five new columns, and that `meta.schema_version == '4'`.

- [ ] **Step 2: Run it, confirm it fails.**

- [ ] **Step 3: Append to `schema.sql`** (all `CREATE TABLE IF NOT EXISTS`):

```sql
CREATE TABLE IF NOT EXISTS stack_frames (
  id INTEGER PRIMARY KEY,
  project_id TEXT NOT NULL,
  slug TEXT NOT NULL,
  depth INTEGER NOT NULL,
  parent_id INTEGER REFERENCES stack_frames(id),
  why TEXT,
  anchor_file TEXT, anchor_lo INTEGER, anchor_hi INTEGER,
  resume_q TEXT,                      -- parent's question, replayed on pop
  rungs TEXT NOT NULL DEFAULT '{}',   -- {predict:HIT, perturb:WEAK, ...}
  pending TEXT NOT NULL DEFAULT '[]', -- queued sibling holes
  state TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE|FROZEN|PASSED
  hop_budget INTEGER NOT NULL DEFAULT 2,
  opened_at TEXT, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS vocab (
  term TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'unknown',  -- unknown|shown|proved
  first_seen TEXT, proved_by INTEGER
);
CREATE TABLE IF NOT EXISTS utterances (
  id INTEGER PRIMARY KEY, session_id INTEGER, frame_id INTEGER,
  hops INTEGER, terms TEXT, verdict TEXT, reason TEXT, ts TEXT
);
```
  Then `ALTER TABLE probes ADD COLUMN rung TEXT` and likewise `hole_kind`,
  `terms`, `question`, `answer` — each guarded in `migrate_v4.py` by a
  `PRAGMA table_info` check so re-running is safe.

- [ ] **Step 4: Write `migrate_v4.py`** — add columns, backfill `probes.rung`
  from `probes.faculty`, copy each `assessments` row into `probes`
  (`hole_kind=gap_type`, `answer=evidence`), `DROP TABLE assessments`,
  `DROP TABLE angles`, set `schema_version='4'`.

- [ ] **Step 5: Run tests, confirm pass. Commit.**

---

### Task 2: One phase variable

**Files:**
- Modify: `.claude/tutor/tutor_hook.py:132-178`, `.claude/tutor/tutor_db.py`
- Test: `.claude/tutor/tests/test_phase.py`

**Interfaces:**
- Produces: `current_phase(con)` reads `meta.phase` only.
- Removes: `targets.phase`, `targets.unlock_gate`, `PHASE_SEQUENCE`,
  `next_phase()`, the phase copy in `.phase_gate.json`.

- [ ] **Step 1: Test** — set `meta.phase='DRILL'`, assert `current_phase()`
  returns `DRILL` and the guard points at `phases/04-drill.md`. Set an
  unknown value, assert it falls back to `SCAN` and does not raise.

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Replace the map:**

```python
PHASE_FILE = {'SCAN':'phases/01-scan.md',  'READ':'phases/02-read.md',
              'DRILL':'phases/03-drill.md','ASSEMBLE':'phases/04-assemble.md',
              'BUILD':'phases/05-build.md','SOLO':'phases/06-solo.md'}
MODE = {'SCAN':'ADVERSARY','READ':'ADVERSARY','DRILL':'ADVERSARY',
        'ASSEMBLE':'ADVERSARY','BUILD':'ALLY','SOLO':'ADVERSARY'}
def current_phase(con):
    row = con.execute("SELECT value FROM meta WHERE key='phase'").fetchone()
    p = row[0] if row else 'SCAN'
    return p if p in PHASE_FILE else 'SCAN'
```
  `.phase_gate.json` keeps `{session_id, expected, read}` only. Migrate
  `meta.phase` `FLOOR→SCAN`, `BUILD_V1→BUILD`, `BUILD_V2→SOLO`,
  `CAPSTONE→SOLO` in `migrate_v4.py`.

- [ ] **Step 4: Tests pass. Commit.**

---

### Task 3: The stack store

**Files:**
- Create: `.claude/tutor/stack.py`  (replaces `context_store.py`)
- Test: `.claude/tutor/tests/test_stack.py`

**Interfaces:**
- Produces: `top(con,pid)`, `push(con,pid,slug,why,anchor,resume_q)`,
  `pop(con,frame_id)`, `set_rung(con,frame_id,rung,result)`,
  `queue_pending(con,frame_id,terms)`, `path(con,pid) -> [slug,...]`.

- [ ] **Step 1: Tests** — (a) push twice, `top()` is the deeper frame and the
  parent is `FROZEN`; (b) `pop()` refuses while a rung is not `HIT`;
  (c) a clean `pop()` thaws the parent and returns its `resume_q`;
  (d) `queue_pending` dedupes and `pop()` refuses while `pending` is non-empty;
  (e) two `WEAK` on one rung converts it to `MISS`.

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement.** Rules that live in code, not prose:
  - `push` sets the current top to `FROZEN`, inherits `anchor_file` if the new
    frame has none, and copies the parent's live question into `resume_q`.
  - `pop` requires all four rungs `HIT` and `pending == []`, else raises with
    the exact missing items. On success: `state='PASSED'`, parent `ACTIVE`,
    write the frame JSON to `passed_context/<slug>_<ts>.json`, return
    `resume_q`.
  - `set_rung` with `WEAK` sets `hop_budget=1`; a second `WEAK` on the same
    rung writes `MISS`.

- [ ] **Step 4: Tests pass. Commit.**

---

### Task 4: `classify` — the one verdict command

**Files:**
- Modify: `.claude/tutor/tutor_db.py`
- Test: `.claude/tutor/tests/test_classify.py`

**Interfaces:**
- Consumes: Task 3's stack API.
- Produces: `classify <slug> --result HIT|WEAK|MISS|BLOCKED --rung
  predict|perturb|produce|transfer --answer TEXT [--terms a,b]`
- Removes: `assess`, `turn-brief`, `concept-pass`, `teach-open`, `teach-close`.

- [ ] **Step 1: Tests** — (a) `BLOCKED` with two terms pushes exactly one frame
  and queues the other; (b) `BLOCKED` auto-inserts unknown terms into
  `concepts` with `source='hole'`, `depth=frame.depth`, `state='CANT'`;
  (c) every result writes exactly one `probes` row; (d) `HIT` on a term sets
  `vocab.status='proved'`; (e) `WEAK` locks the rung — a later `classify` on
  the *next* rung is refused.

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement.** Refusals: unknown rung, unknown result,
  `BLOCKED` without `--terms`, classifying a slug that is not the top frame.
  Ordering for which term to push: lowest existing `concepts.depth`, tie broken
  by appearing in the frame's `anchor_lines` text. Print the new brief after.

- [ ] **Step 4: Tests pass. Commit.**

---

### Task 5: `brief` and `draft` + ship-check

**Files:**
- Modify: `.claude/tutor/tutor_db.py`, `.claude/tutor/router.py`
- Test: `.claude/tutor/tests/test_router_v4.py`,
  `.claude/tutor/tests/test_shipcheck.py`

**Interfaces:**
- Produces: `brief [--full]`, `draft --terms a,b --hops N --about <slug>`.
- `router.render(state)` returns the delta brief.

- [ ] **Step 1: Tests** — (a) `brief` prints the stack path, the frame's real
  anchor lines read from disk, rung status, pending, and the mode doctrine;
  (b) a second `brief` with no state change prints only `Δ none`;
  (c) `draft` refuses a term whose `vocab.status == 'unknown'`;
  (d) `draft` refuses `hops > frame.hop_budget`;
  (e) `draft` refuses `--about` a frozen frame; (f) an accepted draft writes an
  `utterances` row and sets each term to `shown`.

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement.** `brief` reads `anchor_file` lines
  `anchor_lo..anchor_hi` off disk every time — the code is re-printed, never
  referred to. Delete `router.py`'s `GAP_TYPES/ANGLES/FORM_QUESTIONS/
  BUCKET_KEYS` constants and `seed_registry`; the DB is the source, seeded once
  by `init`.

- [ ] **Step 4: Tests pass. Commit.**

---

### Task 6: Hooks, PROGRESS.md, phase files

**Files:**
- Modify: `.claude/tutor/tutor_hook.py`, `tutor_db.py` (`tree`, `WRITES`)
- Create: `.claude/skills/tutor_v3/phases/0{1..6}-*.md`
- Test: `.claude/tutor/tests/test_hook_v4.py`

- [ ] **Step 1: Tests** — (a) `phase-guard` prints the phase file, the MODE
  doctrine line, and the stack path in ≤10 lines; (b) `ship-check` on a Bash
  call blocks a `draft` that violates vocab or hops; (c) `PROGRESS.md` contains
  a STACK section and marks hole-sourced concepts `[h]`.

- [ ] **Step 2: Run, confirm fail.**

- [ ] **Step 3: Implement.**
  - Remove `bucket_status_message`, the auto-archive block, and
    `get_bucket`/`detect_project_id` duplication (import from `tutor_db`).
  - `GATED_CMDS = {'classify','draft','pass','promote','demote','attempt',
    'gate','review'}` — `classify` and `draft` were ungated before, which is
    why the phase file was never enforced last session.
  - `WRITES` shrinks to the commands that change state; `tree` runs on
    `classify`, `pass`, `phase`, `session` only.
  - Six phase files. ADVERSARY files carry the current LAW 0. `05-build.md`
    carries the ALLY doctrine: answer directly, pair, unblock fast, finishing
    is the product. Each file states which rungs it uses and nothing else.

- [ ] **Step 4: Tests pass. Commit.**

---

## Cutover

- [ ] Back up `tutor.db` to `tutor_versions/v3_2026-08-12/`.
- [ ] Run `migrate_v4.py`, then the full test suite.
- [ ] Seed the live stack from the current bucket: root frame `uuid`
      (`anchor` = `soufiane_prompts/prompts/run_prompts.py:469-486`), then
      push `ledger`, then `pathlib` — the two holes the last session found and
      lost. Set `meta.phase='READ'`.
- [ ] Delete `context_store.py`, `projects/*/concept_context/`,
      `projects/*/tutor_state.json`.
