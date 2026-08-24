# Tutor v2 — Journey/Orchestrator Build Plan

Operational tracker for the persistence + orchestrator + UI build. Derives from
`tutor-v2-journey-persistence-proposal.md` §16 and `tutor-v2-turn-orchestrator-contract.md`.
Every stage keeps the existing engine and its tests unchanged.

## Ground rules

- The engine (`WakeupBuilder`, `ClaudeAgentAdapter`, Judge/agents, `Router`,
  `CapabilityPolicy`) keeps its current signatures and behavior. New work is additive.
- Each stage ships with tests. Existing `tests_v2` must stay green at every commit.
- No agent gets a write tool or DB access. Recorders are orchestrator-owned.

## Stage status

| # | Stage | Deliverable | Status |
|---|-------|-------------|--------|
| 0 | **Engine park gap** | `Router.park_current_stack()` / `restore_parked_stack()` + tests | ✅ done |
| 1 | Characterization tests | Existing `tests_v2` freeze router decisions; all kept green and unchanged in meaning | ✅ done |
| 2 | TurnOrchestrator + parser | `ReturnStampParser` strict text→stamp bridge (`parsing.py`) | ✅ done |
| 3 | Journey identity + schema | 6 additive tables; migration v4; projection_revision counter | ✅ done |
| 4 | Recorders | `ConversationRecorder`, `ProbeRecorder`, `JourneyRecorder` (`recorders.py`) | ✅ done |
| 5 | Outer-transaction integration | Route + probe + journey_event atomic via savepoint nesting (`orchestrator.py`) | ✅ done |
| 6 | Journey-event recording | Lifecycle facts (journey/axis/answer/detour/gap/park/resume/complete) | ✅ done |
| 7 | Structure extractor | Deterministic Python AST → module/class/function/method + ranges (`structure.py`) | ✅ done |
| 8 | Semantic graph service | Validation, provenance, evidence-anchoring, range reconciliation (`semantics.py`) | ✅ done |
| 9 | JourneyReader | Live snapshot projection + revision gating (`journey_reader.py`) | ✅ done |
| 10 | Archive writer + reader | `JourneyArchiveService` (episodes/composite) + `ArchiveReader` (legacy + composite) | ✅ done |
| 11 | Park/resume/ownership flow | `park` / `resume` / `finish_child` / `finish_root` on the orchestrator | ✅ done |
| 12 | Live transport | `PollingProjectionFeed` — revision-gated polling (`transport.py`) | ✅ done |
| 13 | UI | Synchronized Map / Conversation / Inspector | ⏸ out of scope (backend-only build) |

**Backend complete: 58 tests passing (`python3 -m pytest tests_v2 -q`).**

## Test discipline

