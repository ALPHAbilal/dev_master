# TUTOR — THE MASTER PIECE (the pillar)

Status: LIVE. This is the single source-of-truth diagram of the whole process
flow and who owns each step. We make SURGICAL edits here. Companion files:
PROCESS.md (the process alone), STONES.md (the data stores), CATALOGS.md (the
wakeup/return/routing templates), DATA.md (the data layer: tables, folders,
schemas), WALKTHROUGH.md (one real unit walked end-to-end with real values),
AGENTIC_REDESIGN.md (the agentic layer detail), ANATOMY.md (the timing inside
one turn: wakeup → runtime capability loop → emit → code reception), and
TECHNICAL_UNIVERSE.md (the implementation capability surface).

Legend:  [CODE] = deterministic, no LLM   ·   [AI] = an agent does it
         (STONE) = where the data lives (see STONES.md for the numbered stones)

---

```
 ╔═══════════════════════════════════════════════════════════════════════════════╗
 ║                          T U T O R   —   T H E   P I L L A R                    ║
 ║   [CODE] = deterministic   [AI] = an agent   (STONE) = where data lives         ║
 ╚═══════════════════════════════════════════════════════════════════════════════╝

  LEARNER'S MESSAGE
        │
        ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ ORCHESTRATOR = DETERMINISTIC DISPATCHER                               [CODE]   │
 │  • take a photo of "where are we now"  → builds the snapshot from (4 meta)+state│
 │  • THE ONE TEST: does resolving this step need the learner's WORDS read?       │
 │      NO  → state alone settles it → do it in pure code (see A below)           │
 │      YES → wake an agent. Code still decides — from DB + snapshot —            │
 │           WHICH agent · WHAT minimal context · WHICH tools  (the wakeup packet)│
 │  • code NEVER classifies what the learner said; it only assembles the packet   │
 └───────┬───────────────────────────────────────────────────────────────────────┘
         │ (A) pure-code steps (no text read): invariant fires · reset due ·
         │     next-unit-in-order · DB-counter facts (2nd SHAKY → MISS)
         │ (B) everything that reads his words → wake the right worker, wired
         │     with just the context + tools that state says it needs
         │
   ╔═════▼═══════════════ PHASE: SCAN (once per codebase) ═══════════════════════╗
   ║  MAPPER  [AI]   read the whole codebase → emit the ladder + unit axes;        ║
   ║                 guarded CODE records it in (1 units)(2 axes)                  ║
   ╚═════════════════════════════════════════════════════════════════════════════╝
         │
   ╔═════▼═══════════════ PHASE: LOOP (one unit at a time) ══════════════════════╗
   ║                                                                             ║
   ║    POINT   [CODE]  highlight file:lo-hi in the REAL editor (INTERFACE.md)    ║
   ║     │              no LLM — folded into PROBE                                  ║
   ║  ① PROBE  TEACHER [AI]  ask; he attempts FIRST        writes (3 stack:resume)║
   ║     │                    (wakeup.probe)                                       ║
   ║     ▼  ── he answers ──────────────────────────────────────────────────     ║
   ║  ② RETURN  JUDGE [AI]  reads his words → stamps a CATEGORY                   ║
   ║     │       (correct-deep? faking? SHAKY? off-topic? deeper-gap? skip-req?)  ║
   ║     │       writes → (2 axes)(5 probes)(6 learner)          (return.grade)   ║
   ║     ▼                                                                         ║
   ║  ③ CODE ROUTES on the category                              [CODE]           ║
   ║       code-only facts join HERE, after the verdict — never before:           ║
   ║       2nd-SHAKY=miss · invariant fires · reset due · next-unit-in-order      ║
   ║     │                                                                        ║
   ║     ├── STAY  → rephrase / hint / narrower  → back to PROBE  TEACHER [AI]    ║
   ║     │                                                                        ║
   ║     ├── LEAVE                                                                ║
   ║     │     • deeper gap → PUSH child, freeze this   [CODE] on (3 stack)       ║
   ║     │                     then POINT on the child  [CODE] → PROBE [AI]       ║
   ║     │     • sibling gap → note it              [CODE] on (3 stack:pending)   ║
   ║     │     • tired       → park + save              DISTILLER [AI]            ║
   ║     │                                                                        ║
   ║     └── CONTINUE the unit:                                                   ║
   ║  ① TEACH  TEACHER [AI]  fill only the gap (~20%)          (wakeup.teach)     ║
   ║     │                                                                        ║
   ║  ① TEST   TEACHER [AI]  a challenge he can't fake         (wakeup.test)      ║
   ║     │                                                                        ║
   ║     ▼  ── he answers ──►  ② RETURN: JUDGE [AI] grades THIS axis              ║
   ║     │       SOLID/SHAKY/MISSING  writes→(2 axes)(5 probes)(6)  (return.grade)║
   ║     ▼                                                                         ║
   ║  ③ CODE ROUTES on the verdict                              [CODE]            ║
   ║     ├── more axes left        → next axis   → ① POINT                        ║
   ║     └── SOLID on ALL axes     → unit OWNED  (invariant: no OWNED w/ open child)║
   ╚═════════════════════════════════════════════════════════════════════════════╝
         │  unit OWNED  (or parked)
         ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ DISTILL + RESET                                                                 │
 │  DISTILLER [AI]  title + save proof + event trace → (7 archive)                │
 │                  update the person → (6 learner)                               │
 │                  leave a start-next note → (8 handoff)                         │
 │  [CODE]          clear working memory → next unit reads its folders back       │
 └───────┬────────────────────────────────────────────────────────────────────────┘
         │ climb back to parent (replay its remembered question) OR next top unit
         │
         ▼  ...repeat up the whole ladder...
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ PHASE: GRADUATION                                                              │
 │  all top-level units OWNED → he writes the codebase from a blank page,          │
 │  and survives "why / when-not / what-breaks-it"  =  CONFIDENT                   │
 └────────────────────────────────────────────────────────────────────────────────┘

 ┌── ALWAYS ON, WATCHING EVERYTHING ──────────────────────────────────────────────┐
 │ HARNESS  [CODE]   observes what every agent did, then REFUSES the illegal:      │
 │   • can't mark a unit OWNED while a deeper gap is still open                     │
 │   • can't mark an angle SOLID without saved evidence (working code ≠ proof)      │
 │   • can't skip a test just because he says "I know it"                           │
 │   • every agent's output must match its form (10 schemas) or it's rejected       │
 └────────────────────────────────────────────────────────────────────────────────┘
```

