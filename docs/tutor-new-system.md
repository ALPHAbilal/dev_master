# Tutor — The New System (mental model)

A single read-through of the agents, what each one does, and — for each — which
jobs are **deterministic** (plain code, runs every time, no tokens) vs **judgment**
(an LLM call, the only place tokens go). Built in-house.

> The one rule that shapes everything: **if a step has one correct output given its
> inputs, it is code, not a prompt.** Tokens are spent only on genuine judgment.
> Everything else is a deterministic tool the agents call.

---

## 1. The shape at a glance

```
 STAGE 0 — SCAN (once)          read the codebase → concept bank + rough order → DB
 STAGE 1 — COVERAGE (once)      capped expert subagents cover every aspect → DB
 STAGE 2 — THE LIVE LOOP        Agent M (plans)  ‖  Agent L (teaches), forever
```

```
        ┌──────────────────────── DATABASE (durable memory) ───────────────────────┐
        │  concepts · prerequisite edges · mastery overlay · mistakes · mappings   │
        └────────▲──────────────────────────────────────────────────▲──────────────┘
                 │ reads state, writes plan                          │ reads plan, writes evidence
        ┌────────┴─────────┐        MAP LIBRARY (*.md)      ┌─────────┴──────────┐
        │     AGENT M       │ ─────── writes ──────────────►│      AGENT L        │
        │   (the planner)   │ ◄────── reads only ───────────│  (the teacher)      │
        └───────────────────┘                               └─────────┬──────────┘
                                                                      │ talks to
                                                                      ▼
                                                                 ┌─────────┐
                                                                 │ LEARNER │
                                                                 └─────────┘
```

Handoff is **one-directional**: M writes the map library, L only reads it. L's
observations reach M through the **database** (recorded mistakes/evidence), never by
writing back to the maps.

---

## 2. The agents

### Agent SCAN — runs once, then never again
Reads the whole target codebase and turns it into the concept bank in the DB. Emits a
**rough order** (what appears later / builds on more = further out) — NOT exact
prerequisites. Teaches nothing. Result persists; the scan never repeats.

**Deterministic:** file walking, parsing, writing rows, tagging each concept by aspect,
computing distance-to-target-slices.
**Judgment:** naming the concepts, the first rough "what builds on what" guess.

### Agent COVERAGE — a capped set of expert subagents, runs once
N subagents (N capped: as few as possible for full coverage). Each is expert in ONE
aspect of the stack (language core, stdlib/api, design patterns, failure modes,
architecture…). Together they cover everything needed to become the best engineer in
**this** codebase's stack. They enrich the bank.

**Deterministic:** spawning, scope limits, merging their outputs, de-duping concepts.
**Judgment:** each subagent's expert read of its aspect.

### Agent M — the planner (never talks to the learner)
Owns the **map library** (a folder tree of many named `.md` files) and the trajectory.
Decides **where to start** and **what's next**. Has a **research tool** (web/docs/wiki)
to verify prerequisite edges and to evaluate the current frontier. Reads the learner's
mistakes from the DB; re-plans one step at a time.

**Deterministic (code — every time, free):**
- compute the READY set (frontier) from the prerequisite DAG + mastery overlay
- score the ready set: `proximity × ZPD-fit × mapping-gap × road-balance`
- recompute ZPD sizing from `pushes-per-task` after each subgoal
- write/update the map files through a schema (reject malformed maps)

**Judgment (LLM — tokens):**
- choose the ROAD for a subgoal (slow-solve / fast-map / intuition-train)
- decide "worth failing at" vs "just tell him" (productive failure vs noise)
- research an unknown prerequisite edge and rewrite the DAG
- write the trajectory prose / the "what to build next" contract

### Agent L — the teacher (the only agent the learner sees)
Reads the current subgoal from the map library and drives the live session: asks,
judges the answer, explains only the residue, forces the JUSTIFY step, and **deposits
the mental mapping** into the library. Sophisticated instructions; adversarial except
in the BUILD road.

**Deterministic (code — every time, free):**
- assemble the per-turn context blocks (phase, frontier, vocab, obligations)
- enforce the vocab door (refuse a question using an unshown term)
- enforce the gate walls (block reading the spec / writing his file)
- enforce `store_mapping` schema (reject a trigger-less / why-less mapping)
- write probe rows / evidence to the DB

