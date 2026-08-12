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
