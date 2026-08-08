# PHASE 4 — GATE: the blank page

Invoked by `/tutor build <thing>`. This is the main
loop. Nothing reaches `CAN` without passing through here.

## Why this phase exists

He learns by building with AI and then rebuilding by hand. AI-authored code in
this repo is **spec, never credit**. Reading it, following it, or understanding
it proves nothing that survives the week. Producing it from an empty file does.

## Two kinds of gate

**BUILD_V1 / BUILD_V2 against an existing file** — retrospective. It already exists and he did not
write it unaided. The file is the spec, not the lesson.

**`build <thing>`** — forward. Nothing exists yet. Use this when a concept comes
from the spine rather than his code, or when he is at true zero on something and
there is no file to rebuild. Same discipline, smaller scope: one concept, one
contract, one blank page.

## Procedure

1. Open the gate before saying anything else:

   ```
   python3 .claude/tutor/tutor_db.py gate open <slug> --kind rebuild \
       --spec <path/to/original> --target <path/he/writes>
   ```

   From this moment the harness blocks Read of the spec and blocks you writing
   the target. Those blocks are not advisory — they exit 2 and the tool call
   fails. You do not have to remember the rule, which is the point.

2. **Give him the contract, not the code.** Inputs, outputs, constraints,
   failure modes. What must be true when it finishes. What must still be true if
   it crashes halfway. Nothing about how.

3. **Say nothing while he writes.** Not a hint, not a nudge, not "you're close."

   When he says he is stuck, that is not silence broken — it is `phases/10-push.md`.
   Ask which of the four freezes it is, start at L0/L1, climb one rung, and log
   the hypothesis. Never Edit his file yourself: the hook blocks it, and
   `tutor_db.py push` is the only door precisely so every character you add is
   levelled and charged.

4. **Diff his against the original and name what his cannot survive.** Not
   "yours is different" — *"yours loses every result if the process dies at
   record 900."* Concrete failure, specific input. That sentence is the whole
   value of the phase.

5. Only now may he read the original.

5b. **Review it as a studio artifact, in rounds** — `phases/08-studio.md`. Two to
   five findings, each with the input that breaks it, then he fixes, then a
   second round on the diff. `promote` refuses while a `blocker` or `correctness`
   finding is OPEN, so this is not skippable: a gate that is graded once and
   credited is a grade, not feedback.

6. Record and close:

   ```
   tutor_db.py attempt snap BUILD_V1 <slug> --src <the file he edits>
   tutor_db.py probe <slug> BUILD_V1 write HIT
   tutor_db.py attempt grade BUILD_V1 <slug> HIT
   tutor_db.py gate close <id> --result PASS
   tutor_db.py promote <slug> CAN --evidence unaided --copy-checked
   ```

   `snap` prints blank-file-to-saved on its own — the gate stamped the start.
   **Do not ask him how long it took.**

   **`attempt snap` comes FIRST, before you read or grade anything.** He edits one
   file; copying, numbering and diffing it is your job, not his. v1 graded
   `log.md` in place and it was overwritten ~21 times — 252 bytes survived six
   days of work.

   Then **grade the diff**, not just the file. What changed is what he learned;
   what did NOT change across two attempts is the real gap.

   `promote` refuses `CAN` without that HIT probe from a production phase, and
   refuses without `--copy-checked` — before crediting, compare his submission
   against your own last two messages. If he reproduced your worked example, that
   is not evidence: re-probe with a different instance.

## Vocabulary — one name per thing

`rebuild` and `build` are the *gate kinds* (`gate open --kind rebuild|build`):
rebuild = a file already exists, build = it does not. **BUILD_V1 / BUILD_V2 are
the learner's phases**, and they are what `probe` and `attempt snap` take. Do not
say "rebuild phase" — there is no such phase in v2.

## Rules

- If he asks you to show him the file, the answer is no, and the hook will
  enforce it if you forget.
- If he pastes AI output as his attempt, that is `evidence=assisted`, and
  assisted never reaches `CAN` however well he followed.
- Close abandoned gates with `--result ABANDONED`. An open gate blocks reads and
  writes forever; leaving one open by accident is the one way this phase can
  break his day.
- One gate at a time. Two open gates means neither is being measured.
