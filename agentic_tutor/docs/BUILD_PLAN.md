# tutor_v2 — Completion Plan (review before any code)

Status: PROPOSAL. Nothing in this file is implemented yet. It exists so we agree on
*what* changes, *why*, and *what must not move* before touching the engine.

## Guiding rule for every change here

**Additive only. The engine's authoritative state (units, axes, stack, meta) and the
Router's decisions are not touched.** Every item below either (a) adds a new method that
composes existing services, or (b) adds a new file. No existing method's signature or
behaviour changes. If a change would alter routing logic, it is out of scope.

Baseline to protect: the current `tests_v2/` suite must stay green after every step.
**Test runner (DECIDED — O1): a dedicated venv with `pytest`.** Create it once
(`python3 -m venv .venv && .venv/bin/pip install pytest`), run with
`.venv/bin/python -m pytest tests_v2/ -q`. The `.venv` lives under `agentic_tutor/` and is
git-ignored. `run_v2_tests.py` stays as the zero-dep smoke runner but pytest is the source
of truth.

---

## Where the backend actually stands (verified by reading the code)

DONE and coherent — do not rebuild:
- Engine: `Router` (map → ladder, grade → route, child dives, sibling queue, park/restore).
- Read side: `JourneyReader` + `PollingProjectionFeed` (revision-gated polling).
- Structural map: `StructureExtractor` + `SemanticGraphService.ingest_structure` (auto-wired
  in `TurnOrchestrator.attach_unit_structure`).
- SDK seam: `ClaudeAgentAdapter` + `TutorToolGateway` (closed, read-only capabilities).
- All contracts (`return.map/grade/distill`, archive manifest) and per-unit
  `ArchiveService.seal()`.

MISSING — the four gaps this plan closes:
1. The DISTILL turn has no execution path (Router emits `wakeup.distill`, nothing runs it).
2. No turn driver: each `run_*` is one step; nothing advances the loop to the next
   learner-blocking point.
3. No API surface / composition root: everything is in-process; nothing to point a UI at.
4. The rich (conceptual) map has a full schema but no producer — only the code skeleton
   is ever written. **It must become LIVE**: updated every turn so the center map is a
   real-time picture of what the tutor is doing, not a snapshot written once at the end.

---

## The evidence that #1 is real (and why it is safe to add)

- `Router.route_grade` returns `RouteDecision("wakeup.distill", …)` in two places:
  all-axes-solid (`_advance_after_solid_locked`, unit → `OWNED`) and fatigue-switch
  (unit → `PARKED`).
- `parsing.py` maps `wakeup.distill → return.distill`; `contracts._validate_distill`
  fully validates it; `ArchiveService.seal()` validates + writes the per-unit artifact.
- **Nobody calls any of it.** `TurnOrchestrator` only ever parses `return.map` and
  `return.grade`. `SessionRunner` has no `run_distill`. `ArchiveService.seal()` has zero
  callers.
- Today `finish_root`/`finish_child` work *without* distill because the unit is already
  `OWNED` from `route_grade`. So distill is currently *skipped*; the per-unit proof artifact
  and the learner-model update it is supposed to produce simply never happen
  (`test_session.py::test_finish_root_finalizes_archive_via_wiring` goes grade → finish_root
  directly). Adding distill inserts the missing seal step **between** grade and finish; it
  does not change the finish path.

---

## STEP 1 — The DISTILL turn (close a unit, seal its proof)

Goal: after a unit becomes `OWNED` (or is `PARKED` by fatigue-switch), run the DISTILLER,
validate its `return.distill`, seal the per-unit artifact, and apply the learner-model diff —
then hand off to the existing `finish_*`/`park` as today.

### 1a. `TurnOrchestrator.commit_distill(distill_blocks, *, unit_id)` — new method
Why: mirror the existing `commit_map`/`submit_answer` shape (parse outside the txn, commit
inside one boundary). It is the missing bridge `return.distill → ArchiveService.seal()`.

