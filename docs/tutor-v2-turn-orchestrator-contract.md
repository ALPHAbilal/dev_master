# Tutor v2 — TurnOrchestrator Contract

## Status

Implementation contract for review. This specifies the application layer that drives
the existing `tutor_v2` engine. It does not change agent responsibilities, wakeup or
return contracts, routing rules, stack behavior, or capability policy.

## 1. Responsibility boundary

`TurnOrchestrator` owns workflow, durable turn identity, parsing at the SDK boundary,
and atomic composition of existing engine operations with additive recorders.

```text
TurnOrchestrator owns
├─ operation and turn IDs
├─ wakeup dispatch order
├─ persistence of tutor and learner messages
├─ parsing model text into a return-stamp candidate
├─ calling existing contract validators
├─ outer transaction boundaries
├─ additive probe/journey recording
├─ retry and crash recovery
└─ publishing projection revisions

TurnOrchestrator does not own
├─ what question to ask
├─ how to teach
├─ the learner verdict or category
├─ hidden-gap discovery
├─ the next route
├─ stack movement
├─ mastery decisions
└─ agent capabilities
```

Those learning decisions remain with the existing agents, contracts, Router, and
CapabilityPolicy.

## 2. Dependencies

The orchestrator composes these existing components:

- `WakeupBuilder`
- `ClaudeAgentAdapter`
- `validate_return`
- `Router`
- `WorkspaceService`
- `ArchiveService`

It also uses these additive components:

- `ConversationRecorder`
- `ProbeRecorder`
- `JourneyRecorder`
- `JourneyReader`
- `JourneyArchiveService`
- `SemanticGraphService`

No agent receives direct access to these recorders or their underlying tables.

## 3. Durable identities

Every orchestration procedure receives a stable idempotency key before any external
model call.

```text
operation_id  identifies one orchestration procedure
turn_id       identifies one learner-facing conversational turn
message_id    identifies one persisted message/tool result
journey_id    identifies the active root-unit journey
```

Retries reuse the same identities. A unique database constraint prevents duplicate
messages, probes, lifecycle facts, routes, or archive episodes.

## 4. Turn types and states

Not every agent response is graded. The state machine therefore models two terminal
shapes.

### 4.1 Common states

```text
CREATED
   │
   ▼
AGENT_RUNNING
   │
   ▼
RECORDED
```

- `CREATED`: durable turn identity exists; no model result has been accepted.
- `AGENT_RUNNING`: a model invocation is in progress or may need safe retry.
- `RECORDED`: returned text/tool output has been persisted with stable IDs.

### 4.2 Non-graded turn

Used for outputs that do not immediately require a Judge verdict, including a
`wakeup.teach` response that explains or redirects.

```text
CREATED → AGENT_RUNNING → RECORDED
                              │
                              ▼
                        COMPLETE_UNGRADED
```

`COMPLETE_UNGRADED` is terminal for this turn. It records no probe, verdict, or
`answer_evaluated` event. A later learner reply begins a new turn or graded procedure
with its own ID and references the teaching message as context.

### 4.3 Learner-answer turn awaiting judgment

```text
CREATED → RECORDED → AWAITING_EVALUATION
                            │
                            ▼
                     JUDGE_RUNNING
                            │
                            ▼
                   STAMP_VALIDATED
                            │
                            ▼
                        EVALUATED
```

- `AWAITING_EVALUATION`: learner answer/action is durable, but no verdict committed.
- `JUDGE_RUNNING`: Judge invocation is in progress or retryable.
- `STAMP_VALIDATED`: model output parsed and passed `validate_return`; no route is
  claimed yet.
- `EVALUATED`: route mutation, probe, journey events, and turn state committed in one
  outer transaction.

### 4.4 Failure states

```text
RETRYABLE_AGENT_FAILURE
INVALID_AGENT_RETURN
TERMINAL_WORKFLOW_FAILURE
```

