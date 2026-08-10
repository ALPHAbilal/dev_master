# TUTOR v3 — THE CIRCLE SYSTEM (design)

Status: DESIGN, not implemented. Backup of v2 lives in
`../v2_backup_2026-08-09/`. Nothing in the live skill or DB is changed by this
file.

> **2026-08-09 pivot (from Bilal): RADICAL, not incremental.** Do not bolt the
> circle onto v2's concept-ladder. Replace the organizing spine. See
> "RADICAL SPINE" below — it supersedes "CHANGE 3 — phases stay" where they
> conflict.

> **2026-08-09 CORRECTION #2 (from Bilal) — the ladder STAYS. This supersedes the
> "kill the ladder" language in RADICAL SPINE below.** The agent had wrongly
> demoted the concept ladder to a demand-paged subsystem. Bilal's actual model is
> three layers, and the ladder is Layer 2, not a subsystem:
>
> ```
>   INPUT (data, agnostic to any specific repo/target):  a codebase + a target
>       │
>   PHASE 1 — SCAN:   AI scans the WHOLE real codebase, scrapes concepts AND all
>       │             aspects (design, failure-handling, api, architecture — not
>       │             just language). Grounded in true code, not toy data.
>       │
>   PHASE 2 — UNLOCK (the ladder): many task TYPES (question, micro-code, break-
>       │             this, explain-this). Learner unlocks every concept, each
>       │             taught from the real code + a real example + explanation.
>       │             ── HARD GATE: all unlocked ──
>       ▼
>   PHASE 3 — BIG BUILD (the pillar): write the real scripts by hand, running the
>                       9-verb CIRCLE (CIRCLE_SPEC.md).
>   ════════════════════════════════════════════════════════════════════════════
>   ACROSS ALL — LAW 0: question first, explain only residue, 20/60/20, AND a
>                       hypothesis-verify loop (below).
> ```
>
> **Codebase-agnostic:** PHASE 1 takes any repo as input; nothing names soufiane.
>
> **The hypothesis-verify loop (Bilal's core mechanic — the AI must never trust
> working code):** the agent SUSPECTS a weak spot from his code or answer → forms
> a hypothesis → TESTS it with a question or a small code task → is only SURE after
> the test. Code that runs, or code he generated with AI, is NOT evidence of
> understanding. A confirmed weakness goes onto the ladder; a falsified one is
> dropped. This reuses v2's `push --hypothesis`, `misconception`, and `probe`
> machinery, generalized: every credited concept must survive a test the agent
> chose *because it would fail if the understanding were fake*.
>
> Net: the RADICAL part is (a) how the AI behaves (LAW 0 + hypothesis-verify),
> (b) the ladder covering ALL aspects not just syntax, (c) the 9-verb circle as
> PHASE 3 — NOT the removal of the ladder. Where text below says "kill the
> ladder / demand-page concepts," read it as: the ladder is Layer 2, unlocked
> before the big build, and concepts may ALSO surface JIT during the build.

## RADICAL SPINE — the target is the anchor, the circle is the engine

Two principles Bilal set, in his words:

