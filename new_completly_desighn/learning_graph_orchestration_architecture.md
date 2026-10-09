# Adaptive Codebase Learning — Orchestrator & Tutor Architecture

> **Design specification | v1.1**  
> A graph-driven learning system that adapts to what a learner reveals while working on small, real tasks in an existing codebase.  
> v1.1 (2026-10-08) adds §15–§26: the decisions from the design review, plus everything still useful from Spec v0.2 (now archived). This file is the whole new design. Anything marked **PROPOSED** is not settled yet.

---

## 0. The Idea in One Picture

```text
                         +-------------------+
                         | REAL CODEBASE TASK|
                         | understand / fix  |
                         | change / build    |
                         +---------+---------+
                                   |
                            Establish goal
                            & success evidence
                                   |
                                   v
                  +----------------------------------+
         +------->|   FLEXIBLE LEARNER WORK LOOP     |<-------+
         |        | inspect / reason / edit / test   |        |
         |        | debug / ask / experiment / learn |        |
         |        +-----------------+----------------+        |
         |                          |                         |
         |                   Learner interaction              |
         |                          v                         |
         |             +--------------------------+           |
         |             |   ORCHESTRATOR AGENT     |           |
         |             | observe -> assess        |           |
         |             | -> update learning graph |           |
         |             | -> choose trajectory     |           |
         |             +------------+-------------+           |
         |                          |                         |
         |          +---------------+----------------+        |
         |          |               |                |        |
         |       On track       Gap(s) found     Goal met     |
         |          |               |                |        |
         |       Continue        Redirect       Verify and    |
         |       current         to needed      resume/finish |
         |       teaching        subgoal             |        |
         |          |               |                |        |
         |          +---------------+----------------+        |
         |                          |                         |
         |                          v                         |
         |                 +-----------------+                |
         |                 |   TUTOR AGENT   |                |
         |                 | teach / guide / |                |
         |                 | probe / feedback|                |
         |                 +---------+-------+                |
         |                           |                        |
         +---------------------------+------------------------+
         
          Exit loop only when the task's required completion
          evidence (and appropriate learning evidence) exists.
```

**Core rule:** The **orchestrator** decides *where learning goes next* and owns the graph and state. The **tutor** decides *how to teach the currently assigned goal* within the orchestrator's boundaries. Learner actions reveal needs indirectly; they do not need to select a new curriculum path.

---

## 1. What Is a Task?

**A task is a real job on a real codebase: something to understand, fix, change, or build.**

- It can be tiny: explain a function, rename a variable, adjust a condition, fix one failing assertion.
- It can also be larger: implement an endpoint or add a small feature.
- It is **not** synonymous with building something new.
- **Investigation is not a mandatory stage.** It is one of many activities a learner can perform at any time.

### Task types share the same architecture

```text
                           [ TASK ]
                              |
             +----------------+----------------+
             |                |                |
         UNDERSTAND          MODIFY           BUILD
             |           +----+----+            |
          Trace and       FIX     CHANGE       Create
          explain         defect  behavior     capability
             |           |         |            |
             +-----------+---------+------------+
                              |
                      Same work loop
                      Same graph model
                      Same orchestrator
                              |
                      Type-specific proof
                      that goal was met
```

| Task | Example | Completion evidence |
|---|---|---|
| Understand | Explain why a function returns a value | Accurate trace/explanation |
| Fix | Repair a faulty condition | Failure no longer reproduces; checks pass |
| Change | Return `None` for empty input | New behavior verified; no unintended breakage |
| Build | Add a small API endpoint | Behavior meets acceptance criteria |

---

## 2. Universal Task Lifecycle: Fixed Boundaries, Fluid Middle

Only the task's **goal** and **completion checks** are stable boundaries. The middle is deliberately non-linear.

```text
                   +------------------------+
                   | 1. UNDERSTAND GOAL     |
                   | What does success mean?|
                   +-----------+------------+
                               |
                               v
                 +----------------------------+
           +---->| 2. OPEN WORK LOOP          |<----+
           |     |                            |     |
           |     | Any order, repeated freely:|     |
           |     |   - inspect existing code  |     |
           |     |   - reason / plan           |     |
           |     |   - edit / implement       |     |
           |     |   - run / test              |     |
           |     |   - debug                   |     |
           |     |   - ask questions           |     |
           |     |   - experiment              |     |
           |     |   - learn a concept        |     |
           |     +-------------+--------------+     |
           |                   |                    |
           |              Assessment                |
           |                   |                    |
           |          +--------+--------+           |
           |          |                 |           |
           |     Not achieved        Achieved       |
           +----------+                 |           |
                                        v           |
                           +-------------------+   |
                           | 3. VERIFY RESULT  |   |
                           | & LEARNING EVIDENCE|  |
                           +---------+---------+   |
                                     |             |
                              +------+-----+       |
                              |            |       |
                       Evidence weak    Evidence   |
                              |          adequate  |
                              +--------------------+
                                           |
                                           v
                                    [ TASK DONE ]
```

**Verification is a condition, not a prescribed single action.** Learners may test and re-check continuously inside the work loop. The final gate evaluates available evidence rather than forcing a separate UI step for every small task.

```text
FIXED                          FLEXIBLE
-----                          --------
Goal                           Activities & their order
Success criteria               Number of attempts
Completion evidence needed     Questions & detours
                               Scaffolding depth
                               Graph path / focus changes
```

---

## 3. Separation of Responsibilities

```text
                +------------------------+
                |        LEARNER         |
                | interacts with code,   |
                | asks, tests, struggles |
                +------------+-----------+
                             |
                             v
          +---------------------------------------+
          |            ORCHESTRATOR               |
          |                                       |
          | OWNS:                                 |
          |   - learning graph & node states      |
          |   - detection of emerging gaps        |
          |   - dependency & blocker handling     |
          |   - current focus / suspended goals   |
          |   - next-goal & resume decisions      |
          |   - task/learning completion gates    |
          +------------------+--------------------+
                             |
                     Tutor assignment
                             |
                             v
          +---------------------------------------+
          |                TUTOR                  |
          |                                       |
          | EXECUTES:                             |
          |   - explain / scaffold / demonstrate  |
          |   - question / probe understanding    |
          |   - hint / guide / give feedback      |
          |   - support current teaching activity |
          |                                       |
          | DOES NOT OWN: graph or trajectory     |
          +------------------+--------------------+
                             |
                       Learner responds
                             |
                             +----> ORCHESTRATOR
```

**On-track optimization:** The orchestrator can emit `CONTINUE` and leave the tutor's current activity unchanged. A new lesson or graph mutation is not necessary for every learner message.

