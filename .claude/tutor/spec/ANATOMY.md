# TUTOR — TURN ANATOMY, RUNTIME CAPABILITY LOOP, AND LIVE ACTIONS

Status: LIVE COMPANION. This document does not introduce another engine
or change the learning logic. It makes the existing two-arrow engine precise at
the time scale of one agent invocation: what is supplied at wakeup, what can
happen while the agent is working, what it emits, and what code does after the
agent exits. It explicitly includes the **runtime capability loop**: scoped
tool use and guarded state updates while an agent is alive.

Read with `MASTER.md` (overall control flow), `CATALOGS.md` (step contracts),
and `agents/*.md` (agent behaviour). The authoritative learning/routing rules
remain in `MASTER.md` and `CATALOGS.md`.

---

## 1. THE MODEL — AGENT LIFE, NOT PRE/BODY/POST

An agent has only three moments in its own life: it wakes with a small packet,
it works with scoped capabilities, and it emits a result. Validation, durable
writes, delivery, and routing happen **after the agent has exited**. They are
code's receiving behaviour, not phases of the agent.

```
                      one invocation of an agent

  CODE                                                         CODE
   │                                                            ▲
   │  ① WAKEUP: selected instruction + minimal context          │
   └──────────────────────────────────────────────────────►     │
                                                ┌─────────────┐  │
                                                │   AGENT     │  │
                                                │             │  │
                                                │ A. wake     │  │
                                                │ B. work     │  │
                                                │ C. emit     │  │
                                                └──────┬──────┘  │
                                                       │         │
   ┌───────────────────────────────────────────────────┘         │
   │  ② RETURN: SAY and/or structured stamp                       │
   └──────────────────────────────────────────────────────────────┘
                               │
                               ▼
                   ③ CODE RECEIVES AND ROUTES
                   validate -> enforce -> commit ->
                   deliver (if SAY) -> next action
```

The only repeating control engine is still:

```
  CODE -- wakeup.<step> --> AGENT -- return.<step> --> CODE -- route --> next step
```

`TURN ANATOMY` is an explanation of what occurs inside those arrows. It is not
a third arrow and it is not a second state machine.

---

## 2. THE FOUR TIME WINDOWS

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ A. AT WAKEUP — code -> agent                                                 │
│                                                                              │
│ Code chooses the step from state and prepares only its minimal packet:       │
│   • step objective and current unit/axis                                     │
│   • the specific source slice, learner message, or state facts required      │
│   • the agent's stable instructions and the step-specific instruction        │
│   • scoped tools and their allowed purpose                                   │
│   • the required SAY/stamp shape                                              │
│                                                                              │
│ Code does not classify the learner's free text here.                         │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ B. DURING WORK — agent is alive                                              │
│                                                                              │
│ The agent reasons under its role rules and may use only its scoped tools.    │
│ It can read, and when explicitly granted write, through the runtime          │
│ capability loop below. Tool results return to the living agent, so it can    │
│ adapt before its final emit. Live learner events can arrive here through      │
│ ACTION HOOKS (section 7).                                                    │
│                                                                              │
│ The agent never chooses the global route; every state write is guarded.      │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ C. AT EMIT — agent -> code                                                   │
│                                                                              │
│ The agent emits exactly what its step allows:                                │
│   • SAY: learner-facing prose, when the agent is learner-facing              │
│   • STAMP: structured result, when code must persist or route on it          │
│   • ESCALATION: a typed inability/need, never a guessed result               │
│                                                                              │
│ The agent's result is a proposal until code accepts it.                       │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ D. AFTER EXIT — code receives                                                │
│                                                                              │
│ Code validates the shape, enforces objective laws, commits approved changes, │
│ delivers approved SAY text, and executes the next deterministic route.       │
│ This is outside the agent's lifetime.                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. THE RUNTIME CAPABILITY LOOP — TOOLS AND LIVE STATE