1. **The anchor never moves: he writes the real target by hand.** The tutor exists
   because he discovered he cannot yet — concepts are missing. So the concept
   machinery (v2's probe→teach→gate) is NOT discarded; it is demoted from *spine*
   to *subsystem* that fires just-in-time when IMPLEMENT trips on a missing concept.

2. **The target is DATA, not code — the process is agnostic to it.** The specific
   goal (for Bilal today: the "soufiane script") is captured once at an **intake
   step in session 1**, stored in the DB, and read generically by every phase.
   No target name ever appears in a skill file. Swap learner → swap target → zero
   code change.

What dies: the **artificial concept-ladder** — climbing ~96 mined features hoping
they sum to the project. What lives: **the learner's real target, cut into
buildable sub-tasks**, each run through the 9-verb circle; concepts taught exactly
when the real work exposes the gap; the same loop applied to any small real task,
so it transfers.

    SESSION 1  = INTAKE (new): capture anchor {name, inputs→outputs, size} → DB.
    SESSION n  : read stored target → decompose next real slice →
                 run that slice through all 9 verbs (see THE CIRCLE) →
                 IMPLEMENT trips on a missing concept → teach it JIT (v2 machinery).

The rigor problem (no fixed answer-key file like v2 had): **the answer key becomes
his own DECOMPOSE.** Code (⑤) is graded against the plan he wrote (②); edge cases
(①) diffed against the list the agent produces after; each verb keeps a mechanical
pass-test; DB keeps enforcing clock/snap/copy-check. He trades the fixed target
file for a system that runs on ANY task — that trade is the radical part.

DB: add a `targets` table (or `learners.target_id`) — `{id, learner, name, inputs,
outputs, size, decomposition_json, created_at}`. Populated by intake, read by all
phases. Nothing in SKILL.md references a specific target.

## Why this exists

Two events on 2026-08-09, in one session:

1. Bilal stopped a working session to say: *"you aren't teaching me like an
   engineer... you just generate explanations... even when I write correct code
   you can see I'm weak at aspects that should be added... you don't teach me to
   think."* He was right, and it is diagnosable in the instruction files, not
   just in agent behaviour.
2. Re-reading `knowledge.md` — his own spec for the mentor he wants — showed the
   whole tutor operates on **one of nine** skills that doc calls the job.

v2 is an excellent instrument for **Implement** (write the file by hand, from
memory, no spec). It measures reconstruction with real rigour. But reconstruction
is one arc of the engineer's loop, and `knowledge.md:448` names all nine:

    UNDERSTAND → DECOMPOSE → REASON → DESIGN → IMPLEMENT →
    DEBUG → EVALUATE → COMMUNICATE → IMPROVE → (back to UNDERSTAND)

This design makes that loop the spine, keeps everything v2 got right, and closes
the four faculties that separate a programmer from an engineer.

---

## LAW 0 — the teaching method (parent of every phase)

Source: `knowledge.md` lines 23, 373-390, 440.

> The agent poses the **question first** and explains only the **residue** the
> learner cannot reach on his own. Session budget: **~20% agent explanation, ~60%
> him producing (code AND reasoning), ~20% review.** Watching the agent think is
> the red flag, not the lesson.

This is the parent of the four file-level fixes already found in v2:

| file | line | v2 does | v3 does |
|---|---|---|---|
| `03-teach.md` | steps 2-4 | delivers "Name it / Teach / Draw" then quizzes at step 5 | **step 2 becomes "ask the question whose answer is the concept"**; explain only what he can't answer |
| `04-gate.md` | 56 | *agent* names what his code can't survive | **ask "what input breaks this?" first**; agent supplies only the residue |
| `08-studio.md` | 31-54 | *agent* authors every finding, he only fixes | **round zero: he reviews his own code first**; grade the gap between his findings and the agent's |
| `SKILL.md` | THE LOOP | every diagnostic box is an agent action | add a parallel track: he inspects / hypothesizes / predicts, agent confirms |

**Key reframing that makes this precise:** v2 forces him to *produce code* but lets
the agent *produce all the reasoning about the code.* "Produce" must mean produce
the reasoning too — the finding, the why, the predicted failure.

---

## THE CIRCLE — nine verbs, current coverage

Coverage measured from the live DB and phase files on 2026-08-09.

| verb | what it is (knowledge.md) | v2 coverage | evidence |
|---|---|---|---|
| **UNDERSTAND** | read a spec/problem, restate it, find constraints & assumptions | partial | READ phase (predict a real file); no "restate the problem" rung |
| **DECOMPOSE** | break a vague problem into steps | **none** | the exact freeze on 2026-08-09; no faculty, no rung; agent decomposed *for* him |
| **REASON** | compare solutions, complexity, "why is A better than B" | **none** | no faculty; Big-O never mentioned |
| **DESIGN** | requirements→architecture→components→APIs→trade-offs | **none** | faculty `design` = NEVER TESTED since day one; `arch`(8) + `api`(11) categories 100% parked |
| **IMPLEMENT** | write it by hand, from memory | **strong** | FLOOR→BUILD_V1→BUILD_V2, the whole v2 |
| **DEBUG** | hypothesis→experiment→evidence→diagnosis→fix→verify | weak | `break` phase exists but only on agent-supplied code; `failure`(13) category 100% parked |
| **EVALUATE** | review code, spot failure modes, judge trade-offs | partial | studio exists, but agent authors findings; he never evaluates his own |
| **COMMUNICATE** | explain a decision, doc, commit/PR, explain to CTO/PM | **none** | no faculty; never asked to explain a choice in words |
| **IMPROVE** | fix on evidence, iterate, retire misconceptions | partial | review round 2 + misconception retire; the one loop v2 does close |

Scoreboard: **strong 1, partial 3, none 5.** The five empties are four ⭐⭐⭐⭐⭐
skills plus DECOMPOSE, which he named himself as his freeze.

### The shelf was built and never used

The DB already contains 54 concepts for the highest-value verbs — **all parked,
all never probed:**

    pattern   22 concepts   parked  (REASON / DESIGN patterns)
    failure   13 concepts   parked  (DEBUG)
    api       11 concepts   parked  (DESIGN / real-world)
    arch       8 concepts   parked  (DESIGN / architecture)

They were parked at depth 3+ by v2's routing (correct at the time — no evidence
demanded them). v3's job is to make them reachable through the verbs that need
them, not to dump all 54 onto the ladder at once.