---

## THE CORE ENGINE — THE TWO-ARROW CYCLE

Everything above runs on ONE repeating engine. It is a cycle of two arrows
between CODE (the router) and an AGENT (the brain), and every arrow reads and
writes the STONES. Learn this and the whole system collapses to one shape.

```
                    (STONES: db tables + folders + live snapshot)
                    ▲ reads                         │ writes
                    │                               ▼
   ┌────────┐  ①  wakeup.<step> ─────────────────► ┌────────┐
   │  CODE  │      code packs the context this      │ AGENT  │
   │(router)│      step needs, PULLED from stones   │(brain) │
   └────────┘  ◄──── ②  return.<step> ──────────── └────────┘
        │            SAY and/or stamp; guarded code accepts any write
        ▼
   ③  CODE ROUTES: reads the stamp's learner route signal/category → maybe pushes/pops the
      stack (dive into a branch / climb back to main) → fires the next wakeup

   ...round and round until GRADUATION.
```

Where every idea lives (nothing is left homeless):

  • code→agent arrow  = the WAKEUP template. Keyed by STEP. This ALONE decides
    which agent · which tools · which harness rules. (probe/grade/distill differ.)
  • agent→code arrow  = the RETURN template (the stamp). Its payload carries a
    verdict and a learner route signal (called `category` in the current v1
    stamp) — the vocabulary the agent speaks back.
  • Learner route signals (faking, off-topic, deeper-gap...) are NOT wakeups;
    they ride the RETURN arrow. Code reads them to ROUTE, never to build a packet.
    Verdicts and code-only policy facts (2nd SHAKY, invariants, reset) stay
    separate even where the current routing table presents them together.
  • BRANCH DOWN / CLIMB UP (descent / ascent) = pure CODE routing in step ③,
    moving the stack, then firing the next wakeup. Not an arrow to an agent.
  • STONES / FOLDERS plug into every arrow: a wakeup names its initial READS;
    a return names the accepted WRITES. During an agent's life it may make
    additional scoped reads or guarded writes only through capabilities granted
    by that wakeup. Minimal injection remains the default — never load all data.

The single template shape (covers what-we-say, the wakeup packet, the stamp,
AND the folder/data-flow — all four levels in one):

    <arrow>.<step> = { agent · WHEN · initial READS/inject ·
                       runtime capabilities(scope + when + guard) ·
                       emit-shape · accepted WRITES[stones] · next route }

Examples:

    wakeup.probe   → agent: TEACHER   tools:[read-code]
                     READS: (9 codebase slice)(6 learner can/cant)
                     inject: just those slices

    return.grade   → stamp:{axis, verdict, category, hidden_gap?}
                     WRITES:(2 axes)(5 probes append)(6 learner append)

    return.distill → stamp: titled archive manifest + learner diff + handoff
                     WRITES:(7 archive)(8 handoff)(6 learner)
                     MOVES:(12 events)→(7 archive); snapshots (11 workspace)