An invalid Judge return never reaches `Router.route_grade()`. It is preserved as an
operator-visible failed model output, not as learner evidence or a verdict.

## 5. Text-to-stamp bridge

`ClaudeAgentAdapter.run()` returns `list[str]`; engine validators accept dictionaries.
The orchestrator owns the explicit bridge:

```text
ClaudeAgentAdapter.run()
        │
        ▼
list[str] text blocks
        │
        ▼
ReturnStampParser.parse(expected_kind)
        │
        ├─ locate exactly one JSON object
        ├─ decode JSON
        ├─ require a dictionary
        ├─ require the expected `kind`
        └─ reject ambiguous/multiple payloads
        │
        ▼
validate_return(candidate)
        │
        ▼
validated plain dictionary
```

Parsing performs no schema repair, field inference, verdict normalization, or retry
through hidden heuristics. The existing validator remains authoritative.

Expected mappings:

```text
wakeup.map      → return.map
wakeup.grade    → return.grade
wakeup.distill  → return.distill
```

Teacher prose from `wakeup.probe`, `wakeup.teach`, and `wakeup.test` is stored as
conversation content and is not parsed as a return stamp unless the existing runtime
contract explicitly requires one.

## 6. Graded-turn flow and atomicity

Model calls and learner waiting occur outside database transactions. Only the final,
validated state transition and its evidence share an outer transaction.

The tutor question is **not** persisted here. It was already stored, with its
stable `question_ref`, by the preceding probe/test turn (§7). The graded turn only
*references* that `question_ref`; exactly one turn ever writes the question message.

```text
1. Create/recover turn_id; bind the existing question_ref from the probe/test turn
2. Receive learner answer/action
3. Persist learner message as AWAITING_EVALUATION, linked to question_ref
4. Build existing wakeup.grade with transient current evidence
5. Run Judge outside transaction
6. Parse text with ReturnStampParser
7. Call validate_return; require return.grade
8. Open outer Database.transaction()
   ├─ recheck turn is not already EVALUATED
   ├─ call Router.route_grade(unit_id, stamp) unchanged
   │    └─ existing inner transaction is a savepoint
   ├─ ProbeRecorder records exact question, answer, verdict, category
   ├─ JourneyRecorder records answer_evaluated
   ├─ JourneyRecorder records resulting route/stack transition
   ├─ mark turn EVALUATED
   └─ increment projection revision
9. Commit outer transaction
10. Publish projection revision after commit
```

If any operation inside step 9 fails, the route, axis mutation, stack mutation, probe,
journey events, and evaluated status all roll back. The durable learner message stays
`AWAITING_EVALUATION` and may be retried using the same `turn_id`.

## 7. Probe/question flow

The tutor's question must be persisted before it can become a parent resume bookmark
or evidence reference.

```text
1. Build wakeup.probe or wakeup.test
2. Run Teacher outside transaction
3. Persist returned tutor text as message(s)
4. Identify the explicit learner-facing question message
5. Save stable question_ref
6. If a child dive may occur, call existing
   Router.record_resume_question(unit_id, exact_question) unchanged
7. Mark the tutor-output turn COMPLETE_UNGRADED
8. Await learner reply under a new answer turn
```

The orchestrator may require the Teacher output contract to identify which returned
text is the question, but it may not rewrite the question before storing
`resume_q`. The stored resume question must remain exact.

## 8. Teaching-turn flow

```text
1. Build wakeup.teach using existing WakeupBuilder
2. Run Teacher outside transaction
3. Persist all returned tutor text in order
4. Record lifecycle fact `teaching_presented`
5. Mark turn COMPLETE_UNGRADED
6. Follow the existing RouteDecision-driven next action
```

No Judge stamp, probe row, verdict, or `answer_evaluated` event is created merely
because teaching text was shown.

## 9. Initial map and journey-start flow

The first root unit is pointed inside `Router.commit_map()`. The orchestrator wraps
that existing operation with the journey start in one outer transaction.