---

## CHANGE 1 — faculties become the circle

v2 `probes.faculty` in use: `write, read, debug, vocabulary` (+ `recall`,
`design` declared but design never written).

v3 faculty set = the nine verbs, collapsed to the measurable ones:

    understand  decompose  reason  design  implement(=write)  debug
    evaluate    communicate  recall

- `implement` is v2's `write` (rename or alias; write stays valid).
- `read` folds into `understand`.
- `vocabulary` stays (naming knowledge he already owns — knowledge.md:45-49).

Effect: `patterns` / `profile` can finally print **"decompose: never tested,
design: never tested, communicate: never tested"** the way it already prints it
for `design`. What is not measured is named, not hidden. This is the mapping he
asked for — "the circle system that maps the full journey."

## CHANGE 2 — a verb-tag on every concept, so routing sees the circle

Add `concepts.verb` (nullable TEXT, one of the nine). Category stays (it says
*what domain*); verb says *which faculty of the loop it trains*. A concept can be
reached because its **verb** is starving, not only because a miss sits beneath it.

Routing rule added to `sweep-next` / `due-slice`:

> When one verb has zero owned concepts and the phase allows it, prefer a rung
> that trains that verb over another sibling in an already-strong verb. A 7-HIT
> streak in `implement` is a signal to jump verbs, not just to widen the gate.

This generalizes v2's existing MOMENTUM rule (streak → widen/phase-jump) from
"same phase" to "same verb."

## CHANGE 3 — phases stay; verbs ride on top

Do **not** replace the five phases. They are the Implement axis and they work.
Instead, three new *loops* that any phase can invoke, each mapped to a starved
verb, each obeying LAW 0:

1. **DECOMPOSE loop** (before a gate, when `build <thing>` is non-trivial):
   he writes the *plan* — the steps, as comments or plain english — and is graded
   on the plan before a line of code. This is the freeze from 2026-08-09 turned
   into a measured rung instead of an agent hint. Faculty `decompose`.

2. **DEBUG loop on his OWN code** (`knowledge.md:255`): after any HIT, agent may
   inject a fault or hand him a failing input and require the explicit chain —
   *hypothesis → experiment → evidence → diagnosis → fix → verify* — in his words.
   Extends the existing `break` phase from supplied code to his code. Faculty
   `debug`.

