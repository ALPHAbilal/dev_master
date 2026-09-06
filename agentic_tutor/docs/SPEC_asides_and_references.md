# Verified backend change specification: asides and highlight references

Verified against the working tree on 2026-09-06. Deliverable: specification only; no engine implementation changes. Paths in citations are relative to `agentic_tutor/`; `:a–b` denotes inclusive source lines. All **proposed** symbols, fields, SQL, and behavior below are new requirements, not claims that they already exist.

## 1. Verification

### Orientation and constraints

The authoritative tables are `units`, `axes`, `stack`, `meta`, and `probes`; journey tables are explicitly additive. Do not change the five tables, their contents' meaning, or routing. SQLite and the persistent-host/FastAPI plus Vercel topology remain. [Evidence: backend/tutor_v2/schema.sql:11–85,114–203; backend/tutor_v2/app.py:1–8.]

The assertion that **all** journey writes live in `recorders.py` is too broad: semantic nodes/edges are written by `SemanticGraphService.add_node`, `add_edge`, and `set_node_status`, composed by the orchestrator. Keep the new aside writes recorder-owned; a lifecycle anchor does not require a semantic node. [Evidence: backend/tutor_v2/semantics.py:50–126; backend/tutor_v2/orchestrator.py:157–164,207–228.]

The orientation documents are not reliable descriptions of current execution: MAP describes M/L and gap stages; BUILD_PLAN still describes missing driver/API/distill code that now exists. Use source as authority. [Evidence: docs/MAP.md:6–45; docs/BUILD_PLAN.md:32–39; backend/tutor_v2/driver.py:63–80; backend/tutor_v2/api.py:41–54; backend/tutor_v2/session.py:134–147.]

### Point 1 — refs_json: incomplete

`conversation_messages` has no reference-list field. Add one with an empty-list default. However `{kind,file,lo,hi,excerpt}` is insufficient: conversation references need a message ID, labels need preserving, and character selections need finer coordinates than inclusive lines. The demo stores `{kind,label,snippet}` only, trims selections, and supplies neither offsets nor conversation message IDs. Its test/editor tabs are client-side sources, not necessarily server files. [Evidence: backend/tutor_v2/schema.sql:131–147; frontend/tutor.html:763–788,1255–1268,1066–1075.]

`WakeupBuilder._source_context` resolves paths and checks root containment, existence, and upper line bound. It does **not** independently validate positive lower bounds or hi >= lo: unit schema constraints supply those guarantees. Do not feed arbitrary refs through it. Reuse the containment algorithm in a separate validator without changing stone packet behavior. It cannot validate unsaved editor text or conversation spans. [Evidence: backend/tutor_v2/packets.py:143–167; backend/tutor_v2/schema.sql:17–18.]

### Point 2 — aside grouping and revision: incomplete

There is no thread grouping today. `ConversationRecorder.record` allocates a journey-global sequence under a transaction, but neither it nor `JourneyRecorder.record_event` increments revision. `bump_revision` is a separate explicit update, not a trigger. New aside transactions must call it. [Evidence: backend/tutor_v2/recorders.py:33–63,199–227,239–250.]

The partial UNIQUE index covers **every learner row** for `(journey_id,turn_id)`, not just answers. `find_learner_answer` likewise filters only role; `set_turn_status` updates every message sharing that turn. Reusing the main turn for an aside would collide or allow an aside question to be mistaken for graded evidence. Preserve the index and use separate, server-derived `aside:<request UUID>` turn IDs; reject these IDs on the graded entry path and require `thread_kind='main'` in graded lookup/status operations. [Evidence: backend/tutor_v2/schema.sql:213–216; backend/tutor_v2/recorders.py:65–85; backend/tutor_v2/orchestrator.py:189–202,227–228.]

Do not describe all recording as one atomic transaction. Grading records a recoverable answer before the route transaction; question recording is separate and may write a stack bookmark; teaching messages precede their lifecycle transaction; tool capture is separately committed. The session actually calls JUDGE **before** `submit_answer`, so the latter's “before the Judge runs” docstring is incorrect for the public path. [Evidence: backend/tutor_v2/orchestrator.py:88–100,124–164,181–228; backend/tutor_v2/session.py:116–130.]

### Point 3 — read-only aside wakeup: incomplete; registry location wrong

`WAKEUP_AGENTS` is defined in `contracts.py`, imported by `packets.py`. Add the step there, a capability entry in `packets.py`, a return validator, a parser mapping, and a session instruction. Merely adding a registry entry fails: the builder currently requires unit AND axis for every non-map step; the parser admits only map/grade/distill. [Evidence: backend/tutor_v2/contracts.py:15–22,94–105; backend/tutor_v2/packets.py:9,17–24,62–87; backend/tutor_v2/parsing.py:17–45; backend/tutor_v2/session.py:37–49,173–183.]

An additional trap: `validate_continuation` uses membership in `WAKEUP_AGENTS` as its next-step allowlist. Adding aside must **not** make it a legal engine continuation. Freeze the existing six continuation steps as a distinct allowlist before extending the agent registry. This preserves, rather than expands, routing semantics. [Evidence: backend/tutor_v2/contracts.py:259–275.]

### Point 4 — API aside path: incomplete