**Runtime capability loop** is the name for an agent's intelligent, scoped
interaction with tools and state while it is alive. It is optional per step:
the wakeup contract names exactly which capabilities exist and their purpose.
It is not deferred until the final stamp.

```
                         AGENT IS ALIVE
                                │
              decides it needs a permitted capability
                                │
                                ▼
                   tool call: read | write | observe
                                │
                                ▼
             [CODE] GUARDED CAPABILITY SERVICE
                │                 │                 │
                ▼                 ▼                 ▼
             authorize          validate          execute
             scope/policy       input/state       read or write
                │                 │                 │
                └─────────────────┴─────────────────┘
                                │
                                ▼
                         result / rejection
                                │
                                ▼
               returned to the still-running agent
                                │
                                └──> reason, retrieve more, update more,
                                     or emit its final SAY/stamp
```

The word **guarded** is essential: an agent can request or invoke a granted
write during work, but the capability service—not an unmediated model response—
authorizes, validates, commits, and logs it. The same policy and invariants that
would protect a final commit protect every live write.

```
 WAKEUP CONTRACT MUST DECLARE
   capabilities: read-code | read-db | write-db | read-folders |
                 write-folders | read-transcript | search | observe-actions
   scope:        exact stones, rows/files, source range, or event stream
   when:         the condition/purpose for each capability
   write rule:   allowed operation + invariant/schema/policy gate
   result:       what the agent receives after success, rejection, or conflict
```

Examples:

```
 TEACHER  reads a relevant source slice after a learner action; it may revise
          its next question using that result.

 JUDGE    reads the transcript/code while evaluating evidence; it may request
          no policy write because verdict persistence remains code-mediated.

 DISTILLER may write an archive through a guarded write capability during its
          work if its contract grants that operation; the service must reject an
          archive lacking required proof before the agent continues.

 CODE     can keep the existing "agent emits a stamp, code commits it" pattern
          for any step. The loop enables live updates; it does not require them.
```

---

## 4. THE COMPLETE PROCESS MAP

```
                                      LEARNER GOAL
                                           │
                                           ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ SCAN                                                                        │
 │ [CODE] phase=SCAN -> wakeup.map                                             │
 │ [MAPPER] reads codebase; emits dependency-ordered units + firing axes       │
 │ [CODE] validates and records units/axes; selects first available unit       │
 └───────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ LOOP: work the deepest live unit and its current learning axis              │
 │                                                                           │
 │  [CODE] POINT: highlight U.file:lo-hi in the real editor (no LLM)          │
 │       │                                                                   │
 │       ▼                                                                   │
 │  ① wakeup.probe -> TEACHER                                                │
 │     inject: code slice + current axis + learner level + hop budget        │
 │     emit: one question/SAY + resume_q                                     │
 │       │                                                                   │
 │       ▼                                                                   │
 │  LEARNER answers, runs a command, edits the one workspace file, or acts  │
 │       │                                                                   │
 │       ├─ CODE records (12 events), then action hook (section 7)           │
 │       │                                                                   │
 │       ▼                                                                   │
 │  ① wakeup.grade -> JUDGE                                                  │
 │     inject: learner words + current axis/evidence bar + relevant history  │
 │     emit: verdict + category + evidence_ref + optional hidden_gap          │
 │       │                                                                   │
 │       ▼                                                                   │
 │  ② return.grade -> CODE                                                   │
 │       │                                                                   │
 │       ▼                                                                   │
 │  ③ ROUTE [CODE]                                                          │
 │     ├─ re-probe needed -> wakeup.probe                                    │
 │     ├─ harder proof needed -> wakeup.test                                 │
 │     ├─ small residue -> wakeup.teach -> pause or wakeup.test              │
 │     ├─ child prerequisite -> push child -> POINT -> probe child           │
 │     ├─ sibling gap -> queue pending; continue current unit                 │
 │     ├─ unit complete -> wakeup.distill                                    │
 │     └─ fatigue -> park -> wakeup.distill                                  │
 └───────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ DISTILL + RESET                                                            │
 │ [DISTILLER] emits titled archive + learner diff + handoff                  │
 │ [CODE] saves proof/snapshot, moves (12 events) into archive, then clears  │
 │        unit live working state; the one workspace document remains          │
 │ [CODE] pops to a parent and replays resume_q, or starts next top unit      │
 └───────────────────────────────────────────────────────────────────────────┘
                                           │
                                           ▼
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ GRADUATION                                                                  │
 │ all top-level units are OWNED -> learner rebuilds target code from blank   │
 │ and explains why, when-not, and what breaks it -> CONFIDENT                │
 └───────────────────────────────────────────────────────────────────────────┘
```

