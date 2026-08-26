# TO CURE — the outer request loop is unread/unverified

Date noted: 2026-08-26

## What is confirmed (tutor_v2)
Two-loop architecture, cleanly separated:

- **Decision loop — `routing.py::Router.route_grade`**: pure deterministic state
  machine. Never reads learner prose. Input = validated `return.grade` stamp +
  DB state. Output = `RouteDecision(next_step, unit_id, axis, ...)`.
- **Drive loop — `driver.py::TurnDriver.advance`**: dispatches ONLY on
  `decision.next_step`. Runs every non-learner step (teach, distill, finish,
  point-next) forward and STOPS at the first `wakeup.probe`/`wakeup.test`.
  Terminal states: `awaiting_learner` | `parked` | `done`. `_MAX_HOPS=256` is a
  defensive anti-spin guard only.
- Layers: `app.py` (HTTP) → `api.py::ApiHandlers` → `TurnDriver` →
  `SessionRunner` → `TurnOrchestrator` (atomic DB boundary) → `Router`.

Key mechanics already traced:
- SHAKY x2 on one axis → MISSING → forces a child dive (`_effective_verdict`).
- Subhole stack: parent's exact question saved as `resume_q` BEFORE dive,
  replayed verbatim on return (`resume_after_child`). Agent never regenerates it.
- Park/resume serializes the whole live stack into one `handoff` row — never in
  two homes at once.
- Atomicity: learner answer durable (`AWAITING_EVALUATION`) before Judge runs;
  only a valid grade commits the route. Replayed grade returns original decision
  (`_replay_decision`) — never routes twice.

## The GAP to cure
`api.py::ApiHandlers` was NOT read. That is where the actual request→advance→poll
cycle lives (`app.py` is only HTTP translation). If "the loop we need" means the
outer per-request cycle (answer POST → run_grade → advance → poll for revision),
that file must be read and verified. Do this before building anything that
depends on the outer loop's semantics.

Next action: read `agentic_tutor/tutor_v2/api.py`, trace `answer()` and `poll()`,
confirm how `TurnDriver.advance` is invoked and how projection_revision polling
terminates a turn.
