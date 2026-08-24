# Tutor v2 — Root Journey Persistence and Archive Proposal

## Status

Proposal for review. This document does not authorize implementation or changes to
the existing agentic behavior.

## 1. Objective

Support a live, rich map of the learner's complete journey through one root unit,
including:

- class, function, and method structure;
- questions, answers, tests, and evidence;
- prerequisite child-unit detours;
- returns to the exact parent question;
- multiple park/resume episodes;
- permanent conversation retention;
- reconstruction after the root unit is completed.

The solution must preserve the existing `tutor_v2` agentic layer and learning logic.

## 2. Non-negotiable compatibility boundary

The following behavior remains unchanged:

```text
MAPPER
├─ produces ordered top-level units
└─ does not become responsible for UI graph layout

TEACHER
├─ probes and teaches the active axis
└─ keeps the same step-scoped context and capabilities

JUDGE
├─ returns the same verdicts, categories, evidence, and hidden gaps
└─ remains the source of learner-evaluation judgment

DISTILLER
├─ distills an owned or parked unit
└─ keeps its existing learning responsibilities

Router
├─ preserves every existing route and state transition
├─ preserves shaky escalation, harder proof, child dives, and parent return
└─ remains deterministic and authoritative

WakeupBuilder and CapabilityPolicy
├─ preserve current packet shapes and scoped access
└─ grant no new implicit agent capabilities
```

No agent prompt, category, verdict rule, hop behavior, stack rule, or learning route is
changed to satisfy the UI. New persistence is attached around successful existing
operations.

The current package is an engine, not a complete learner-facing runtime. It contains
no caller that owns the full turn from question to learner answer to grading. This
proposal therefore includes one new application-layer prerequisite:
`TurnOrchestrator`. It composes the existing engine without moving learning decisions
out of it.

## 2.1 New application boundary: `TurnOrchestrator`

```text
TurnOrchestrator — owns workflow and durable turn identity
├─ builds the existing wakeup packet
├─ invokes ClaudeAgentAdapter.run()
├─ persists returned tutor text
├─ exposes that text to the learner-facing transport
├─ accepts and persists the learner reply/action
├─ invokes the existing Judge wakeup
├─ validates the existing return.grade stamp
├─ calls Router.route_grade() unchanged
└─ records the probe and journey transition atomically with that route

Existing engine — continues to own learning behavior
├─ WakeupBuilder owns scoped agent context
├─ ClaudeAgentAdapter owns the closed model/tool boundary
├─ Judge owns evaluation judgment
└─ Router owns deterministic state transitions
```

The orchestrator does not interpret learner prose, select verdicts, choose routes, or
grant capabilities. It is deterministic workflow glue and the owner of stable turn,
message, and idempotency identities.

## 3. Core design decision

Separate the durable **root journey** from per-unit evidence archives.

```text
ROOT JOURNEY — durable learner-facing history
├─ begins when a top-level unit is pointed
├─ survives every child-unit detour
├─ survives parking and resumption
├─ records lightweight graph and lifecycle facts
└─ closes only when the root unit becomes OWNED

UNIT EVIDENCE ARCHIVES — immutable proof packages
├─ preserve heavy events, tests, conversations, and revisions
├─ may be created for child units or completed episodes
└─ are referenced by the root journey
```

The map is reconstructed from the root journey. Heavy supporting evidence is loaded
from live storage or an immutable archive through stable references.

## 4. Identity model

Add a stable `journey_id` representing one top-level/root-unit learning journey.

```text
journey_id
└─ root_unit_id
   ├─ root unit activity
   ├─ child unit A
   │  └─ child unit B
   ├─ parked episode 1
   ├─ resumed episode 2
   └─ final owned episode
```

All units in the active stack inherit the root's `journey_id`. Existing `unit_id`,
`parent_id`, stack depth, and router behavior remain unchanged.

## 5. Additive persistence model

Exact SQL is intentionally deferred until this proposal is accepted. The conceptual
tables are:

### 5.1 `journeys`

```text
journeys
├─ id
├─ session_id
├─ root_unit_id
├─ state: LIVE | PARKED | OWNED
├─ started_at
├─ updated_at
└─ completed_at, optional
```

Purpose: stable boundary for the learner-facing map.

### 5.2 `conversation_messages`

```text
conversation_messages
├─ id
├─ journey_id
├─ unit_id
├─ axis, optional
├─ role: learner | tutor | tool | system
├─ message_kind
├─ content
├─ turn_id
├─ sequence
├─ status: RECORDED | AWAITING_EVALUATION | EVALUATED
├─ source_wakeup_step, optional
├─ created_at
└─ archived_artifact_ref, optional
```

