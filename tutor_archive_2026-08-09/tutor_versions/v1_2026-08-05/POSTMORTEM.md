# TUTOR v1 — POSTMORTEM

**Frozen:** 2026-08-05
**Ran:** 2026-07-23 → 2026-08-05 (12 sessions, ~9 contact hours)
**Learner:** bilal
**Target codebase:** `soufiane_prompts/` (`run_prompts.py` 1,182 lines, `check_quality.py` 144) — AI-written, declared spec-not-credit on day 1
**Evidence for every claim below:** `evidence/` in this folder. The lab session is `teacher-lab.raw.jsonl` (session `cd6bd584`, 744 records, 55 learner turns, 224 assistant messages). `lab.exchanges.md` is the readable digest, `lab.user.md` is every learner turn verbatim.

This document exists so that when v2 is running, we can still see what v1 was and
why it was changed. Nothing here is a criticism of the learner. Every failure
listed is a failure of the machine.

---

## 1. WHAT v1 WAS

A knowledge-state database plus a skill that drives it through phases.

```
concepts → sweep → descend → floor → TEACH → gate → APPLIED → transfer
                     ↑                                            │
                     └──────── drill / audit / decay ─────────────┘
```

Four states: `UNKNOWN → SEEN → EXPLAINED → APPLIED`.
Four evidence levels: `none → assisted → unaided → transferred`.
Six faculties: `write | read | debug | recall | design | vocabulary`.
Thirteen commands: `concepts sweep descend teach rebuild build transfer break drill profile ladder audit map`.

Core doctrine, and it was right:
- Reading AI-written code can never reach APPLIED.
- Never teach before an attempt.
- No praise without evidence.
- Do not infer the floor from the ceiling.

Enforcement was in three layers: the DB refuses illegal writes, hooks block
reading the spec while a gate is open, prose handles judgment.

---

## 2. WHAT IT ACHIEVED — this part worked and is being kept

```
  18 APPLIED, all evidence=unaided
  ────────────────────────────────
  depth 1 (11)  block-colon-indent  comment-syntax  dict-basics  file-object
                for-loop  function-def  if-elif-else  not-operator
                range-enumerate  truthiness  while-loop
  depth 2 (7)   accumulator  break-continue  comprehension  context-manager
                json-dump-load  or-default  try-except
```

From a standing start of **0 APPLIED and 13 MISS out of 16** on the first sweep.

Three things v1 got right that must survive into v2:

**a. The floor-finding worked, and it worked fast.** One sweep, one descend, and
the true floor was located inside two hours — `assignment-binding` /
`expression-statement`. The evidence was sharp: the learner answered `s.upper()`
correctly and `n + 1` incorrectly, which are the same rule. That is a real
diagnosis and no amount of asking "what do you know?" would have produced it.

**b. Refusing a promotion on suspicion of copying.** At exchange E16 the agent
noticed the submitted line was near-identical to its own worked example and
withheld credit. This is the single highest-integrity event in the entire log.

**c. Catching its own blind spots — eventually.** All three `ladder_log` rows are
the machine admitting it taught on sand and repairing itself mid-climb.

---

## 3. WHY IT WAS CHANGED — failure by failure

### F1 — The concept bank was built from the wrong end

`concepts` extracted 241 rows from AI-written code. Final measured coverage:

```
   depth 1  ████████████████  51    15 measured   (29%)
   depth 2  ████████████████  52     9 measured   (17%)
   depth 3  ██████████████████████ 66   0 measured
   depth 4  ████████████████ 48         0 measured
   depth 5  ████████ 24                 0 measured
                                   ───────────────
                                   138 concepts never touched,
                                   and not reachable
```

The extractor mined what was *impressive* in the code (`enum-pinning`,
`bounded-pool`, `checkpoint-ledger`) rather than what was *load-bearing*. It
produced a bank whose centre of mass sits four levels above the learner.

The machine knew and could not act on it. At E35 `/tutor map` printed
*"`checkpoint-ledger` gates 10 concepts"* and immediately had to warn
*"don't let its size pull you toward it — it's not reachable."* The ranking
function and the routing function disagreed, every session.

