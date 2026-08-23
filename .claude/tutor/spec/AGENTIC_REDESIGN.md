# TUTOR — AGENTIC LAYER REDESIGN (living doc)

Status: BRAINSTORM. Nothing here is built. We edit this until it is complete,
then it becomes the spec.

---

## 0. WHY THIS DOC EXISTS

The current system is one agent + scattered enforcement hooks + a DB. It has no
**agentic layer**: no worker roles, no routing between modes, no observing
orchestrator. This doc designs that layer. Order of design is fixed:

    PROCESS (how a human learns)  →  AGENTS + TOOLS  →  HARNESS  →  DB/SCHEMA

The process is the spec. Everything else is derived from it.

---

## 1. OBJECTIVE & PHILOSOPHY

- The objective is a **real codebase**. Success = the learner can **build that
  codebase by hand, confidently** — and survive being asked *why*, *when-not*,
  and *what-breaks-it*, not just make it run.
- Teaching philosophy = a **senior engineer** teaching someone who does not know
  it at all: highlight the real code, talk through it, test, move up only on
  evidence. ("senior" is the PHILOSOPHY, never an agent name.)
- Carried laws from the old system (do not lose these):
  - Observe THEN enforce — never trust an agent to remember an invariant.
  - One state source decides routing — no second copy that can drift.
  - Distill-to-folders on reset — archived and re-read, never a raw wipe.
  - Schema delivered as a PATH to open, not baked into the prompt.
  - Evidence over self-report. Working code is NOT evidence.
  - Question-first: he attempts before anything is explained (~20% we talk).

---

## 2. THE PROCESS (rethought from scratch)

The codebase is decomposed into **UNITS** (a function, a module, a data flow) in
dependency order. The code's own shape is the curriculum — not a syllabus.

### 2.1 The axes (understanding is multi-dimensional, not syntax)
A unit is OWNED when SOLID across the axes THIS code demands. Which fire depends
on the code's nature.

    COMPREHEND   what does this line/block actually do
    MECHANISM    how it works underneath (not just the surface call)
    RATIONALE    why THIS shape — design intent
    JUDGMENT     when to use it, when NOT, the trade-off
    ROBUSTNESS   what breaks it, the edge/failure it must survive
    INTEGRATION  how it fits the rest of the system
    EVOLUTION    how you'd change / extend / debug it

Syntax alone = COMPREHEND with the other six missing. That is the old failure.

### 2.2 The atomic loop (one unit)

    ① POINT    highlight the exact lines in the TRUE codebase (file:line,
                 re-read off disk — the code is the lesson)
    ② PROBE    "what does this do? why this way?" — he attempts FIRST
    ③ TEACH    only the residue he couldn't reach (~20%)
    ④ TEST     a challenge that FAILS if he's faking (predict / break / port)
    ⑤ JUDGE    per firing axis: SOLID · SHAKY · MISSING
         ├─ SHAKY/MISSING on a prerequisite → DESCEND (open sub-unit, freeze
         │    this one, remember the interrupted question)
         └─ SOLID on every firing axis → MOVE UP to the next unit

### 2.3 The journey

    scan codebase → build ladder of units + axes
      └► for each unit in dependency order: run the atomic loop, descending
         into sub-units whenever a prerequisite is SHAKY
      └► DISTILL what happened → folder files → RESET context → next unit
         reads its folder back
    GRADUATION: he writes real slices from a blank page, confidently.

Reset is MULTI-GRAIN (rung / concept / phase) and PARTIAL — distilled state
persists to organized folders; nothing important is erased.

---

## 3. THE AGENTIC LAYER