**Judgment (LLM — tokens):**
- pose the question whose answer is the next step
- judge HIT / WEAK / MISS / BLOCKED
- explain the residue he cannot reach
- author the mapping prose (trigger + solution + why)

---

## 3. The categorization, in one table

| Job | Owner | Deterministic (code) | Judgment (LLM) |
|---|---|---|---|
| Scan codebase → bank | SCAN | walk/parse/tag/write | name concepts, rough order |
| Cover all aspects | COVERAGE | spawn/merge/dedupe | each expert read |
| Find the frontier | M | READY set from DAG+overlay | — |
| Choose what's next | M | score the ready set | tie-breaks near the edge |
| Choose the road | M | — | slow / fast / intuition |
| Fail-vs-tell | M | — | productive failure vs noise |
| Fix a prereq edge | M | apply the edit | research + decide |
| Size difficulty (ZPD) | M | pushes-per-task → resize | — |
| Assemble context | L | render blocks, filter empties | — |
| Ask the question | L | route through the gate | author the question |
| Judge the answer | L | record the verdict row | HIT/WEAK/MISS/BLOCKED |
| Teach the residue | L | — | explain the gap |
| Deposit the mapping | L | enforce schema, write file | author trigger+why |
| Change phase | learner→L | write the state, log it | — |

---

## 4. The core loops (what actually runs)

**The teaching turn (L):**
```
 assemble context (code) → ask (LLM) → learner answers →
 judge (LLM) → record evidence (code) →
    HIT → advance   WEAK/MISS → teach residue (LLM)   BLOCKED → push a frame (code)
 → on subgoal done: store_mapping (LLM authors, code enforces)
```

**The planning turn (M):**
```
 read new evidence (code) → recompute frontier + ZPD (code) →
 pick next subgoal (code scores, LLM tie-breaks) →
 choose road + fail-vs-tell (LLM) → write the map file (LLM authors, code enforces)
```

**The closed calibration loop (the secret sauce):**
```
 M sizes a task ──► L runs it ──► learner's real performance (pushes, self-corrects)
      ▲                                                    │
      └──────────── code re-sizes the next task ◄──────────┘
 Nothing is scripted. Difficulty, road choice, and prereq edges all self-tune to the
 individual learner, turn after turn. Health metric: pushes-per-task falling while
 difficulty holds or rises = he can build more of it himself, with confidence.
```

---

## 5. The learning theory underneath (why it works)

- The learner is made into an engineer who can build the whole codebase **solo, with
  confidence** — not "good at syntax."
- Learning is not mistakes-only. Six sources: (1) error made & fixed [richest],
  (2) productive struggle, (3) judgment forks, (4) surprise/calibration, (5) leveling
  up working code, (6) things to be told. M sorts which is which per subgoal.
- Every subgoal ends in a stored **mental mapping** = `problem-shape (trigger) →
  solution idea → why`. Enough mappings = strong intuition = recognition = confidence.
- Three roads all end at "create mapping": **slow-solve** (prove it, trains reasoning),
  **fast-map** (read the solution, absorb), **intuition-train** (guess → check →
  correct; the mistake road). M must keep enough slow-solving that reasoning keeps
  pace with pattern-recognition.

---

## 6. Non-negotiable invariants

1. **Function-tool mindset.** No agent shells out to a database or CLI. Every state
   change is a tool call; the tool validates and refuses what the rules forbid.
2. **One-directional handoff.** M writes maps, L reads maps; L's signal to M is DB
   evidence only.
3. **Deterministic where possible.** One-correct-output steps are code, not prompts.
4. **The library never lies.** A mapping without a trigger+why is rejected; L cannot
   close a subgoal without a valid mapping stored.
5. **Calibrate on the learner.** Difficulty and road self-tune from real performance;
   pushes-per-task is the meter.
6. **Never credit working code.** A HIT must survive a re-probe on a new instance;
   AI-authored code is spec, never credit.

---

*Design rationale and the running list of detected holes live in
`docs/tutor-redesign-holes.md` (H-items = holes, D-items = decisions D1–D6).*