3. **COMMUNICATE loop** (`knowledge.md:290-308`): after a build, one question —
   *"explain why you structured it this way, in three sentences, as if to another
   engineer."* Graded on the explanation, not the code. Doubles as interview rep.
   Faculty `communicate`.

REASON and DESIGN are heavier; they attach to CAPSTONE and to a new lightweight
**trade-off rung** (`knowledge.md:282`): given constraints, *"I'd choose X
because…"* — two forks, a defence in his words, exactly the CAPSTONE contract but
scoped to one decision. Faculty `reason` / `design`.

## CHANGE 4 — the mapping surface (what he sees)

He asked for a system that **maps his full journey.** Extend the existing
furniture (never a pasted message — v2's rule holds):

- `tree` / `PROGRESS.md` gains a **circle header**: the nine verbs with an owned
  count and a "never tested" flag each. One glance = where he is on the whole
  loop, not just "21/97 language concepts."
- `profile` reports per-verb, replacing the language-heavy faculty table.
- `statusline` gains the weakest untested verb, so the starved axis is always
  on screen.

---

## DB SCHEMA CHANGES (concrete, additive, reversible)

    ALTER TABLE concepts ADD COLUMN verb TEXT;        -- one of the nine
    -- faculties: no schema change; probes.faculty already free TEXT.
    --   just widen the CHECK/validation list in tutor_db.py to the nine verbs.
    -- unparking: UPDATE concepts SET parked=0 WHERE ... is NOT run wholesale;
    --   verb-routing pulls a parked concept onto the ladder only when its verb
    --   is starved AND a miss/leverage demands it (v2's RUNG SOURCE rule intact).

New migration file: `migrate_v3_circle.py`, following the existing
`migrate_v3*.py` pattern. Backfill `verb` from `category` as a first pass:
failure→debug, arch/api→design, pattern→reason, language/stdlib→implement — then
correct by hand where wrong.

No column is dropped. v2 rows keep working; `faculty='write'` still validates.

---

## WHAT IS EXPLICITLY *NOT* CHANGING

- The five phases and the "he chooses the phase only" rule.
- The DB-as-enforcer model: every rule stays a non-zero exit, not prose.
- The push ladder, the clock discipline, the copy-check, the snap/diff grading.
- The anti-explanation defence (`03-teach.md:13-16`). LAW 0 *sharpens* it — the
  fix for "he watches me code" is not to explain less about syntax, it is to make
  him produce the reasoning. Explanation of the residue stays legal.

## RISKS

- **Breadth trap.** Nine verbs × six categories is a bigger surface; the same
  extractor that mined 241 dead concepts could mine 900. Mitigation: verbs are
  reached by starvation + evidence, never bulk-unparked. RUNG SOURCE rule holds.
- **Design/Reason are hard to grade mechanically.** A trade-off defence is prose,
  not a passing test. Mitigation: grade the *fork count* and the *presence of a
  reason per fork* (CAPSTONE already does this), not the "correctness" of the
  choice.
- **Scope.** This is a multi-session build. Suggested order:
  1. LAW 0 + the four file fixes (method — highest leverage, lowest risk).
  2. Faculty rename to the nine verbs + `profile`/`tree` circle header (mapping).
  3. `concepts.verb` column + migration + verb-routing.
  4. The three new loops (decompose / debug-own / communicate).
  5. Trade-off rung; REASON/DESIGN into CAPSTONE.

## OPEN QUESTIONS (for Bilal)

1. Order above — method-first (fix how I teach *now*), or mapping-first (see the
   whole circle *now*, even while most of it reads "never tested")?
2. DECOMPOSE as a *gate of its own* (grade the plan, then separately grade the
   code) or as a *sub-step inside every build*?
3. Interview mode — is COMMUNICATE enough, or do you want an explicit `interview`
   phase (timed, "explain it to a CTO", mock system-design) as a sixth phase he
   can choose?
