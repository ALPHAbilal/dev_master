# TUTOR — THE TEMPLATE CATALOGS

Status: LIVE. These are the fill-in-the-blank templates that ride the two arrows
of the core engine (see MASTER.md → THE CORE ENGINE). Nothing here is code yet;
this is the spec every agent-wakeup and every agent-return must obey.

The one shape everything follows:

    <arrow>.<step> = { agent · WHEN · initial READS/inject ·
                       runtime capabilities · emit · accepted WRITES · next route }

Four catalogs:
    A. WAKEUP templates   code → agent   (keyed by STEP; sets agent/tools/harness)
    B. RETURN templates   agent → code   (the stamp; payload is the CATEGORY)
    C. ROUTING table      code → code    (category → next wakeup; the stack moves)
    D. ACTION hooks       code → code/agent (live learner events during work)

Stone numbers refer to STONES.md (the 12-stone set):
    LIVE-DB   (1) units  (2) axes  (3) stack  (4) meta
    PERSIST   (5) probes(DB)  (6) learner(DB)  (7) archive(file)  (8) handoff(DB)
    READ-ONLY (9) codebase  (10) schemas
    LIVE      (11) workspace(file)  (12) events(DB, moved to archive on close)
    (`snapshot` = the per-turn wakeup input, assembled fresh; not a stone.)

Tool vocabulary (the only tools that exist):
    read-code · read-db · read-folders · read-transcript · search
    talk-to-learner · write-db · write-folders · observe-action

## THE LIFECYCLE INSIDE EVERY WAKEUP

A wakeup defines a complete agent-life contract. It does not create another
engine: the agent still returns through Catalog B and code still routes through
Catalog C.

```
 AT WAKEUP  code injects only the named minimum packet and grants scoped tools.

 DURING WORK an agent may call only the named capabilities. A capability has a
             purpose, scope, and guard. A read/write/observe result or rejection
             returns to the still-running agent so it can adapt before emitting.
             Any write is authorized, validated, committed, and logged by code.

 AT EMIT    the agent produces only the step's SAY, stamp, or typed escalation.
             Its output shape is known at wakeup, never supplied after it finishes.

 AFTER EXIT code validates, applies deterministic policy, records accepted
             effects, delivers approved SAY, and picks the next route.
```

`READS` below means the initial injection. A step may make a further read or a
guarded live write only when its TOOLS/capabilities line explicitly grants it;
no step receives all stones or unrestricted filesystem/database access.

---

## CATALOG A — WAKEUP TEMPLATES  (code → agent)

One per STEP. Code fills the blanks from live state, hands the agent ONLY what
the READS line names, and nothing more (minimal injection is enforced here).