```text
1. Create map operation_id
2. Build existing wakeup.map
3. Run MAPPER outside transaction
4. Parse text → return.map candidate
5. Call validate_return; require return.map
6. Open outer Database.transaction()
   ├─ call Router.commit_map(stamp) unchanged
   │    └─ existing inner transaction is a savepoint
   ├─ create journey_id for returned root unit_id
   ├─ record journey_started
   ├─ record initial axis_started
   ├─ link deterministic structural graph nodes for the unit range
   └─ increment projection revision
7. Commit
8. Dispatch the RouteDecision returned by commit_map
```

For `return.map` extension, new root units are persisted by the existing Router, but
a journey is created only when `_point_next_root_locked()` actually points one as the
active root.

## 10. Child completion and parent-return flow

An owned child is distilled and sealed without ending the root journey.

```text
1. Receive and validate existing return.distill
2. Produce/verify child evidence using existing services
3. Open outer Database.transaction()
   ├─ commit child-owned distillation facts
   ├─ call Router.finish_owned_unit(child_id) unchanged
   │    └─ existing logic resumes the parent
   ├─ record detour_completed
   ├─ record parent_resumed with exact resume_question
   ├─ retain child graph branch under root journey_id
   └─ increment projection revision
4. Commit
5. Seal heavy child evidence through existing ArchiveService
6. After durable verification, attach ArchiveReceipt to journey branch
7. Publish projection update
```

Because filesystem archive writes cannot participate in SQLite atomicity, the archive
attachment uses a recoverable two-phase status:

```text
ARCHIVE_PENDING → artifact durably written/verified → ARCHIVED
```

Heavy live evidence is deleted only under the existing verified archive behavior.

## 11. Root completion and next-root flow

`Router.finish_owned_unit(root_id)` may both finish the current root and point the next
root. The orchestrator records both facts within the same outer transaction.

```text
1. Complete and validate root distillation
2. Open outer Database.transaction()
   ├─ capture current root journey_id
   ├─ call Router.finish_owned_unit(root_id) unchanged
   ├─ record journey_completed for old root
   ├─ mark old journey OWNED
   ├─ if RouteDecision points next root:
   │    ├─ create new journey_id
   │    ├─ record journey_started
   │    └─ record initial axis_started
   └─ increment affected projection revisions
3. Commit
4. Finalize old root per-unit evidence package
5. Finalize composite journey through JourneyArchiveService
6. Dispatch next RouteDecision, if any
```

No journey completion is emitted merely because a child becomes owned.

## 12. Park and resume flow

### 12.1 Park

```text
1. Existing grade route returns wakeup.distill with park reason
2. Validate existing return.distill with final_verdict=PARKED
3. Open outer Database.transaction()
   ├─ call Router.park_current_stack() (moves the full live stack → handoff,
   │    sets parked_stack=1, clears the live stack, nulls current_unit_id)
   ├─ mark journey PARKED
   ├─ record journey_parked
   ├─ allocate next immutable episode number
   └─ mark episode ARCHIVE_PENDING
4. Commit
5. JourneyArchiveService writes/verifies episode checkpoint
6. Mark episode ARCHIVED
```

`Router.park_current_stack()` must run only after the DISTILLER has read the
still-live stack for the parked unit's `wakeup.distill`. Parking does not call the
existing one-time final per-unit seal as though ownership were complete.

### 12.2 Resume

```text
1. Load existing HandoffService record
2. Validate existing continuation
3. Open outer Database.transaction()
   ├─ call Router.restore_parked_stack() (rebuilds every frame, clears parked_stack,
   │    restores current_unit_id, returns the resume RouteDecision)
   ├─ mark same journey LIVE
   ├─ create new episode identity
   ├─ record journey_resumed
   └─ increment projection revision
4. Commit
5. Build ordinary resumed wakeup through WakeupBuilder.build_resumed() using the
   restored RouteDecision's unit_id/axis/resume_question
6. Dispatch ordinary wakeup
```