Purpose: preserve the complete conversation with stable IDs. `TurnOrchestrator`
records learner inputs and returned agent text; agents do not receive a new write
tool. The status supports honest crash recovery without fabricating a verdict.

### 5.3 `probe_records`

Use the existing `probes` table through a new deterministic `ProbeRecorder` service.
The service records the exact question, learner answer, step, verdict, and category
after the existing evaluation succeeds.

Purpose: make the already-defined probe history real without changing Teacher or
Judge behavior.

### 5.4 `journey_events`

```text
journey_events
├─ id
├─ journey_id
├─ unit_id
├─ parent_unit_id, optional
├─ axis, optional
├─ event_type
├─ payload_json
├─ message_refs_json
├─ probe_refs_json
├─ action_event_refs_json
├─ source_ref_json, optional
├─ workspace_revision, optional
├─ workspace_hash, optional
└─ created_at
```

Purpose: append-only chronological facts needed to reconstruct the journey.

### 5.5 `semantic_nodes` and `semantic_edges`

```text
semantic_nodes
├─ id
├─ journey_id
├─ unit_id
├─ kind: file | class | function | method | concept | failure | test | ...
├─ title
├─ summary
├─ source_ref_json, optional
├─ status
├─ provenance: parser | agent | system
├─ evidence_refs_json
└─ timestamps

semantic_edges
├─ id
├─ journey_id
├─ from_node_id
├─ to_node_id
├─ relationship_type
├─ label
├─ explanation, optional
├─ provenance: parser | agent | system
├─ evidence_refs_json
└─ timestamps
```

Purpose: provide a reliable semantic graph independently from visual layout.

### 5.6 `learner_notes`

```text
learner_notes
├─ id
├─ journey_id
├─ target_kind: node | edge | message | journey
├─ target_id
├─ content
└─ timestamps
```

Learners may mutate their notes only. Verified nodes, edges, messages, verdicts, and
evidence remain immutable from the learner UI.

## 6. Reliable semantic graph production

The graph uses three producers without changing existing agent responsibilities.

```text
DETERMINISTIC STRUCTURE EXTRACTOR
├─ parses the configured repository
├─ emits files, classes, functions, and methods
├─ records exact source ranges
└─ emits only relationships it can establish reliably

EXISTING AGENT OUTPUTS
├─ hidden gaps become prerequisite/concept candidates
├─ judgments become misconception/proof candidates
└─ existing prose may supply learner-facing explanations

VALIDATION SERVICE
├─ validates node and edge schemas
├─ restricts relationship vocabulary
├─ requires evidence for agent-authored claims
├─ rejects invalid source anchors
└─ commits accepted graph changes
```

Agents do not lay out the graph and do not mutate it directly. The application
translates existing validated outputs into candidate graph mutations and commits them
through deterministic services.

## 7. Source-range reconciliation

Unit ranges and AST structure ranges serve different purposes and must both remain
truthful.

```text
UNIT SOURCE RANGE
└─ the code slice selected by MAPPER for the learning task

STRUCTURAL SOURCE RANGE
└─ exact parser-derived range of a class/function/method
```

Rules:

1. Never rewrite the Mapper's unit range to match an AST node.
2. Never crop an AST node's canonical source range to match the unit.
3. Link a structural node to a unit when their ranges overlap or the unit contains it.
4. Record the relationship explicitly: `contains`, `overlaps`, or `focuses_on`.
5. If a unit spans several structural nodes, show each relevant node under the same
   unit journey.
6. If a unit covers only part of a method, the Code panel may highlight the unit
   focus while still identifying the full method boundary.

This preserves both pedagogical focus and structural accuracy.

## 8. Recording without altering agentic logic

Use `TurnOrchestrator` around the existing engine operations. Agent calls occur
outside database transactions. Once a valid Judge stamp exists, the route and its
evidence commit atomically through an outer transaction.

```text
1. Build wakeup using existing WakeupBuilder
2. Run existing agent adapter                     outside DB transaction
3. Persist tutor message with stable turn_id
4. Persist learner answer/action with same turn_id
5. Run Judge and validate existing return.grade   outside DB transaction
6. Open outer Database.transaction()
   ├─ call Router.route_grade() unchanged
   │    └─ its current transaction becomes a nested savepoint
   ├─ ProbeRecorder writes question + answer + accepted verdict
   ├─ JourneyRecorder writes answer_evaluated + route transition
   └─ mark conversation turn EVALUATED
7. Commit outer transaction
8. Publish updated projection revision
```

