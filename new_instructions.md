# TASK — Make the tutor_v2 backend serve the frontend contract (multi-tenant + auth + SSE)

You are extending an existing Python backend so a Next.js frontend (already built to a fixed
contract) can connect to it live. Do NOT change the engine internals, the aside layer, or any
"stone" logic — this is purely the HTTP/transport surface. You have full repo read access; read
the sources before writing. Keep all existing tests green and add tests for new surface.

## Read first
- `agentic_tutor/backend/tutor_v2/app.py` — current FastAPI surface (single-tenant, one AppContext).
- `agentic_tutor/backend/tutor_v2/api.py` — framework-neutral `ApiHandlers` (the logic; unchanged).
- `agentic_tutor/backend/tutor_v2/registry.py` — `ControlPlane` / `SessionRegistry` (multi-tenant resolver, already built + tested).
- `agentic_tutor/backend/tutor_v2/factory.py`, `journey_reader.py`, `session.py`.
- `agentic_tutor/frontend/lib/api/types.ts` and `lib/api/live.ts` — the EXACT contract to satisfy
  (endpoints, request/response shapes, headers, SSE event names). This is the source of truth.

## Hard rules
- No changes to engine stones, routing, grading, or the aside/refs logic. Only `app.py`
  (and, if needed, a thin new module for auth + a streaming helper) may change.
- Every existing test in `backend/tests_v2` must still pass; run via `../.venv/bin/python -m pytest tests_v2 -q`.
- The engine runs on a persistent host (NOT Vercel). Provide a runnable server + Dockerfile.

## 1) Make the API multi-tenant, resolved per request
Today `create_app` binds one `AppContext`. Change it to resolve a context per request from
`(user_id, codebase_id)` via `ControlPlane`:
- Add auth: read `Authorization: Bearer <jwt>` + `X-User-Id` header. Provide a verifier behind an
  interface: a **Supabase JWT verifier** (verify against `SUPABASE_JWT_SECRET`/JWKS, extract the
  user id, confirm it equals `X-User-Id`) AND a **dev/no-auth mode** (env-gated) that trusts
  `X-User-Id` so the stack runs before Supabase is configured. Reject mismatches with 401.
- The journey/session routes operate on the caller's resolved `AppContext` (via
  `ControlPlane.open(user_id, codebase_id)`), so `codebase_id` must be resolvable for those routes
  (the frontend holds the active codebase; accept it as a header `X-Codebase-Id` or a path prefix —
  pick one and document it).

## 2) Control-plane routes (new)
- `POST /codebases` `{ name, source }` → `{ codebase_id, name }` — `ControlPlane.create_codebase`.
- `GET /codebases` → `[{ id, name, session_id, unit_count }]` — `ControlPlane.list_codebases`.
- `POST /codebases/{id}/open` → `{ session_id }` — `ControlPlane.open` (returns its session id).
`user_id` always comes from auth, never the body.

## 3) Existing routes — keep, but resolve context per request
`POST /session`, `POST /session/map`, `POST /session/resume`, `GET /journey/{id}`,
`POST /journey/{id}/answer`, `POST /journey/{id}/aside`, `POST /journey/{id}/park`, `POST /workspace`
— same shapes as today / as the frontend contract. They now run against the resolved context.

## 4) Streaming (SSE) — Phase 1: event streams, not token streams
The engine is synchronous/batch, so do NOT attempt token-by-token model streaming now. Implement
Server-Sent Events that give the frontend its live feel:
- `GET /journey/{journey_id}/stream` — emit:
  - `revision` `{ revision }` whenever the journey's `projection_revision` advances (poll the
    reader internally on a short interval and push on change). The client refetches the snapshot.
  - `tool` `{ turn_id, capability, agent, step }` for tool activity recorded on the journey.
- `GET /session/map/stream` — during a scan (`start_map`), emit `thinking` `{ text }` and one
  `unit` `{ slug, file, lo, hi }` per unit as/after the map commits, then `done` `{ journey_id }`.
Match the event names/payloads in `frontend/lib/api/types.ts` (`StreamEvents`, `ScanEvents`)
exactly. Set correct SSE headers; support the client's fetch-hook auth (headers on the SSE request).
Handle disconnects cleanly. (Token-level streaming of replies is an explicit Phase 2 — leave a
clear seam, don't build it.)

## 5) Deployment
- A `main` entrypoint running `uvicorn` (host/port from env), CORS allowing the Vercel origin
  (`ALLOWED_ORIGINS` env).
- A `Dockerfile` (installs `requirements-server.txt`, runs the server) suitable for Railway/Fly/Render.
- A short `README` section: env vars (`SUPABASE_JWT_SECRET`, `AUTH_MODE=supabase|dev`,
  `ALLOWED_ORIGINS`, DB/state paths), how to run locally, how the frontend points at it.

## Deliverables & acceptance
- All existing `tests_v2` pass, plus new tests: control-plane routes, per-request auth resolution
  (401 on mismatch, dev-mode passthrough), and an SSE test that a `revision` event fires after a
  write and `unit`/`done` fire during a scan.
- `curl`-able: import a codebase → list → open → map (stream) → answer → aside, end to end, in
  dev auth mode with a fixed `X-User-Id`.

## Do NOT
- Touch engine stones, grading, routing, or the aside/refs internals.
- Add token-level model streaming (Phase 2).
- Put secrets in code; everything sensitive comes from env.