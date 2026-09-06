# Tutor frontend

Next.js App Router + React + TypeScript. The original HTML files remain untouched. `/` is the tutor; `/scan` is the import and scan screen.

Use Node 22.12+ (Vercel: Node 22.x). From this directory:

```sh
npm ci
npm run dev
npm test
npm run build
npm start
```

Copy `.env.example` to `.env.local`:

| Variable | Value |
| --- | --- |
| `TRANSPORT` | `stub` (default) or `live`; restart/rebuild after changing |
| `NEXT_PUBLIC_API_BASE` | Separate backend origin, e.g. `http://localhost:8000` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public anonymous/publishable key; never a service-role key |

Without Supabase configuration, `useAuth()` returns a stub identity. With configuration, it observes the Supabase session and refreshes the access token for each HTTP request and SSE reconnection. A configured project with no signed-in session renders the shell and reports that sign-in is required. The auth interface intentionally does not add a login redesign.

Set the Vercel project root to `agentic_tutor/frontend`, use the Next.js preset, and configure the variables above. The backend stays on its own persistent host. No backend handlers or secrets are deployed with this frontend. Dependencies are locked by `package-lock.json`.

`lib/api/types.ts` is the wire contract; `live.ts` and `stub.ts` implement the same interface. Components consume `useTutor()` and do not fetch. The stub is in memory and resets on a full reload. CSS is copied from the demos and scoped per screen to preserve both token systems. The extraction script is only a migration aid.

## Backend wiring gaps verified in the repository

- Existing `app.py` does not yet expose `/codebases`, codebase open, or either stream. The client implements the requested target URLs; it does not substitute invented routes. Snapshots also poll every four seconds while SSE is unavailable. The existing server has no authenticated control-plane/session routing; it must verify the Bearer token and select the opened user's session.
- `user_id` is carried as `X-User-Id`, not an extra JSON property: `AsideBody` forbids extra fields. The server must derive identity from the verified token rather than trust this header. Enable CORS for the Vercel origin and these headers.
- Native browser `EventSource` cannot send `Authorization`. The standards-compatible `eventsource` client supplies a fetch hook for Bearer headers and token refresh. Tokens never appear in URLs.
- Current journey, unit, and conversation IDs are integers. Types accept string or number and preserve the received wire type. Code references capture complete lines, including indentation, because `references.py` requires exact file/line equality.
- The API has no source-file read/upload contract. Folder selection reads source locally for the explorer; registration sends only the specified `{name, source}`. A browser cannot give the remote backend access to a local folder. The backend must already resolve the chosen source. Remote-only codebases cannot display unseen source until a file-read/upload contract is supplied.
- Mapping has no unit-count request field. Generate starts one map operation; the stepper controls how many streamed units are revealed at once. Later batches reveal the remaining returned units without rerunning mapping or inventing a count field.
- The existing `/session/resume` restores **parked** sessions only. Codebase open returns only `session_id`, with no journey ID or active DriverState. This browser caches its last live routing state for reloads, but opening an already-active session in a fresh browser still needs a backend contract for returning that state. The client does not remap an existing session to work around this gap.
- `/workspace` has one document and an optimistic revision. Submit initializes that document through `/session`, then writes the returned revision. Editor tabs remain local; the API does not provide a multi-file write or workspace read endpoint.

On this Windows machine, Application Control blocks Next's native SWC binary. The scripts use webpack so Next can use its supported WASM fallback without changing system security settings.