Add `ApiHandlers.aside` plus an HTTP body/route, but delegate invocation to `SessionRunner` and writes to `TurnOrchestrator`; the API should not directly call recorders. Never reuse `answer`, which grades and then advances. `present_question` is unsuitable because it only accepts probe/test and may mutate the stack via `record_resume_question`. [Evidence: backend/tutor_v2/api.py:47–54; backend/tutor_v2/app.py:32–37,85–87; backend/tutor_v2/session.py:89–104; backend/tutor_v2/orchestrator.py:124–145.]

The existing response convention cannot be obtained by calling `driver.advance(decision=None)`: that reports `done`. Nor does the driver retain a current `DriverState`; it stores only a sequence counter. Specify an explicit aside acknowledgment exception to the write-response convention, leaving the client's main DriverState intact. Setup/workspace writes already have distinct response shapes. [Evidence: backend/tutor_v2/driver.py:59–67,132–146; backend/tutor_v2/api.py:31–37,69–73,85–93.]

### Point 5 — grade evidence and projection: partly confirmed

Grade transient fields are closed to `learner_answer`, `question_ref`, `action_evidence`; adding refs currently fails. Extend the complete chain: HTTP body → handler → session validation → packet → recorder. `read_transcript` is actually a view of `current_evidence`, not a DB transcript query; embedding refs there makes them available through the existing tool. [Evidence: backend/tutor_v2/app.py:32–37; backend/tutor_v2/api.py:47–54; backend/tutor_v2/session.py:116–128; backend/tutor_v2/packets.py:131–136; backend/tutor_v2/sdk_runtime.py:88–93.]

SELECT * does expose new message columns, but as raw JSON **strings**, not a decoded `refs` array, and does not project newly added tables. Add explicit thread/turn projection and a decoded refs property. Archive snapshots and conversation JSONL are copied from the live reader; old archives need defaults on read. [Evidence: backend/tutor_v2/journey_reader.py:62–98; backend/tutor_v2/journey_archive.py:105–125,157–167.]

The map demo has a seeded clickable aside linking by `data-id`; newly created asides have no ID and add no map story entry. Selection attaches a chip; an explicit mode switch, not an implemented @ parser, chooses aside mode. The backend must supply stable IDs and the frontend adapter must consume them. [Evidence: frontend/tutor.html:725–752,880–888,910–918,1215–1268.]

## 2. Schema delta

**Proposed version 7.** Add only journey-layer storage. UUIDs below are canonical lowercase text, generated/validated in Python. Timestamps for new tables are application-supplied UTC ISO-8601 strings with a fixed format; JSON is serialized text, validated in Python. This avoids introducing SQL JSON dialects, native UUID dependencies, timestamp functions, or identity syntax for new tables. Existing integer journey/unit/message IDs remain unchanged. [Existing migration seam: backend/tutor_v2/db.py:12–13,37–83; existing JSON storage: backend/tutor_v2/schema.sql:149–203.]

Exact SQL for an existing v6 database (run once; column-existence checks described below):

```sql
CREATE TABLE IF NOT EXISTS aside_threads (
    id TEXT PRIMARY KEY NOT NULL,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    unit_id INTEGER NOT NULL REFERENCES units(id),
    origin_message_id INTEGER REFERENCES conversation_messages(id),
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (journey_id, id)
);

ALTER TABLE conversation_messages ADD COLUMN refs_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE conversation_messages ADD COLUMN thread_kind TEXT NOT NULL DEFAULT 'main'
    CHECK (thread_kind IN ('main', 'aside'));
ALTER TABLE conversation_messages ADD COLUMN thread_id TEXT REFERENCES aside_threads(id);

CREATE TABLE IF NOT EXISTS aside_turns (
    id TEXT PRIMARY KEY NOT NULL,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    thread_id TEXT NOT NULL,
    request_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'COMPLETE')),
    learner_message_id INTEGER NOT NULL REFERENCES conversation_messages(id),
    reply_message_id INTEGER REFERENCES conversation_messages(id),
    anchor_event_id INTEGER REFERENCES journey_events(id),
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (journey_id, thread_id) REFERENCES aside_threads(journey_id, id),
    CHECK ((status = 'PENDING' AND reply_message_id IS NULL AND completed_at IS NULL)
        OR (status = 'COMPLETE' AND reply_message_id IS NOT NULL AND completed_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_aside_threads_journey ON aside_threads(journey_id, id);
CREATE INDEX IF NOT EXISTS idx_messages_thread
    ON conversation_messages(journey_id, thread_id, sequence);
CREATE INDEX IF NOT EXISTS idx_aside_turns_thread
    ON aside_turns(journey_id, thread_id, created_at, id);
```

Keep the existing learner uniqueness index unchanged. Recorders enforce cross-table rules that the additive columns cannot cheaply express: main ⇒ null thread_id; aside ⇒ nonnull thread_id belonging to the same journey/unit, axis null, status RECORDED; all origin/message/event links belong to that journey; only a first thread turn has `anchor_event_id`. Delete by journey, not by individual linked messages/threads. Do not retrofit a table rebuild or triggers solely for these conditions. [Existing sequence/role/status constraints and index: backend/tutor_v2/schema.sql:131–147,213–216; recorder validation: backend/tutor_v2/recorders.py:46–62.]