`Database.transaction()` already supports nesting through savepoints. Therefore the
orchestrator can establish the outer atomic boundary while `Router.route_grade()`
keeps its current signature and internal transaction. The orchestrator holds the
question and learner answer; the router does not need to receive them.

If routing or evidence recording fails, the outer transaction rolls back the axis,
unit, stack, probe, lifecycle, and evaluated-status mutations together. The already
persisted conversation remains truthful and marked `AWAITING_EVALUATION`; recovery
may retry it with the same idempotency key. It never claims an evaluation that did
not commit.

This design explicitly rejects both undesirable alternatives:

- do not widen `route_grade()` with conversation fields;
- do not accept a committed axis verdict without its probe/evaluation record.

Examples:

```text
Existing result                    Additive recorded fact
─────────────────────────────────  ─────────────────────────────
root becomes POINTED               journey_started
axis selected                      axis_started
Teacher text returned              tutor_message
learner replies                    learner_message
Judge return accepted              answer_evaluated + probe row
hidden gap pushes child            detour_started
child becomes OWNED                detour_completed
resume_after_child succeeds        parent_resumed
fatigue-switch parks unit          journey_parked
root becomes OWNED                 journey_completed
```

## 9. Child-unit archival

Keep the current ability to seal a completed child, but do not remove its existence
from the root journey.

```text
Child becomes OWNED
├─ child evidence package is sealed
├─ root journey records archive reference
├─ semantic nodes and lightweight lifecycle facts remain queryable
├─ heavy live child events may be deleted after archive verification
└─ UI keeps the completed detour branch visible
```

The root journey snapshot shows the branch immediately. Opening detailed evidence can
hydrate it from the child archive through an `ArchiveReader`.

The existing `ArchiveService.seal()` remains the per-unit evidence sealer. Its public
contract and current behavior are not repurposed as the composite journey writer.

## 10. Park and resume semantics

The existing one-directory-per-slug finalization model cannot safely represent
several park/resume episodes. Parking must create an episode checkpoint, not finalize
the unit's only archive identity.

```text
PARK
├─ preserve stack/handoff exactly as today
├─ mark root journey PARKED
├─ checkpoint the current episode immutably
├─ keep the journey reopenable
└─ do not claim final ownership

RESUME
├─ load handoff and ordinary wakeup exactly as today
├─ mark the same journey LIVE
└─ append new messages/events to a new episode

OWNED
├─ finalize all episodes
├─ write the final composite archive index
└─ mark the root journey OWNED
```

Add a separate `JourneyArchiveService` for episode checkpoints and the composite
root index. It coordinates existing per-unit archive receipts rather than changing
what `ArchiveService.seal()` means.

Recommended artifact layout for the new journey service:

```text
archive/<root-unit-slug>/
├─ journey-manifest.json
├─ episodes/
│  ├─ 0001-parked/
│  ├─ 0002-parked/
│  └─ 0003-owned/
├─ units/
│  ├─ <child-a>/
│  └─ <child-b>/
└─ graph.json
```

Existing archive content shapes remain valid inside each per-unit evidence package.
The new composite journey manifest indexes them. Existing archives remain readable.

### 10.1 Service ownership

```text
ArchiveService (existing)
├─ seals one unit evidence package
├─ preserves its current manifest contract
└─ keeps its current tests

JourneyArchiveService (new)
├─ checkpoints park/resume episodes
├─ indexes existing child ArchiveReceipts
├─ writes conversation/lifecycle/graph artifacts
└─ finalizes the root journey after ownership

ArchiveReader (new)
└─ reads both legacy per-unit and composite journey formats
```

On `PARKED`, `TurnOrchestrator` calls the new journey episode checkpoint operation,
not the existing final per-unit `ArchiveService.seal()` path. On child `OWNED`, the
existing per-unit seal may run and its receipt is linked into the live root journey.
On root `OWNED`, the existing evidence package and the new composite journey index are
both finalized.

## 11. Conversation archival

Extend the archive contract in a versioned, backward-readable way.

The final journey manifest references:

- the complete ordered conversation;
- lifecycle events;
- semantic graph snapshot;
- root and child evidence packages;
- workspace snapshots and tested revisions;
- learner notes, if export is desired;
- final ownership/parking history.

Conversation storage should use JSONL so messages retain stable IDs and can be
streamed without loading one large document.