---

## 5. STEP CONTRACT INVENTORY

This is the preservation checklist for a future catalog/card cleanup. Changing
any trigger, initial injection, allowed retrieval, output, guard, write, or
route below is a **logic change**, not documentation cleanup.

```
 STEP / OWNER          AT WAKEUP              DURING WORK            AT EMIT
 ──────────────────────────────────────────────────────────────────────────────
 point / CODE          U.file:lo-hi           —                      highlight, then probe

 map / MAPPER          repo + goal             read-code/search      return.map: units + axes

 probe / TEACHER       code; axis; learner;    scoped code/DB reads  SAY question + resume_q
                        hop budget

 teach / TEACHER       code; proof state;      scoped code/DB reads  SAY residue + pause boolean
                        learner

 test / TEACHER        code; axis/evidence bar scoped code/DB reads  SAY challenge; log question

 grade / JUDGE         words; code; axis;      transcript/code/DB    return.grade: verdict,
                        evidence/history        reads                 category, evidence, hidden gap

 distill / DISTILLER   unit; axes; stack;      contract-scoped       return.distill: archive,
                        diary; learner; status guarded reads/writes  learner diff, handoff

 route / CODE          accepted result + DB    guarded state moves   next step / stack movement
                        facts/invariants
```

```
 RECEIVER / CODE ACTIONS
 ─────────────────────────────────────────────────────────────────────────────
 map      validate unit order/ranges/axes -> commit units + axes -> first unit
 probe    validate SAY rules -> deliver -> wait for learner
 teach    validate SAY rules -> deliver -> STOP or test from pause boolean
 test     validate SAY rules -> deliver -> wait for learner
 grade    validate evidence -> enforce threshold policy -> commit grade/diary
          /misconception -> route category
 distill  validate proof -> commit archive/learner/handoff -> clear live state
          -> pop/replay parent resume_q or choose next top-level unit
```

### Current agent ownership

```
 MAPPER      maps the codebase; never talks to the learner.
 TEACHER     probes, teaches, and tests; never grades; learner-facing.
 JUDGE       interprets an answer; grades one current axis; never talks to the
             learner and never decides policy thresholds.
 DISTILLER   compresses proof, learner changes, and the warm-start note; never
             talks to the learner.
 CODE        highlights POINT, validates, persists, counts policy thresholds,
             moves the stack, and routes.
```

---

## 6. SUBHOLES, SIBLINGS, AND SMOOTH RETURN

The stack is what makes a detour reversible. Only the deepest live unit may be
taught or graded.

```
 PARENT UNIT P
   probe question Qp is saved as P.resume_q
        │
        │ JUDGE detects a missing prerequisite C
        ▼
 [CODE] freeze P; PUSH child C on stack
        │
        ▼
 POINT C -> probe/teach/test/grade C -> C becomes OWNED
        │
        ▼
 DISTILL C -> [CODE] POP C
        │
        ▼
 restore P as deepest unit; replay exact saved question Qp
        │
        ▼
 continue P without losing the original lesson thread
```

Sibling gaps do not interrupt the current prerequisite chain:

```
 JUDGE finds sibling S while working unit U
        │
        ▼
 [CODE] append {S, why} to stack.pending
        │
        ▼
 continue U's current axis
        │
        ▼
 when U's dependency-safe route permits it, select queued S as the next unit
```