Fresh schema includes the final columns and tables. **Bootstrap ordering matters:** `_initialize` executes schema.sql before migrations. Place the index on new message columns in migration 7, after conditional ALTERs, rather than in the pre-migration schema script. A narrow column-inspection helper skips ALTERs for fresh DBs. Existing v6 data becomes main with empty refs and null thread. Migration 7 is recorded only after all its statements succeed; retry partial initialization through schema inspection. Never use `executescript` inside the migration's transaction. [Evidence: backend/tutor_v2/db.py:37–54,69–76,106–129.]

### SQLite portability inventory

The new DDL above uses shared SQL forms. The following existing constructs remain or are used by the proposed SQLite integration and must be isolated for a later mechanical port; this is not authorization to change stones now.

| Construct | Current evidence / proposed use | Later PostgreSQL substitution |
|---|---|---|
| sqlite3 connection, sqlite3.Row, OperationalError | backend/tutor_v2/db.py:6,27–28,72–76 | PostgreSQL driver, dict-row adapter, typed errors |
| `?` parameters | backend/tutor_v2/db.py:51–53; new recorder SQL | Driver placeholder adapter, typically `%s` |
| PRAGMA foreign_keys, busy_timeout, journal_mode=WAL | backend/tutor_v2/db.py:31–34; schema.sql:4 | FK enforcement is native; connection/lock timeout configuration; PostgreSQL WAL is server-managed |
| PRAGMA table_info | backend/tutor_v2/db.py:108,118; proposed migration helper | information_schema.columns query |
| sqlite_master inspection | backend/tutor_v2/db.py:85–94 | PostgreSQL catalogs/information_schema; legacy SQLite migration itself need not rerun |
| executescript | backend/tutor_v2/db.py:39,94 | Transactional statement-by-statement migration runner |
| INTEGER PRIMARY KEY rowid allocation; AUTOINCREMENT | backend/tutor_v2/schema.sql:11–12,118–119,131–132,149–150,218–219 | Generated identity columns, matching FK integer width; advance sequences after copied IDs |
| cursor.lastrowid | backend/tutor_v2/recorders.py:63,186,227 | INSERT … RETURNING id; shared insert-ID adapter for new message/event inserts |
| datetime('now'), TEXT timestamp defaults | backend/tutor_v2/schema.sql:8,125–127,145; recorders.py:232–242 | Central timestamp-expression adapter or application ISO timestamps; preserve wire format. New tables already use application timestamps |
| BEGIN IMMEDIATE | backend/tutor_v2/db.py:149–175 | BEGIN plus per-journey SELECT … FOR UPDATE before sequence allocation/check-and-insert; same lock discipline for every journey writer |
| RLock over one SQLite connection | backend/tutor_v2/db.py:29,136–138,152 | Connection transaction scope and database row locks; no process-local-lock correctness assumption |
| duplicate-column text matching | backend/tutor_v2/db.py:69–76 | Metadata inspection or typed SQLSTATE, not English error matching |

SAVEPOINT/RELEASE/ROLLBACK TO, COALESCE, CHECK, FK, CREATE INDEX IF NOT EXISTS and the existing partial UNIQUE index have PostgreSQL counterparts with the same SQL semantics; they are **not SQLite-only**. MAX(sequence)+1 is portable SQL but needs equivalent serialization, so isolate journey locking now. JSON stays TEXT for a mechanical port; JSONB is optional future optimization. [Evidence: backend/tutor_v2/db.py:149–175; backend/tutor_v2/recorders.py:52–62; backend/tutor_v2/schema.sql:215–216.]

## 3. Recorders, contracts, API, packets, projection

### Reference contract and validation — proposed new backend/tutor_v2/references.py

Add `ReferenceValidator(db: Database, config: TutorConfig)` and `validate(self, refs: list[dict[str, Any]], *, journey_id: int) -> list[dict[str, Any]]`. Calls are read-only. Never initialize/write/checkpoint a workspace to validate a pin. Existing `WorkspaceService.read` is read-only, but supports one persisted document; it does not represent the demo's multiple unsaved tabs. [Evidence: backend/tutor_v2/services.py:127–156; frontend/tutor.html:1066–1075.]

**Proposed normalized pin:** required `kind`, `label`, `snippet`, `source`, `start`, `end`. `kind` ∈ code|test|convo; label nonblank ≤256 Unicode code points; snippet nonempty ≤16,384 UTF-8 bytes. `start/end` are zero-based, half-open Unicode code-point offsets into a precisely identified source string, with 0 ≤ start < end ≤ len(source). Reject booleans as integers, unknown keys, non-list refs and non-object elements. Preserve list order and whitespace; do not trim highlighted text. Allow at most 32 refs and 256 KiB total canonical refs JSON per message. These limits are proposed defaults. [Motivation: frontend/tutor.html:779–788,1255–1268; strict validator conventions: backend/tutor_v2/contracts.py:36–62.]

Closed source variants:

* `code` → `{type:'repository', file:<relative POSIX path>, sha256:<64 lowercase hex>}`. Read UTF-8 with LF newline normalization, validate digest and exact slice == snippet. Reject absolute, drive/UNC, traversal and resolved symlink escapes; require a real file under codebase_root; cap read at 1 MiB. Path checks derive from packets.py:143–167 but validate all untrusted types first. No arbitrary file reads selected by a label.
* `test` → `{type:'editor_snapshot', editor_id:<UUID>, text:<full selected-version source>}`. Cap source text at 64 KiB UTF-8; verify offsets/slice, compute/store `sha256` server-side as an additional normalized source property. This is explicitly **learner-supplied**, not an authenticated on-disk file. Persist it within refs_json for reproducibility and unsaved/multiple-tab support; never invoke workspace_write. The validator accepts absent digest on input and checks equality if present on normalized replay.
* `convo` → `{type:'message', message_id:<positive integer>}`. Resolve persisted message in the same journey/session; offset into stored content; verify exact snippet. Do not substitute file/line semantics or trust a client-supplied message body. For rich rendering, frontend must map selections to stored source text; split a multi-message selection into separate pins. No arbitrary rendered-DOM offsets.

Always check journey.session_id against configured session and unit membership through `JourneyRecorder.journey_for_unit`. For retries compare the incoming request identity against the stored canonical request **before** rereading mutable source files; unchanged retries reuse frozen validated refs. A changed request under the same id is a conflict. Distinguish submitted source evidence from agent instructions in both prompts. Existing grade packets rent only current evidence, and the demo previews a stored snippet; neither warrants rereading changed files to render history. [Evidence: backend/tutor_v2/recorders.py:188–197,258–273; backend/tutor_v2/packets.py:131–136; frontend/tutor.html:779–781,790–791.]

### backend/tutor_v2/recorders.py — proposed changes

Extend `ConversationRecorder.record(..., refs: list[dict[str, Any]] | None = None, thread_kind: str = 'main', thread_id: str | None = None) -> int` with the rules above; serialize refs and persist grouping. Preserve existing arguments/default behavior. Extend `set_turn_status(..., thread_kind: str = 'main')` to scope updates; `find_learner_answer` must require main + message_kind='answer'. Add `find_aside_reply(self, *, journey_id: int, turn_id: str) -> dict | None`, selecting aside/tutor/aside_reply. Do not make `record` automatically bump revision. [Existing seams: backend/tutor_v2/recorders.py:33–85.]

Add `AsideRecorder(db: Database, config: TutorConfig)` with `create_thread(*, thread_id: str, journey_id: int, unit_id: int, origin_message_id: int | None, title: str, created_at: str) -> None`, `get_turn(*, journey_id: int, request_id: str) -> dict | None`, `start_turn(*, request_id: str, journey_id: int, thread_id: str, request: dict, learner_message_id: int, anchor_event_id: int | None, created_at: str) -> None`, and `complete_turn(*, journey_id: int, request_id: str, reply_message_id: int, completed_at: str) -> None`. These write only their two new tables. Validate ownership and immutable links on each write; update completion only from PENDING. Orchestrator owns the outer transaction; nested recorder transactions use existing savepoints. [Pattern: backend/tutor_v2/recorders.py:173–227; backend/tutor_v2/db.py:149–175.]

Use existing `JourneyRecorder.record_event` and `bump_revision`, without changing their meanings. On thread creation emit exactly one `event_type='aside'`, payload `{thread_id,title,origin_message_id}`, message_refs=[first learner message id], probe/action refs empty, and source_ref equal to the first normalized pin or null. All pins remain on the message. This event is a navigational fact, never an axis verdict. Followups do not create duplicate map anchors. [Existing permissive event shape: backend/tutor_v2/recorders.py:199–227; UI anchor behavior: frontend/tutor.html:725–752.]

### backend/tutor_v2/orchestrator.py and session.py — proposed new path

Add immutable `AsideResult(journey_id: int, thread_id: str, request_id: str, learner_message_id: int, reply_message_id: int | None, status: str, projection_revision: int)`; it has **no RouteDecision**. Add `TurnOrchestrator.begin_aside(*, journey_id: int, unit_id: int, request_id: str, question: str, refs: list[dict], thread_id: str | None = None, origin_message_id: int | None = None) -> AsideResult` and `commit_aside(*, journey_id: int, request_id: str, aside_blocks: list[str]) -> AsideResult`. Wire optional AsideRecorder and ReferenceValidator constructor dependencies. [Existing composition and result: backend/tutor_v2/orchestrator.py:33–86.]

`SessionRunner.run_aside` has the same input signature as begin_aside and returns AsideResult. Its required workflow:

