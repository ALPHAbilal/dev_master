# TUTOR — THE LEARNING PROCESS (independent of agents)

Status: BRAINSTORM. This file describes ONLY the process a human goes through to
learn a codebase — the variables, the parameters, and the full step sequence.
No agents, no harness, no DB tables. Reason about the process here alone; when it
is right, the agentic layer (see AGENTIC_REDESIGN.md) is derived from it.

Rule for this file: if a step cannot be described without naming an agent, the
step is not yet understood. Push failures/holes to Section 4 as they appear.

---

## 1. THE VARIABLES (the full state of a learning session)

### 1.1 Global (one value at a time)
    G.target         the codebase to be able to build
    G.current_unit   the unit being worked right now (deepest on the stack)
    G.mode           DETERMINISTIC | AGENTIC   (derived, not stored by a human)
    G.phase          SCAN | LOOP | GRADUATION   (coarse position)

### 1.2 Per unit (every unit on the stack carries its own)
    U.slug           name of the unit
    U.file, U.lo, U.hi   the real code it lives in (highlighted off disk)
    U.kind           TARGET (destination, full ownership) | TRANSIT (stepping stone)
    U.depth          0 = a top-level unit; >0 = a sub-hole
    U.parent         which unit this was descended from
    U.state          NEW | POINTED | PROBED | TAUGHT | TESTED | JUDGED | OWNED | PARKED
    U.axes_firing    which of the 7 axes THIS code demands
    U.axis_verdict   per firing axis: UNGRADED | SOLID | SHAKY | MISSING
    U.resume_q       the question that was interrupted when we descended
    U.pending        sibling holes found but not yet opened

### 1.3 Learner model (persists across ALL resets — never wiped)
    L.can            axes/units proven SOLID (with evidence, not self-report)
    L.cant           known gaps
    L.misconceptions cross-unit wrong beliefs, disproved by real code
    L.shown          terms/ideas he has been EXPOSED to (vs proved)
    L.hop_budget     how many inferences a question may chain (shrinks when SHAKY)

---

## 2. THE PARAMETERS (what modulates a step's behavior)

