# Tutor frontend

Next.js App Router + React + TypeScript. `/` is the tutor; `/scan` is the import page. The old HTML prototypes now live in `dev_master/new_completly_desighn/archive/agentic_tutor/frontend/`.

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
| `NEXT_PUBLIC_TRANSPORT` | `stub` (default) or `live`; restart/rebuild after changing |
| `NEXT_PUBLIC_API_BASE` | Separate backend origin, e.g. `http://localhost:8000` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public anonymous/publishable key; never a service-role key |

Without Supabase configuration, `useAuth()` returns a stub identity. With configuration, it observes the Supabase session and refreshes the access token for each HTTP request and SSE reconnection. A configured project with no signed-in session renders the shell and reports that sign-in is required. The auth interface intentionally does not add a login redesign.

Set the Vercel project root to `agentic_tutor/frontend`, use the Next.js preset, and configure the variables above. The backend stays on its own persistent host. No backend handlers or secrets are deployed with this frontend. Dependencies are locked by `package-lock.json`.

`lib/api/types.ts` is the wire contract; `live.ts` and `stub.ts` implement the same interface. Components consume `useTutor()` and do not fetch. The stub is in memory and resets on a full reload. CSS is copied from the demos and scoped per screen to preserve both token systems; `app/sidebar.css` holds what both screens share.

## The contract

`lib/api/types.ts` is the wire contract, described in `new_completly_desighn/FRONTEND.md` §7–§8. It is page 1 of the backend spec: the backend serves exactly these routes.

- One snapshot per workspace, with a revision number. The stream sends `revision` when it changes, plus `tutor` (the reply, piece by piece) and `tool` (what the tutor is reading).
- Two sidebars on the left, following the reference design's layout. The first lists the repositories and their tasks, one short row each. A click on a task folds it into its rail and opens the second: the task's goal, tier, files, the job box, its concepts with their boxes, and its issues: the waiting room, in priority order, where dark is now, pale is on hold and grey is done. A concept's box shows its text only once it is ticked; the server sends `null` until then, and the screen shows a blank bar.
- Brand rule: the screen never numbers things (no task, box, concept or issue numbers); the order of a list says it.
- The answer key, the orchestrator's answers, the stuck level and the tutor's instructions never reach this screen.
- Demo mode (`stub.ts` + `demo.ts`) plays task 3 of the design's scenario from turn 6; each message plays the next turn. The fifth ticks the last box, but an issue still waits, so it is picked up; the sixth clears it, which closes task 3 and opens task 4. Importing any `https://` URL simulates the four preparing steps.

On this Windows machine, Application Control blocks Next's native SWC binary. The scripts use webpack so Next can use its supported WASM fallback without changing system security settings.