1. Validate UUID request identity, journey ownership and unit membership. Default policy: accept LIVE or PARKED journeys; reject OWNED until archive amendment is decided. For followups require existing thread in the same journey/unit; origin is immutable and omitted on followups. Question may be empty only when refs are nonempty. Title is first 120 code points of first question or 'Side question'; model cannot set IDs or title.
2. Under a short outer transaction, recheck request existence. Exact COMPLETE replay returns stored message IDs with current revision and invokes no agent. Exact PENDING replay reuses saved input. New request: validate/freeze refs, create thread if necessary (server UUID), record learner `aside_question` with `axis=None`, status RECORDED, turn_id=`aside:<request UUID>`, create initial anchor if new thread, insert PENDING aside_turn, bump revision once. Existing request ID with different payload or owner is rejected. Use transaction serialization to close concurrent check/insert races.
3. Outside any DB transaction build the aside packet from that persisted question/refs plus only that thread's completed prior Q&A, then `_invoke('wakeup.aside', packet)`. Invocation or contract failure leaves a durable PENDING question and unchanged ladder; retry with the same request ID. Permit duplicate in-flight model calls, but only one persisted completion. No background scheduler/lease is introduced.
4. `commit_aside` parses output outside the write transaction, then rechecks status inside it. COMPLETE is a no-op. Otherwise record one tutor `aside_reply` with the same aside turn/thread, RECORDED status, empty refs, mark COMPLETE, and bump revision once, atomically. Losing concurrent completions return the winner's IDs. Failures roll back reply/completion/revision together.
5. Optional existing `_record_tools` runs only for the winning completion; its extra revision bump is independent observability. Return a freshly read revision after tool capture, not the earlier commit revision. Do not promise exactly two total bumps if tools were recorded. Current capture already deduplicates by journey+turn. [Evidence for the adopted boundaries and tool behavior: backend/tutor_v2/orchestrator.py:88–100,203–228; backend/tutor_v2/session.py:173–195; backend/tutor_v2/recorders.py:95–114.]

For a PENDING replay, transient context uses persisted data, not a changed request. For concurrent followups, thread history is the completed history available when the packet is built; no promise of serialized model execution. Order display by conversation sequence. Suppress duplicate completion even across process restart using aside_turns, not a memory counter. The existing driver's `turn-N` minting is deliberately left unchanged. [Evidence: backend/tutor_v2/driver.py:59–61,144–146; backend/tutor_v2/recorders.py:52–62.]

### contracts.py, packets.py, parsing.py, sdk_runtime.py — proposed contract

Add `WAKEUP_AGENTS['wakeup.aside']='TEACHER'`; exact capabilities **('read_turn_context',)**. This existing tool returns a packet context copy and has no persistence calls. No workspace, repository search, axis evidence, probe history, shell, write, or routing capabilities are granted. No SDK tool implementation is needed; launch policy matching and tool dispatch already enforce grants. [Evidence: backend/tutor_v2/sdk_runtime.py:68–107,150–167,229–246.]

Add `WakeupBuilder.build_aside(self, *, journey_id: int, request_id: str) -> dict[str, Any]`. It validates owned persisted aside records, emits the existing envelope with unit_id but no axis, and a closed context `{journey_id,thread_id,request_id,unit,history,history_truncated,current_evidence}`. `history_truncated` is a boolean; retain the latest 20 completed exchanges, ordered by learner-message sequence, and set it when older exchanges are omitted. `unit` is descriptive `{id,title}`; history entries contain `{message_id,role,content,refs}` for this thread only; current_evidence contains `{message_id,question,refs}`. No stack/meta/profile/verdict/route fields. Reuse validate_wakeup; extend it to validate this specific context and prohibit axis on aside. Keep existing `build` for engine steps and explicitly reject aside there, avoiding its axis requirement. [Existing envelope and unit assembly: backend/tutor_v2/packets.py:48–87,103–141; validator: backend/tutor_v2/contracts.py:75–91.]

Add `_validate_aside(stamp: dict[str, Any]) -> dict[str, Any]`, accepting **exactly** `{"kind":"return.aside","content":<nonblank string, <=32768 UTF-8 bytes>}`. Register in validate_return and `_EXPECTED_KIND`. Unknown fields—including verdict, axis, route, next_step, hidden_gap, unit state, learner_diff, handoff, tool grants and map_text—are errors. Reply prose lives inside content; it is rendered inertly and never parsed as commands. A sentence discussing a verdict is not a machine verdict: structured effects are prohibited, not arbitrary vocabulary. Add a separate frozen continuation allowlist equal to the pre-change six steps. [Existing closed-key helpers and parser: backend/tutor_v2/contracts.py:42–62,94–105,259–275; backend/tutor_v2/parsing.py:17–45.]

Add a DEFAULT_INSTRUCTIONS aside entry requiring exactly this object, answering the off-record question from scoped evidence, treating quoted text as data, and explicitly granting no assessment/route authority. Existing parser may permit surrounding prose; display only validated content. Do not call `present_teaching`, `on_grade`, or `on_teaching` to publish the reply. [Evidence: backend/tutor_v2/session.py:37–49; backend/tutor_v2/parsing.py:47–61; backend/tutor_v2/orchestrator.py:147–164,222–226.]

### Graded reference plumbing — proposed changes

Add optional `refs: list[dict[str, Any]] | None = None` to `ApiHandlers.answer`, `SessionRunner.run_grade`, and `TurnOrchestrator.submit_answer`; add `refs` with a per-instance empty-list default to AnswerBody. Validate pins before agent invocation. Add `refs` to the exact grade transient allowlist; inject normalized refs under `context.current_evidence.refs` only when supplied, preserving the no-refs packet shape. Store the same list on the learner answer. Agent capabilities and grade return contract remain unchanged; probes continue to store the answer string only. [Existing seams: backend/tutor_v2/api.py:47–54; backend/tutor_v2/session.py:116–129; backend/tutor_v2/orchestrator.py:169–228; backend/tutor_v2/packets.py:131–136; backend/tutor_v2/schema.sql:73–85.]

