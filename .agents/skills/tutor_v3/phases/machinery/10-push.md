# PHASE 10 — PUSH: the freeze, metered

Invoked by `/tutor push`, or by him saying any version of *"I'm stuck."* Runs
inside an open gate. It does not end the gate and it does not replace teaching.

## Why this phase exists

He said it plainly: *"sometimes while coding I freeze, I need just a push."*

Both simple answers are wrong.

```
   REFUSE THE PUSH              GIVE IT FREELY
   he sits there                you write his file
   the session dies             he follows along
   nothing measured             he learns nothing
   ── this is what              ── this is v1, ten agents
      "discipline" costs           explaining, zero produced
```

The third answer: **give the smallest push that moves him, price it, and treat
the freeze itself as the most valuable measurement in the system.** A stall is
the only moment where the hole is visible from the outside — he is standing
still, at a known line, on a known contract. Nothing else in this instrument
localises a gap that precisely.

## The write path

The `write-guard` hook blocks you writing his target file, always, with no
exception for helpfulness. `tutor_db.py push` writes it instead. That is
deliberate: **the only characters that ever reach his file from you are ones
that were levelled, hypothesised, sha-locked and logged.** If you find yourself
wanting to Edit his file, you are about to do the thing the whole instrument
exists to prevent.

## Procedure

1. **Ask what kind of stuck.** Do not guess — the four kinds have opposite
   remedies and two of them are made worse by a hint.

   ```
   "What's stopping you: you don't know what it should do, you know
    what but not how to write it, you're hunting a name, or you know
    it and don't want to type it?"
                blank            form            recall        commit
   ```

   He will not always answer accurately. Look at the file: an empty body after
   ten minutes is `blank`; three rewrites of the same line is `form`; a comment
   like `# the method that strips` is `recall`; a correct line typed and deleted
   is `commit`.

2. **Start at L0 or L1. Climb one rung at a time.** The DB refuses a first push
   above L1 and refuses any skip.

3. **Write the hypothesis before you write the push.** Required, and it is the
   point of the whole phase. *"He cannot state what the function must return
   before he starts writing"* is a hypothesis. *"He is struggling"* is not.

4. **Between rungs, he must touch the file.** L3+ is refused while the target's
   sha is unchanged. If he is not editing, more hint is not the missing thing —
   ask him what he thinks the next line does, and stay at L2.

5. **Stop at four.** The DB says so. Four pushes means the gate is too big or
   the floor is under it: close ABANDONED, `descend`, and come back with a
   smaller contract. That is not a failure — a gate you had to carry him through
   was mis-sized when you opened it, which is your error.

6. **When the gate closes, run the interview** — see below. Do not let a session
   end with pushes recorded and no hypotheses tested; that is the freeze
   happening for nothing.

## The interview

```
python3 .claude/tutor/tutor_db.py push interview
```

He asked for this too: *"if there are many holes, will the AI take a
conversation with the learner to say if the hypothesis is correct or false."*
Yes — with three rules the tool prints every time:

- **A flat claim, one at a time.** "You freeze when the output shape is not
  written down yet." Not "do you struggle with return values?" — a vague
  question gets a vague yes, and a vague yes has built rungs he never needed.
- **A yes is a hint, not a verdict.** His self-report is a hint; his code is
  evidence — his own rule. Follow every yes with a probe that would FAIL if the
  hypothesis were true, and record `--by probe`.
- **A no is worth more than a yes.** It deletes a rung you were about to spend
  an hour on. Record it `--false` and say thank you.

When one hypothesis froze him on **two or more different concepts**, the
interview flags it: that is a misconception, not a rung. Open it with
`misconception open` and stop trying to fix it one concept at a time.

## What this is measuring

The number that matters is **pushes per gate, falling.**

```
#3: 4 @L4     #5: 2 @L2     #7: 1 @L1     #9: 0
▓▓▓▓          ▓▓            ▓                        <- this is the curve
```

Flat is the alarm. Flat means the ladder is above his floor and he is being
carried, and being carried feels exactly like learning from the inside — which
is precisely the failure mode that ended every previous attempt.

The goal is not a learner who never freezes. Everyone freezes. The goal is a
learner whose freezes get shorter, who can say which of the four kinds he is in,
and who reaches for the docs on a `recall` freeze without being told. That last
one is the whole job: nobody at a large company remembers the argument order of
`str.rsplit`. They know it takes eleven seconds to check, and they check.
