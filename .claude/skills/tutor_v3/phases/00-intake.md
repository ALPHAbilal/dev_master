# INTAKE — capture the anchor as DATA

Runs once, before SCAN. Record **what he is building toward** and **which codebase
to scan**, as data in the `targets` table. Nothing about the target enters a skill
file.

## Procedure

1. **Ask, do not assume.** Four questions, in his words:
   - What is the real thing you want to write by hand? (name it)
   - What does it take in, what does it produce?
   - Which codebase should I scan for it? (a path)
   - How big — one script, several, or a large system?

   These are the only questions. Do not propose a target for him; the goal is his.

2. **Record it:**

   ```
   python3 .claude/tutor/tutor_db.py target set --learner <name> \
     --name "<goal>" --codebase <path> --inputs "..." --outputs "..." \
     --size "one|several|large" --scripts "a.py,b.py,..."
   ```

   Writes one `targets` row, `phase=SCAN`.

3. **Read it back to him in one sentence and let him correct it.** Every later
   phase inherits this anchor; a wrong one poisons all of them.

4. Advance to SCAN. Do not teach, do not probe, do not open the codebase yet.

## Rules

- One active target per learner. A second `target set` retires the first unless
  `--additional` is passed (a target can be several scripts under one goal).
- The codebase path is his repo, captured as data, never hard-coded into a phase.
- INTAKE captures; it does not grade. No clock, no concept, no verb here.
