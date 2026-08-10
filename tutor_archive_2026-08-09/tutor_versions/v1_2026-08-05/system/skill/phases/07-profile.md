# PHASE 7 — PROFILE: the shape, not the level

Invoked by `/tutor profile`. Read-only. No teaching, no grading, no writes.

## Why this phase exists

"How good am I at coding" has no answer, and every attempt to give one has made
things worse for him. His knowledge is holes at random depths: he specified a
bounded worker pool while not knowing what `main()` was. A single number
averages that into a lie, and the lie is always demoralising in the same
direction — he reports "I can't get the basics" while shipping systems.

A profile is six numbers that cannot be averaged. Some are high, some are low,
and the point is the gap between them.

## The axes

| Faculty | What it measures | Probed by |
|---|---|---|
| `write` | produces it from a blank page | REBUILD, BUILD, SWEEP |
| `read` | says what existing code does | SWEEP, BREAK |
| `debug` | predicts the failure before it runs | BREAK |
| `recall` | states it from memory, no editor | DRILL |
| `design` | names what a design cannot survive | BREAK, DESCEND |
| `vocabulary` | gives the industry name for what he did | SWEEP, TEACH |

## Procedure

```
python3 .claude/tutor/tutor_db.py profile      # the shape
python3 .claude/tutor/tutor_db.py velocity     # the rate
python3 .claude/tutor/tutor_db.py gaps         # what has never been entered
```

Then say, in plain sentences, the three things the numbers show:

1. **The widest gap between two axes.** That gap is the finding — not the
   highest axis and not the lowest.
2. **What is unmeasured.** An axis with zero attempts is not a zero. Say
   "unmeasured", never draw it, and never let it read as weakness.
3. **One consequence.** "You can build it and you cannot yet say what breaks it"
   is worth more than any table.

## Rules

- Never produce a single number, grade, percentage, or level. Not even when
  asked directly. The answer to "what level am I" is the shape.
- Never compare him to other learners. There is no cohort in this database and
  inventing one is a fabrication.
- `velocity` is for pacing, not pressure. If it is slow, the finding is that the
  ladder is too wide (a `TOO_WIDE` revise trigger), not that he is slow.
- Do not teach in this phase. If the profile reveals a floor, that is a
  `descend`, next session.