```
┌─ wakeup.map ─────────────────────────────────────────── agent: MAPPER ───┐
│ WHEN     phase = SCAN, codebase not yet mapped                            │
│ TOOLS    read-code · search                                               │
│ READS    (9 codebase, whole repo)                                        │
│ INJECT   the repo root + the target goal — "what must he be able to build"│
│ HARNESS  units MUST be in dependency order; every unit gets its axis set  │
│ PRODUCES return.map; guarded code validates then records (1 units)+(2 axes)│
└──────────────────────────────────────────────────────────────────────────┘

┌─ point ──────────────────────────────────────────────── [CODE, no agent]─┐
│ WHEN     a unit is NEW, about to be worked                                │
│ ACTION   highlight (9 codebase) U.file:lo-hi in the REAL editor           │
│          (INTERFACE.md) — no LLM call. Then wakeup.probe fires.           │
│ WHY      the learner reads the code where it lives; POINT needs no brain. │
└──────────────────────────────────────────────────────────────────────────┘

┌─ wakeup.probe ───────────────────────────────────────── agent: TEACHER ──┐
│ WHEN     unit POINTED, or a re-probe was routed to us                     │
│ TOOLS    read-code · read-db                                              │
│ READS    (9 codebase slice) (2 axes: current axis) (6 learner: can/cant)  │
│          (3 stack: hop_budget) (snapshot: last category)                 │
│ INJECT   the lines + the ONE axis + his level + how narrow to go          │
│ HARNESS  question-first — reveal NO answer; he attempts first; via `draft`│
│ PRODUCES one probing question → learner ; WRITES (3 stack: resume_q)      │
└──────────────────────────────────────────────────────────────────────────┘

┌─ wakeup.teach ───────────────────────────────────────── agent: TEACHER ──┐
│ WHEN     routing said CONTINUE and a small residue remains                │
│ TOOLS    read-code · read-db                                              │
│ READS    (9 codebase slice) (2 axes: what he already proved) (6 learner)  │
│ INJECT   only the gap he could NOT reach on his own                       │
│ HARNESS  fill ~20% MAX; never teach an un-probed prerequisite unasked     │
│ PRODUCES SAY: short explanation + pause_for_reaction:boolean               │
└──────────────────────────────────────────────────────────────────────────┘

┌─ wakeup.test ────────────────────────────────────────── agent: TEACHER ──┐
│ WHEN     unit TAUGHT, or a harder test was routed (faking / skip-req)     │
│ TOOLS    read-code · read-db                                              │
│ READS    (9 codebase slice) (2 axes: axis + evidence_bar)                 │
│ INJECT   the axis + what counts as proof for THIS axis (predict/break/port)│
│ HARNESS  the test must FAIL if he's faking; working code is NOT evidence   │
│ PRODUCES a challenge → learner                                            │
└──────────────────────────────────────────────────────────────────────────┘

┌─ wakeup.grade ───────────────────────────────────────── agent: JUDGE ────┐
│ WHEN     the learner just answered a PROBE or a TEST                      │
│ TOOLS    read-transcript · read-code · read-db                           │
│ READS    (snapshot: his answer) (9 codebase slice) (2 axes: verdict hist) │
│          (5 probes: recent struggle on this axis) (6 learner: misconceptions)│
│ INJECT   his words + the axis + the evidence_bar + prior verdicts         │
│ HARNESS  no SOLID without cited evidence; must also FLAG any hidden gap    │
│ PRODUCES the verdict stamp (see return.grade)                            │
└──────────────────────────────────────────────────────────────────────────┘

┌─ wakeup.distill ─────────────────────────────────────── agent: DISTILLER ┐
│ WHEN     unit became OWNED, or the learner is fatigued (park)             │
│ TOOLS    read-db · read-transcript                                        │
│ READS    (1 units) (2 axes) (3 stack) (5 probes) (11 workspace)(12 events)│
│ INJECT   what to preserve: tests, evidence, event trace, workspace snapshot│
│ HARNESS  titled archive MUST be written before events/live memory clear   │
│ PRODUCES return.distill: title + archive + learner update + handoff      │
└──────────────────────────────────────────────────────────────────────────┘
```

NOTE — the pure-code steps (invariant fires, reset due, next-unit-in-order,
2nd-shaky=miss) have NO wakeup card: they wake no agent. They live only in
Catalog C (routing).

---

## CATALOG D — LIVE ACTION HOOKS  (code → code/agent, during work)

An action hook observes a learner command, source edit, test result, or UI
action while an interaction is live. It is not a return stamp and never creates
a second routing system.

```
┌─ action.<event> ─────────────────────────────────────────── [CODE] ─────┐
│ WHEN     a learner command, edit, test output, or UI action is observed   │
│ READS    only the event evidence + current unit/axis + relevant code slice│
│ WRITES   (12 events) automatically before policy/agent handling           │
│ IF FACT  code can decide objectively → block | factual feedback | record  │
│            | refresh context | continue                                    │
│ IF MEANING / INTENT / REASONING                                             │
│          code wakes TEACHER or JUDGE with a minimal event packet            │
│ THEN     the agent emits normally → Catalog B → Catalog C routes normally  │
│ GUARD    code NEVER infers a learner category from semantic event meaning   │
└──────────────────────────────────────────────────────────────────────────┘
```

Every observed event is appended immediately to (12 events). On unit close,
Catalog B's distill transaction moves the raw stream into the titled (7 archive)
artifact. `probes` remains the separate semantic Q&A diary.

---

## CATALOG B — RETURN TEMPLATES  (agent → code)

The stamp the agent hands back. Its payload is what code routes on. Teacher
steps primarily return SAY to the learner, with small step effects where needed:
PROBE supplies `resume_q`; TEACH supplies `pause_for_reaction`; TEST logs its
question. The three full structured stamps below are map, grade, and distill.

