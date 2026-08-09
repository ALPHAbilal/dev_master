# SCAN — scrape the ladder from the real codebase

Read the whole target codebase and build the concept ladder from it — **all
aspects, not just language.** Reading unfamiliar production code is itself one of
the skills being trained.

SCAN's output is **targets, not rungs**: a rung becomes real only when a MISS lands
on it. SCAN populates the shelf; UNLOCK decides what is actually climbed.

## What to scrape — all six aspects, tagged by verb

For each script, pull concepts across every category and set `concepts.verb` (not
just `category`) — the verb is what routing starves on:

| aspect (category) | verb | what to look for in the real code |
|---|---|---|
| language | implement | the constructs he must type: unpacking, comprehensions, generators |
| stdlib | implement | `json`, `pathlib`, `os.environ`, `argparse`, `asyncio` as USED here |
| pattern | reason | the shapes: stream-don't-load, resume-ledger, idempotent-write |
| failure | debug | what this code guards against: silent truncation, partial-failure |
| api | design | how it calls its dependencies: budgets, retries, concurrency, chunking |
| arch | design | the structure: load-order contracts, thin-wrapper-over-orchestrator |

**Draw the codebase before listing concepts:** a one-screen map of which script
does what and what crosses each edge. He should be able to say "roughly how this
works" — that is the SCAN deliverable and the first `understand` measurement.

## Procedure

1. Say the plan first: "reading the N scripts now, ~M min."
2. Read every script in `targets.codebase_path`. Real code only.
3. Load concepts with `verb` set:
   ```
   python3 .claude/tutor/tutor_db.py concepts <dir>
   # then correct concepts.verb from category where the first-pass guess is wrong
   ```
4. Draw the codebase map (ASCII, one screen) and show it once.
5. Advance to UNLOCK. **Do not teach and do not probe during SCAN** — teaching or
   probing here ends the measurement early.

## Rules

- SCAN reads; it does not grade. It may take at most a single `understand` probe
  ("roughly, what does this codebase do?"), optional, never blocking.
- Depth 3+ concepts park (`parked=1`) — off routing, on the shelf. UNLOCK pulls
  them only on evidence.
- Never explain a script's code here. Reading it FOR him is not the lesson;
  UNDERSTAND and UNLOCK make him read it.
