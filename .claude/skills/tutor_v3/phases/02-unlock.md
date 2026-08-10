# UNLOCK — the ladder, with the hypothesis-verify loop

Every concept SCAN scraped is unlocked here — from the **real code**, through
**many task types**, credited only after a test chosen *because it would fail if
the understanding were fake.* When the whole ladder is owned, the gate opens and
BIG BUILD begins. Not before.

UNLOCK's job is not to *explain* concepts — it is to **verify** them, and to teach
only the residue verification exposes. LAW 0 is the method.

## Task types — vary the attack

A concept is not unlocked by one question answered once. Rotate the type so he
cannot pattern-match through, and so different faculties are touched:

| task type | he does | catches |
|---|---|---|
| `question` | answers in words | recall / vocabulary — does he have the name |
| `micro-code` | writes 1–3 lines on a NEW instance | can he produce, not just recognize |
| `predict-this` | says what the real code prints/returns | does he model execution, or guess |
| `break-this` | is shown a variant and says what breaks | does he own the mechanism |
| `explain-this` | says WHY the real code is written this way | understanding vs surface |

**Draw before you explain. Fundamentals before conveniences:** what a name binds
to, what a call returns, what is on disk, before the library that hides it.

## The hypothesis-verify loop — never trust working code (LAW 0.3)

On every concept:

```
   1. read his code or answer
   2. SUSPECT: name a weak spot you actually see
   3. HYPOTHESIS: write it as a flat claim that is FALSE if he understands
        e.g. "he can copy `for k,v in d.items()` but cannot say why it unpacks"
   4. TEST: pick the CHEAPEST task above that FAILS if the hypothesis is true.
        The test must NOT be passable by copying the example in front of him —
        new values, new names, new surface.
   5. VERDICT:
        passes -> hypothesis FALSE -> credit, move on
        fails  -> CONFIRMED -> teach the residue at the floor,
                  then RE-TEST on a second new instance (transfer).
```

Record: a suspicion is `push --hypothesis` or `misconception open`; the verdict is
`push verdict` / `misconception hit`. **A concept reaches `CAN` only with
`--copy-checked` against a genuinely different instance** — the DB refuses
otherwise. Working code, or code he generated with AI, is `evidence=assisted` and
never reaches `CAN` on its own.

## Procedure

1. `due-slice` / `sweep-next` to pick the next concept, **preferring a starved
   verb** (`verb_coverage` shows which). A run of `implement` HITs is a signal to
   jump to a `reason`/`design`/`debug` concept, not to drill another sibling.
2. Probe with the cheapest task type. HIT → next (spend no minute on the known).
   MISS → run the hypothesis-verify loop, teach the residue, transfer.
3. Every non-HIT carries an `error_class`; every question opens a clock with `ask`
   (the clock is a subtraction, never a question to him).
4. Repeat until `verb_coverage` shows every non-parked concept owned.

## THE GATE — all unlocked, then build

```
python3 .claude/tutor/tutor_db.py unlock-gate <target_id>
```

Refuses to open BIG BUILD while any non-parked ladder concept is `CANT`, and prints
what remains, by verb. Parked (depth 3+) concepts do not block — they return JIT
during the build if IMPLEMENT trips on them.

## Rules

- Teach only at a floor, only after a failed verification, only the residue.
- Never teach a concept whose latest probe is a HIT (`teach-open` refuses it).
- 20/60/20: if you are explaining more than he is producing, you are breaking
  LAW 0.
- The example is always the real code. No invented toy data once SCAN has run.
