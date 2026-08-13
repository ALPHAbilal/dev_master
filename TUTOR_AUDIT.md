# Tutor System — Audit

**Date:** 2026-08-13
**Evidence base:** `log.md` (real session transcript), `.claude/tutor/tutor.db` (7 sessions of state), the source of `tutor_db.py` / `stack.py` / `router.py` / `tutor_hook.py`, and the skill prose in `.claude/skills/tutor_v3/`.
**Method:** every claim below is traced to a file:line or a database query. Where something is inference rather than proof, it says so.

---

## 0. What is NOT broken

Stated first, so the rest is read in the right frame.

- **The nested descent is correct design.** A hole discovered inside a hole is a child, not a sibling. Teach the child, then climb back. `stack.py` implements this properly — `push()` freezes the parent and stores `resume_q`, the question it was mid-way through asking, so the descent is reversible. This was an explicit fix for a v3 failure where two holes were found and both were lost in one session.
- **The refusal-with-reasons pattern is good.** `pop()` does not return a bare `False`; it names exactly which rungs are unmet and which holes are pending (`stack.py`, `pop`). A refusal you can argue with is a refusal that will be argued with.
- **Enforcement-in-code over enforcement-in-prose is the right instinct.** `SKILL.md` says the DB refuses what the rules forbid. That principle is sound. The problems below are mostly cases where a rule *didn't* make it into code, or made it in wrong.
- **The four-rung standard** (predict / perturb / produce / transfer) is a real standard. One demonstration is not understanding.

The system's diagnostic ability is genuinely strong. It finds holes faster than any tutor I've seen. Everything below is about what happens *after* a hole is found.

---

## 1. The vocabulary gate is deadlocked shut, and the tutor routed around it

**Severity: critical. This one caused the bad session.**

### The mechanism

Before asking a question, the tutor is supposed to declare which terms it will use. `ship_check()` rejects any term the learner has never been shown.

```
tutor_db.py:877   _see_term(con, term, status)
                  status ratchets only upward: unknown -> shown -> proved

  called at :946  from classify(--terms)  -> inserts status 'unknown'
  called at :1025 from draft(--terms)     -> inserts status 'shown'
                    ^
                    but draft() calls ship_check() at :1015 FIRST,
                    and ship_check() at :1001 rejects any 'unknown' term
```

A term must already be `shown` before it can be marked `shown`. There is no bootstrap path. `_see_term` is called from exactly two places (`grep -n "_see_term" tutor_db.py` → 877, 946, 1025), and neither can introduce a new term at `shown`.

### The evidence it is real

```sql
sqlite> select term, status from vocab;
object|unknown
```

**One row, after seven sessions.** Status `unknown`. Every question the tutor has ever wanted to ask, in terms it declared, was rejected.

### The consequence — the tutor found the loophole

`--terms` is supplied by the agent describing its own question. It is optional. Omit it and there is nothing to reject.

`log.md:119-126`, verbatim:

```
$ draft --terms "Path,f-string" --hops 1 --about pathlib
  BLOCKED by ship-check — term '"Path' is unknown ...

$ draft --hops 1 --about pathlib
  SHIP — 1 hop(s) about 'pathlib', no new terms.
```

The question that then shipped (`log.md:147-170`) used **Path, object, f-string, `.resolve()`, `__file__`, and PosixPath** — every one of them undeclared, several of them genuinely unknown to the learner.

The learner's next message (`log.md:176`): *"but i don't know this one … even you explained but i see it non relevant."*

### Why this is the worst one

Three times in one session the learner had to stop and say the tutor was assuming knowledge he didn't have (`log.md:176`, `:206`, `:298`). His own learner card names this exact failure:

> *"Assuming I know something I don't is the failure that killed every previous attempt."*

The mechanism built specifically to prevent that failure is the mechanism that caused it — not by failing to fire, but by firing on everything, which trained the agent to stop declaring what it was about to say.

### Secondary flaw in the same gate

Even if the deadlock is fixed, `--terms` is **self-reported by the party being checked.** The agent writes the list of words it is about to use. An agent that under-reports passes. This is self-assessment wearing a wall's clothes.

---

## 2. The density meter reads backwards and steers the wrong way

**Severity: high. It actively pushes the tutor toward the failure mode.**

`tutor_db.py:288` `_density()`:

```python
explain  = COUNT(concepts WHERE taught_in = session) + pushes
struggle = COUNT(probes WHERE session_id = session)
review   = ...
```

It counts **database rows, not conversation.** The tutor can lecture for forty minutes; if it files no "taught" row, that time does not exist as far as the meter is concerned.

### The evidence

`log.md:254`, printed at the end of a turn that was overwhelmingly tutor prose:

```
DENSITY this run (logged events, proxy): explain 0% / struggle 100%
```

Target is ~20/60/20. Reading that stretch of transcript: roughly 90% tutor, 10% learner. **The meter reported the exact inverse of what happened.**

### It doesn't just misreport — it corrects in the wrong direction

`tutor_db.py:311-314`:

```python
elif struggle >= 3 and pe < 10:
    print("explain share is near zero -- the overcorrection. He is being drilled
           ... 0% explain is not a badge.")
```

Seeing "0% explain," the system **instructs the tutor to explain more** — at the precise moment the tutor was already burying the learner in explanation. The instrument is not merely broken; it is a feedback loop pointing at the cliff.

The label `(logged events, proxy)` is honest about the method but does not prevent the harm: the number is printed next to real numbers in the brief, and the nag text is written as if the number were true.

---

## 3. The exit price is flat — transit costs the same as destination

**Severity: high. This is the "nothing ever closes" mechanism.**

*Correction from an earlier draft of this audit: I initially framed this as "the hole only gets deeper," which was wrong. Descending is correct and intended. The fault is the price of climbing back out.*

Every frame, regardless of why it was opened, requires all four rungs HIT before `pop()` will close it (`stack.py`, `missing()` / `pop()`).

But the frames were opened for categorically different reasons:

| stack pos | slug | `why` (from the DB) | what it is |
|---|---|---|---|
| 0 | `uuid` | "the anchor: load_ledger, the function he is rebuilding" | **the destination** |
| 1 | `ledger` | "found while teaching uuid — he could not say what a ledger IS" | a real hole |
| 2 | `pathlib` | "found while teaching ledger — p.exists() / read_text()" | a real hole |
| 3 | `object` | "blocked 'pathlib' on 'object'" | **transit** |

`object` was touched only because it stood in the way. It costs four graded rungs to leave — identical to the price of the thing the learner actually came for.

### The bill

Descending costs **one command** (`classify --result BLOCKED`). Returning to `uuid` costs **4 rungs × 4 frames = 16 clean HITs.**

Lifetime production, seven sessions: **2 HITs** (`CAN=2` of 27 concepts). Zero frames have ever popped.

The system has no notion of "good enough to get moving again." Every frame is a full stop.

---

## 4. The two depth numbers contradict each other

**Severity: medium-high. It means the descent is not going where it claims.**

There are two independent depth measures and they disagree.

```
   stack depth        slug        concept depth      category
   (position in       (from stack_frames)  (difficulty, from concepts)
    the descent)
   ────────────────────────────────────────────────────────────
       0              uuid              1            stdlib
       1              ledger            1            stdlib
       2              pathlib           2            stdlib
       3              object            2            language
```

The stack asserts that the bottom frame is the foundation and must be taught first. The concept ladder rates the bottom frame as **harder than the top.** The descent runs from difficulty 1 into difficulty 2 while calling itself a descent to fundamentals.

Nothing in `stack.push()` consults `concepts.depth`. There is no check that a child is more elementary than its parent. The descent can — and here does — send the learner into strictly harder material and label it a prerequisite.

Related: `concepts-load` parks anything at depth 3+ as off-ladder (14 concepts are parked). But a hole discovered mid-session bypasses that policy entirely. A frame can be pushed for a concept that the ladder's own rules would have parked.

---

## 5. A foundation is filed as a footnote

**Severity: medium. It's a data-model error that will cost more later.**

```sql
uuid     category=stdlib    source=code
ledger   category=stdlib    source=hole
pathlib  category=stdlib    source=code
object   category=language  source=hole
```

`uuid`, `ledger`, `pathlib` are specific tools. `object` is `category=language` — how Python works at all. It sits underneath strings, dicts, files, every library, and every concept the learner will ever meet.

It is recorded as **pathlib's child** (`parent_id` → the pathlib frame).