**Root cause:** rungs were derived from a codebase. They should be derived from
observed failure.

### F2 — Every ladder repair was reactive, and one required the learner to complain

All three `ladder_log` entries:

| when | what was missing | how it was found |
|---|---|---|
| 07-27 10:05 | no rung for `for` / `while` / `if` anywhere in 107 concepts | learner missed 4 loop-shaped concepts |
| 07-27 13:00 | no rung for the trailing `:` | learner wrote 6/6 compound statements without one |
| 07-28 14:09 | no rung for `file-object` | **learner asked "what does opening even look like… you didn't detect them, why is that??"** |

The third is the important one. The agent had inferred that a file object was
known *because the AI-written code used them everywhere* — the exact
floor-from-ceiling error the skill forbids on line one. It took the learner
noticing to fix it.

**Root cause:** the agent never states its assumptions, so they can never be
vetoed before a rung is built on them.

### F3 — The database stores verdicts, not evidence

```
   probes table, 73 rows
   ─────────────────────
   median stored question :  25 chars   ← a label, e.g. "jsonl write/read gate"
   median stored answer   :  63 chars   ← the agent's paraphrase
   learner's actual code  :  0 chars    ← not stored anywhere
   seconds populated      :  0 of 73
   faculty values used    :  1 of 6 (all 'write')
   taught_in populated    :  0 of 241
```

Meanwhile `log.md` — the one file the learner actually wrote in — was
overwritten roughly 21 times. It is 252 bytes today (`evidence/log.md.final`).
Every earlier attempt is gone.

So a system whose founding rule is *"your code is evidence"* retained no code.
The difference between attempt 1 and attempt 4 on `truthiness` — which is the
literal shape of the learning — was destroyed 21 times.

**Root cause:** no artifact archiving. Grading read a file that had already
replaced its own history.

### F4 — Retry cost was invisible, and repeated failures had one shape

```
   attempts to reach a non-UNKNOWN state
   1 attempt  ███████ 7
   2 attempts █████████ 9
   3 attempts ██████ 6
   4 attempts ██ 2      ← truthiness (3 fails), dict-basics (3 fails)
   5 attempts █ 1
```

`truthiness` and `dict-basics` both failed three times, and both failed the
*same way*: the learner reproduced the shape of the agent's example instead of
applying the rule. That is a learner-level failure mode. The schema has no place
to record it, so it was rediscovered from scratch each time.

Worse, the vocabulary was too coarse to separate causes. All of these collapsed
into `MISS` / `PARTIAL`:

```
   genuine gap        "if 0: prints"           → needs teaching
   syntax habit       missing colon (6/6)      → needs drilling
   typo               pirnt, wount_words       → costs nothing, teach nothing
   language bleed     //  !  =  from JS        → needs unlearning
   fatigue            dropped a rule seen 5m ago → needs stopping
```

The two typos alone consumed three exchanges and taught nothing.

### F5 — Fatigue was predicted correctly three times and measured zero times

The agent flagged the "tired zone" repeatedly and was right. E42 is the
collapse: the learner dropped the `+ '\n'` he had been shown five minutes
earlier, wrote `f.read` for `print`, and stalled. `jsonl` stayed UNKNOWN.

`probes.seconds` exists in the schema. It is NULL in all 73 rows. The instrument
was built and never plugged in, so the agent inferred exhaustion from prose.

### F6 — Phase labels do not describe what happened

```
   probes by phase          what it actually was
   ───────────────          ────────────────────
   REBUILD  43   ←──────── ladder gates. No rebuild ever ran.
   SWEEP    16   ✓
   DESCEND  10   ✓
   DRILL     2   ✓
   BUILD     2   ←──────── 7 exchanges of real work, 2 rows recorded
```

`transfer` never ran — no concept carries `evidence='transferred'`.
`audit`, `break`, `profile` never ran at all.

Nine of thirteen commands were used. The four highest-value phases in the design
(`rebuild`, `transfer`, `audit`, `break`) never executed once.

