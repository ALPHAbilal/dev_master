# Backend implementation plan — 12-stone tutor

## Scope

Build the new agentic backend only. No learner interface, HTML, CSS, HTTP routes,
or UI-state payloads belong to this plan.

The existing `agentic_tutor/tutor/` package is a useful legacy prototype, but it
uses the former seven-table / two-agent model. Do **not** mutate it into the new
model in place. Build a parallel backend at `agentic_tutor/tutor_v2/`, prove it
with tests, then choose a deliberate migration point for the interface.

```text
interface later
      │ calls only these application services
      ▼
tutor_v2 / application services
      │
      ├── SQLite state + atomic transactions
      ├── workspace and event recorder
      ├── contract validator + router + stack engine
      └── Claude Agent SDK adapter + scoped custom tools
```

## Delivery rule

Complete, test, and review one stage before beginning the next. A stage is not
complete merely because its classes exist: its acceptance tests must pass with
no Claude/API key required. Real SDK tests are added only after deterministic
tests cover the same behavior.

## Stage 0 — establish the backend boundary

Create `agentic_tutor/tutor_v2/` and a separate test package. It may import
standard-library Python only at first. The old backend and `ui/` remain untouched.

**Deliverables**

- package layout and configuration object (`database path`, `workspace root`,
`archive root`, `session id`)
- domain names shared by the backend: `Unit`, `Axis`, `StackFrame`, `Event`,
  `Workspace`, `Handoff`, `WakeupPacket`, `ReturnStamp`
- error hierarchy for validation, invariant, unavailable capability, and stale
  workspace revision errors

**Done when:** importing the package has no SDK or interface dependency.

## Stage 1 — SQLite foundation and 12 stones

Implement the authoritative stores from `STONES.md` and `DATA.md`:

```text
SQLite: units, axes, stack, meta, probes, learner, handoff, events
Filesystem: workspace document and archive artifacts
Read only: target codebase, return-schema files
```

Use SQLite transactions, foreign keys, WAL mode, explicit transaction contexts,
and a schema-version migration table. Store `workspace_revision` and content hash
on each accepted edit. Enforce one-home ownership: a live event cannot also be
declared archived; a PARKed stack cannot remain live after it moves to handoff.

**Done when:** a fresh database can initialize, migrate, and round-trip every
store; failed transactions leave no partial event/archive/stack state.

## Stage 2 — code-owned state services

Implement small application services; agents never receive raw SQL access.

```text
WorkspaceService   read / guarded write / revision conflict
EventRecorder      append edit, command, test, output, UI, feedback events
ArchiveService     title, manifest, evidence, event seal, workspace snapshot
HandoffService     read/write latest; move/restore parked continuation
StateReader        returns only step-scoped domain data
```

The workspace keeps one visible learner file throughout an active unit. Every
test captures an internal checkpoint of the exact tested revision; unit archive
contains the final file plus only those test-linked checkpoints. Archive and
event movement must be one guarded transaction boundary: archive
artifact written durably first; only then mark/move the live events.

**Done when:** workspace edits, event recording, archive sealing, and handoff
read/write work without an agent; archive retries are idempotent after a
simulated crash. Full stack checkpoint/restore is deliberately Stage 9.

## Stage 3 — formal contracts and validation wall

Create strict JSON Schemas (or equivalent typed validators) for:

```text
wakeup.map / wakeup.point / wakeup.probe / wakeup.teach / wakeup.test /
wakeup.grade / wakeup.distill
return.map / return.grade / return.distill
action event packet / continuation / archive manifest
```

The validator verifies required fields, allowed enum values, evidence references,
scope ownership, and no write target outside the contract. Define one canonical
v1 route field: `category`, clearly distinct from a grade verdict and from
code-only policy facts.

**Done when:** malformed, out-of-scope, and contradictory stamps are rejected
before any state change; valid fixtures create deterministic commits.

## Stage 4 — deterministic stack and routing engine

Implement all code→code decisions without model judgment:

- select current deepest teachable unit/axis
- push prerequisite child subholes and preserve the exact parent `resume_q`
- queue sibling holes without interrupting a prerequisite chain
- pop an OWNED/PARKed child and replay the parent question
- apply accepted `return.grade.category` routes
- enforce state transitions and axis threshold policy

