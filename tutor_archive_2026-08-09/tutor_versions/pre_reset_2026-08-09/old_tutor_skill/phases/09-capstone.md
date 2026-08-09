# PHASE 9 — CAPSTONE: the phase with no answer key

Invoked by `/tutor capstone`. The last learner phase, and the only one where
there is no file to diff against.

## Why this phase exists

FLOOR, READ, BUILD_V1 and BUILD_V2 all have a right answer sitting on disk. They
measure **reconstruction** — real, necessary, and not the job. The job is what
happens when the requirements do not determine the program.

That is why `profile` has printed `design: never tested` since the day it was
written. It is not an oversight in the probe set. **There was nowhere for a
design probe to live**, because every gate had an answer key.

```
   BUILD_V2                          CAPSTONE
   ┌──────────────────┐              ┌──────────────────┐
   │ spec: run_prompts│              │ spec: "must       │
   │       .py exists │              │  survive kill -9" │
   │                  │              │                   │
   │ success = his    │              │ success = it runs,│
   │ file does what   │              │ and he can defend │
   │ that file does   │              │ every fork he took│
   └──────────────────┘              └──────────────────┘
     one correct shape                many correct shapes,
                                      most of them bad
```

## Preconditions

Do not open one before BUILD_V2 has produced at least one unaided artifact. A
capstone before the fundamentals is the thing every bootcamp does and it produces
someone who can start projects.

## Procedure

1. **Write the brief as what must be TRUE, never how.**

   ```
   python3 .claude/tutor/tutor_db.py capstone propose <slug> \
     --title "..." \
     --brief "Given 50k prompts it must finish, survive kill -9 at any point,
              and never send the same record twice." \
     --decision "where does the resume mark live — in the output file, or beside it?" \
     --decision "a record that fails twice: skip, halt, or quarantine?" \
     --by learner|agent
   ```

   The DB refuses fewer than two `--decision` forks, and refuses one phrased as
   an instruction (`use sqlite`). A capstone whose decisions are all made is a
   gate with a longer description.

2. **He may propose it himself** (`--by learner`), and that is the better case —
   an open-ended project he chose is the only artifact here that also measures
   whether he can *scope*. Your job then is to cut it: the first proposal is
   always three projects.

3. **You do not resolve a fork.** When he asks which to pick, you give the
   trade-off — what each choice makes cheap and what it makes impossible — and
   then you stop talking. If he picks the worse one for a reason he can state,
   he ships the worse one and finds out. That is the phase working.

4. **Review it as a studio artifact** (`phases/08-studio.md`), in rounds, and
   with real severities. This is where `robustness` findings stop being
   pedantry: nobody specified the empty input, which is exactly the point.

5. **Ship requires a defense.**

   ```
   python3 .claude/tutor/tutor_db.py capstone ship <slug> \
     --artifact "path or the command that runs" \
     --defense "why he chose each fork, in HIS words"
   ```

   Refused without both, and refused while a blocking review finding is open.
   A capstone with no defense measured typing. The defense is the design probe —
   `probe <slug> CAPSTONE design HIT|MISS` — and it is the first honest data this
   system will ever have on that faculty.

## Rules

- One capstone at a time.
- **Scope down, never up.** The version that ships beats the version that was
  ambitious. Cutting scope is itself an engineering skill and you should name it
  when he does it.
- It is his project. Do not write any of it, do not "just fix" the broken part,
  and do not accept AI-authored code inside it — the hooks still apply, and
  assisted never reaches CAN.
- If he stalls for two sessions, the brief was too vague or too big. That is
  your error, not his: rewrite the brief with one fork removed and say so.
- When it ships, `attempt log` it into the portfolio. This is the artifact he
  shows people. It is also the only proof the whole instrument worked.