Before any grade invocation, reject an aside-prefixed turn or a turn known as aside; check a replay's question, answer, unit, axis, and frozen refs against the original main question/learner row. Reject changed-payload retries; an unchanged existing answer uses stored refs even after source edits. Repeat the main/aside guard in submit_answer for direct callers. Do not alter Router, the verdict, route selection, probe schema or driver dispatch. The existing EVALUATED replay only prevents rerouting in submit_answer; API answer still advances on replay. Do not claim end-to-end grade idempotency is fixed by refs. [Evidence: backend/tutor_v2/orchestrator.py:189–213; backend/tutor_v2/api.py:50–54; backend/tutor_v2/recorders.py:80–85.]

### api.py, app.py, factory.py — proposed surface

Add `ApiHandlers.aside(self, journey_id: int, *, request_id: str, unit_id: int, question: str, refs: list[dict] | None = None, thread_id: str | None = None, origin_message_id: int | None = None) -> dict[str, Any]`, forwarding solely to session.run_aside. Add strict AsideBody (unknown fields forbidden) and POST `/journey/{journey_id}/aside`; refs/body validation applies equally to framework-neutral calls. Handler returns `{operation:'aside',journey_id,thread_id,request_id,status:'pending'|'complete',learner_message_id,reply_message_id,projection_revision}`. **No main DriverState fields are overwritten.** Poll remains GET `/journey/{id}?since=<last consumed revision>`; do not mark a write acknowledgment's revision as consumed before fetching its snapshot. [Existing routes/poll: backend/tutor_v2/app.py:81–87; backend/tutor_v2/api.py:77–93.]

Use existing ValidationError→400 behavior for malformed refs/IDs and explicit InvariantError→409 for request conflicts (document this existing exception reuse; a later dedicated conflict type can preserve the same HTTP status). Session ownership errors must not reveal other sessions' content. Wire new dependencies in build_session without adding a router route or driver state. API tests currently exercise handlers, not FastAPI HTTP validation, so add a real route-level test as well. [Evidence: backend/tutor_v2/app.py:64–71; backend/tutor_v2/factory.py:45–67; backend/tests_v2/test_app.py:53–84.]

### journey_reader.py, journey_archive.py, frontend adapter — proposed projection

Keep flat `conversation` in global sequence order; retain refs_json for compatibility and add decoded `refs`, thread_kind, thread_id. Add `aside_threads` (identity/unit/origin/title/created_at) and `aside_turns` (id/thread/status/learner_message_id/reply_message_id/anchor_event_id); omit request_json and duplicated editor snapshot input from turn summaries. Snapshot version becomes 2. Use a short, nonmutating read-snapshot boundary across revision and all SELECTs: today each query locks independently, so a concurrent write can produce a snapshot inconsistent with its revision. A proposed `Database.read_transaction()` should use BEGIN (not BEGIN IMMEDIATE), hold the connection lock, share a containing transaction if present, and perform no schema/state writes. [Evidence: backend/tutor_v2/journey_reader.py:48–98; backend/tutor_v2/db.py:136–175.]

Frontend groups aside messages by thread_id, leaves main messages in the main loop, positions each thread at its first learner sequence, and renders lifecycle aside anchors by unit. Clicking an anchor opens `thread_id` and scrolls to its first message; use an encoded fragment such as `#aside-<UUID>`. Collapse state is client-local. Preview is always the persisted snippet. Update selection code to supply source identity/offsets and preserve whitespace; adapt normalized refs to existing chip `{kind,label,snippet}`. These are required integration tasks, not functionality SELECT * provides. [Evidence: frontend/tutor.html:748–752,779–788,880–907,1255–1268.]

ArchiveReader.read_journey adds v1 defaults in memory (empty refs, main grouping, empty thread/turn arrays) and emits the v2 projection without rewriting immutable archives. Keep archive container format version 1 unless its structure changes; snapshot_version distinguishes the projection. New archive writes already include reader output and JSONL messages. Do not finalize/checkpoint archives on an aside path. [Evidence: backend/tutor_v2/journey_archive.py:83–94,105–125,157–167.]

## 4. Invariant proof and accidental violations

**Scope of proof:** a correctly implemented new path using the production closed SDK gateway and these recorder contracts. The current Database.transaction is atomicity machinery, not a database permission sandbox: it allows arbitrary connection SQL. It cannot itself prove that a future buggy method never writes stones. Combine a restricted call graph with negative mutation tests. [Evidence: backend/tutor_v2/db.py:132–175; backend/tutor_v2/sdk_runtime.py:68–107.]

The only proposed write edges are API → run_aside → begin_aside/commit_aside → ConversationRecorder/AsideRecorder/JourneyRecorder (and optional ToolCallRecorder). They write conversation_messages, aside_threads, aside_turns, journey_events, journeys.projection_revision/updated_at, and tool_calls. Reads of units/journeys establish ownership; no write to units, axes, stack, probes, meta, events, learner, handoff or workspace/archive files is required. Nested recorder transactions become savepoints; rollback of completion removes reply/status/revision together while leaving the already committed PENDING question. [Existing transaction and recorder write patterns: backend/tutor_v2/db.py:149–175; backend/tutor_v2/recorders.py:52–72,95–114,217–250.]