```
┌─ return.map ─────────────────────────────────────── from: MAPPER ────────┐
│ STAMP    a list of units, each: {slug, file, lo, hi, depth, parent,       │
│                                   axes_firing[]}  in dependency order      │
│ WRITES   (1 units: initial rows, all state=NEW) (2 axes: firing rows,     │
│          all UNGRADED)                                                     │
│ THEN     code opens the first unit with no unmet prereqs → point→probe    │
└──────────────────────────────────────────────────────────────────────────┘

┌─ return.grade ───────────────────────────────────── from: JUDGE ─────────┐
│ STAMP    { axis, verdict: SOLID|SHAKY|MISSING,                            │
│            category: <learner route signal; one of the 15 in Catalog C>,  │
│            evidence_ref, hidden_gap?: {slug, why} }                       │
│ WRITES   (2 axes: this axis + shaky_count) (5 probes: append one Q&A row) │
│          (6 learner: append a misconception if found)                    │
│ THEN     code reads `category` → Catalog C picks the next wakeup          │
└──────────────────────────────────────────────────────────────────────────┘

┌─ return.distill ─────────────────────────────────── from: DISTILLER ─────┐
│ STAMP    the archive file itself — its SHAPE is the folder's shape:       │
│          { unit, title, logical_document, axes_tested[], tests[], evidence[],│
│            event_log, workspace_snapshot, final_verdict, resume_at? }    │
│ WRITES   (7 archive) (6 learner) (8 handoff); MOVES (12 events) → archive │
│ THEN     on PARK, CODE MOVES (3 stack) → (8 handoff.resume_stack) and     │
│          records continuation{next_step, awaiting, question_ref?, refs[]} │
│          at a safe boundary; then it clears unit live state. Workspace     │
│          (11) stays under one name. On re-entry code restores the stack    │
│          and sends the ordinary minimal wakeup—no “resume mode” prompt.   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## CATALOG C — ROUTING TABLE  (code → code, step ③)

Code reads the learner route signal currently named `category` off return.grade
and fires the next wakeup. Verdicts are the assessment; categories are learner
signals; pure-code facts are deterministic policy. This is where the stack moves
(branch down / climb up). Invariant: every category has a next — NONE dead-ends.

```
 CATEGORY (what the learner did)     STACK MOVE        NEXT WAKEUP
 ───────────────────────────────────────────────────────────────────────────
 correct & deep                      —                 next axis → point→probe
   └ if SOLID on ALL axes            pop (OWNED)       wakeup.distill → climb up
 faking (pattern-matched)            —                 wakeup.test  (harder)
 SHAKY  (1st on this axis)           —                 wakeup.probe (narrower,hop−)
 SHAKY  (2nd on this axis)   [code: =MISSING]  push child   point→probe (child)
 wrong / misconception               push child        point→probe (child)
 different prereq hole               push child        point→probe (child)+resume_q
 sibling hole              [code: queue 3 stack.pending] — continue → wakeup.teach/test
 confused about the question         —                 wakeup.probe (rephrase)
 answered a different axis           —                 wakeup.probe (redirect axis)
 off-topic / tangent                 —                 wakeup.probe (redirect)
 "I don't know" / gives up           —                 wakeup.probe (metered hint)
 silent / stuck                      —                 wakeup.probe (metered push)
 disputes the verdict     [code: hold verdict]     —   wakeup.teach (show evidence)
 "I already know this" (skip-req)    —                 wakeup.test  (cannot skip)
 fatigue / wants to switch           park + pop        wakeup.distill → RESET
 working code, wrong reasoning       —                 wakeup.probe (MECHANISM axis)
```

Pure-code facts that fire in this same step ③ (no agent, no category needed):
```
 invariant fires   →  BLOCK the illegal move (no OWNED with an open child;
                      no SOLID without evidence)  → stay put, re-route
 reset due         →  a unit closed → wakeup.distill → clear → next
 next-unit         →  after a pop with no parent → pick next top-level unit
                      in dependency order → point→probe
 2nd-shaky=miss    →  (2 axes: shaky_count) reached 2 → verdict=MISSING, push child
```

---

## OPEN SLOTS (fill as we go)
- [x] POINT → RESOLVED: it's a code-side editor highlight (no agent), folded
      into probe. Routing shows "point→probe" = highlight then wakeup.probe.
- [ ] exact evidence_bar per axis (what "proof" means for each of the 7 axes)
- [ ] hop_budget mechanics: how much it shrinks per SHAKY, floor value
- [ ] search: confirm it stays a shared TOOL, not its own agent
- [ ] schema files (10 schemas): one schema file per return.* stamp above
