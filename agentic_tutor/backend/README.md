# Tutor HTTP server

Run on a persistent host with a writable disk. The HTTP surface resolves every request
through `ControlPlane`; the engine and `ApiHandlers` are unchanged.

## Local run

From `agentic_tutor/backend`, using Python 3.12+:

```sh
python -m pip install -r tutor_v2/requirements-server.txt
export AUTH_MODE=dev
export STATE_ROOT="$PWD/state"
export CODEBASE_ROOT=/absolute/path/to/repos
export ALLOWED_ORIGINS=http://localhost:3000
export ANTHROPIC_API_KEY='your-key'
python -m tutor_v2
```

Dev mode bypasses user authentication only; tutoring still uses the existing Claude
Agent SDK and needs model credentials. No fake answers are installed in the server.
Tests inject a deterministic agent and do not require model credentials.

| Environment | Purpose |
| --- | --- |
| `AUTH_MODE` | `supabase` (default; fails closed without keys) or explicit `dev` |
| `SUPABASE_URL` | Project URL; derives JWT issuer and JWKS endpoint |
| `SUPABASE_JWT_SECRET` | Legacy HS256 signing secret; server only |
| `SUPABASE_JWKS_URL` | Optional explicit JWKS URL for RS256/ES256 signing keys |
| `SUPABASE_JWT_ISSUER` | Optional explicit issuer; otherwise derived from project URL |
| `SUPABASE_JWT_AUDIENCE` | Defaults to `authenticated` |
| `ALLOWED_ORIGINS` | Comma-separated exact origins, including the Vercel deployment origin |
| `STATE_ROOT` | Defaults to `./state`; contains `tutor.sqlite` and `projects/<session>/workspace` and `archive` |
| `CODEBASE_ROOT` | Optional restriction on registered source directories; Docker defaults to `/codebases` |
| `HOST`, `PORT` | Defaults to `0.0.0.0`, `8000`; platforms can supply `PORT` |
| `ANTHROPIC_API_KEY` | Model credentials for the existing SDK adapter |
| `TUTOR_MODEL` | Optional model override; otherwise the existing adapter default |

In Supabase mode, send both `Authorization: Bearer <access-token>` and `X-User-Id`.
Signature, expiry and audience are verified, plus issuer when configured. Token `sub`
must equal the user header. Configure `SUPABASE_URL` for issuer validation. In dev mode,
`X-User-Id` is required and trusted. Never expose dev mode as an authenticated service.

## Frontend contract

Set frontend `TRANSPORT=live` and `NEXT_PUBLIC_API_BASE` to this server's HTTPS origin;
configure the frontend Supabase public variables for authenticated use. Rebuild after
changing frontend environment variables.

Session, workspace and journey requests, including SSE, require **`X-Codebase-Id`**.
The frontend must retain the selected codebase ID after `open` and attach it to its
shared HTTP/SSE header helper. The current `frontend/lib/api/live.ts` does not yet send
this header. It must also call `/session` with the target/document metadata before its
first `/session/map`. These frontend changes are outside this backend-only task's hard
file boundary; pointing its base URL here alone does not complete that wiring.

`source` is an existing directory on the backend host, not a URL or a browser folder.
Mount/import repositories onto that host first. No clone, upload or file-read API is
introduced here.

SSE emits `revision {revision}` and recorded `tool {turn_id,capability,agent,step}`
for journeys; scans emit `thinking {text}`, committed `unit {slug,file,lo,hi}`, then
`done {journey_id}`. Open the scan stream before starting the map request. A late
subscriber can replay the latest scan; reconnects accept `Last-Event-ID`. Close the
scan subscription on `done`. Failed scans send a final `thinking` message and close;
the map POST carries the HTTP error. Revision streams send an initial revision and
poll for changes. Disconnects cancel stream polling; an in-flight engine write finishes
under its session lock. Model-token events are intentionally deferred to Phase 2;
`streaming.py` is the transport seam for future support.

## Curl walkthrough

Requires Bash, curl and jq. Set `SOURCE` to a host directory containing `run.py`; adjust
the session target/language for your codebase. Model output determines the question,
axis and subsequent status.

```sh
BASE=http://localhost:8000
SOURCE=/absolute/path/to/repos/example
AUTH=(-H 'X-User-Id: local-learner')
CID=$(curl -fsS "${AUTH[@]}" -H 'Content-Type: application/json' "$BASE/codebases" \
  -d "$(jq -n --arg source "$SOURCE" '{name:"Example",source:$source}')" | jq -r .codebase_id)
curl -fsS "${AUTH[@]}" "$BASE/codebases"
curl -fsS -X POST "${AUTH[@]}" "$BASE/codebases/$CID/open"
H=("${AUTH[@]}" -H "X-Codebase-Id: $CID")
curl -fsS "${H[@]}" -H 'Content-Type: application/json' "$BASE/session" \
  -d '{"target":"run.py","document_id":"learner-main","display_name":"solution.py","language":"python"}'
curl -fsSN "${H[@]}" "$BASE/session/map/stream" &
SCAN_PID=$!
MAPPED=$(curl -fsS -X POST "${H[@]}" "$BASE/session/map")
wait "$SCAN_PID"
JID=$(jq -r .journey_id <<< "$MAPPED")
UNIT=$(jq -r .unit_id <<< "$MAPPED")
curl -fsS "${H[@]}" "$BASE/journey/$JID"
curl -fsS "${H[@]}" -H 'Content-Type: application/json' "$BASE/journey/$JID/answer" \
  -d "$(jq '{turn_id,unit_id,axis,question,answer:"It reads the file and returns its contents."}' <<< "$MAPPED")"
curl -fsS "${H[@]}" -H 'Content-Type: application/json' "$BASE/journey/$JID/aside" \
  -d "$(jq -n --arg rid "$(python -c 'import uuid; print(uuid.uuid4())')" --argjson unit "$UNIT" \
    '{request_id:$rid,unit_id:$unit,question:"What does path refer to?"}')"
```

## Deployment and tests

Build from this backend directory: `docker build -t tutor-backend .`. Mount a persistent
volume at `/data` and repositories at `/codebases` (read-only is sufficient for source).
Set auth/model secrets using the host's secret settings. Configure Railway/Fly/Render
to run one instance with one Uvicorn worker. Session locks, scan replay and driver
contexts live in that process; multiple replicas/workers are not supported. SQLite
and workspace/archive files must survive restarts together. Disable proxy buffering
for SSE and allow long-running POST requests for model turns.

```sh
python -m pip install pytest httpx
../.venv/bin/python -m pytest tests_v2 -q
```

`tests_v2/test_http_surface.py` exercises import/list/open/init/map/answer/aside over
HTTP, tenant ownership, JWT failures and real TCP SSE with the actual engine and a
deterministic agent. External model inference and a hosted deployment need their own
credentials and infrastructure.