The agent gets one tool that returns already assembled data. Its return has only content; no route-bearing stamp is accepted. No route function, driver advancement, question bookmark, grade projection, distill or workspace write is called. Explicit references in a **later graded answer** may contain an aside quote, as the user requested conversation pins; that is deliberate evidence submitted by the learner, not an automatic aside verdict. [Existing tool and dangerous entry points: backend/tutor_v2/sdk_runtime.py:91–93; backend/tutor_v2/api.py:47–54; backend/tutor_v2/orchestrator.py:138–144,207–228,273–280.]

Places naive implementation would violate the guarantee:

* Calling answer or submit_answer to handle “off-topic” prose still routes and creates a probe. There is no safe grading category substitute for an aside. [backend/tutor_v2/orchestrator.py:203–228.]
* Calling present_question(save_resume_question=True) changes the bookmark; calling driver.advance(None) reports done. [backend/tutor_v2/orchestrator.py:138–145; backend/tutor_v2/driver.py:65–67,132–135.]
* Reusing a main turn hits learner uniqueness or broad status/answer lookup. Separate IDs plus explicit main filtering are mandatory. [backend/tutor_v2/schema.sql:215–216; backend/tutor_v2/recorders.py:65–85.]
* Registering aside in WAKEUP_AGENTS silently expands valid continuations unless separated. [backend/tutor_v2/contracts.py:259–264.]
* Saving editor pins via workspace_write changes meta revision/hash and files. Pin snapshots belong in journey refs instead. [backend/tutor_v2/services.py:140–160.]
* Assuming record_event bumps revision makes durable asides invisible to revision-gated polling. [backend/tutor_v2/recorders.py:217–250; backend/tutor_v2/journey_reader.py:54–59.]

## 5. Test plan

Baseline executed during this review: `python agentic_tutor/backend/run_v2_tests.py` → **90 passed, 0 failed**. Also verified `python -m pytest tests_v2 -q` from `agentic_tutor/backend`: **90 passed**. Running pytest from the workspace root without adding backend to the import path initially failed collection (`tutor_v2` unavailable); running from backend resolved it. This is baseline verification, not a claim that proposed functionality exists. The runner discovers no-argument test_* functions; follow the existing temporary-directory, fake-agent, try/finally cleanup pattern. Also run pytest per BUILD_PLAN. [Evidence: backend/run_v2_tests.py:22–40; backend/tests_v2/test_orchestrator.py:17–25,87–109; backend/tests_v2/test_app.py:34–60; docs/BUILD_PLAN.md:12–17.]

Proposed tests, with concrete assertions:

| File | Tests to add |
|---|---|
| backend/tests_v2/test_foundation.py | Fresh v7 and v6 upgrade yield identical new columns/tables/indexes; existing messages become main/[]/null; reopen does not duplicate migration; old DB does not fail on a pre-ALTER index; intentional interrupted migration recovers; aside FK/unique constraints reject invalid inserts. |
| backend/tests_v2/test_references.py (new) | Mixed many refs preserve order/whitespace; exact repository hash/span; traversal, absolute/UNC and symlink escape; missing file/invalid UTF-8; negative/reversed/out-of-range/bool offsets; unknown kind/key; mismatched excerpt; Unicode emoji offsets; foreign-journey message; unsaved multi-tab snapshot works without filesystem/meta writes; all byte/count limits; unchanged replay after file edit uses saved refs. |
| backend/tests_v2/test_recorders.py | Aside main/group/status rules; separate request IDs coexist with one main turn; broad answer/status operations cannot match aside; global sequences stay unique; begin/reply writes do not bump implicitly; direct recorder ownership validation. |
| backend/tests_v2/test_contracts.py and test_parsing.py | Exactly return.aside/content accepted; blank/oversize/wrong-kind/multiple-object/missing-content rejected; iterate forbidden extra keys; aside is rejected as engine continuation; original continuations unchanged. |
| backend/tests_v2/test_packets.py | Aside has no axis/verdict/profile/stack/probes/meta, only target thread history; one exact capability; builder rejects cross-session IDs; grade refs appear only in current_evidence; no-refs packet stays unchanged; unknown grade transient still rejected. Mirror existing packet equality assertions at test_packets.py:36–70. |
| backend/tests_v2/test_sdk_runtime.py | launch_spec grants only mcp__tutor__read_turn_context; gateway refuses write_workspace, read_workspace, read_axis_evidence, read_probe_history, search_repository, arbitrary tool names; injected capability does not bypass policy; tool result is only the scoped packet context. |
| backend/tests_v2/test_asides.py (new) | Full API→session→fake agent→orchestrator path; two threads and followups; LIVE/PARKED accepted and OWNED rejected; exactly one lifecycle anchor per thread; recorded learner/reply IDs and refs link correctly; blank question+refs succeeds. |
| backend/tests_v2/test_asides.py (new) | **Negative ladder test:** snapshot SELECT * of units, axes, stack, probes, meta ordered by primary key before and after begin, successful reply, followup, malformed reply, invocation error and retry. Assert byte-for-byte row equality (including timestamps), same pending main question and driver counter, unchanged workspace/archive bytes. Include events, learner and handoff too. Replace driver.advance, Router mutation methods and ProbeRecorder.record with raising spies to prove they are never invoked. |
| backend/tests_v2/test_asides.py (new) | Fault injection at reply insert, turn completion and bump_revision rolls back completion atomically; durable PENDING question remains. Exact replay makes no model call after COMPLETE and no new rows/revision; changed payload conflicts; concurrent identical calls persist one question/reply; restart with PENDING then retry uses frozen refs; colliding request ID from another journey rejects. |
| backend/tests_v2/test_session.py and test_app.py | Capturing fake JUDGE receives exactly the persisted graded refs; aside return never reaches grade; forged aside turn rejected before agent call and by direct submit_answer; old answer API remains compatible; changed-ref main replay rejected. Existing API grade replay advancement remains a separately documented risk. |
| backend/tests_v2/test_app.py | Real FastAPI route test for strict body, 400 invalid refs, 409 request conflict, aside acknowledgment shape and no main state overwrite; GET since previous revision returns pending/completed thread; equal consumed revision reports unchanged. Keep handler tests runnable without importing FastAPI at module import if dependency unavailable. |
| backend/tests_v2/test_journey_projection.py | Decoded refs/grouping/anchor/turn summaries; coherent revision under interleaved writer; one poll after begin and after completion; full archive roundtrip and v1 defaults; source mutation after send does not change preview; no JSON/editor duplication through request_json projection. Existing snapshot/archive tests start at test_journey_projection.py:61–94. |