---

## 4. The Orchestrator's Continuous Decision Loop

Every meaningful learner interaction is assessed for **state variation**, not merely routed by input type ("question", "code", "error").

```text
                      [NEW INTERACTION]
                               |
                               v
                   [READ CURRENT GRAPH]
                               |
                               v
                    [ASSESS LEARNER STATE]
                               |
               +---------------+------------------+
               |               |                  |
          ON TRACK        GAP / BLOCKER       GOAL SATISFIED
               |               |                  |
               |          Identify 1..N           |
               |          distinct issues         |
               |               |                  |
               |       [UPSERT ISSUE NODES]       |
               |          & dependencies          |
               |               |                  |
               |        Prioritize required       |
               |        learning detour(s)        |
               |               |                  |
               |      Suspend previous focus      |
               |      and activate a subgoal      |
               |               |                  |
               |               |           Resolve current
               |               |           node and resume
               |               |           closest ready goal
               |               |                  |
               +---------------+------------------+
                               |
                               v
                     [SELECT TUTOR DIRECTIVE]
                               |
                               v
                         [TUTOR ACTS]
                               |
                               v
                      [LEARNER RESPONDS]
                               |
                               +----> Repeat
```

### Assessment / decision variations

| Orchestrator assessment | Graph / focus effect | Tutor directive |
|---|---|---|
| `ON_TRACK` | Preserve focus; record evidence as needed | `CONTINUE` |
| `GAP_DISCOVERED` | Create/reactivate gap node, link to active goal | Target that gap |
| `MULTIPLE_GAPS` | Keep all issues; prioritize blocking issue(s) | Address selected gap |
| `DEPENDENCY_MISSING` | Add prerequisite edge, suspend dependent goal | Teach prerequisite |
| `STAGNATING` | Record repeated ineffective attempts | Change scaffolding strategy |
| `UNDERSTANDING_UNCERTAIN` | Mark evidence incomplete, not automatically failed | Probe briefly |
| `GAP_RESOLVED` | Resolve node; unblock dependent nodes | Resume ready parent/goal |
| `MASTERY_DEMONSTRATED` | Store evidence; mark concept sufficiently known | Skip unnecessary detour |
| `TASK_COMPLETED` | Verify required evidence and close task | Wrap up / advance |

**Keep these concepts separate:** `GAP_DISCOVERED` is an **assessment/event**; `BLOCKED` is a **node status**. One is what the orchestrator has detected, the other is what the graph currently records.

---

## 5. Scenario Categories: What May Go Wrong?

The categories below are **diagnosis labels**, not mandatory lifecycle steps. A learner can have **zero, one, or several** at once. They apply anywhere in the work loop.

```text
                       [DETECTED DIFFICULTY]
                                 |
                         Diagnose 0..N
                                 |
         +-----------------------+------------------------+
         |                       |                        |
      COGNITIVE                PRACTICAL                REGULATORY
         |                       |                        |
    1. Task meaning        5. Implementation          10. Self-regulation
    2. Codebase model      6. Tools / environment
    3. Knowledge gaps      7. Debugging
    4. Problem solving     8. Verification
                                 |
                             LEARNING
                                 |
                         9. Mastery / transfer
                                 |
                     Create/link issue node(s)
                                 |
                  Each issue can spawn subissues
```

| # | Category | Examples | Candidate intervention |
|---:|---|---|---|
| 1 | Task understanding | Goal misread; expected outcome unclear | Clarify objective; check paraphrase |
| 2 | Codebase understanding | Cannot locate behavior; confused by call flow | Guided trace of relevant code |
| 3 | Knowledge gaps | Concept missing; misconception; forgotten syntax | Teach concept; recursively resolve prerequisite |
| 4 | Problem solving | No approach; weak decomposition | Narrow problem; compare approaches |
| 5 | Implementation | Knows idea, cannot express it in code | Targeted hint; small coding step |
| 6 | Environment & tools | Dependency failure; tooling unfamiliarity | Diagnose setup; restore workflow |
| 7 | Debugging | Cannot isolate failure or root cause | Reproduce; hypothesize; inspect evidence |
| 8 | Verification | Incorrect tests; missing edge cases | Design/interpret checks |
| 9 | Mastery & transfer | Working code, weak explanation; overreliance | Probe or small variation as warranted |
| 10 | Self-regulation | Frustration; unproductive repetition | Adjust difficulty/scaffolding; support recovery |

**The same recursive mechanism applies to all categories**, not just prerequisite knowledge. A testing difficulty may expose a missing concept. A debugging difficulty may expose a tool problem. An implementation issue may expose uncertainty about the codebase.

---

## 6. Unified Graph: Goals, Issues, Concepts, and Evidence

The learning graph is an **active navigation model**, not merely a history log.

```text
                     +--------------------------+
                     |       LEARNING GRAPH     |
                     +-------------+------------+
                                   |
          +------------------------+-------------------------+
          |                        |                         |
        NODES                     EDGES                 FOCUS STATE
          |                        |                         |
   - Task / goal            - requires                  current_node
   - Issue / blocker        - blocks                    active_path
   - Concept / skill        - parent_of                 suspended_goals
   - Subgoal                - related_to                return_context
   - Evidence               - evidenced_by             next_candidates
          |                        |                         |
          +------------------------+-------------------------+
                                   |
                            ORCHESTRATOR
                        reads -> updates -> routes
```

### Graph-node data (conceptual)

```text
Node
  id
  kind                 task | issue | concept | subgoal
  objective            what must be resolved/learned
  status               OPEN | READY | ACTIVE | BLOCKED |
                       SUSPENDED | RESOLVED
  category             issue category, if relevant
  dependencies[]       other nodes that must be resolved
  linked_parent_goals[]
  evidence[]           observations supporting status
  return_context       where/how to resume after detour
  origin               crafted | discovered                  (§15)
  bank_link            a bank concept id, or none; optional,
                       may be added or removed at any time   (§15)
  closes_when          the evidence that resolves it, set
                       when the node becomes ACTIVE
```

### Learner-wide navigation data

```text
LearningSession
  root_task_id
  current_focus_id
  suspended_focus_stack[]   # useful for nested detours
  open_issue_ids[]          # may be multiple, not a stack
  concept_knowledge{}       # known / uncertain / missing
  interaction_log[]         # actions, attempts, support
  next_candidates[]         # computed from ready nodes
```

**Important distinction:** The graph supports multiple simultaneously open branches. A **focus stack** helps resume nested detours, but the whole graph is **not** a stack. A single issue or concept can be relevant to several goals, and one activity can reveal multiple blockers.

---

## 7. Recursive Detours — Prerequisites and Beyond