- `python3 -m pytest tests_v2 -q` must pass at every stage boundary.
- New behavior gets new tests; old assertions never change meaning (proposal Acceptance #1).
- Atomicity stages get rollback tests (probe failure rolls back route, etc.).

## Done log

- **Stage 0** — Added `park_current_stack()` / `restore_parked_stack()` to `routing.py`.
  Park serializes the full live stack into the single `handoff` record
  (`parked_stack=1`), clears the live stack, and nulls `current_unit_id`; restore is
  its exact inverse and clears the parked flag in the same transaction so the
  one-home DB invariant holds. Closes the "Stage 9" stub the park/resume episode
  model depended on. Tests: `test_park_moves_full_stack_to_handoff_then_resume_restores_top_frame`,
  `test_restore_without_parked_handoff_is_rejected`. Contract §12 updated to compose
  these real methods; §6/§7 question-ownership overlap resolved.
- **Stage 3** — Added the six additive journey-layer tables to `schema.sql`
  (`journeys`, `conversation_messages`, `journey_events`, `semantic_nodes`,
  `semantic_edges`, `learner_notes`) with indexes, FK cascades on `journey_id`,
  and CHECK constraints on state/role/status/provenance. Bumped `SCHEMA_VERSION` to
  4 with a no-op migration (new tables are idempotent via `CREATE ... IF NOT EXISTS`
  in `schema.sql`, run on every init — fresh and existing DBs both get them). The
  engine tables are untouched. Tests: journey state constraint + cascade delete,
  per-journey sequence uniqueness; existing version-literal assertions updated 3→4.
- **Stages 2/4** — `parsing.py` (`ReturnStampParser`: one-object extraction, strict
  kind check, no schema repair) and `recorders.py` (`ConversationRecorder`,
  `ProbeRecorder`, `JourneyRecorder`). All recorder writes nest as savepoints.
- **Stages 5/6/11** — `orchestrator.py` (`TurnOrchestrator`). Agent calls are a seam
  (blocks passed in) so it is SDK-independent and fully tested. The graded turn commits
  route + probe + `answer_evaluated` + `EVALUATED` status in one outer transaction;
  a forced probe failure rolls the route back and leaves the answer `AWAITING_EVALUATION`
  (proven by test). Lifecycle facts emitted for map-start, answer, detour start/complete,
  parent resume, gap, park, resume, and journey completion.
- **Stages 7/8** — `structure.py` (AST extractor + `reconcile_range`) and `semantics.py`
  (`SemanticGraphService`: node/edge schema, restricted relationship vocabulary per
  provenance, agent-claims-need-evidence, source-anchor validation, parser-structure
  ingestion with unit range reconciliation).
- **Stages 9/10/12** — `journey_reader.py` (`JourneyReader` live snapshot + revision
  gating + learner-facing axis wording), `journey_archive.py` (`JourneyArchiveService`
  episodes + composite finalize with atomic staging swap; `ArchiveReader` returns the
  same snapshot shape for archived journeys and still reads legacy per-unit manifests),
  `transport.py` (`PollingProjectionFeed`). End-to-end test drives map→graph→question→
  graded-answer→owned→finalize and reads the journey back identically from the archive.
- **Stage 13 (UI)** — intentionally not built; this was a backend-only build.

## Integration/wiring layer (post-review, additive only — no logic changed)

Turned the "built but not auto-wired" gaps green. Engine and orchestrator decision
logic untouched; every hook is additive and inert unless its optional dependency is
injected. **61 tests passing.**

- **Idempotency (row 6)** — `submit_answer` now guards on `turn_id`: an already-EVALUATED
  turn returns the stored `RouteDecision` (reconstructed from the enriched
  `answer_evaluated` fact) without re-routing; a recovery replay reuses the existing
  `AWAITING_EVALUATION` answer instead of inserting a duplicate. Partial unique index
  `idx_unique_learner_answer_per_turn` is the DB backstop. Test: `test_replayed_grade_turn_is_idempotent`.
- **Auto semantic graph (row 4)** — `TurnOrchestrator.attach_unit_structure` runs the
  parser extractor for a newly pointed unit, outside any route transaction, idempotent,
  `.py`-guarded. Called after map-commit and after a child dive. Inert unless a
  `SemanticGraphService` is injected. Test: `test_full_runnable_session_maps_grades_and_auto_attaches_graph`.
- **Archive integration (row 5)** — `park` checkpoints a `parked` episode; `finish_root`
  checkpoints an `owned` episode and finalizes the composite journey — both post-commit
  (filesystem writes can't join the SQLite txn). `next_episode_number` derives the index
  from written episodes. Inert unless a `JourneyArchiveService` is injected. Test:
  `test_finish_root_finalizes_archive_via_wiring`.
- **Runnable session (row 3)** — `session.py` `SessionRunner`: builds each scoped wakeup,
  invokes the agent through one seam `(wakeup, instruction) -> list[str]`, forwards text
  to the orchestrator. `agent_run_from_adapter` wraps `ClaudeAgentAdapter.run` for
  production; tests pass a deterministic fake, so it runs end-to-end without the SDK. It
  adds no learning logic — no verdict, route, or step choice.
</content>
</invoke>
