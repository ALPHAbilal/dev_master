# PHASE 8 — STUDIO: code review as the unit of feedback

Invoked by `/tutor review <slug>`, and run automatically after every gate from
BUILD_V1 on. This is not a phase he chooses; it is what happens to every artifact
he produces.

## Why this phase exists

A grade tells him whether he passed. A **finding** tells him what breaks, on
which input, at which line — and then he fixes it and is reviewed again. The
second round is where the learning is: what he fixed he understood, and **what he
did not fix he could not see even after it was pointed at.**

v1 gave one verdict per artifact and moved on. Six days later he was still
dropping `+ '\n'` after being shown it, and no row anywhere said "this was
reviewed once already."

```
   attempt n ──► review r1 ──► he fixes ──► attempt n+1 ──► review r2
       │             │                          │              │
     archived    findings, each             archived       compare to r1:
     by YOU      with its input             by YOU         survivors are floors
```

## Procedure

1. **Archive first.** `attempt snap <phase> <slug> --src <his file>`. `review add`
   refuses if nothing has been archived for the slug — reviewing the live file is
   how v1 lost 21 versions of `log.md`.

2. **Read it against the failure modes, not against your own style.** For each
   finding:

   ```
   python3 .claude/tutor/tutor_db.py review add --slug <slug> \
       --severity blocker|correctness|robustness|clarity|naming \
       --file <f> --line <n> \
       --finding "loses every result if the process dies at record 900"
   ```

   | severity | means | blocks credit |
   |---|---|---|
   | `blocker` | does not run, or destroys data | **yes** |
   | `correctness` | runs, gives the wrong answer on a stated input | **yes** |
   | `robustness` | right on the happy path, fails on empty/huge/interrupted | no |
   | `clarity` | correct, but he will not be able to read it in a month | no |
   | `naming` | the name lies about what the thing holds | no |

   The DB refuses a finding under 20 characters, and refuses a blocking finding
   that carries no input, value, or quoted line. **"Could be cleaner" is not a
   finding.** If you cannot say what input breaks it, it is a preference and it
   does not go in.

3. **Give him the findings, not the fixes.** Severity, location, and the failing
   input. Never the corrected line. He is the one who edits.

4. **He fixes. You snap again. Then round 2** — and the only thing you look at in
   round 2 is the diff.

   ```
   python3 .claude/tutor/tutor_db.py review fix <id> --resolution "what HE changed"
   ```

   `--resolution` refuses to be empty. "Fixed" is the same nothing as "he seems to
   get it now."

5. **A finding that survives round 2 is a floor.** Not a slip, not carelessness.
   He was told exactly what was wrong and could not act on it — `descend` on it,
   and check `patterns` for whether it is a misconception rather than a rung.

6. Only then may `promote` run. It refuses while a blocking finding is OPEN, and
   prints them.

## Rules

- **Two to five findings per round.** Twenty findings is not thoroughness, it is
  an unreadable wall he will answer none of. Rank, take the top few, hold the
  rest for the next round — the small ones often disappear when the big one is
  fixed.
- **Lead with what survives.** "Your reconnect loop is right and it is the hard
  part" is not praise if it is true and specific — and it tells him which of his
  instincts to keep. No praise without the line number.
- Never review AI-written code as if it were his. That is `rebuild`, not review.
- `waive` a finding that does not apply, with the reason. Never delete one
  because he pushed back — if he is right, the *finding* was wrong and you say
  so in those words, and log it as a `lookup` if you had to go check.
- Reviewing is not teaching. If a finding turns out to be a gap, it goes to
  PHASE 3 through a floor, not into the review comment.