### 7A. Missing prerequisites, recursively

```text
              [T0: CHANGE ONE FUNCTION]
                         ACTIVE
                           |
          Learner: "I don't understand this call"
                           |
                  [I1: FUNCTION CALLS]
                         ACTIVE
                           |
             Learner lacks PARAMETERS
                           |
                  [I2: PARAMETERS]
                         ACTIVE
                           |
             Learner lacks ARGUMENTS
                           |
                   [I3: ARGUMENTS]
                         ACTIVE
                           |
                    Evidence sufficient
                           |
                      I3 RESOLVED
                           |
                       Resume I2
                           |
                      I2 RESOLVED
                           |
                       Resume I1
                           |
                      I1 RESOLVED
                           |
                       Resume T0
                           |
                 [ORIGINAL WORK CONTINUES]
```

**Resume rule:** Once the blocking dependency is resolved, reactivate the closest suspended goal whose blockers are cleared. Preserve the relevant context so the tutor can reconnect the concept to the original task.

### 7B. Other difficulties recurse the same way

```text
                 [T0: FIX FAILING TEST]
                           |
                    [I1: DEBUGGING]
                           |
               "I cannot run the tests"
                           |
                   [I2: TOOL SETUP]
                           |
              "I don't understand venv"
                           |
                 [I3: VENV CONCEPT]
                           |
                       RESOLVE I3
                           |
                       RESOLVE I2
                           |
                       RESUME I1
                           |
                       RESUME T0
```

### 7C. Multiple issues are simultaneous, not necessarily sequential

```text
                         [T0: TASK]
                              |
           +------------------+------------------+
           |                  |                  |
      [I1: CODEBASE]     [I2: SYNTAX]     [I3: TESTING]
          ACTIVE             OPEN               OPEN
           |
      [I4: CONCEPT]
         ACTIVE
           |
      [I5: PRE-REQ]
        RESOLVED
           |
    Resume I4 -> I1
           |
    Return to T0 or another READY issue
           |
     I2 and I3 remain recorded throughout
```

A gap discovered during work is not discarded merely because the orchestrator chooses a different immediate focus.

---

## 8. State Transitions: Explicit and Recoverable

A practical node-state machine:

```text
                   [OPEN / DISCOVERED]
                           |
                   prerequisites clear?
                       /          \
                     yes           no
                      |             |
                      v             v
                    READY         BLOCKED
                      |             |
                 select focus       | dependency met
                      |             |
                      v             v
                    ACTIVE <------- READY
                      |
           +----------+-------------------+
           |          |                   |
     detour needed  evidence adequate   pause/switch
           |          |                   |
           v          v                   v
       SUSPENDED    RESOLVED           SUSPENDED
           |                              |
       blockers clear / goal selected again
           |                              |
           +-------------> READY <-------+
```

- `OPEN`: identified but not yet evaluated/scheduled for work.
- `READY`: actionable now; dependencies are sufficiently met.
- `ACTIVE`: current focus receiving tutor support.
- `BLOCKED`: cannot progress until specified dependency resolves.
- `SUSPENDED`: paused because another goal has priority; it may or may not be blocked.
- `RESOLVED`: enough evidence exists that this node's objective is met.

**Do not conflate `SUSPENDED` and `BLOCKED`:** switching attention is different from having an unmet dependency. A resolved issue can remain in history and support future tasks.

### Multiple simultaneous states exist at different scopes

```text
SYSTEM SCOPE           TASK SCOPE           NODE SCOPE
------------           ----------           ----------
Orchestrator event     root ACTIVE          issue BLOCKED
ON_TRACK / GAP /       root COMPLETE        concept RESOLVED
RESUME / COMPLETE      etc.                 etc.
       |                    |                    |
       +--------------------+--------------------+
                            |
                  Combined decision context
```

---

## 9. How the Orchestrator Picks What Comes Next

```text
                 [CURRENT GRAPH + EVIDENCE]
                              |
                     [ASSESS CHANGES]
                              |
                  +-----------+-----------+
                  |                       |
                No gap                Gap(s) detected
                  |                       |
          Continue current             Upsert and link
          tutor objective               issue node(s)
                  |                       |
                  |                 Check dependencies
                  |                       |
                  |                   +---+---+
                  |                   |       |
                  |                 Ready   Blocked
                  |                   |       |
                  |                   |    Resolve
                  |                   |    prerequisite
                  |                   |       |
                  +-------------------+-------+
                              |
                   [CHOOSE NEXT FOCUS]
                              |
                +-------------+--------------+
                |             |              |
            CONTINUE        REDIRECT        RESUME
                |             |              |
                +-------------+--------------+
                              |
                      [TUTOR DIRECTIVE]
                              |
                         [TUTOR ACTS]
                              |
                   [NEW LEARNER EVIDENCE]
                              |
                              +----> repeat
```

Suggested decision priority (policy, not a rigid curriculum):

1. Preserve current focus when progress is smooth.
2. Address blockers that prevent meaningful progress on current focus.
3. Reuse already-resolved concepts/issues instead of reteaching them.
4. Preserve other detected gaps as open nodes; do not lose them.
5. When a detour resolves, resume the closest useful suspended goal.
6. Finish the root task only with adequate objective and learning evidence.

A learner's question or mistake is **evidence**, not always proof of a missing concept. The orchestrator may request a quick diagnostic probe before restructuring the graph.

---

## 10. State Updates and Tutor Directives — Conceptual Contract

The diagram above can be implemented with a minimal handoff contract. This is an **illustrative design**, not a mandated API schema.

```text
Learner interaction
       |
       v
+------------------------------+
| ORCHESTRATOR ASSESSMENT      |
| assessment: ON_TRACK / ...   |
| confidence / supporting data |
| graph_updates[]              |
| next_focus_id                |
| decision: CONTINUE /         |
|           REDIRECT / RESUME /|
|           VERIFY / COMPLETE  |
+---------------+--------------+
                |
                v
+------------------------------+
| TUTOR DIRECTIVE              |
| active_goal_id               |
| teaching_intent              |
| context / return connection  |
| allowed_assistance_depth     |
| desired learner evidence     |
| readable files + tools (§18) |
+---------------+--------------+
                |
                v
        Tutor teaching turn
                |
                +----> Learner -> Orchestrator
```

### Three representative transitions

