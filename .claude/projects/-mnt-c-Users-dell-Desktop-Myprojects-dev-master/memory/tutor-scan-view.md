---
name: tutor-scan-view
description: The import + live-scan UI for tutor_v2, and the backend changes it requires
metadata:
  type: project
---

Building a new first page for the tutor_v2 frontend: import a codebase → watch the MAPPER
agent generate learning units live → browse units. Prototype lives at
`agentic_tutor/frontend_sample/scan_view.html` (self-contained HTML, mock data, CSS-only
"shader" vibration on generating cards — matches tutor.html design tokens). Built 2026-08-28.

Locked product decisions:
- Unified left sidebar: codebases (each = one session) → expand → units. Replaces tutor.html's
  separate left tree.
- Multiple codebases, each its OWN session (own codebase_root/meta/units/journeys).
- 10 units per MAPPER batch; reaching scroll index (batchEnd-2) auto-prefetches next batch in
  background; manual "Generate next 10" button as fallback. Gate on objective_covered==false.
- ALL generated units appear; unreachable ones are visible but LOCKED (read-only, no message
  send). Next unlocks only when current unit is OWNED. Reachability is derived FE-side from
  `order` + unit.state (first non-OWNED = current/reachable; everything after = locked).

Backend deltas this forces (tutor_v2 is single-codebase, synchronous MAPPER today):
- B1 batch-size param into wakeup.map context (MAPPER decides count today).
- B2 split POST /session/map so it returns after commit_map (units visible) instead of
  advancing to first probe.
- B3 SSE endpoint streaming MAPPER tool calls live (only real "agent working" signal;
  captured post-commit today). Optional v1 → choreographed fallback.
- B4 codebase registry (list/switch sessions) — codebase_root is fixed in TutorConfig now.
- B5 extend endpoint honoring mode:"extend"+continues_after.

See [[tutor-v2-architecture]] for the backend map.