EXTENSIBILITY LAW: adding a new data concept = register a new stone + add it to
the READS/WRITES line of the steps that touch it. The engine (the two arrows)
NEVER changes. New data = new stone + a line on a template, never a new engine.

---

## TURN ANATOMY — WHAT HAPPENS INSIDE THE TWO ARROWS

The two-arrow engine is the only control flow. This section defines timing
inside one agent invocation; it does not add an arrow or a second state machine.

```
 CODE -> AGENT  ① AT WAKEUP
   code selects the step and injects its minimum packet:
   objective · current unit/axis · relevant evidence/source slice · output shape
   · scoped capabilities. Code does not classify learner words.

 AGENT ALIVE   DURING WORK: RUNTIME CAPABILITY LOOP
   agent -> permitted read/write/observe capability -> guarded code service
         -> authorize + validate + execute + log -> result/rejection -> agent
   The agent can adapt to the result before it emits. A live write is allowed
   only when its wakeup grants it; the guarded service enforces every write.

 AGENT -> CODE  ② AT EMIT
   agent emits only its allowed SAY, stamp, or typed escalation. The output
   contract is known from wakeup, not introduced after the work is done.

 CODE           ③ AFTER EXIT
   code validates the result, applies deterministic policies, records accepted
   effects, delivers approved SAY, and routes to the next step.
```

### Live action hooks

Learner commands, edits, test output, and UI actions are events during an
interaction—not a replacement for the return/routing engine.

```
 action event -> [CODE] EVENT RECORDER appends (12 events) -> ACTION HOOK
       ├─ objective policy/fact -> block | factual feedback | continue
       └─ meaning, intent, or reasoning required -> wake the relevant agent
                                                -> normal return -> code route
```

Code only handles the first branch when it can decide without interpreting
learner language or intent. The second branch receives a minimal event packet
(action, output/diff, current unit/axis, and relevant source), then returns by
the normal agent→code arrow. Thus a detected child gap still pushes the stack,
and a sibling still queues in `stack.pending`; action hooks create no parallel
gap system. At unit OWNED/PARK, the guarded distill transaction seals and moves
the raw unit events into the titled archive artifact. The learner's one logical
workspace document (11) remains under its stable UI name; the archive saves the
representative snapshot/diff, never forces the learner to switch filenames.

### Warm-start and parent resume

At a cold start, code reads the compact authoritative SQLite handoff record
first, selects the next unit, and builds a normal minimal wakeup packet. It does not inject every
archive, probe, or database row. During a live child detour, code restores the
parent frame and replays its exact `resume_q`; that is a stack resume, not a
full warm-start.

**Continuity-equivalence law:** PARK/session exit moves the complete live stack
into `handoff.resume_stack`. On return, code restores that stack and rebuilds
the same ordinary wakeup packet the deepest unit would have received without an
interruption: current unit/axis/state, exact resume question, pending siblings,
hop budget, relevant evidence references, and current workspace revision. The
agent is not given a degraded "you are resuming" narrative, a full raw database,
or an unrelated transcript dump. A resumed lesson must be behaviourally
indistinguishable from an uninterrupted one unless elapsed time itself matters.

The parked handoff also carries a code-owned `continuation` record:
`{next_step, awaiting, outstanding_question_ref?, context_refs[]}`. It says
where the ordinary engine continues, rather than becoming a new instruction
pattern for an agent. For example: a displayed question waits for its saved
learner answer without re-running the Teacher; a saved answer resumes at grade;
a TEACH pause waits for the learner reaction. Code writes this record only after
a complete agent return, persisted learner event, or committed guarded tool
action—never during an in-flight agent call or transaction.

---

## THE FIVE PILLARS

| Pillar | Who | Job |
|--------|-----|-----|
| Orchestrator | CODE | photo → if state settles it, act; else assemble the wakeup packet (which agent · what context · what tools). Never reads the learner's words. |
| Teacher | AI | PROBE / TEACH / TEST — faces the learner; POINT is code-side highlighting |
| Judge | AI | read hard answers into a box, grade angles, spot deeper gaps |
| Mapper / Distiller | AI | build the ladder; save proof + reset |
| Harness | CODE | watch every agent, refuse the illegal, enforce the forms |

Load-bearing idea: **agents do the judgment, code does the routing and the
refusing. The two never mix** — that is what keeps it from drifting.

---

## SURGERY LOG (record every change we make to the diagram)
- S1 (2026-08-22) Fixed the deterministic/agentic line. OLD (wrong): orchestrator
  splits answers into "easy = CODE reads it" vs "hard = AI reads it." NEW: code
  NEVER reads the learner's words. The real test is "does resolving this step
  need his words interpreted?" NO → pure code from state alone (invariant fires,
  reset due, next-unit, DB-counter facts like 2nd-shaky=miss). YES → code wakes
  an agent, and code's deterministic job is only to ASSEMBLE THE WAKEUP PACKET
  (which agent · what minimal context · which tools) from DB + live snapshot.
  Orchestrator reframed as DETERMINISTIC DISPATCHER. Touched: orchestrator box,
  both RESOLVE-THE-TURN boxes, pillar table row.