```text
CASE A: SMOOTH
  learner progress
      -> orchestrator: ON_TRACK
      -> graph: preserve focus, append evidence
      -> tutor: CONTINUE

CASE B: NEW NESTED GAP
  learner reveals misunderstanding
      -> orchestrator: GAP_DISCOVERED
      -> graph: create/link issue, preserve return context,
                suspend old focus, activate needed subgoal
      -> tutor: REDIRECT to subgoal

CASE C: GAP RESOLVED
  learner demonstrates target understanding
      -> orchestrator: GAP_RESOLVED
      -> graph: resolve issue, unblock dependents,
                restore closest ready suspended focus
      -> tutor: RESUME with bridge to interrupted activity
```

---

## 11. Worked Example: A Tiny Change, Several Detours

**Task:** Update an existing Python function so empty input returns `None`.

```text
                         [T0: EMPTY INPUT CHANGE]
                                  ACTIVE
                                    |
                   Learner opens function / reads code
                                    |
                  ORCHESTRATOR: still on track -> CONTINUE
                                    |
                Learner: "Why is this function called here?"
                                    |
                     [I1: CODEBASE UNDERSTANDING]
                                  ACTIVE
                                    |
                 Learner: "I don't get the parameter"
                                    |
                      [I2: PARAMETERS CONCEPT]
                                  ACTIVE
                                    |
                 Tutor explains; learner shows evidence
                                    |
                              I2 RESOLVED
                                    |
                              Resume I1
                                    |
                              I1 RESOLVED
                                    |
                              Resume T0
                                    |
                        Learner edits condition
                                    |
                         Learner runs a test
                                    |
                     Learner misunderstands failure
                                    |
                         [I3: DEBUGGING ISSUE]
                                  ACTIVE
                                    |
                     Tutor guides error interpretation
                                    |
                              I3 RESOLVED
                                    |
                              Resume T0
                                    |
                          Correct test passes
                                    |
                     ORCHESTRATOR: verify evidence
                                    |
               Task behavior correct? ----- no --> WORK LOOP
                        |
                       yes
                        |
                Learning evidence adequate?
                       / \
                     no   yes
                     |     |
                  Probe   RESOLVE T0
                     |     |
                     +-----+----> [NEXT TASK]
```

### What remains true in this example?

- I1, I2, and I3 are **discoveries within one small task**, not new mandatory phases.
- The orchestrator owns the transitions; the tutor only handles assigned teaching.
- Different learner behavior could create *no issues at all*.
- If a second issue appeared while I2 was active, it could be recorded and linked without losing the path back to T0.

---

## 12. Completion: Codebase Success Is Not the Same as Learning Success

```text
                        [TASK WORK OUTPUT]
                                |
                     +----------+----------+
                     |                     |
                 TASK SUCCESS         LEARNING SUCCESS
                     |                     |
            Requirement achieved?    Evidence of actual
            Code/behavior correct?   understanding/ability?
                     |                     |
                     +----------+----------+
                                |
                        Appropriate gate
                                |
                   +------------+------------+
                   |                         |
               Sufficient                Uncertain
                   |                         |
               COMPLETE               Short tutor probe
                                             |
                                      return to work loop
```

For a trivial task, evidence can be implicit in independent action. For an important new concept, a short explanation or small transfer challenge may be appropriate. **Do not demand a formal quiz after every tiny tweak.**

---

## 13. Essential Architectural Invariants

1. **Orchestrator owns state and trajectory.** Tutor executes the teaching move; it never silently rewrites the graph.
2. **Investigation is an optional activity**, not a fixed stage.
3. **One task can expose 0..N issues.** Issues from different categories can coexist.
4. **Every category can recursively expose subissues.** Prerequisites are only one special case.
5. **Detours preserve a return path.** Resolve a nested issue, then resume the most relevant suspended goal.
6. **Graph != stack.** The graph stores all relationships; the focus stack only assists with nested return navigation.
7. **Assessments != node statuses.** Events such as `GAP_DISCOVERED` trigger mutations; states such as `BLOCKED` record enduring conditions.
8. **On-track interactions need not change the trajectory.** `CONTINUE` is a valid and common orchestrator decision.
9. **Known concepts are reusable.** Evidence already in the graph should prevent unnecessary reteaching.
10. **Achievement and learning are distinct.** Completion uses both, with depth proportional to the task.
11. **Detours are the orchestrator's own nodes.** A crafted bank concept is an optional link, never the place a detour has to go (§15).
12. **Every task opens a fresh tutor and a fresh orchestrator, and the learner never sees the break** (§18).
13. **Context reaches agents as files they can read, chosen by the orchestrator.** Collections are never pasted into a prompt (§18).
14. **The crafters run once per codebase.** Discoveries go into the bank with their own label; nothing re-runs the crafters (§17).
15. **No per-language traps, and the learner is never asked what they already know.** Misconceptions come from what the learner says and does (§16).
16. **Phase 1 runs no code on the server.** The learner runs code and checks in their own editor and pastes the results (§19).
17. **Every readable file comes with a tool, and every tool comes with a guide:** what it does, when to use it, how to use it well, and why it is available this turn (§18).
18. **Tools are custom abstractions by default.** An agent calls them with fixed parameters and gets a shaped result. Primitive SDK tools (`Read`, `Grep`, `Bash` ...) are given only where the job is open exploration and nothing gated is reachable (§18).
19. **The learner can stop at any point.** The task parks with its focus stack, and comes back exactly there (§24).

---

## 14. Compact Reference: The Whole System

```text
  REAL CODEBASE
       |
    [TASK T0] --- goal + success criteria
       |
       v
  +--------------------------------------------------------------+
  |                   FLUID TASK WORK LOOP                       |
  |                                                              |
  |     inspect  reason  edit  test  debug  ask  experiment       |
  |         \       |      |    |     |     /      /            |
  |                 learner interaction                          |
  |                         |                                    |
  |                         v                                    |
  |             +------------------------+                       |
  |             |  ORCHESTRATOR AGENT    |                       |
  |             |                        |                       |
  |             | assess state variation |                       |
  |             | diagnose 0..N gaps     |                       |
  |             | update graph + focus   |                       |
  |             | choose next trajectory |                       |
  |             +------------+-----------+                       |
  |                          |                                   |
  |      +-------------------+--------------------+              |
  |      |                   |                    |              |
  |   ON TRACK          GAP(S) FOUND        NODE RESOLVED         |
  |      |                   |                    |              |
  |   CONTINUE       graph issue(s)         unblock / RESUME     |
  |      |            & dependencies              |              |
  |      |                   |                    |              |
  |      |         recursive nested detour        |              |
  |      |         with saved return path         |              |
  |      +-------------------+--------------------+              |
  |                          |                                   |
  |                      TUTOR AGENT                             |
  |                 explain / guide / probe                      |
  |                          |                                   |
  |                    learner acts ----------------------+       |
  |                          |                           |       |
  |                  new evidence ------------------------+       |
  +--------------------------+-----------------------------------+
                             |
                       Root task met?
                        /         \
                      no           yes
                      |             |
                    repeat      Verify evidence
                                    |
                               [TASK COMPLETE]
                                    |
                                [NEXT TASK]
```