The spec's final acceptance condition is all original tests green plus the negative ladder test and adversarial retry tests above. A semantic map node is intentionally not required; verify the frontend adapter renders lifecycle anchors and can deep-link to stable thread IDs. [Existing map link: frontend/tutor.html:725–752.]

## 6. Risks and open questions

1. **Refs-only graded answer conflicts with the hard constraint.** UI enables send with empty text and pins, but ProbeRecorder requires a nonblank learner_answer. Default proposal: allow this for asides; require text for a graded answer and show that rule in the connected UI. Fabricating text or loosening probe semantics would violate additive-only. Product must explicitly reconcile the mismatch before claiming full demo parity. [frontend/tutor.html:1211,1223–1230; backend/tutor_v2/recorders.py:143–152.]
2. **Write response convention.** The aside acknowledgment is a deliberate API extension. If every aside must instead return a complete current DriverState, an additional journey-layer persisted main-state projection and wiring is required; calling the driver is not acceptable. This spec recommends the acknowledgment and client retention of its current main state. [backend/tutor_v2/api.py:10–13; backend/tutor_v2/driver.py:59–67.]
3. **Editor evidence trust.** Proposed snapshots verify what was submitted, not whether it existed in a real test file or executed successfully. Product may instead require saved revision-backed documents, but that requires an additional journey-layer editor document model; the current workspace represents one file. Never label snapshot text as a passing test. [backend/tutor_v2/services.py:127–138; frontend/tutor.html:1066–1075,1260–1263.]
4. **Rendered conversation selections.** The demo permits arbitrary DOM selection, including selections across turns. Stored content and rendered HTML may differ. Mapping to persisted content must be implemented, or selections restricted to a single source-text region; don't silently invent offsets. Proposed convention is Unicode code points, requiring JavaScript conversion from UTF-16 selection positions. [frontend/tutor.html:883–884,1265–1268.]
5. **Archived journeys and “off-record.”** Here off-record means ungraded but durably visible and archived, consistent with the requested map anchor. Allowing new replies after OWNED needs a policy for immutable archive amendments. Default reject new OWNED asides; preserve previously recorded ones in archives. Collapsing stays client-local unless cross-device persistence is requested. [backend/tutor_v2/journey_archive.py:83–94,105–125; frontend/tutor.html:895–896.]
6. **Existing grade recovery weaknesses remain.** JUDGE invocation precedes answer persistence; replay guard does not compare original payload; API still advances after replay; driver turn IDs reset on restart. New refs must not claim to repair all of this. Side IDs and durable aside_turns avoid these hazards for asides. A separate main-turn reliability specification may be needed. [backend/tutor_v2/session.py:116–129; backend/tutor_v2/orchestrator.py:189–213; backend/tutor_v2/api.py:50–54; backend/tutor_v2/driver.py:59–61,144–146.]
7. **Context/storage limits and simultaneous followups.** Limits in §3 are concrete defaults, not existing product policy. Snapshot refs duplicate editor content; thread history must have a bound (proposed latest 20 completed exchanges plus current evidence, deterministic truncation with a context flag if truncated). If strict conversational ordering is required for simultaneous followups, add a journey-layer serialization policy; do not hold a DB transaction during model execution. [Existing outside-transaction principle: backend/tutor_v2/orchestrator.py:3–11; current demo followup behavior: frontend/tutor.html:899–907.]
8. **Security proof boundary.** The configured Python agent_run callable is trusted application code; it can perform arbitrary side effects if malicious. SDK tool restrictions prove the exposed production tool path, not arbitrary Python/plugin code. Keep reference text inert in prompts and escape it in UI rendering. [backend/tutor_v2/session.py:33,173–183; backend/tutor_v2/sdk_runtime.py:150–190; frontend/tutor.html:775–781.]

Implementation order: migration/reference validation → recorder and contract tests → isolated aside session path → graded refs plumbing → projection/archive defaults → HTTP and frontend adapter → invariant/retry/full-suite acceptance. No engine-stone migration, Router branch, serverless deployment change, or database replacement is part of this specification.