Invariants:

```
 • Only the deepest unit may be taught or graded.
 • A parent cannot become OWNED while a child is live.
 • A unit cannot become OWNED until every firing axis is SOLID.
 • A pop replays the exact remembered resume_q.
 • A sibling is queued, not mistaken for a blocking child.
```

### Cold return / checkpointed continuity

Parking is a code-owned, atomic state move—not a weaker second kind of lesson.
At a safe boundary, code moves the live stack from (3) into
`(8) handoff.resume_stack`, records the next normal engine step, and anchors it
to the current workspace revision and only the needed evidence references.

```
 normal live interaction                         cold return
 ───────────────────────                         ───────────
 agent return / learner event / guarded commit
                    │                                  │
                    ▼                                  ▼
     [CODE] safe checkpoint boundary          [CODE] read handoff first
                    │                                  │
                    ▼                                  ▼
 MOVE stack (3) -> handoff (8)                MOVE resume_stack (8) -> (3)
 continuation:                                 restore workspace revision
   next_step, awaiting, question ref, refs     load only referenced evidence
                    │                                  │
                    ▼                                  ▼
 clear live unit state                         build ordinary wakeup packet
                                                    │
                                                    ▼
                                               same agent behavior as if
                                               the session never stopped
```

The `continuation` record distinguishes important cases without changing an
agent's instruction quality: an already displayed question waits for the saved
learner answer (no duplicate Teacher call); a saved answer can continue at
`wakeup.grade`; a TEACH pause waits for a reaction; a finished child restores
the parent frame and its `resume_q`. Code never checkpoints an agent call or a
tool transaction halfway through. The agent receives the ordinary scoped packet,
not a full database dump or a “you are resuming” narrative.

---

## 7. LIVE ACTION HOOKS — CONDITIONAL FEEDBACK DURING WORK

An action hook is a code-owned event gate for learner commands, code edits,
test runs, or other observable actions. It runs while an interaction is live;
it is neither an agent return nor a replacement for routing.

```
 learner command / edit / test result / UI action
                         │
                         ▼
                [CODE] ACTION HOOK
                         │
     ┌───────────────────┼────────────────────────────────────┐
     │                   │                                    │
     ▼                   ▼                                    ▼
 objective rule      state-changing event              interpretation needed
 (no text reading)   (no text reading)                 (meaning/intent matters)
     │                   │                                    │
     ▼                   ▼                                    ▼
 block or give        record the event /                wake the appropriate
 immediate factual    refresh the next packet           agent with the minimum
 feedback             / continue                        action evidence
                                                             │
                                                             ▼
                                                   normal return -> route
```

Examples:

```
 CONDITION (CODE can know objectively)          RESPONSE
 ─────────────────────────────────────────────────────────────────────────────
 command is prohibited in this exercise          block; explain the constraint
 answer/test is requested before an attempt      block/redirect to required probe
 action is allowed and exposes expected output   record event; continue
 source edit changes the current code slice      record/refresh code slice; continue

 CONDITION (requires interpreting meaning)       RESPONSE
 ─────────────────────────────────────────────────────────────────────────────
 learner's command shows a misconception         wake JUDGE with command + output
 learner's edit reveals a prerequisite gap       wake JUDGE/TEACHER with evidence
 learner asks why an observed result occurred    wake TEACHER with the event context
```

Rules for action hooks:

```
 • Code may block or explain only facts it can determine without interpreting
   the learner's words or intent.
 • If feedback needs semantic judgment, code packages the event and wakes an
   agent. It does not invent a category itself.
 • Every observed action is first saved to (12 events). The event packet contains
   only relevant command, output, edit diff, test
   result, current unit/axis, and source slice.
 • If an agent's response reveals a child or sibling gap, the existing
   return.grade -> route path handles it. No parallel gap mechanism exists.
 • Action hooks may create an immediate learner-facing factual message, but
   never bypass the normal validation/routing path for judgments or state moves.
```