**One-sentence design principle:** *A fixed real-world task sits inside a flexible, recursive, graph-state learning loop; the orchestrator adapts the trajectory from learner evidence, and the tutor delivers the instruction.*

---

## 15. Where Nodes Come From: Crafted vs Discovered

The graph holds two kinds of nodes.

```text
   CRAFTED  (made before any learner)        DISCOVERED  (made by the orchestrator)
   ----------------------------------        --------------------------------------
   the task (T3)                             every issue and detour (I1, I2, I3)
   the concepts the task needs (C15 ...)     created the moment the learner reveals it
   from tasks/ and concepts/                 any of the 10 categories in §5
```

**A detour is always a discovered node.** It is created from what the learner said or did. A bank concept is never the place a detour has to go.

**A bank concept is an optional link** (`bank_link`). After creating a node, the orchestrator may ask: is this stuck point a case of something the crafter already prepared?

- **Yes:** link it. The tutor can read the concept file (explanation, examples, misconceptions), and the node's evidence counts for that concept.
- **No:** no link. The node works exactly the same inside the loop.

A link can be added at any depth and at any time, including late, after several misses show what the gap really is. A wrong link can be removed. Both are ordinary graph changes.

In T3, I1 links to C15. I2 (codebase) and I3 (testing) link to nothing in the crafted bank.

**Side questions use the pieces that already exist.** A side question is an ordinary issue node. The orchestrator either answers it briefly and saves it (I3 at step 9), or follows the learner into it as an ordinary detour. There is no separate kind of node.

**PROPOSED: a concept's status is computed, never set.** Evidence lives on the orchestrator's nodes. A concept's status (no evidence, uncertain, missing, known) is computed from the nodes linked to it. Adding a late link, removing a wrong one or reopening a node then just recomputes it. If a concept that was "known" gets contrary evidence, it drops back to uncertain.

---

## 16. The Concept Bank

Crafter 1 builds one file per concept, per codebase, before any learner arrives. The bank may be huge. It only covers ideas this codebase actually uses; it is not a general course.

```text
concepts/C15_loop_scope.md
---
id:       C15
name:     loop variables outlive the loop (function scope)
kind:     language    # syntax | language | stdlib | api | design | failure | architecture
claim:    a for loop's variable keeps its last value after the loop;
          if the loop never runs, it is never set                  (PROPOSED)
proof:    what does last([]) do, and why?                          (PROPOSED)
anchors:  symbol + exact line text + hash, for every place the idea is used
prereqs:  [C04]
---
## What it is
## Examples
## Common misconceptions
## Other ways to say it          (filled by discoveries, §17)
```

**How Crafter 1 works:**

1. It starts at the entry points and follows the real call path.
2. For every line, it asks: "What must a person know to understand this line?"
3. Each answer becomes a concept with an anchor.
4. The same idea in several places becomes one concept with several anchors.

Code then checks that every anchor exists, that prerequisites don't form a cycle, and that no id is used twice.

**No traps, no background.** Concept files carry no per-language traps, and the learner is never asked what languages or concepts they already know. Misconceptions are found from what the learner says and does, and written on the orchestrator's own nodes. "Common misconceptions" in a concept file are fine, because they don't depend on the learner's background.

**One bank per learner per codebase.** The bank sits in the learner's workspace (§23), so discoveries change only that learner's bank. If banks are ever shared between learners of the same repo, discovered entries need a review step first.

**PROPOSED: how big one concept is.** A concept is the smallest idea in this code that a learner can get wrong on its own. Crafter 1 applies four tests:

| test | rule |
|---|---|
| Claim | One sentence that is true or false about how code behaves. A topic ("loops") is not a concept. |
| Proof | One short question whose answer proves the learner has it. |
| Split | If a learner could get part of the answer right and the rest wrong, it is two concepts. |
| Merge | If a learner can't get one right while getting the other wrong, they are one concept. |

Every concept also needs at least one common misconception and at least one anchor. The proof question also gives a ready `closes_when` for any node linked to that concept.

---

## 17. Discoveries: the Bank Grows from the Journey

Whatever the learner's journey reveals goes into the bank, labeled as discovered. That way it is always clear what the crafter made and what was found later.

| discovery | where it goes | T3 example |
|---|---|---|
| a new misconception | the concept's "Common misconceptions" | C15: "after an empty loop it is None" (step 4) |
| a new way to explain it | the concept's "Other ways to say it" | C15: "it never gets assigned, exactly like x in last([])" (step 7) |
| a new concept | a new concept file with a D-id | D1: a test can swap the real OpenAI client for a fake one (I3, step 9) |

```text
## Common misconceptions
- the loop variable disappears when the loop ends    [crafted]
- after an empty loop it is None                     [discovered · T3 · step 4 · I1]
```

Rules:

- Every discovered entry cites the evidence that revealed it. No evidence, no entry.
- Crafted text is never overwritten. Discovered entries sit next to it.
- Entries are written when the task closes.
- A new concept gets a D-id, must pass the same tests as a crafted one, and needs an anchor. The node that revealed it links to it (I3 links to D1). The learner's own status on it starts at "no evidence" unless that node resolved.

**The crafters never run again because of a discovery.** A discovered concept gets no task of its own. The work loop is already flexible: whatever the learner swims into becomes a node, the orchestrator supports it, and once it resolves the learner returns to the main stream. If the learner wants to go deeper, the orchestrator configures the tutor for that direction on the next turn. §20 uses this case to test the orchestrator.

This means the ladder never schedules practice on a discovered concept. The learner learns it when they meet it, and later detours can still link to it and give it credit.

---

## 18. Context and Continuity

```text
 ══ TASK T3 ══════════════════════════════╗   ══ TASK T4 ═════════════════════════
  tutor: fresh at open, one conversation  ║    tutor: FRESH again
  orchestrator: fresh at open             ║    orchestrator: FRESH again
                                          ║
  learner's screen: ─────────── one continuous conversation ──────────────────►
                                          ║
  carried between them as FILES only: journey/T3.md, INDEX.md, concept knowledge,
  carried open issues, the T3 transcript
```

