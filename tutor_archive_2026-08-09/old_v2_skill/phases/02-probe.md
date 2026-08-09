# PHASE 2 — PROBE: find the floor without burning the session

Invoked by `/tutor sweep` and `/tutor descend`. Requires PHASE 1.

## The two rules everything rests on

**Recognition is not knowledge.** "Do you know X?" and "what is X?" both fail —
he has seen every construct in his repo a thousand times in code he shipped, so
recognition always says yes. Every question must demand **production** ("write
the two-line version, blank page") or **prediction** ("what prints, in what
order, and why"). A gap cannot hide from a prediction.

**His knowledge is holes at random depths, not a level.** He learned by osmosis
from AI output, so he designed admission control while not knowing `main()`.
Never infer the floor from the ceiling. Sample at depths that look insultingly
low, on purpose, and tell him that is what you are doing.

## SWEEP — breadth, no descent

Draw from `tutor_db.py sweep-next`: never-swept concepts, shallowest first.

- 10-15 questions spread across the WHOLE target, never clustered in one area.
- On a miss: record it, say nothing, move on. **Do not teach. Do not dig.**
- Cover every area before descending on any of them.
- Write one `probes` row per question (`phase='SWEEP'`, `depth_below=0`), set
  `concepts.swept_in`, leave `state` alone.
- Output: a map of hits and misses. That is the deliverable — not a lesson.

The discipline that makes this work is **silence during the sweep**. Both of you
will want to fix a miss the moment it appears. That instinct is what turns a
profile into a lecture and is why every previous attempt died.

## DESCEND — depth, only after a sweep

Descending on the first miss lets question ORDER decide what gets explored: one
corner eats the session and the rest of the map stays blank. Worse, it hides
shared roots — several misses are often one missing idea in different clothes,
and that only becomes visible once the cluster exists.

1. Cluster the misses by suspected common root.
2. Rank roots by how many misses each would explain, then by how many concepts
   it gates via `requires`. Descend on the top one, **never the first one**.
3. Ask one level lower per miss until he answers correctly. Do not explain on the
   way down — explaining ends the descent early and patches a symptom.
4. That point is the **floor**. Write a `floors` row with `explains` and
   `descents`. Teach up from there, never down.
5. Budget **2-3 descents per session**. Remaining misses become concepts to
   revisit, not detours taken now.
6. 5+ descents on one root = a foundation gap. Log it to `ladder_log` as
   `BLIND_SPOT` and make it its own rung.

## Worked example (real, 2026-07-20)

> `if __name__ == '__main__':` — what does it do? → MISS
> ↓ when Python runs a file, what is `__name__`? → MISS
> ↓ difference between `python x.py` and `import x`? → MISS
> ↓ what happens, step by step, when you type `python x.py`? → **HIT**

Floor = "executing a file". The gap was never `main()`. Teaching `main()` would
have patched one symptom and left the hole — which is exactly what happened, and
four days later he reported he still could not get the basics.

## Grading

Two states in v2: **`CANT` / `CAN`**. `SEEN` and `EXPLAINED` are gone — they
lived in the schema for 12 sessions and never once changed a decision.

`→ CAN` only through a gate (PHASE 4), `evidence=unaided`, and only with
`--copy-checked`. `assisted` never reaches `CAN`, however well he followed.
Demote as readily as promote — but a `typo` or a `fatigue` slip never demotes,
and the helper refuses if you try.

**Sweep runs once, ever.** A second sweep re-measures the same hole; v1's own
agent said so and was right.

Open the clock as the question goes on his screen, then write the answer through
the helper — it stamps the axis, subtracts the clock, and increments
`attempts`/`fails` for you:

```
python3 .claude/tutor/tutor_db.py ask <slug>                    # one live question
python3 .claude/tutor/tutor_db.py ask s1,s2,...,s15 --phase SWEEP   # one worksheet

python3 .claude/tutor/tutor_db.py probe <slug> SWEEP <faculty> HIT|MISS|PARTIAL \
    -q "<what you asked>" -a "<what he said>" \
    --error-class gap|syntax|typo|bleed|fatigue
```

**Never ask him how long he took.** `--seconds` is refused; the clock is
`now − ask`. A whole sweep is ONE `ask`, so its span belongs to the batch and is
never divided into fifteen fake per-question times — which is precisely what
happened on 2026-08-05.

`--error-class` is REQUIRED on any non-HIT: "he got it wrong" is not a finding,
which WAY it was wrong decides what happens next. `typo` and `fatigue` cost him
nothing. After 6 probes the helper watches the *measured* spans and prints a
FATIGUE warning to stderr; believe it and land the session.

`<faculty>` is one of `write read debug recall design vocabulary` — the axis the
question actually tested, not the topic it was about. "Write the two-line
version" is `write`; "what is this technique called" is `vocabulary`; "what does
this print" is `read`. A probe with the wrong faculty is worse than no probe: it
draws a false shape in PHASE 7. The helper refuses any value outside that list.

If you forgot to `ask`, the probe records `clock=unmeasured` and that is the
correct outcome. Do not repair it by asking him — an admitted hole is worth more
than a number somebody made up.

## After the descent

Finding the floor is not the end of the session. Write the `floors` row, then go
to `phases/03-teach.md`. A floor that is found and not taught is a diagnosis he
has to take somewhere else — which is the failure this whole instrument exists
to prevent.
