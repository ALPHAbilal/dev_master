# PHASE 5 — TRANSFER: prove it was not a memory of one file

Invoked by `/tutor transfer <slug>`. Requires the concept to be APPLIED.

## Why this phase exists

APPLIED means he produced it unaided, once, in one place. That is real, and it
is not yet mastery. A concept learned inside one file is often a memory of that
file: the shape of the loop, the names of the variables, the order he wrote them
in. Move it and it evaporates.

Transfer is the second, later, unaided use **in a different context** — a
different file, a different problem, or a different language. It is the strongest
evidence the system records, and it buys a 90-day silence instead of 30.

The TypeScript port is the natural instrument here. Porting `run_prompts.py`
concept by concept is not a side quest; it is the transfer test for every
concept the original taught him.

## Procedure

1. Pick an APPLIED concept whose `next_review` is due, or one the port touches.
2. Set a problem that needs the same idea and shares nothing else — different
   domain, different data, different language. If he can pattern-match his old
   file, the test is contaminated.
3. Blank page. Open a gate with `--kind transfer`.
4. Record `probe <slug> TRANSFER write HIT` and then:
   `promote <slug> APPLIED --evidence transferred`
   This refuses unless the concept is already APPLIED and a TRANSFER-phase HIT
   exists.
5. On a MISS: `demote`. The APPLIED was a memory of one file, and now you know.
   That is a finding, not a setback — say so plainly and move on.

## Rules

- Never run transfer on the same day the concept reached APPLIED. Time is part
  of the test; twenty minutes later proves nothing about next month.
- Never let him see the original file. Same rule as PHASE 4, same hook.
- A failed transfer is worth more than a passed sweep. Log it and let the
  `revise` trigger fire — repeated transfer failures across a cluster are a
  `BLIND_SPOT`, not bad luck.
