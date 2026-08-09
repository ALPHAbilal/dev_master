# PHASE 1 — CONCEPTS: build the map

Invoked by `/tutor concepts <dir>`. Produces the question bank. Nothing else in
the system works until this exists, because every later phase draws from it.

## Why this phase exists

He cannot report a gap he has no name for. He designed a bounded worker pool with
token-based admission control and did not know those words — so he could not
search for it, say it in an interview, or recognise it in someone else's code.
**Unnamed knowledge feels like no knowledge.** This phase gives every technique
already present in his own code its industry name.

It also solves unknown-unknowns without guessing: the code enumerates the
concepts. Anything in the file he cannot name is a gap. Coverage is guaranteed by
the source, not by the agent's imagination.

## Procedure

1. Read EVERY source file in `<dir>`. Not a sample. Not the docstrings.
2. Extract every distinct concept actually present:
   - `language`  — syntax and semantics (`yield`, `nonlocal`, `with`, decorators,
     truthiness, mutable default args, closures, `__name__`)
   - `stdlib`    — APIs used (`pathlib`, `json.JSONDecoder.raw_decode`, `codecs`,
     `sqlite3`, `argparse`, `re`)
   - `pattern`   — design (generator pipeline, correlation ID, checkpointing,
     idempotency, bounded worker pool, admission control, reconciliation)
   - `failure`   — how errors are handled (fail-safe default, retry, partial
     failure accounting, poison-record isolation)
   - `api`       — provider mechanics (batch endpoints, structured outputs,
     token budgets, rate limits)
   - `arch`      — how the whole thing is shaped (orchestrator, ledger, staging)
3. For each, record: `slug`, industry `name`, one-line `definition`, `category`,
   `depth` 1-5, and `file:line` where it lives IN HIS CODE with a short `snippet`.
4. `depth`: 1 = primitive a beginner meets first · 3 = intermediate · 5 = system
   architecture. Depth drives sweep order — shallow first, so coverage is broad.
5. Write the rows to a CSV, then load them through the helper — never raw SQL:

   ```
   python3 .claude/tutor/tutor_db.py concepts-load <csv>
   ```

   Columns: `slug,name,definition,category,depth,file,line,snippet,requires,gate`.
   It inserts `state='CANT'`, `swept_in=NULL`, and sets `parked=1` on anything at
   depth 3+ — off the routing ladder, still in the bank. Merge is by slug: a
   concept already there keeps its history and is never overwritten.
   Grade NOTHING here. This phase names; it does not judge.
6. Set `requires` only where genuinely true (`generator` requires `function-def`).
   A guessed prerequisite is worse than none.
7. Report: total concepts, count per category, count per depth, and **how many
   are on the ladder vs parked**. The ladder number is the one that matters — v1
   reported 241 and 216 of them were never reachable. Say the ladder number out
   loud. It is finite and it is smaller than he fears.

## Rules

- Every concept must point at real code in `<dir>`. No concept he does not
  already own. This is an inventory, not a syllabus.
- Use the name a job description would use, not a teaching name.
- Never teach in this phase. Never grade. Name and locate only.
- Regenerate only when the code changes. Never re-derive per session — a list
  that shifts each time makes coverage meaningless.