### 3.1 Orchestrator = a MODE SWITCH (code decides the mode)
Reads the current user message + DB state. Mode is chosen by a FIXED TABLE in
code, never by an agent (no drift at the top of the loop).

    DETERMINISTIC states (pure code, no LLM):
      • an invariant must fire     (open child → can't own parent)
      • a distill / reset is due   (unit closed → write folders → clear)
      • mechanical routing         (which unit is next in dependency order)
      • enforce a schema on an agent's output

    AGENTIC states (spawn a worker, needs judgment):
      • teach / probe / test the learner on a unit
      • decide SOLID/SHAKY/MISSING on an axis from evidence
      • decide which axes THIS code demands
      • find a unit / prereq in the codebase or web

### 3.2 The worker agents (placeholders — refine the TRUE set)

    MAPPER     scan repo → ladder of units + axes    tools: read-code, search-repo
    TEACHER    run POINT→PROBE→TEACH→TEST loop        tools: read-code(disk), read-DB
    JUDGE      axis verdict + DETECT sub-holes        tools: read-DB, read-transcript
    SEARCHER   codebase / web(MCP) / DB lookup        tools: search-repo, web, read-DB
    DISTILLER  write findings → folders, do the reset tools: write-folders, write-DB

Each worker: cold context, own tool set. TODO: confirm the real role list and
each role's exact tools.

### 3.3 The harness (observe + enforce, deterministic)
Does NOT teach or judge. Watches what agents did, detects state events, refuses
illegal actions:
  • a sub-hole was surfaced → FREEZE unit, PUSH child, REMEMBER the interrupted
    question. (DETECTION MECHANISM — TODO: agent declares vs harness infers)
  • no-own-with-open-child
  • no-mark-axis-SOLID-without-recorded-evidence
  • no-move-up-with-a-firing-axis-unproven
  • validate every agent output against its schema (reject → retry)
Fail-open on unexpected error; fail-closed only on a positive invariant match.

### 3.4 Schema-on-demand
  1. worker finishes a task
  2. calls get_schema(task) → returns a PATH to a schema file + little guidance
  3. worker OPENS it, emits output in that exact structured shape
  4. harness validates output ↔ schema (reject → retry)

---

## 4. THE TABLE WE MUST FILL NEXT  ← main brainstorm target

For every AGENT × STATE, define four things. Other parameters (axis, depth,
verdict history, learner-model flags) modulate the output.

| agent | state / trigger | inputs it reads | OUTPUT it must give | WHERE it goes | WHAT HAPPENS NEXT |
|-------|-----------------|-----------------|---------------------|---------------|-------------------|
| MAPPER | codebase not yet scanned | repo, target | ladder of units+axes | /codebase-map/ | orchestrator opens first unit |
| TEACHER | unit ACTIVE, not yet probed | unit code, learner-model | POINT+PROBE question | to learner + DB(utterance) | wait for learner answer |
| JUDGE | learner answered a TEST | answer, evidence | per-axis verdict | DB(probes) | orchestrator: move up / descend |
| ... | ... | ... | ... | ... | ... |

TODO: enumerate every (agent, state) row. This is where "other parameters affect
what output, where to put it, and what happens next" gets pinned down.

---

## 5. DB DESIGN (TODO — derive from Section 4)

Tables implied so far (refine):
  - units            (id, slug, file, lo, hi, depth, parent_id, state, kind)
  - axes             (unit_id, axis, verdict, evidence_ref)   -- which axes fire + verdict
  - probes           (one row per judgment: unit, axis, test, result, evidence)
  - stack_frames     (the focus stack; only deepest is teachable)  [keep from old]
  - learner_model    (can/can't, misconceptions)  -- NEVER wiped
  - meta             (single state source: current unit, mode inputs)
  - schemas          (task → schema file path)

Folders (persist across reset):
  /learner-model/  /codebase-map/  /concept-archive/  /handoff/

TODO: exact columns, which writes each agent is allowed, invariant SQL.

---

## 6. OPEN DECISIONS

- [ ] Sub-hole detection: agent DECLARES (calls surface_hole) vs harness INFERS
      from transcript. (Leaning: declare + harness backstop.)
- [ ] The TRUE agent list and each one's exact tools.
- [ ] Full AGENT × STATE table (Section 4).
- [ ] DB columns + per-agent write permissions (Section 5).
- [ ] Which axes fire: fixed rule per code-kind vs JUDGE decides per unit.
- [ ] Reset grains: exact triggers for rung / concept / phase resets.