- **Every task opens a fresh tutor and a fresh orchestrator.** Nothing from the previous task's model context carries over.
- **The learner never sees the break.** On screen the conversation is one thread. The new tutor's first turn bridges from the previous task using its journey entry ("You fixed the guest error in T3. Next ...").
- **Continuity lives in files, not in prompts.** Journey entries, the learner record, the graph, concept files and past transcripts are files an agent can read. Small values (focus, return note, `closes_when`) go into the prompt. Anything large stays a file.
- **The orchestrator decides which files each agent can read**, turn by turn, as part of the tutor's kit: templates, tools, state values and files. If the learner refers back ("is this like the label bug?"), the orchestrator makes `journey/T3.md` readable for that turn.
- **Hard gates stay in code** (§24): the answer key is never readable before the learner has tried, and the journey is written only at close.
- Within a task, the orchestrator's memory is the graph files it reads and updates each turn.

### Pattern: every file comes with a tool, every tool comes with a guide

A readable file is no use if the agent doesn't know when or how to read it. So the kit never hands over a file on its own. Each readable file comes with a tool, and each tool's description is a short guide:

| part of the guide | written by | changes |
|---|---|---|
| what it does | the tool's author, once | never |
| when to use it, and when not to | the tool's author, once | never |
| how to use it well (read one section, not the whole file) | the tool's author, once | never |
| why it is available this turn | the orchestrator | every turn, as one line in the kit |

The first three parts live in the tool's definition and never change, which keeps the prompt cache intact (§26, item 9). Only the fourth changes, and it travels in the turn's kit. The same pattern applies to the orchestrator's own tools.

Illustrative catalogue:

```text
read_concept(id, section)
  What:  one section of a concept file: What it is | Examples |
         Common misconceptions | Other ways to say it
  When:  before explaining a concept, or to work out what a wrong answer means
  Not:   to browse the bank; read only concepts listed as readable this turn
  How:   read the one section you need; Examples first when the kit says experiment_first

read_journey(task)
  What:  the journey entry of a closed task: what was fixed, what clicked, what was missed
  When:  the learner refers back to that task, or a bridge between tasks needs it
  Not:   at the start of every task; only when it is listed as readable

read_file(path, around)
  What:  lines of the learner's code
  When:  the learner is looking at code, or a trace needs its next step
  How:   read around an anchor or a line number, not the whole file

search(query)
  What:  where something is defined or used in the repo
  When:  the learner can't find something, or before pointing at a line
```

The kit's "why this turn" line, at T3 step 3:

```text
readable now:  concepts/C15  (I1 links to C15: use its Examples for the scratch-pad
                              example and its misconceptions to read the prediction)
```

### Two kinds of tools: custom and primitive

| | custom tools (ours) | primitive tools (Claude Agent SDK built-ins) |
|---|---|---|
| examples | `read_concept(id, section)`, `update_graph(change)`, `write_journey(entry)` | `Read`, `Glob`, `Grep`, `Bash`, `Write`, `Edit`, `WebSearch`, `WebFetch` |
| what the agent can do | only call with fixed parameters (ids, section names) and get a shaped result back | anything the primitive allows, on any path it can reach |
| where gates live | in the tool's code: it refuses, and the refusal names what is missing | only in outside rules: allowed and blocked tools, path rules, working directory |
| guide (§18 pattern) | written by us | the SDK's own; we add only the "why this turn" line |

**Custom tools are abstractions.** The agent asks for a meaning ("section Examples of C15"), not a path, so it can't reach what it shouldn't. For example, nothing it can pass makes `read_concept` return `reference.patch`. Every call is logged.

**Writes go through custom tools.** A custom write tool is also where validation lives. The orchestrator owns the graph but changes it only through `update_graph`, which refuses a change the §8 state machine does not allow. This is one way to settle §26, item 1.

**PROPOSED: which agent gets which tools:**

| agent | custom | primitive |
|---|---|---|
| Crafters | `write_concept`, `write_task`, `write_ladder` (validate before writing) | `Read`, `Glob`, `Grep` on the repo copy. No `Bash` in phase 1 (§19). |
| Orchestrator | `read_graph`, `update_graph`, `read_concept`, `read_journey`, `set_kit` | none |
| Tutor | `read_concept`, `read_file(path, around)`, `search`, `read_journey`, `write_journey` (close only) | none |

The rule: primitives only where the agent's job is open exploration and nothing gated can be reached. Everywhere else, custom tools.

---

## 19. Phase 1: No Code Runs on the Server

- The learner runs the code and the scratch examples in their own VS Code.
- **No done-check tests in phase 1.** A task is done when its purpose is met (the answers are correct, or the pasted code is correct), as judged by the orchestrator (`BACKEND_SPEC.md`, D8).
- The orchestrator sees only what the learner pastes from a run: the full test output, plus `git diff` for edits. Pasted output counts as evidence, but it is the learner's own report and weaker than a run the system did itself.
- Removed in phase 1: the tutor's `run_tests` and `run_snippet`, and any examiner run. The scratch pad stays as a shared place for tiny examples, and the learner runs them.
- **PROPOSED:** the crafter's validation that each done-check fails before the fix and passes after it runs once per codebase, on the author's machine.

---

## 20. Acceptance Case: Following the Learner Somewhere New

This case tests whether the orchestrator really works as this spec says.

```text
 In T4 the learner says: "how does the T3 test fake OpenAI? I want to understand that"
   -> ORCHESTRATOR reactivates the carried issue I3 (OPEN -> ACTIVE), bank link D1
   -> T4's current goal is SUSPENDED with a return note
   -> tutor kit: guided_trace · readable files: check/test_t3.py, concepts/D1
   -> the learner traces the fake client and explains it
   -> GAP_RESOLVED: I3 RESOLVED, D1 gets the learner's evidence
   -> RESUME: back to T4 with a bridge to where it paused
   No crafter runs. No new task is created.
```

**Pass when:** the learner went where they wanted, the tutor had the right kit for it, and the learner came back to the main stream with no crafter run and no visible break.

---

## 21. What the Learner Sees: the Story Map

The current product (tutor_v2 + its frontend) already shows the learner where they are: on the main stream or inside a detour, and what happened before. This mechanism carries over. Only its inputs change, from engine events to orchestrator changes.

**How it works today.**

- Every engine decision writes a typed fact (`journey_events`) in the same transaction as the decision itself: `journey_started`, `teaching_presented`, `answer_evaluated`, `detour_started`, `gap_opened`, `parent_resumed` (with the exact paused question), `unit_distilled`, `journey_parked`, `journey_resumed`, `journey_completed`, `aside`.
- Each committed change bumps a revision number. The frontend hears about it (SSE `revision`) and refetches one snapshot.
- The map pane (`frontend/components/Map.tsx`, first drawn in `frontend/tutor.html`) turns each fact into **one plain-English line**. Indentation shows detour depth, so the learner sees at a glance whether they are on the main stream or how deep in a detour. A side question is a clickable line that opens its thread in the conversation, and "You are here" marks the current question.