What it does, in order:
1. `parser.parse(distill_blocks, expected_kind="return.distill")` (outside any txn).
2. Resolve `journey_id` via `journeys.journey_for_unit(unit_id)`.
3. Guard: the unit must be `OWNED` or `PARKED` (matches Router's two distill exits). If
   neither, raise `InvariantError` — never seal a unit the Router did not finish.
4. Call `ArchiveService.seal(unit_id=…, unit_slug=…, title=…, final_verdict=…,
   axes_tested=…, tests=…, evidence=…, resume_at=…)` using values from the validated stamp.
5. Record a `unit_distilled` journey event (typed lifecycle fact) + `bump_revision`.
6. Return a `TurnResult`.

Safety:
- `ArchiveService.seal()` is already crash-idempotent (re-seal reuses the existing manifest's
  captured event ids). Re-running distill is safe.
- `commit_distill` is **wired only when an `ArchiveService` is provided** (constructor-optional,
  same pattern as `graph`/`archive` today). When omitted, behaviour is byte-for-byte the
  current version → existing tests unaffected.

### 1b. Learner-model diff application
Why: `return.distill.learner_diff` (can / cant / misconceptions) is the ONLY thing the spec
says survives across codebases (`WALKTHROUGH.md` §"what we know about bilal"). Today nothing
writes it.
- Add a small `LearnerModelService.apply_diff(...)` (new, or a method on an existing service)
  that merges the diff into the `learner` table's `profile_json`. Additive; append-and-dedupe,
  never delete a proven `can`.
- Open question O2: exact merge semantics (append vs. replace). Needs one decision.

### 1c. `SessionRunner.run_distill(*, unit_id)` — new method
Why: symmetry with `run_mapping`/`run_grade` — build the `wakeup.distill` packet, invoke the
DISTILLER through the existing agent seam, forward blocks to `commit_distill`.
- `wakeup.distill` packet already builds (`packets.py:137`), its capability policy and default
  instruction already exist. This method only sequences them.

Files touched: `orchestrator.py` (+1 method), `session.py` (+1 method), possibly a new
`learner_model.py`. No signature changes to existing methods.

Tests: new `test_session.py` case — map → probe → grade(SOLID) → `run_distill` →
`finish_root`; assert the per-unit artifact exists under `archive_root/<slug>` and the
learner profile gained the diff. Existing finish-root test stays untouched and green.

---

## STEP 2 — The turn driver (advance the loop to the next learner input)

Goal: turn the 8 separate `run_*` calls into one running tutor. A caller (API or test)
hands the driver a `RouteDecision`; the driver runs every non-learner step (teach, distill,
finish, point-next) until it reaches a `wakeup.probe`/`wakeup.test` that needs the learner,
then stops and reports the pending turn.

### 2a. `TurnDriver.advance(decision) -> DriverState` — new file `driver.py`
Why: the Router already says *what* comes next (`RouteDecision.next_step`); nothing consumes
it. Without this, the frontend would have to re-implement the state machine (e.g. know that
`working-code-wrong-reasoning` means "probe MECHANISM next"). That logic must stay server-side.

Behaviour (a deterministic loop over existing `SessionRunner` calls):
- `wakeup.teach` → `run_teaching`, then continue with the follow-up probe.
- `wakeup.probe` / `wakeup.test` → **stop**; return `AwaitingLearner{turn_id, unit_id, axis,
  question}`.
- `wakeup.distill` → `run_distill`, then `finish_child`/`finish_root` (child vs root by
  `parent_id`), then continue with whatever `finish_*` returns.
- `next_step is None` → journey/ladder complete → return `Done`.

Hard constraints:
- The driver **chooses no verdict, no route, no axis** — it only dispatches on
  `decision.next_step`. All intelligence stays in Router/JUDGE.
- A hop/step ceiling to prevent any infinite loop (defensive; the Router already terminates,
  but the driver must not be able to spin).
- `turn_id` generation: the driver mints turn ids deterministically (open question O3 — who
  owns `turn_id`: driver or caller?).

Files touched: new `driver.py` only. `__init__.py` export. Nothing existing changes.

Tests: new `test_driver.py` — scripted agent drives a full unit map→…→owned→distilled with
one `advance` per learner answer; assert it stops exactly at each probe and ends `Done`.

---

## STEP 3 — API surface + composition root

Goal: a URL the frontend can hit, and one factory that assembles the whole graph of services.

### 3a. `factory.py` — `build_session(config) -> AppContext` — new file
Why: today every component is hand-wired in tests' `_setup()`. There is no single assembly
point. The factory constructs Database, WorkspaceService, Router, WakeupBuilder, recorders,
SemanticGraphService, ArchiveService, JourneyArchiveService, TurnOrchestrator, SessionRunner,
TurnDriver, JourneyReader, PollingProjectionFeed and returns them bundled.
- Pure wiring, no logic. Mirrors what `test_session.py::_setup` already does by hand.

### 3b. `app.py` — FastAPI layer — new file
Why: `PollingProjectionFeed.poll()` and `SessionRunner`/`TurnDriver` are in-process method
calls; the React client on Vercel needs HTTP/SSE endpoints. FastAPI (see Deployment Topology):
async to match the SDK, CORS for the Vercel origin, OpenAPI for typed clients, SSE to later
replace polling with push. Runs on a persistent host, never a Vercel function.

Endpoints (each wraps an existing method; no new logic):
| Method | Endpoint | Wraps |
|---|---|---|
| POST | `/session/map` | `SessionRunner.run_mapping` → `TurnDriver.advance` |
| GET | `/journey/{id}?since={rev}` | `PollingProjectionFeed.poll` |
| POST | `/journey/{id}/answer` | `SessionRunner.run_grade` → `TurnDriver.advance` |
| POST | `/journey/{id}/park` | `SessionRunner.park` |
| POST | `/session/resume` | `SessionRunner.resume` → `TurnDriver.advance` |
| POST | `/workspace` | `WorkspaceService.write` (learner edits) |

Contract detail the UI needs: every write endpoint returns the `DriverState`
(`AwaitingLearner` or `Done`) **plus** the new `projection_revision`, so the client knows
what to render and what to poll from. The read model itself is unchanged.

Files touched: new `factory.py`, `app.py`. Existing modules unchanged.

Tests: `test_app.py` driving the endpoints in-process against a scripted agent (no network).

---

## STEP 4 — The LIVE rich map (real-time observability) — DECIDED: live, not deferred

Goal: the center map is a **live, up-to-date picture of what the tutor is doing right now**.
Every turn that produces meaning (a grade, a taught axis, a child dive, a distill) also emits
the matching agent-provenance nodes/edges **in the same atomic boundary as the state
transition**, and bumps the projection revision — so the moment the UI polls, the new node is
there. The map is never written "once at the end"; it grows tick by tick alongside the loop.

Why live (your call): the map is the observability surface. If it only fills in at distill,
the learner can't watch reasoning form, can't click a just-formed node to see the turn that
made it, and the "loop = tick" view has nothing to animate. Live means: node/edge writes are
part of each turn's commit, carry `evidence_refs` to the exact message/probe that caused them,
and ride the same `projection_revision` the transport already gates on.

Why it's currently empty: `SemanticGraphService.add_node(provenance="agent")` /
`add_edge(semantic relationship)` exist and are validated, but **no caller ever invokes them**.
Only `ingest_structure` runs (parser + system provenance).

### 4a. A per-turn graph translator — new `graph_projection.py`
A deterministic translator that takes an already-validated agent stamp + the ids just written
this turn, and emits agent-provenance graph entries. It authors nothing itself — it only
mirrors validated agent output into nodes/edges. Called from inside each turn's existing
transaction (additive, like the recorders):

| Turn (existing commit) | What the translator emits, live | evidence_refs |
|---|---|---|
| `submit_answer` (grade) | on `misconception`/`working-code-wrong-reasoning`: a `misconception` node + `disproved_by`/`revealed_gap_in` edge; on child dive: a `prerequisite` node + `detoured_to` edge; on SOLID: `proved_by` edge to the axis concept | the probe id + learner message id from this turn |
| `present_teaching` | a `concept`/`mechanism` node for the taught axis + `requires_understanding` edge | the teaching message ids |
| `commit_distill` (Step 1) | `takeaway`/`test` nodes, `proved_by` edges, `returned_to` on parent resume | the distilled event id |

All writes: `provenance="agent"`, real `evidence_refs` (so the center-map click → highlight
the exact conversation segment works — this is the linkage that was missing), and they
**bump the same projection revision** so `PollingProjectionFeed` ships them on the next poll.

### 4b. DECIDED (O5a) — ATOMIC: map writes share the turn's transaction
The translator runs **inside** each turn's existing `db.transaction()`, alongside the grade.
Grade and map node commit together or roll back together — the map can never disagree with the
tutoring state, no reconcile-on-read needed, no one-tick lag.

This choice is only safe if the translator **cannot throw**. That is the engineering contract
for this module, and it is enforceable because the translator's inputs are already fully
validated and its logic is pure. The discipline:

1. **Total, not partial.** The translator has an explicit branch for *every* grade `category`
   and every route outcome (the same closed set the Router already switches on). No `else`
   that silently drops; an unmapped category is a build-time impossibility, guarded by an
   exhaustiveness test that iterates `GRADE_CATEGORIES` and asserts each has a branch.
2. **Inputs are pre-validated.** It receives the stamp *after* `validate_return`, plus ids the
   turn just wrote. It reads no raw model text, does no JSON parsing, no filesystem, no network,
   no clock — pure function of already-checked data. Nothing left that can raise.
3. **Only calls the validated writer.** All writes go through `SemanticGraphService.add_node/
   add_edge`, which already enforce the node/edge/relationship vocabulary and evidence rules.
   The translator can't construct an invalid node — the service rejects it before this plan,
   and we treat any such rejection as a bug caught in tests, not at runtime.
4. **Idempotent under replay.** The existing `submit_answer` idempotency path (replayed graded
   turn returns early) must also skip re-emission. Additionally key agent nodes by
   `(journey_id, turn_id, kind)` with a uniqueness guard so a double-call is a no-op, never a
   duplicate and never an error.
5. **No judgment, no routing.** It mirrors validated agent output into graph rows; it chooses
   no verdict, category, or route. It is a projection, not a decision-maker.
6. **Proven by tests before it ships.** Property-style coverage: for every category, feed a
   representative stamp and assert the exact nodes/edges + `evidence_refs`; a fuzz test throws
   many valid stamps at it and asserts it never raises and never leaves a partial write.

Net: because the input is validated, the branch set is closed and exhaustively tested, and the
only writer is the schema-enforcing service, there is no runtime path that raises — so atomic
(A) gives us the stronger consistency guarantee without the failure mode that made A risky.

### 4c. Projection already carries it — no read-model change
`JourneyReader.read` already returns `semantic_nodes` + `semantic_edges` for the journey and a
monotonic `projection_revision`. Live emission needs no reader change; the nodes simply appear
in the next snapshot. The UI toggle (conversation ⇄ map) and click→highlight are then fully
backed.

### 4d. (Small) `imports`/`calls` structural edges
- `StructureExtractor` currently emits only `contains`. The vocabulary already allows
  `imports`/`calls`. Add them so the structural layer shows call wiring, not just nesting.

Files touched: new `graph_projection.py`; `orchestrator.py` (call the translator from the
existing commits — additive, gated behind the optional `graph` service already there);
`structure.py` (4d only). No Router, contract, or reader changes.

Tests: `test_graph_projection.py` — after a scripted grade with `misconception`, assert an
agent `misconception` node exists with `evidence_refs` pointing at that turn's probe id, and
that `projection_revision` advanced; replay the turn and assert no duplicate node.

---

## Order, and why this order

1. **STEP 1** first — smallest, unblocks the loop, everything else assumes a unit can close.
2. **STEP 4a/4b (live map on grade + teach)** — bring this forward. Because the map is now
   the observability surface, wire the per-turn translator into `submit_answer`/
   `present_teaching` right after Step 1, so every following step is testable *with* the live
   map, not retrofitted onto it. (The distill-side emission in 4a rides on Step 1.)
3. **STEP 2** — driver dispatches on `wakeup.distill`; needs `run_distill` from Step 1.
4. **STEP 3** — API; needs the driver to expose. The write endpoints already return the new
   `projection_revision`, so the live map is visible to the UI from the first endpoint call.
5. **STEP 4d** (`imports`/`calls` edges) — small polish, last.

Steps 1–3 = "make it run + frontend-ready." Step 4 (live map) is woven through 1–3, not
bolted on after, because real-time observability was made a hard requirement.

---

## Open questions to resolve before coding (need your call)

- **O1. DECIDED** — use a `.venv` with pytest (see "Test runner" above).
- **O5. DECIDED** — the rich map is LIVE: agent-provenance nodes/edges emitted every turn,
  carrying `evidence_refs`, riding the projection revision (Step 4 rewritten accordingly).
- **O5a. DECIDED** — ATOMIC (Option A): map writes share the turn's transaction. Safety is
  guaranteed by making the translator unable to throw (total over categories, pre-validated
  inputs, pure, validated-writer-only, idempotent, exhaustively tested — see Step 4b).
- **O2. DECIDED** — state-machine merge: proven skills move `cant → can`; misconceptions
  marked `disproved` but kept for history; a proven `can` is never removed in v1. Lists always
  reflect the present; history is never lost.
- **O3. DECIDED** — the driver mints `turn_id` when it presents a question and returns it in
  `AwaitingLearner`; the React client echoes it back on answer. Single source of identity; the
  existing `submit_answer` replay guard already keys on it.
- **O4. DECIDED** — FastAPI on a persistent host; see "Deployment Topology". Not stdlib
  `http.server`, not Vercel serverless.
- **State store. DECIDED** — v1 keeps SQLite + mounted volume (no data-layer rewrite);
  Postgres/Supabase port is a future item, out of scope for this plan.

All open questions are now resolved. The plan is ready to execute.

## Deployment Topology (React on Vercel + Python engine)

Hard fact that drives Step 3: `tutor_v2` is **stateful and local** — SQLite on disk, a
filesystem workspace with revision checkpoints (`workspace_root`), an archive tree
(`archive_root`), and it spawns the Claude Agent SDK for long LLM turns. Vercel serverless
functions are ephemeral, have no durable local disk, and time out well before long agent
turns. **The engine cannot run inside Vercel functions.**

Chosen shape (provisional, matches O3/O4 above):

```
   ┌─────────────────────────┐         HTTPS / SSE          ┌────────────────────────────┐
   │  Vercel                 │ ──────────────────────────► │  Persistent host           │
   │  React / Next.js UI     │   GET  /journey/{id}        │  (Fly.io / Railway / Render)│
   │  - editor + highlight   │   POST /answer, /map, /park │                             │
   │  - center map (live)    │ ◄────────────────────────── │  FastAPI  +  tutor_v2       │
   │  - conversation toggle  │   AwaitingLearner | Done    │  +  SQLite + mounted volume │
   └─────────────────────────┘   + projection_revision     │  +  Claude Agent SDK        │
                                                            └────────────────────────────┘
```

- **Frontend:** React/Next on Vercel — fine, it's just a client.
- **Backend:** FastAPI (ASGI) on a persistent process. Async matches the async SDK; gives CORS
  for the Vercel origin, OpenAPI types the React client can generate from, and SSE/WebSocket to
  replace polling with push (the transport was designed for this swap — `transport.py` docstring
  says SSE/WebSocket can replace polling "without changing the UI contract").
- **State (v1):** keep SQLite + the filesystem workspace/archive exactly as written, on **one
  instance with a persistent volume**. Zero data-layer rewrite. Single-instance cap — acceptable
  for one / a few learners. If multi-instance or serverless-DB is later required, port `db.py` +
  `schema.sql` to Postgres (Supabase is already wired) and move workspace/archive artifacts to
  object storage — tracked as a future item, **not** in this plan.
- **CORS + auth:** FastAPI restricts origins to the Vercel deployment; a simple bearer/session
  token gates the write endpoints (learner identity already exists as `learner_id`). Detail for
  Step 3, not a blocker now.

Consequence for Step 3: the API layer targets FastAPI from the start (not stdlib
`http.server`), and every write endpoint returns `DriverState + projection_revision` so the
React client knows what to render and what revision to poll/subscribe from.

## Risk summary

- Highest-risk touch is `orchestrator.py` (Step 1a) because it sits on the atomic boundary.
  Mitigation: new method only, gated behind an optional `ArchiveService`, existing methods
  untouched, existing tests must stay green.
- Router, contracts, read model, SDK seam: **not modified at all** in Steps 1–3.
- Step 4 is the only step that changes what agents must output; it is deferrable and isolated.