No synthetic resume narrative is injected into the agent context.

## 13. RouteDecision dispatch

The orchestrator dispatches, but never invents, the next step.

```text
RouteDecision.next_step
├─ wakeup.probe    → probe/question flow
├─ wakeup.teach    → teaching flow
├─ wakeup.test     → test/proof flow
├─ wakeup.distill  → distillation + child/root/park flow
└─ null            → no next mapped root
```

The decision's `unit_id`, `axis`, `highlight`, and `resume_question` are passed through
to the existing packet/UI projection boundaries. The orchestrator does not substitute
another axis or unit.

## 14. Crash recovery

Recovery is state-driven and idempotent.

```text
AGENT_RUNNING
└─ retry model call or mark operator failure; no route exists

RECORDED / COMPLETE_UNGRADED
└─ content is durable; no evaluation expected

AWAITING_EVALUATION / JUDGE_RUNNING
└─ retry Judge with persisted question/answer evidence

STAMP_VALIDATED
└─ rerun atomic evaluation using same turn_id

EVALUATED
└─ return stored RouteDecision/projection; never route again

ARCHIVE_PENDING
└─ retry deterministic artifact write/verification
```

The model output used to produce a validated stamp is retained for auditing. A retry
must not silently replace an already validated stamp with a different judgment.

## 15. Concurrency rules

- Only one active learner-answer evaluation may exist for the top stack frame.
- A turn records the expected unit, axis, workspace revision, and projection revision.
- Before atomic evaluation, the orchestrator verifies the turn still targets the live
  top frame and expected axis.
- Duplicate submissions with the same idempotency key return the existing result.
- Stale workspace actions use the existing optimistic revision checks.
- Projection publication happens only after database commit.

## 16. Public application operations

Conceptual interface:

```text
initialize_session(...)
map_target(operation_id)
dispatch_next(route_decision)
submit_learner_answer(turn_id, answer)
submit_learner_action(turn_id, action_evidence)
park_journey(operation_id)
resume_journey(operation_id)
get_live_journey(journey_id, after_revision=None)
get_archived_journey(journey_id)
```

These operations return application DTOs, not database connections or raw agent SDK
objects.

## 17. Required tests

### Compatibility

- All existing `tutor_v2` tests pass unchanged.
- Router signatures and wakeup/return contracts remain unchanged.
- Existing per-unit archive tests retain their current meaning.

### Turn state machine

- Teaching turn ends `COMPLETE_UNGRADED` without a probe/verdict.
- Learner answer reaches `EVALUATED` only after atomic route/evidence commit.
- Invalid JSON and invalid return stamps never call Router.
- Retry with the same `turn_id` does not duplicate output or route.

### Atomicity

- Probe failure rolls back the Router mutation.
- Journey-event failure rolls back Router and probe mutations.
- Successful evaluation commits verdict, probe, lifecycle events, and status together.
- Conversation remains `AWAITING_EVALUATION` after rollback.

### Lifecycle boundaries

- Initial `commit_map()` creates the first root journey atomically.
- Completing a child records detour completion and parent return, not root completion.
- Finishing a root completes its journey and starts the next pointed root journey.
- Parking creates an episode checkpoint; resuming reuses the same journey identity.

### Parsing

- Exactly one valid JSON return object is accepted.
- Multiple objects, prose-only output, wrong kinds, and schema violations are rejected.
- Parser never repairs or guesses missing fields.

## 18. Definition of done

The orchestrator contract is implemented when:

1. Both graded and non-graded turn shapes are durable and recoverable.
2. The text-to-stamp boundary is explicit, strict, and tested.
3. Map commit, grade routing, child return, root completion, park, and resume each
   produce correct journey facts.
4. Verdict, probe, lifecycle transition, and evaluated status commit atomically.
5. Existing engine behavior and contracts remain unchanged.
6. The UI can consume a live projection without containing tutoring logic.

