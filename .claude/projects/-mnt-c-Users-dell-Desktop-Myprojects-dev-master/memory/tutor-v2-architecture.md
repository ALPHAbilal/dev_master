---
name: tutor-v2-architecture
description: How the tutor_v2 backend engine is structured (mapping, routing, snapshot, API)
metadata:
  type: reference
---

`agentic_tutor/tutor_v2/` — backend engine for an AI code tutor. Pure Python, ~4400 lines,
no frontend of its own. Teaches a codebase unit-by-unit across 7 axes (COMPREHEND, MECHANISM,
RATIONALE, JUDGMENT, ROBUSTNESS, INTEGRATION, EVOLUTION).

Layers:
- State: schema.sql (SQLite) + filesystem workspace/archive. Engine truth = units, axes, stack,
  meta, probes. Journey/observability layer = journeys, conversation_messages, journey_events,
  semantic_nodes/edges, tool_calls.
- routing.py Router = the brain (map→ladder, grade→route, child dives, park/restore). Only it
  makes learning decisions.
- orchestrator.py = atomic commits; session.py SessionRunner = one step each; graph_projection.py
  = live semantic-map producer.
- driver.py TurnDriver.advance(decision) = runs non-learner steps until a probe needs a human.
  UI must NOT reimplement it.
- factory.py build_session→AppContext; api.py handlers; app.py FastAPI (POST /session,
  /session/map, GET /journey/{id}?since=, POST /journey/{id}/answer, /park, /session/resume,
  /workspace).

Scan/mapping flow: POST /session/map → run_mapping → MAPPER returns return.map (units:
{slug, title?, file, lo, hi, depth=0, parent=null, axes[]}, all top-level; children only come
later from JUDGE hidden_gap). Router.commit_map inserts units (state NEW), points first unit,
attach_unit_structure runs AST parser (structure.py) → parser-provenance nodes. Then driver
advances to first question. Unit state: NEW→POINTED→PROBED→TAUGHT→TESTED→JUDGED→OWNED/PARKED.

UI contract: every write returns DriverState (status awaiting_learner/parked/done + turn_id,
unit_id, axis, question, projection_revision). GET /journey returns snapshot (units, axes, stack,
semantic_nodes/edges, conversation, tool_calls, lifecycle). journey_reader.py AXIS_WORDING maps
axis names to learner copy.

Existing frontend prototypes: `agentic_tutor/frontend_sample/tutor.html` (3-panel map+conversation
mock, not wired). `agentic_tutor/ui/` is the OLD v1 UI (binds to `tutor` package) — ignore for v2.
See [[tutor-scan-view]] for the new import/scan page.