```text
conversation.jsonl
{"id":1,"role":"tutor","unit_id":10,"content":"..."}
{"id":2,"role":"learner","unit_id":10,"content":"..."}
```

The original conversation is permanent. Summaries are optional indexes and never
replace it.

## 12. Archive reader

Add a read-only `ArchiveReader` service that:

- validates manifest and artifact versions;
- reads root and child packages;
- reconstructs ordered conversation and lifecycle history;
- resolves evidence and workspace revision references;
- returns the same learner-facing journey projection shape used by live sessions;
- performs no routing and no agent calls.

This gives the UI one conceptual read contract for both live and completed journeys.

## 13. UI projection and live transport

Add a deterministic `JourneyReader` projection:

```text
journey snapshot
├─ journey identity and state
├─ root and child units
├─ active stack position
├─ semantic nodes and edges
├─ lifecycle overview
├─ conversation messages
├─ evidence references
├─ learner notes
└─ monotonic projection revision
```

For a live journey, it reads SQLite and hydrates already-sealed child evidence only
when needed. For a completed journey, `ArchiveReader` returns the equivalent shape.

Transport is replaceable:

```text
first implementation: short polling by projection revision
later implementation: Server-Sent Events or WebSocket notifications
```

The transport must not contain tutoring or routing logic.

## 14. Migration and backward compatibility

1. Add new tables without rewriting existing unit, axis, stack, probe, event, learner,
   handoff, or meta semantics.
2. Give archive manifests an explicit format version.
3. Keep the archive reader compatible with existing unit archives that contain only
   `manifest.json`, `events.jsonl`, and workspace snapshots.
4. Existing sessions without journey rows may lazily create a journey projection from
   the active root and stack, marking unavailable historical details honestly.
5. Do not synthesize missing conversations or semantic relationships for old data.

## 15. Failure and consistency rules

- A journey event must not claim a route that did not commit.
- An archive reference becomes visible only after its artifact is durably written and
  verified.
- Heavy live events are deleted only after archive verification succeeds.
- Agent-authored nodes and edges require evidence references and validation.
- Parser-authored nodes retain parser provenance and exact ranges.
- Learner notes cannot modify verified evidence.
- Replaying a request must not duplicate messages, probes, journey events, or archive
  episodes; recorder operations need idempotency keys.
- A failed UI projection must never roll back or alter tutoring state.

## 16. Implementation sequence

```text
1. Characterization tests for current engine behavior
2. TurnOrchestrator contract, turn state machine, and idempotency
3. Journey identity + additive schema
4. ConversationRecorder + ProbeRecorder
5. Outer-transaction route/evidence integration
6. Transactional journey-event recording
7. Deterministic Python structure extractor
8. Semantic graph validation/persistence
9. Live JourneyReader snapshot
10. JourneyArchiveService + backward-compatible ArchiveReader
11. Park/resume/final ownership orchestration
12. Live update transport
13. Synchronized map/conversation/inspector UI
```

Every stage must keep the existing `tutor_v2` tests passing. New characterization
tests should freeze existing router decisions before transaction boundaries are
touched.

## 17. Acceptance criteria

The persistence design is complete when:

1. Existing wakeup, return, routing, stack, capability, grading, and per-unit archive
   tests remain unchanged and pass. New journey/archive behavior is covered by new
   tests rather than changing the meaning of the old assertions.
2. A root journey retains completed child detours after child evidence is archived.
3. The exact parent question remains the visible return point.
4. Multiple park/resume episodes can be finalized without losing later evidence.
5. The complete conversation can be read during and after the journey.
6. Class/function/method nodes have deterministic source anchors.
7. Agent-authored semantic claims are validated and evidence-backed.
8. Live and archived journeys expose equivalent UI projection shapes.
9. Learner notes remain editable without altering system evidence.
10. No frontend operation can directly change routing, verdicts, mastery, or stack
    state.
11. A committed axis verdict always has its corresponding probe and
    `answer_evaluated` record in the same committed transaction.
12. A crash before evaluation commit leaves a recoverable
    `AWAITING_EVALUATION` turn and no partially committed route.

## 18. Explicitly rejected approaches

- Rewriting the agent roles or prompts to make them UI-state managers.
- Widening `Router.route_grade()` to carry question or conversation data.
- Giving agents direct database or graph mutation access.
- Making the frontend infer routing history from current mutable rows.
- Treating a parked unit as a permanently finalized single archive.
- Replacing the original conversation with a summary.
- Letting semantic graph requirements change Judge verdicts or Router decisions.
- Delaying the reliable class/method graph beyond the first release.