- S2 (2026-08-22) Added THE CORE ENGINE — the two-arrow cycle. The whole system
  is one repeating loop: ① code→agent wakeup (keyed by STEP; sets agent+tools+
  harness) → ② agent→code return (a stamp whose payload is the CATEGORY) → ③ code
  routes on the category, pushing/popping the stack (branch down / climb up),
  then fires the next wakeup. Homes assigned: steps key wakeups; categories ride
  the return arrow; branch/climb is code routing in ③; stones plug into every
  arrow via READS/WRITES. Single template shape: <arrow>.<step> = {agent·tools·
  harness·READS·inject·WRITES}, covering all four levels (say / packet / stamp /
  folder-data). Extensibility law: new data = new stone + a template line, never
  a new engine. Next: build the two catalogs (wakeup.* by step, return.* by
  category) in this shape.
- S3 (2026-08-22) Purged old-architecture leftover from THE PILLAR. The RESOLVE-
  THE-TURN box still showed the false FORK ("code reads it OR agent reads it") at
  the moment the learner answers — the exact placement bug caught earlier but only
  half-fixed. Replaced with the relay: RETURN (JUDGE reads words -> stamps a
  category) then CODE ROUTES, with the code-only facts (2nd-shaky=miss, invariant,
  reset, next-unit) moved INTO routing (after the verdict), never as a sibling to
  reading his words. Annotated every step with its engine phase (wakeup/return/
  route) and template name (wakeup.point/probe/teach/test/map, return.grade).
  Unified "angles"->"axes" throughout the diagram.
- S4 (2026-08-23, historical intermediate) Re-synced the diagram to the then
  10-stone set (STONES.md).
  Renumbered every stone reference: codebase 1->9, schemas 2->10, units 3->1,
  axes 4->2, stack 5->3, meta 6->4, learner 7->6, archive 9->7, handoff 10->8.
  CUT `codebase-map` (MAPPER now writes units+axes directly) and demoted
  `snapshot` (not a stone). ADDED `probes` (5) as a write target of every grade
  (the Q&A diary). Renamed to the clean nouns (learner / archive / axes). This
  was superseded by S6, which added workspace and events and aligned all current
  contracts to the 12-stone model.
- S5 (2026-08-23) Promoted the approved turn anatomy into the Master: an agent
  wakes with a minimal packet, works through a scoped runtime capability loop,
  emits a known SAY/stamp shape, and exits before code validates/records/routes.
  Added live action hooks: objective events are handled deterministically;
  semantic events wake an agent and return through the same two-arrow engine.
  Clarified that `category` is the current v1 name for a learner route signal,
  distinct from verdicts and code-only policy facts. No routing behaviour or
  existing stamp schema changed in this surgery.
- S6 (2026-08-23) Added workspace (11) and events (12) to make learner coding
  automatic and durable: one stable visible learner document, plus an append-only
  event trace for edits/commands/tests/errors/UI feedback. At unit close, a
  guarded transaction writes a reflective archive title, snapshot, and event
  stream, then moves the live events into archive. `probes` remains the separate
  semantic Q&A diary.
- S7 (2026-08-23) Closed cold mid-dive continuity: PARK/session exit moves the
  live stack into `handoff.resume_stack`; re-entry restores it and builds a
  normal minimal wakeup packet, preserving agent behaviour and response quality.
```


A step = one named action in the learning process — the smallest unit of "do one thing." Agent steps are wakeups in the catalogs; pure-code steps (such as POINT and ROUTE) run without waking an agent.

Here's the full list (these are the exact column headers in the §0 grid):

 step      what happens in it                         agent
 ─────────────────────────────────────────────────────────────
 map       scan the codebase → build the ladder       MAPPER
point     highlight the real lines                   CODE
 probe     ask a question; he attempts first          TEACHER
 teach     fill only the gap (~20%)                   TEACHER
 test      pose a challenge he can't fake             TEACHER
 grade     read his answer → verdict + category       JUDGE
 route     pick what happens next                     (CODE, no agent)
 distill   save the proof + reset                     DISTILLER

So a "step" is not a phase and not an axis:

- Phase = the big chapter of the journey (SCAN → LOOP → GRADUATION). Coarse.
- Step = one action inside a phase (probe, teach, test...). Fine.
- Axis = which dimension of understanding a step is working on (COMPREHEND, RATIONALE...). A step like probe runs once per axis.