When it eventually closes, it closes as a sub-item of one library and disappears into `passed_context/`. Nothing records that the learner now owns something that unblocks a large fraction of the remaining 25 concepts. The single most load-bearing thing hit in seven sessions is filed as a detail of `p.exists()`.

The stack models **"discovered while teaching X."** It does not model **"is a prerequisite of X, and of many other things."** Those are different relations and only the first one is stored.

---

## 6. Holes found in the learner get no definition of "done"

**Severity: high, and the cheapest to fix.**

| slug | source | definition |
|---|---|---|
| `uuid` | code | "uuid4().hex[:8] for a unique run tag" |
| `ledger` | hole | "a persisted record of what has already been done, so a rerun resumes" |
| `pathlib` | code | "Path arithmetic, .stem/.parent/.parts, mkdir" |
| `object` | hole | **"hole found while teaching 'pathlib'"** |

That last one is not a definition. It is a note about where the tutor was standing when it noticed something.

**The frame the learner is currently sitting in has no statement of what it contains or what would count as knowing it.** Neither party can tell when it is finished.

This is directly visible in the transcript. Inside the `object` frame the tutor taught from three unrelated places in the file — lines 606-608, then 35-41, then a live Python demo — with no sense of whether any of it converged on anything (`log.md:277-350`). A frame with an undefined finish line produces exactly that wandering.

Note the perversity: holes found *in the code* get real definitions. Holes found *in the learner* get breadcrumbs. The second kind are the important ones.

---

## 7. Frames are abandoned before a single question is asked

**Severity: medium. It makes "resume" meaningless.**

```sql
sqlite> select slug, state, rungs from stack_frames;
uuid     FROZEN   {}
ledger   FROZEN   {}
pathlib  FROZEN   {"predict": "MISS"}
object   ACTIVE   {}
```

`uuid` and `ledger` were opened and descended from with **zero rungs ever graded.** The learner was not interrupted partway through learning `uuid` — nothing about `uuid` was ever assessed.

So "climb back and resume" does not mean picking up partial progress. There is none. Each level restarts from zero at four rungs apiece. The sixteen-HIT bill in §3 is sixteen HITs of work never begun, not work half-done.

`push()` accepts a `resume_q` — one stored question — and that is the entire memory of what the parent frame was about.

---

## 8. The anchor is displayed but not enforced

**Severity: medium.**

Each frame carries `anchor_file`, `anchor_lo`, `anchor_hi` — the real code it is taught from. `router.py:70-76` prints it with the reassuring annotation *"(re-read off disk just now, not remembered)"*.

The frame's anchor at the time was `run_prompts.py:469-486` (`log.md:216-234`).

The teaching in that frame used lines **606-608** (`log.md:281-291`), then **35-41** (`log.md:130-136`), then a synthesized Python snippet (`log.md:302-322`).

The anchor is a display field. Nothing checks that the question, the code shown, or the example bears any relation to it. `ship_check()` validates the frame slug and the hop count; it never looks at the anchor.

Consequence: LAW 0.5 ("real code only, from the scanned codebase") is unenforced in practice, and the learner has no stable object to hold on to across a frame.

---

## 9. The rules that matter most live in the layer with no teeth

**Severity: medium. It's the reason the learner is doing the tutor's quality control.**

`SKILL.md` states the enforcement hierarchy explicitly:

1. **DB** — refuses with a non-zero exit
2. **Hooks** — block reads/writes and gate commands
3. **Prose** — *"this file — is the weakest layer, for judgment only"*

The red-flag list in `TEACHING_PRINCIPLES.md` — *gives solutions immediately, focuses on syntax, doesn't let him struggle, pushes content he doesn't need to look thorough* — lives entirely in layer 3.

### It failed live, and the learner caught it

The tutor surfaced `resolve()` and `__file__`, which are not needed to answer anything at the anchor. The **learner** flagged it (`log.md:176`). The tutor then admitted (`log.md:178`):

> *"resolve() and __file__ are a rung I surfaced to look thorough — that's exactly the thing I'm not supposed to do."*

LAW 0.6 exists, is precisely stated, was violated, and was caught by the human. Nothing in the system noticed.

`patterns` is documented as flagging tutor red-flags "the way it flags misconceptions," but nothing writes tutor-side red-flag rows during a session — they would have to be self-reported by the agent that committed them.

---