These change WHAT happens at a step without changing the step sequence.

    P.axis           which axis is being taught/tested right now
    P.depth          deeper = tighter, shorter questions
    P.verdict_hist   a second SHAKY on one axis = MISS (twice-shaky ≠ almost)
    P.proximity      distance of a unit to G.target (far = don't surface it)
    P.evidence_bar   what counts as proof for THIS axis (predict/break/port/...)
    P.reset_grain    rung | unit | phase — what a reset clears and distills
    P.code_nature    what kind of code the unit is (selects P.axis set)

---

## 3. THE FULL PROCESS (state machine, no agents)

### 3.1 Phase SCAN (runs once per codebase)
    S0  read the whole real codebase
    S1  decompose into UNITS in dependency order
    S2  for each unit, mark U.axes_firing from P.code_nature
    S3  → enter LOOP at the first unit with no unmet prerequisites

### 3.2 Phase LOOP — the atomic loop on G.current_unit
    Precondition: U.state = NEW on the deepest live unit.

    POINT   highlight U.file:U.lo-U.hi off disk        U.state: NEW → POINTED
    PROBE   ask the question whose answer IS the next   U.state: POINTED → PROBED
            step (he attempts FIRST). Record U.resume_q.
            → wait for his answer.
    TEACH   explain ONLY the residue he could not reach U.state: PROBED → TAUGHT
            (~20%). Skip if PROBE already showed SOLID.
    TEST    pose a challenge that FAILS if he is faking U.state: TAUGHT → TESTED
            (predict a change / break it / port it).
            Choose test by P.evidence_bar and P.axis.
    JUDGE   grade the firing axis: SOLID | SHAKY | MISSING  U.state: TESTED → JUDGED
            update U.axis_verdict[P.axis], L.can/L.cant.

    Then branch on JUDGE:
      (a) a NEW sub-hole surfaced (any axis, even mid-test):
              freeze U, push child unit (U.depth+1), copy the interrupted
              U.resume_q, → POINT on the child.
      (b) SHAKY/MISSING on this axis, no deeper hole:
              re-PROBE narrower (P.hop_budget shrinks), stay on the unit.
      (c) SOLID and MORE firing axes remain:
              advance P.axis to the next firing axis, → POINT (or PROBE) again.
      (d) SOLID on ALL firing axes:
              U.state → OWNED. DISTILL (3.4). Pop to parent, replay parent's
              U.resume_q. If no parent → next top-level unit.

### 3.3 Descent / ascent invariants (the part the old flat chain lost)
    - only the DEEPEST unit may be taught/graded.
    - a unit cannot become OWNED while any child is live.
    - a unit cannot become OWNED with any firing axis UNGRADED/SHAKY/MISSING.
    - popping replays the exact interrupted question (U.resume_q).

### 3.4 DISTILL + RESET (multi-grain, partial — never a raw wipe)
    On a reset boundary (grain = P.reset_grain):
      - write the OWNED unit's axes, tests, evidence, verdict → concept-archive
      - update the learner model (L.*) → learner-model store
      - write a 'what just happened' handoff → handoff store
      - clear working context
      - next unit re-reads its folder(s) back (warm start, not cold)

### 3.5 Phase GRADUATION
    When all TARGET units at depth 0 are OWNED:
      - he writes real slices of G.target from a blank page.
      - CONFIDENT = builds it AND survives why / when-not / what-breaks-it.

---

### 3.6 LEARNER-STATE TAXONOMY (every category a turn can fall into)

The clean branches in 3.2 (a–d) are not enough. A real turn falls into one of
the categories below. Each has a RESOLUTION and a RE-ENTRY point. The invariant:
**every category resolves back to a known U.state — no category dead-ends.** This
is what "go back to the main loop" means.

    category                          resolution         re-enter loop at
    ────────────────────────────────────────────────────────────────────────
    correct & deep                    accept             advance P.axis / MOVE UP
    correct but pattern-matched(fake) harder TEST        re-TEST (deeper)
    partially right (SHAKY)           narrow re-PROBE     PROBE (hop_budget−)
    wrong / misconception (MISSING)   name it, descend   POINT (child)
    reveals a DIFFERENT prereq hole   push child         POINT (child) + resume_q
    reveals a SIBLING hole            queue U.pending    continue current unit
    confused about the QUESTION       rephrase           re-PROBE (same axis)
    answers a DIFFERENT axis          redirect           PROBE (intended axis)
    off-topic / tangent               redirect           resume U.state
    "I don't know" / gives up         metered hint       re-PROBE (smaller)
    silent / stuck                    metered push       re-PROBE (smaller)
    disputes the verdict              show evidence      hold verdict, continue
    "I already know this" (skip req)  TEST anyway        TEST (cannot skip)
    fatigue / switch unit-or-phase    DISTILL + park     reset → new unit
    working code, wrong reasoning     probe reasoning    re-PROBE (MECHANISM/RATIONALE)

This list is not final — add categories as they appear.

### 3.7 WHO HANDLES CATEGORIZATION (orchestrator + minimal injection)

The ORCHESTRATOR is a DETERMINISTIC DISPATCHER. It never reads or classifies the
learner's words — that is always judgment (an agent's job). Each turn it captures
LIVE state (U.state, last verdict, hop_budget, recent category, DB status) and
applies ONE test:

  DOES RESOLVING THIS STEP NEED THE LEARNER'S WORDS INTERPRETED?

  - NO → the state alone settles the move → resolve it in pure code, no agent.
    These are narrow and never read free text: an invariant fires; a reset is
    due; the next unit in dependency order; a DB-COUNTER fact (second SHAKY on an
    axis = MISS — a stored count, not a reading of his sentence).

  - YES → wake an agent. Code's deterministic job is only to ASSEMBLE THE WAKEUP
    PACKET from state: WHICH agent, WHAT minimal context, WHICH tools. The agent
    then interprets the words and picks the category (skip-request? off-topic?
    faking? deeper gap?).

Watch the trap: skip-request and off-topic REQUIRE reading his message → agent.
Only count/state facts (2nd SHAKY) are pure code. Do not conflate them.

Principle: the agent is never handed the whole rulebook. Live status is the
filter that shapes the wakeup packet — a few lines + the right tools, not tens of
pages. Bombarding the agent with the full process is itself a failure mode (H-INJ
below); so is having code try to parse the learner's words.

## 4. FAILURE MODES / HOLES (fill as they appear — before we build/test)

These are the places the process can silently break. Add each hole here the
moment we spot it, with the variable/step it threatens.

    H1  ...
    H2  ...
    H3  ...

(seed candidates to pressure-test:)
  - a sub-hole surfaces but the interrupted U.resume_q is not captured → descent
    is irreversible (the exact old-system failure).
  - U.axes_firing chosen wrong → a unit marked OWNED that is only COMPREHEND-deep.
  - reset distills the wrong thing → next unit cold-starts and re-derives.
  - P.evidence_bar too weak → working code credited as understanding.
  - L.shown vs L.proved conflated → a question uses a term he never actually owned.
  - H-INJ: the agent is handed the full process/rulebook instead of the one
    category's minimal instruction → it ignores or misapplies it. Live status
    must FILTER what is injected; deterministic cases inject nothing to an agent.
  - a learner category has no re-entry point → the loop dead-ends in a side branch.

---

## 5. WHAT THIS FILE OWES THE AGENTIC LAYER

Once Sections 1–3 are stable, AGENTIC_REDESIGN.md Section 4 maps each STEP above
to (agent, output, destination, next). Every U.state transition here becomes a
row there. If a transition has no owner, that is a missing agent — not a missing
rule.