---

## 8. DATA OWNERSHIP THROUGH THE TURN

```
                              READ AT WAKEUP / DURING WORK
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ (1) units       current unit, source range, state                         │
 │ (2) axes        current axis, verdict history, evidence_bar               │
 │ (3) stack       resume_q, depth, pending siblings, hop budget             │
 │ (4) meta        target, phase, current unit                               │
 │ (5) probes      recent Q&A evidence and struggle history                  │
 │ (6) learner     established ability, gaps, misconceptions                 │
 │ (7) archive     retained proof for future review                           │
 │ (8) handoff     warm-start context                                         │
 │ (9) codebase    real source, read only                                     │
 │ (10) schemas    return shapes, read only                                   │
 │ (11) workspace  one stable learner-visible document                        │
 │ (12) events     automatic commands/edits/tests/errors while unit is live  │
 └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                           ACCEPTED RETURNS / CODE WRITES
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ map       -> (1) units, (2) axes, (4) meta                               │
 │ probe     -> (3) stack.resume_q                                           │
 │ grade     -> (2) axes, (5) probes, (6) learner when misconception found  │
 │ route     -> (1) units, (3) stack, (4) meta                              │
 │ distill   -> (6) learner, (7) titled archive, (8) handoff; MOVES (12)    │
 │              events into archive; snapshots (11) workspace                │
 │                                                                            │
 │ Every write is performed through a guarded code capability. An agent may  │
 │ invoke a granted capability during work; code may also commit an accepted  │
 │ final stamp after exit.                                                     │
 └──────────────────────────────────────────────────────────────────────────┘
```

`snapshot` is assembled afresh for a wakeup from the relevant stones plus the
current learner message/event. It is input, not a persisted stone.

---

## 9. NON-NEGOTIABLE GUARDRAILS

```
 JUDGMENT BOUNDARY
   • Code never classifies learner free text, intent, or reasoning.
   • Teacher asks/teaches/tests; Judge grades. No self-grading.

 EVIDENCE BOUNDARY
   • No SOLID without cited evidence from the learner's words/actions.
   • Working code, confidence, and jargon are not proof by themselves.
   • The second SHAKY -> MISSING conversion is policy in code, not Judge logic.

 STATE BOUNDARY
   • An agent output is validated before it can be persisted or delivered.
   • Every durable write passes through a guarded code capability; agents may
     invoke only capabilities explicitly granted to their current step.
   • Code owns stack motion and global routing.
   • No OWNED unit with an open child or non-SOLID firing axis.
   • Archive proof must be accepted before live working state is cleared.

 TEACHING BOUNDARY
   • Learner attempts first; Teacher does not reveal the answer/fix early.
   • TEACH fills only the small residue; TEST must expose faking.
   • No learner may skip an un-fakeable test merely by claiming prior knowledge.

 CONTEXT BOUNDARY
   • Each wakeup receives only its step's minimal context and scoped tools.
   • Every category and action-hook outcome has a known continuation; no dead end.
```

---

## 10. HOW THE DOCUMENTS SHOULD DIVIDE RESPONSIBILITY

This is an ownership guide, not a request to remove any design information.

```
 MASTER.md       The pillar: phases, two arrows, global invariants, ownership.
 CATALOGS.md     The executable contract per step: when, initial injection,
                 allowed retrieval/tools, emit shape, receiver effects, routing.
 agents/*.md     The agent's stable identity, reasoning method, role rules,
                 self-checks, escalation behaviour, and learner-facing style.
 ANATOMY.md      The timing model: wakeup -> runtime capability loop/action
                 hooks -> emit -> code reception; plus the cross-step map.
```

The catalog is the canonical place for operational facts that must not drift:
which agent is woken, what it initially receives, which tools it may use, what
it returns, where code records accepted results, and which route follows. Agent
cards reference those step IDs and define how the agent behaves with that
contract; they do not create a competing route or write authority.