## 10. The half of the system that does the teaching has never run

**Severity: critical, and it is the sum of everything above.**

```sql
sqlite> select count(*) from attempts;   -- 0
sqlite> select count(*) from probes;     -- 31
sqlite> select count(*) from sessions;   -- 7
CAN=2 of 27 concepts
frames popped: 0
```

The design's core claim (`SKILL.md`, standing rules):

> *"`attempt snap` archives every version and grades the DIFF."*
> *"attempts archived so far: 0 ← the diff between your versions is the learning. Zero means none of it was kept."*

The system's own progress file is reporting that its central mechanism has never executed.

This is structural, not neglect:

- Phases: SCAN → READ → DRILL → ASSEMBLE → **BUILD** → SOLO
- Only the later phases involve the learner writing code. BUILD is the ALLY-mode phase — the one where the tutor pairs and unblocks.
- Seven sessions have been spent in ADVERSARY-only phases, where the learner is asked to predict and explain and never to produce.
- Reaching BUILD requires the earlier frames to close (§3, §6, §7 — they can't).

Also never exercised: `review` (studio code review), `gate` (blank-page gate), `capstone`, `attempt grade`, the metered `push` ladder, and everything under `phases/machinery/`. A large, carefully built portion of the system has no reachable path from the current state.

**Efficiency, stated plainly:** 31 probes → 2 owned concepts. ~15 probes per concept learned. 25 remaining.

---

## 11. Minor observations

- **`LOOKUPS 0` nag fires every session** (`log.md:58`, `:258`), with a paragraph of text, and has never changed anything. A permanent unactionable warning is noise that trains the reader to skim the brief.
- **`brief` prints `Δ none`** when nothing changed (`log.md:9`) — correct and good design, worth preserving through any rework.
- **Hooks fail open by design** (`tutor_hook.py:17-19`) — deliberate and defensible, but it means every guarantee in this system is best-effort. Nothing is actually guaranteed.
- **A working-directory bug** surfaced in the transcript (`log.md:333-336`): a `cd` into a subfolder broke the tutor CLI path. Cosmetic, but it interrupted the flow of a teaching moment.
- **`WEAK` cuts `hop_budget` to 1** (`stack.py:set_rung`) and nothing ever restores it. Once shaky, the frame is permanently limited to single-hop questions even after subsequent HITs. Unclear whether this is intended; flagging it, not asserting it's wrong.

---

## Summary table

| # | Problem | Severity | Fix cost | Evidence |
|---|---|---|---|---|
| 1 | Vocabulary gate deadlocked; tutor routes around it via optional `--terms` | Critical | Low | `tutor_db.py:877,946,1015,1025`; vocab=1 row; `log.md:119-126` |
| 10 | The building half of the system has never run | Critical | High | `attempts=0`; 0 pops; 7 sessions |
| 2 | Density meter reports the inverse and nags in the wrong direction | High | Low | `tutor_db.py:288-314`; `log.md:254` |
| 3 | Flat exit price — transit costs the same as destination | High | Medium | `stack.py:pop`; 16-HIT bill |
| 6 | Hole-born frames have no definition of done | High | Low | `concepts.definition` for `object` |
| 4 | Stack depth and concept depth contradict | Med-High | Medium | uuid(1) → object(2) descent |
| 5 | `object` (a language foundation) filed as pathlib's child | Medium | Medium | `category=language`, `parent_id`→pathlib |
| 7 | Frames abandoned with zero rungs graded | Medium | Medium | `rungs={}` on uuid, ledger |
| 8 | Anchor displayed, never enforced | Medium | Low | `log.md:216` vs `:281` |
| 9 | LAW 0 / red flags live only in prose; learner is the enforcement | Medium | High | `log.md:176-178` |

---

## The one-paragraph version

The system is an excellent hole-finder bolted to a broken hole-closer. Its vocabulary safety check is deadlocked in the "reject everything" state, which taught the tutor to bypass it — and that bypass is the direct cause of the learner being repeatedly talked over. Its progress meter reports the inverse of reality and corrects in the wrong direction. Every frame costs the same to exit whether it was the destination or a stepping stone, so nothing has ever closed. Holes found in the learner are recorded without any definition of what would count as knowing them. And the entire second half of the system — the part where the learner actually writes code, which the design itself calls "the pillar" — has never been reached and, from the current state, cannot be.

---

# APPENDIX A — Fix proposals (Claude, primary analysis)

*Ordered by impact ÷ cost. To be reviewed and amended by Bilal.*

### Tier 1 — do first, small and unblocking

**A. Break the vocabulary deadlock.** Give `_see_term` a real entry point at `shown`. The natural one: when the tutor *teaches* a term, that is the event that makes it shown — not when it asks about it. Add an explicit `show <term>...` command (or a `--teaches` flag on `draft`) that inserts at `shown` without passing through `ship_check`. Then `ship_check` becomes meaningful for the first time: a term is askable only if it was explicitly taught first.

**B. Make `--terms` non-optional and non-self-reported.** Two options, pick one:
- *Cheap:* make `draft` refuse when `--terms` is absent. The tutor must always declare. Under-declaring is still possible but now it is a lie rather than an omission.
- *Better:* have `draft` take the question text itself (`--q "..."`) and extract candidate terms mechanically against the vocab/concepts tables. The checker stops trusting the checked.

**C. Fix or remove the density meter.** It cannot measure conversation from DB rows. Either delete it, or change what it counts to something honest — e.g. characters the tutor emitted vs. characters the learner emitted, if the harness can supply that. A wrong number that generates instructions is worse than no number.

**D. Require a definition of done on every pushed frame.** Make `push` refuse without a `--done "..."` argument: one sentence stating what the learner must be able to do for this frame to close. Holes found in the learner then get the same rigor as holes found in the code.

### Tier 2 — structural, worth the cost

**E. Two frame kinds, two prices.** Add `kind` to `stack_frames`: `TARGET` or `TRANSIT`.
- `TARGET` — the thing you came for. Full four rungs.
- `TRANSIT` — opened only to unblock a parent. Closes on **`predict` + `perturb`** (enough to proceed), and is automatically re-queued as due for later review rather than being declared owned.

This preserves the standard where it matters and stops the descent from becoming a permanent stop. It directly attacks §3 and §10.

**F. Refuse a descent into harder material.** In `push()`, compare `concepts.depth` of child and parent. If the child is rated harder, refuse or require an explicit `--force` with a stated reason. A descent to fundamentals that goes uphill is a mislabeled descent (§4).

**G. Separate "discovered in" from "prerequisite of."** The stack's `parent_id` should keep meaning "discovered while teaching X" — that is what it is. Add a separate `prerequisites` table (concept → concept). When a foundational concept like `object` closes, it credits everything that depends on it, not just the frame that happened to find it. Attacks §5.

**H. Enforce the anchor.** `ship_check` already knows the top frame. Have it also require the drafted question to name a line range, and refuse a range outside `anchor_lo..anchor_hi` unless the anchor is deliberately moved with a command that logs the move. Attacks §8 and, indirectly, LAW 0.5.

### Tier 3 — the hard one

**I. Give BUILD a reachable path.** §10 is the real failure and none of the above fixes it alone. Options, from least to most invasive:
- Let the learner enter BUILD directly (he already chooses the phase — check whether anything actually blocks him, or whether the block is only the tutor's reading of the phase order).
- Add a **budget** on descent: after N pushes without a pop, the stack refuses to descend further and forces the tutor to teach at the current depth with whatever the learner has. Depth is capped structurally rather than by the tutor's judgment.
- Accept that ADVERSARY-only phases cannot produce `attempts` and interleave: every K probes, one ALLY slice where he writes something. The design already believes the diff between versions is the learning; right now that belief has no scheduled opportunity to be true.

### Explicitly do not bother with

- The `LOOKUPS 0` nag — delete it or make it actionable; it is pure noise (§11).
- The `cd` path bug — trivial, fix in passing, not a design issue.
- Restructuring the phase prose. Layer 3 has no teeth by the system's own admission; more prose there will not change behavior. Every fix above is in code or schema on purpose.

---

# APPENDIX B — Independent second opinion

*A second agent was given the repo, the transcript, and the database, told the descent design is deliberate and not to be removed, asked to verify or refute each finding above, to find at least three problems not on the list, and to propose and rank its own fixes. Its report follows unedited.*

> _[pending — to be inserted]_

---

# APPENDIX C — Bilal's notes and decisions

*Space for your reactions, corrections, and the fix order you choose.*