**Done when:** a pure unit-test suite covers normal advance, child dive/return,
sibling queue, invalid transition rejection, and no parent ownership while a
child is live.

## Stage 5 — packet builder and capability policy

Implement a `WakeupBuilder` that assembles the minimal ordinary packet for the
selected step from scoped references—not the database or transcript wholesale.
Implement a `CapabilityPolicy` mapping each wakeup to allowed custom tools.

The resulting packet must look identical whether it came from an uninterrupted
session or restored handoff, except where elapsed-time policy legitimately adds a
fact.

**Done when:** snapshot tests show expected packet contents and prove unrelated
learner history, archives, and tools never leak into a wakeup.

## Stage 6 — Claude Agent SDK adapter

Add an isolated runtime adapter. It owns SDK import/configuration, session
lifecycle, streaming events, cancellation, and translation between SDK messages
and the stage-3 contracts.

Expose narrow custom tools only, for example `read_code_slice`,
`read_workspace`, `observe_learner_action`, and scoped evidence reads. Global
routing, stack moves, archive commits, and checkpoint/restore remain code-owned,
not agent-callable.

**Done when:** a fake adapter exercises the whole backend without the SDK; an
optional, explicitly enabled real-SDK smoke test can run one bounded wakeup.

## Stage 7 — four agent definitions

Translate the current anatomy into executable agent definitions:

```text
MAPPER     maps a bounded code batch; returns return.map
TEACHER    probes, teaches, tests; returns learner-facing SAY only
JUDGE      interprets answer/action evidence; returns return.grade
DISTILLER  proposes archive, learner diff, and handoff note; returns return.distill
```

Agent definitions contain stable behavior and step-specific instructions only.
The packet builder supplies current facts; tools supply live, scoped capability;
the validator/code router retains authority.

**Done when:** contract fixtures prove each role receives only its permitted
tools/context and cannot emit an unauthorized effect.

## Stage 8 — action hooks and automatic event capture

Implement the backend entry points the future interface/terminal will call:

```text
record_editor_change
record_terminal_command
record_terminal_result
record_learner_message
record_ui_action
```

Each first records an event. Objective policy can block or give factual feedback;
semantic interpretation creates a scoped agent wakeup that returns through the
normal validator/router. No parallel gap or feedback engine is allowed.

**Done when:** tests cover allowed action, forbidden action, semantic command,
code edit exposing a gap, and test failure; every case has an event row and one
known continuation.

## Stage 9 — PARK, cold restore, and archive lifecycle

Implement `checkpoint_continuation` and `restore_continuation` as code-only
operations. A checkpoint may occur only after:

1. an agent return is fully validated and committed;
2. a learner event is persisted; or
3. a guarded action transaction commits.

Persist `{next_step, awaiting, outstanding_question_ref?, context_refs[]}` plus
the moved complete stack, workspace revision, pending siblings, hop budgets, and
relevant evidence references. Never checkpoint an in-flight model/tool call.

**Done when:** deterministic tests interrupt at every safe boundary and verify
the next packet/route equals the uninterrupted run. Tests also verify that a
question already displayed is not asked twice.

## Stage 10 — end-to-end backend harness

Create a command-line test harness only (not frontend) with scripted Mapper,
Teacher, Judge, and Distiller fixtures. It runs scenarios against a temporary
SQLite database and workspace:

```text
map -> point -> probe -> answer -> grade -> teach/test -> grade -> own -> distill
child subhole -> own child -> restore parent question
sibling discovery -> queue -> later deterministic selection
forbidden terminal action -> record + factual block
semantic action -> record + Judge/Teacher return path
PARK at every safe boundary -> cold restore -> equivalent next packet
```

**Done when:** all scenario tests pass, the database/archive can be inspected,
and a test report proves the invariants from `MASTER.md` and `ANATOMY.md`.

## Only after Stage 10

Connect the workbench interface through thin API endpoints. The frontend must
never call SQLite directly or decide agent, route, grade, stack, archive, or
checkpoint behavior.

## First implementation task

Start with **Stage 0 and Stage 1 only**: scaffold `tutor_v2`, create the SQLite
schema/migration transaction layer, and write its tests. Do not call the Claude
SDK and do not touch frontend files in this task.