### F7 — The real work was the best evidence and the least recorded

The strongest event in six days is E49: the learner wrote a script from a blank
page that pulled 2 records out of a 2.4 GB file, and it was **verified running in
0.055 seconds** — proof, not belief, that the `break` worked.

```
   BUILD phase:  7 exchanges (13% of the lab)
                 → 2 probe rows
                 → the only unmediated evidence in the whole system
```

Toy gates got 43 rows. The real tool got 2.

### F8 — The learner was routed by the machine but asked to route himself

Six session-ends handed the routing decision back:

```
   E19 "want to keep going, or land it here?"
   E23 "keep going, or land it here?"
   E27 "one more rung, or land the session?"
   E29 "one more rung and we land it. Deal?"
   E34 / E39 "good place to leave it"
```

And two full exchanges (`/tutor map`, `/tutor ladder` — 7% of the lab, 8,259
characters of output) produced reports rather than learning. The learner was
being asked to navigate a map he could not see, which is the one thing the
database existed to do for him.

### F9 — Progress stalled at the phase boundary the design never crossed

```
   climb        07-24 ▓▓  07-27 ▓▓▓▓▓▓  07-28 ▓▓▓▓▓  07-29 ▓
   real build   07-31 ████  08-05 ██
                            ▲
                            └── the learner initiated this himself
                                ("let's truly practice this in true rel building")
                                v1 had a verb for it (`rebuild`) and never used it
```

At 3 APPLIED per session against a 241-concept bank, the remaining work needs
roughly 70 more sessions. The teach-one / gate-one loop does not scale to the
territory the extractor mapped.

### F10 — One turn was dropped silently

E12: the learner asked how to build a research-partner skill. The agent produced
**zero characters**. Nothing recorded the drop. In an agentic tutor a lost turn
is invisible by default.

---

## 4. THE ONE-LINE VERDICT

> v1 proved the doctrine (only unaided production counts) and proved the
> diagnosis (sweep → descend finds a real floor fast). It failed on
> **bookkeeping** — it measured the wrong things, kept none of the learner's
> actual output, and built its curriculum from the codebase instead of from the
> learner's misses.

---

## 5. WHAT v2 CHANGES, AND WHICH FAILURE EACH ONE ANSWERS

| # | change | answers |
|---|---|---|
| D1 | drop depth 3+ from the ladder; they become a checklist on the target file | F1, F9 |
| D2 | agent picks the rung; learner never chooses a concept | F8 |
| D3 | `map` / `ladder` stop being typed commands; 3 lines at session open | F8 |
| D4 | four states → two (`CAN'T WRITE IT` / `CAN WRITE IT`) + review clock | F6 |
| D5 | one sweep, ever | F1 |
| D6 | toy data retired once the real file is open | F7 |
| A1 | learner picks the **phase**, four times total, never the concept | F8, F9 |
| A2 | reviews are scheduled as slices of the real project that contain the due concepts | F4, F7 |
| A3 | agent snapshots every attempt to `attempts/` and grades the **diff** | F3, F4 |
| A4 | error classes split: gap / syntax / typo / bleed / fatigue | F4, F5 |
| A5 | `seconds` populated on every probe | F5 |
| A6 | agent states its assumed prerequisites before each rung and invites a veto | F2 |
| A7 | copy-detection against the agent's own last messages before any promotion | F3 |
| A8 | wide multi-concept gates at depth 1–2; serial only for rungs gating ≥5 | F9 |

---

## 6. RESTORING v1

```
cd /mnt/e/chinese_translation/.claude
cp -r tutor_versions/v1_2026-08-05/system/tutor   ./tutor
cp -r tutor_versions/v1_2026-08-05/system/skill   ./skills/tutor
cp    tutor_versions/v1_2026-08-05/system/settings.json ./settings.json
```

Snapshot verified at freeze time: `concepts=241 probes=73 sessions=12
ladder_log=3 floors=1`, states `APPLIED=18 EXPLAINED=4 SEEN=3 UNKNOWN=216`.
