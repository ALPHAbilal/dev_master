# Agentic Tutor

An AI code tutor. A learner imports a codebase, an agent (**MAPPER**) scans it into a ladder of
units, and the learner is taught + graded unit-by-unit, with off-record **side questions** and
**highlight references** alongside the graded conversation.

```
agentic_tutor/
├── backend/     # Python engine (tutor_v2) + FastAPI HTTP surface. Runs on a PERSISTENT host.
│   └── tutor_v2/     ...engine, api.py, app.py, auth.py, streaming.py, Dockerfile-target
├── frontend/    # Next.js + React + TypeScript. Deploys to Vercel.
└── docs/        # design + spec docs
```

The frontend and backend are decoupled by a stable HTTP contract (`frontend/lib/api/types.ts`).
The backend is **stateful** (SQLite + workspace files + long agent turns) so it does **not** run
on Vercel — deploy it to a persistent host with a volume.

## Deploy (recommended order)

### 1. Backend → a persistent host (Railway / Fly / Render)
- Build from `backend/` using `backend/Dockerfile` (entrypoint: `python -m tutor_v2`).
- Mount a **persistent volume** and point state + codebases at it.
- Env:

  | var | value | notes |
  |---|---|---|
  | `STATE_ROOT` | `/data` | volume path — SQLite + workspace/archive/aside files |
  | `CODEBASE_ROOT` | `/codebases` | volume path — imported repos must live under here |
  | `AUTH_MODE` | `dev` → later `supabase` | `dev` trusts `X-User-Id` (fine for first smoke test) |
  | `ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` | CORS |
  | `HOST` / `PORT` | `0.0.0.0` / `8000` | |
  | `SUPABASE_JWT_SECRET` **or** `SUPABASE_JWKS_URL` | from Supabase | only when `AUTH_MODE=supabase` |
  | `SUPABASE_URL`, `SUPABASE_JWT_AUDIENCE` | from Supabase | optional issuer/audience |
  | `TUTOR_MODEL` | e.g. `claude-…` | model for agent turns (needs Claude Agent SDK creds) |

### 2. Frontend → Vercel
- New Vercel project, **Root Directory = `frontend`**.
- Env:

  | var | value |
  |---|---|
  | `NEXT_PUBLIC_TRANSPORT` | `live` (or `stub` to run standalone) |
  | `NEXT_PUBLIC_API_BASE` | `https://<your-backend-host>` |
  | `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | from Supabase (blank = stub user) |

### 3. Add Supabase auth (after it's talking)
Create a Supabase project → set the frontend `NEXT_PUBLIC_SUPABASE_*` and the backend
`SUPABASE_JWT_SECRET`/`SUPABASE_JWKS_URL`, then flip backend `AUTH_MODE=supabase`.

## Known gap
"Import a codebase" currently registers a **directory that already exists on the backend host**
(`POST /codebases {name, source}`, jailed to `CODEBASE_ROOT`). There is no browser upload yet — for
a first hosted demo, place a repo under `CODEBASE_ROOT` and register it. Browser upload is future work.

## Local development
```bash
# backend (needs a venv with the server deps)
cd backend && python -m venv .venv && .venv/bin/pip install -r tutor_v2/requirements-server.txt
AUTH_MODE=dev STATE_ROOT=./state CODEBASE_ROOT=./codebases .venv/bin/python -m tutor_v2
# backend tests:  .venv/bin/python -m pytest tests_v2 -q

# frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```
