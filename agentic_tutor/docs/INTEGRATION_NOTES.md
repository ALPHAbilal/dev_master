# Frontend ↔ Backend integration log

Running notes on decisions made while building the `tutor.html` demo, so that when
it becomes a real frontend wired to `tutor_v2`, we remember what the UI assumes and
where the **backend must be tweaked to match**. Ordered by how much backend work each implies.

Backend surface referenced: `tutor_v2/app.py` (routes), `api.py` (handlers),
`driver.py` (`DriverState`), `services.py` (`WorkspaceService`).

---

## 1. The Editor is the learner's answer surface — and it is now MULTI-FILE

**UI decision:** the right-panel *Editor* tab holds one or more files the learner
fills in; the AI checks them. Tabs add / close / rename; each file has `{name, content}`.

**Backend today is single-file.** `WorkspaceService` (`services.py`) stores exactly one
document: one `content`, one `workspace_revision`, one `document_id` row in `meta`.
`workspace_write(expected_revision, content)` and `read_workspace` are single-blob.
So `POST /workspace` cannot represent N files.

**Tweak needed (pick one):**
- **(a) File-keyed workspace (preferred).** Make the workspace a map `path -> {content, revision}`.
  `read_workspace` returns a list; `workspace_write` takes `{path, expected_revision, content}`.
  The SDK tool `read_workspace` in `sdk_runtime.py` (TutorToolGateway) then returns all files,
  so the JUDGE/TEACHER agents can see every file — which #4 says they must.
- **(b) Single blob, concatenated.** FE joins files with a delimiter header
  (`# === file: name.py ===`). Zero backend change, but the agent can't address a file cleanly
  and revisions collide. Use only as a stopgap.

**Decision:** go with (a) when wiring for real. Flag the `meta` schema + `_revision_directory`
per-document assumption in `services.py`.

## 2. Submit → which route?

**UI:** the Editor's *Submit* button is currently inert (mock).

**Backend:** two candidate paths —
- `POST /journey/{id}/answer` with `{turn_id, unit_id, axis, question, answer}` — this is the
  graded turn (JUDGE runs). The editor content is the `answer`. **This is the real target** for
  "AI checks my code."
- `POST /workspace` — just persists edits (optimistic concurrency via `expected_revision`),
  no grading.

**Decision:** Submit should (1) `POST /workspace` to save, then (2) `POST /answer` with the code
as `answer`, echoing back the driver-minted `turn_id` from the last `DriverState`. Multi-file (#1)
means `answer` must carry all files — settle the payload shape together with #1.

## 3. Filenames are learner-editable → they must ride in the payload

**UI:** tab names rename inline (double-click). New files default `untitled_N.py`.

**Backend:** any write/answer payload must include the filename per file (see #1a `path`).
`initialize()` currently takes a single `document_id`/`display_name`; a multi-file session needs
per-file identity. Don't assume the FE filename is stable — treat it as data.

## 4. Agents must be able to READ these files (capability surface)

**UI premise (user):** "would AI agent have those available in its places" — yes. The agents only
see what the wakeup packet grants. `read_workspace` is the relevant read-only capability
(`sdk_runtime.py` `TutorToolGateway`, `CapabilityPolicy`). Today it returns ONE document.

**Tweak needed:** once #1a lands, `read_workspace` returns all files so JUDGE can grade code that
spans files and TEACHER can reference siblings. No new capability name needed — just widen the
existing one's return shape. Keep it read-only (writes stay blocked — `_BUILTINS_BLOCKED`).

## 5. Pure-frontend concerns (no backend impact) — recorded for completeness

- **Tab indentation:** Tab inserts 4 spaces (never moves focus to Submit); Shift+Tab dedents;
  Enter preserves indent and adds a step after a line ending in `:`. Selections indent line-by-line.
- **Scrollbar is inside** the editor (textarea owns overflow; gutter synced to its scrollTop).
- **`+` new-file button is pinned** outside the scrolling tab strip, so it never leaves the viewport.
- **Line-number gutter** is derived from content, kept in vertical sync with the textarea.
- Accent left-stripes removed from highlighted code lines (neutral tint instead).

---

### Quick checklist when we wire the real frontend
- [ ] Decide workspace file model (#1a) and migrate `meta`/`WorkspaceService`.
- [ ] Widen `read_workspace` return to all files; keep read-only.
- [ ] Define the multi-file Submit payload (files[] with `{path, content}`); wire to `/workspace` + `/answer`.
- [ ] Carry `turn_id` from `DriverState` back on the answer.
- [ ] Confirm filename is treated as untrusted learner data server-side.
