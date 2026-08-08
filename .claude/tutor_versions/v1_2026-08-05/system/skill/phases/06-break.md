# PHASE 6 — BREAK: hand him something wrong

Invoked by `/tutor break [slug]`.

## Why this phase exists

Every other phase starts from a clean slate and asks him to produce. Real work
does not look like that. Most of it is reading something that already exists,
deciding whether it is right, and predicting how it fails. Those are separate
faculties from writing, and until this phase existed none of them were ever
measured — a profile drawn without them is a profile with invisible holes.

## The three forms

**Broken code.** Give him a short function with a real defect: an off-by-one, a
mutable default argument, a race between two writers, a resource never closed,
an exception swallowed. He must say *what input makes it fail and what happens*
— before running it. `faculty=debug`.

**Working code, wrong design.** Nothing errors. It just cannot survive
production: a retry loop with no cap, a checkpoint written after the side
effect instead of before, an ID regenerated on every run. He must name what it
cannot survive. `faculty=design`.

**An ambiguous spec.** Two readings, both defensible. He must notice there are
two, not pick one. This is the one most people fail, and the failure is silent —
they answer confidently and never see the fork. `faculty=design`.

## Procedure

1. Draw the defect from a concept already in the bank so the probe attaches to
   something. Prefer concepts at `state >= EXPLAINED` — this tests whether the
   knowledge is real, not whether he has seen it.
2. Show the code. **Do not run it. Do not let him run it.** Prediction is the
   test; execution is the answer key.
3. He predicts: the failing input, the observable behaviour, the reason.
4. Then run it. Being right for the wrong reason is a PARTIAL, not a HIT — say
   which, and why.
5. Record with the correct faculty:
   `probe <slug> BREAK debug HIT|MISS|PARTIAL --seconds <N>`

## Rules

- Never fabricate a defect the language cannot actually produce. He will
  eventually check, and a rigged question poisons every later one.
- Prefer defects that exist in his own repo's problem space — batch APIs,
  crash-safe resume, ID preservation. Generic puzzles measure puzzle skill.
- A MISS here does not demote anything. It records a faculty gap, which is a
  different axis from the concept's state. Do not conflate them.
- Three of these is a session. It is exhausting in a way sweeps are not.