**The contract to keep:**

1. **One line per recorded change, 1:1.** The UI invents nothing, and nothing that happened is missing.
2. **The record is written in the same transaction as the graph change**, so the map can never disagree with the state.
3. **Depth is recorded on each fact** from the focus stack at that moment. The old code computed it from the unit tree, but the new graph is not a tree: a node can be reached from more than one goal, and can be re-entered.
4. **Each line links to the turn and the evidence that caused it.** Clicking a line opens the conversation at that turn.
5. **Plain words only.** The learner never sees ACTIVE, SUSPENDED or GAP_DISCOVERED.
6. **The return note is written so it can be shown to the learner.** It appears as "picking up: …" when the learner comes back from a detour.
7. **Two views, one source.** This learner story and the designer's orchestrator map (`t3-orchestrator-map.html`) both read the same recorded changes, so they can't disagree. Only the learner story appears on the learner's page.

**Orchestrator change → story line:**

| orchestrator change | story line | replaces (tutor_v2) |
|---|---|---|
| task opens | `• Started <task>` | `journey_started` |
| evidence added while on track | `✓ Did <evidence>` | (new: tutor_v2 showed only graded answers) |
| node created + REDIRECT at depth 1 | `⚠ Found a gap <why>` then `↳ Went to learn first — <node>` | `gap` + `detour_started` |
| node created + REDIRECT deeper | `↳ Needed first — <node>` | `detour_started` (depth > 0) |
| evidence showing a wrong belief | `~ Almost <what they thought>` | `answer_evaluated` SHAKY |
| wrong belief later disproved | `✓ Cleared up — ~~<belief>~~` | semantic node `disproved` |
| node RESOLVED | `★ Cleared — <node>` | `unit_distilled` |
| RESUME | `↩ Came back to <node>` + `picking up: <return note>` | `parent_resumed` + resume question |
| node saved, not blocking | `○ Saved for later <node>` | `gap_opened` / sibling note |
| side question | `@ side question <title>` (opens its thread) | `aside` |
| concept proven | `✓ Proved <evidence>` | `answer_evaluated` SOLID |
| task COMPLETE | `★ Done — <goal> · you now know <concepts>` | `journey_completed` |
| current focus | `◉ You are here — <the tutor's current question>` | driver state |

**T3 as the learner would see it at the close:**

```text
• Started       Guests always get "Une erreur s'est produite"
✓ Did           reproduced the bug as a guest
✓ Did           found the broad except at line 821
⚠ Found a gap   label doesn't exist for a guest
↳ Went to learn first — A loop variable only exists if the loop ran
│  ~ Almost      you expected None after an empty loop
│  ✓ Did         explained x after the loop
│  ↳ Needed first — Why the loop on line 684 runs 0 times for a guest
│  │  ✓ Did         read lines 469–470
│  │  ★ Cleared — Why the loop runs 0 times for a guest
│  ↩ Came back to  A loop variable only exists if the loop ran
│        picking up: you get last([]); now connect it to label
│  ✓ Proved      explained why label is unbound for a guest
│  ✓ Cleared up — after an empty loop it is None   (shown struck through)
│  ★ Cleared — A loop variable only exists if the loop ran
↩ Came back to  Guests always get the generic error
      picking up: you have the traceback; line 722 reads label
✓ Did           found question_label (line 610)
✓ Did           check passed, 2 of 2 (you pasted it)
○ Saved for later   how the test fakes OpenAI
✓ Proved        explained what the if on line 722 decides
★ Done — guests get a real answer again · you now know C15, C17, C13
```

**Sidebar.** Tasks from the ladder, each with its discovered nodes nested under it. Clicking a node shows its own story, which opens with why it exists: `↪ You came here because label didn't exist for a guest`.

---

## 22. The Crafter Pipeline

Three crafters run once per codebase, before any learner, in a strict order. Each one starts only after the previous one's output has passed validation, and it receives that output as files plus tools, never pasted into its prompt. Discoveries never re-run them (§17).

```text
 repo ─► [ scrub secrets · outline · find entry points ]          (code)
            │
            ▼
 CRAFTER 1 · concepts ──► concepts/  ──► VALIDATE 1 ──fail──► back to Crafter 1
                                            │ pass
 CRAFTER 2 · tasks ─────► tasks/     ──► VALIDATE 2 ──fail──► back to Crafter 2
                                            │ pass
 CRAFTER 3 · ladder ────► ladder.md  ──► VALIDATE 3 ──fail──► back to Crafter 3
                                            │ pass
                                    the first task can open
```

**Crafter 1, concepts:** see §16.

**Crafter 2, tasks.** It reads the repo and `concepts/` through tools, then:

1. **Finds change points**, places where a real change makes sense: TODO comments, hardcoded values, a correct line that can be broken on purpose (debug tier), missing pieces, real weaknesses.
2. **Turns each change point into a task**: a one-line goal, a tier, the concepts the correct solution touches, the files, a done-check test and a reference patch (the answer key).
3. **For the debug tier**, it plants the bug, or marks `real_bug: true` when the bug is already in the repo. T3 is a real bug.

The output is an unordered bag of tasks. It is done when every tier has at least one task and every concept appears in at least one task.

```text
tasks/T3_guest_error/
  task.md            goal · tier · concepts · files · the story told to the learner · why this task exists
  check/test_t3.py   the done-check
  reference.patch    the answer key, locked (§24)
```

Phase 1 (`BACKEND_SPEC.md`, D8 and A2): there is no done-check test. `check/` is dropped, the reference solution stays, and VALIDATE 2 checks structure only.

**Crafter 3, ladder.** It orders the tasks into `ladder.md`:

- Tiers go in order: understand → change → debug → modify → assemble → build → solo.
- Prerequisites come first.
- Each task adds at most 2 new concepts beyond the tasks before it.

**Validation is code:**

| stage | checks |
|---|---|
| VALIDATE 1 | every anchor's text exists at its symbol · no prerequisite cycles · no duplicate ids · PROPOSED: every concept has a claim, a proof question and a misconception (§16) |
| VALIDATE 2 | each done-check fails on the starting code and passes with the reference patch · every listed concept exists |
| VALIDATE 3 | every task appears once · the ladder rules above hold |

VALIDATE 2 needs code to run, and phase 1 runs none on the server (§19). **PROPOSED:** the author runs VALIDATE 2 once per codebase on their own machine.

The crafters get primitive `Read`, `Glob` and `Grep` on the repo, plus custom write tools that validate before writing (§18).

---

## 23. The Workspace: Everything Is a File

One workspace per learner per codebase.

```text
/workspace/<repo>/
├── repo/                          the learner's code (learning branch), secrets scrubbed
├── concepts/                      CRAFTER 1, plus labeled discoveries (§17)
│   ├── C15_loop_scope.md          crafted; discovered entries labeled inside
│   └── D1_fake_client.md          a discovered concept
├── tasks/                         CRAFTER 2, one folder per task
│   └── T3_guest_error/            task.md · check/ · reference.patch (locked)
├── ladder.md                      CRAFTER 3, the task order
├── learner/                       survives between tasks
│   ├── graph/
│   │   ├── knowledge.md           status per concept (PROPOSED: computed, §15)
│   │   └── open-issues.md         saved issues carried to later tasks (I3)
│   └── journey/
│       ├── INDEX.md               one line per closed task
│       ├── T3.md                  the task's journey entry
│       ├── T3.transcript.md       the task's full conversation, readable on demand (§18)
│       └── T3.changes.log         the task's recorded changes, so its story map still renders (§21)
└── session/                       the CURRENT task only; cleared at close
    ├── focus.md                   focus stack, current node, return notes
    ├── graph/                     this task's nodes, edges and evidence
    ├── changes.log                every orchestrator change, with its id (feeds §21)
    ├── pasted/                    what the learner pasted: test output, git diff (§19)
    ├── summary.md                 older turns, compacted, for long tasks
    └── scratch/                   scratch-pad examples
```

**Changes from Spec v0.2:**

- No traps.
- No examiner files (`check.json`, `verdict.json`).
- No server run results: `run_result.json` became `pasted/`.
- `board.md` (rungs) became `graph/knowledge.md`.
- Added: `open-issues.md`, the transcript, the changes log and `session/graph/`.

The exact formats of the graph files and the changes log are **PROPOSED**.

| path | written by |
|---|---|
| `concepts/`, `tasks/`, `ladder.md` | the crafters, once; labeled discoveries at close |
| `learner/graph/` | the orchestrator, through custom tools |
| `learner/journey/T.md` | the tutor, at close only |
| `INDEX.md`, transcripts, changes logs | code, at close |
| `session/` | the orchestrator (graph, focus, changes) and code (pasted, summary) |

The journey entry the tutor writes at close:

```text
# T3 · Guests get "Une erreur s'est produite"
concepts: C15, C17, C13 known · D1 discovered (open)
what clicked: "it never gets assigned, exactly like x in last([])"
missed: expected None after an empty loop (JS habit)
fix: app.py ChatbotAssistant.chat · label → question_label
open: I3 how the test fakes OpenAI
```

---

## 24. Hard Gates and Parking

Gates are enforced in code: the custom tools refuse (§18).

| resource | available only when | never |
|---|---|---|
| `reference.patch` (the answer key) | the orchestrator decides to show the answer after the learner's own attempts (the bottom-out rule is open, §26) | before the learner has tried |
| `write_journey` | at close | during the loop |
| the tutor writing code for the learner | build tier (ally mode) | every other tier |
| hint-giving templates | ally mode, bottom-out | solo tier |
| a past task's journey or transcript | the orchestrator made it readable this turn | by default |

Every change to what an agent can read is logged with its reason.

**Parking.** The learner can stop at any point ("stop", "later", "I'm done for today"). The task closes as parked, and `session/` is saved as it is. On return, a fresh tutor and a fresh orchestrator open with the saved focus stack, and the story shows `↩ Came back to <node> · picking up: <return note>`. tutor_v2 already does this with its handoff record.

---

## 25. The Cast and Cost

| agent | kind | runs | reads | writes | never |
|---|---|---|---|---|---|
| Crafter 1 · concepts | LLM | once per codebase | the repo | `concepts/` | sees a learner |
| Crafter 2 · tasks | LLM | after VALIDATE 1 | the repo, `concepts/` | `tasks/` | sees a learner |
| Crafter 3 · ladder | LLM or code (§26) | after VALIDATE 2 | `tasks/`, `concepts/` | `ladder.md` | sees a learner |
| Orchestrator | LLM | every learner message; fresh per task | the message, the graph, files it chooses | the graph, the tutor's kit | speaks to the learner |
| Tutor | LLM | one conversation per task; fresh per task | the files in its kit | turns; the journey entry at close | grades or picks what comes next |
| Engine | code | always | everything | file plumbing, gates, logs, revisions | decides anything that needs judgment |

**No examiner.** Spec v0.2 had a separate judge for attempts. In this design the orchestrator assesses the evidence (§4, §10). Whether a separate judge comes back is open (§26).

**Cost per learner turn:** the orchestrator, then the tutor, one after the other. The crafters run once per codebase. In v0.2 the orchestrator was a small classifier. Here it diagnoses and judges, so it probably needs a mid-tier model (open, §26).

---

## 26. Open Decisions

Raised in the design review and not settled yet:

1. **Who commits graph changes.** The orchestrator directly, or code that first checks each change against the state machine in §8. One answer: the orchestrator writes only through a custom `update_graph` tool that refuses illegal changes (§18).
2. **Status model.** One status field, or lifecycle plus attention with readiness computed from edges. Today SUSPENDED and BLOCKED overlap (§8).
3. **Orchestrator output.** A list of assessments per turn (step 9 of T3 has two) plus one decision.
4. **Depth.** A limit on nested detours, and what STAGNATING does after repeated misses.
5. **Wrong diagnosis.** A "dropped" status for a node that turns out to be the wrong one.
6. **Help level.** Evidence earned right after heavy hints counts for less. The 4 rungs from v0.1 are not in this design.
7. **Templates.** One for each category in §5. The T3 library only covers its own scenario.
8. **Side questions.** Off-record asides (tutor_v2) or saved issues on the record (I3 in T3).
9. **Prompt cache.** Changing the system prompt or tool list every turn throws away the cache. Keep the base prompt and the full tool list fixed, and send each turn's kit as a message.

Still open from Spec v0.2:

10. **Crafter 2's output.** A strictly unordered bag, or a rough order that Crafter 3 enforces.
11. **Crafter 3.** An agent, or plain code. Its rules are explicit, so a topological sort could do it.
12. **When the orchestrator runs.** On every message, or behind a cheap code pre-filter ("stop", "I know this").
13. **Bottom-out.** When the answer key may be shown, and how "I don't know" counts.
14. **A separate judge.** v0.2's examiner for attempts, or the orchestrator alone.
15. **Spaced reviews between tasks** (v0.2 §9). Keep or drop.
16. **Migration.** Extend tutor_v2, or build the new engine fresh. This is the next planning step.
