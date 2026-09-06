# BUILD SPEC — Tool-call capture (the conversation's grounding lines + full trace)

A cold agent can execute this top to bottom. It assumes **no prior knowledge** of the repo —
§0 and §1 give you the whole map before any step. Paths are relative to `agentic_tutor/tutor_v2/`.
Grep for the named symbol; line numbers drift.

---

## 0. Orientation — what this system is (read fully before touching anything)

`tutor_v2` is a local, single-learner tutoring engine. It teaches one **unit** of code at a
time (a function/region). Per learner interaction it runs a **turn**: it builds a scoped
**wakeup** packet, calls a Claude agent through the SDK, validates the agent's returned
**stamp**, and routes deterministically. State lives in one SQLite DB (`schema.sql`, opened by
`db.py`). A read-only **projection** (`journey_reader.py` → `transport.py`) feeds the frontend.

### The turn pipeline (who calls whom)
```
 API/driver ──▶ SessionRunner ──▶ [agent seam] ──▶ ClaudeAgentAdapter.run (SDK) ──▶ Claude
   (api.py)       (session.py)     Callable          (sdk_runtime.py)                  │
      ▲                │                                    │ text blocks              │ tool calls
      │                ▼                                    ▼   (returned)              ▼  (LOST today)
      │        TurnOrchestrator ◀───────────────────────  list[str]        TutorToolGateway.call
      │         (orchestrator.py)  commits inside ONE db.transaction()      (executes each read tool)
      │                │
      │                ▼
      └──────  JourneyReader.read (projection_revision-gated snapshot the UI polls)
```

### The five agents and their tools
Each wakeup step wakes one agent and grants a **fixed, per-step tool allowlist** — the
"rented-context law." From `packets.py::CapabilityPolicy._BY_STEP`:
```
wakeup.map     MAPPER    : read_code_slice, search_repository
wakeup.probe   TEACHER   : read_code_slice, read_axis_evidence, read_probe_history
wakeup.teach   TEACHER   : read_code_slice, read_axis_evidence, read_probe_history
wakeup.test    TEACHER   : read_code_slice, read_axis_evidence, read_probe_history, read_workspace
wakeup.grade   JUDGE     : read_code_slice, read_axis_evidence, read_probe_history, read_transcript
wakeup.distill DISTILLER : read_turn_context, read_probe_history, read_workspace, read_event_trace
```
There are exactly **8 read-only tools** total; every write/builtin tool is blocked
(`sdk_runtime.py::_BUILTINS_BLOCKED`). The tools are served in-process by
`TutorToolGateway.call(capability, arguments)` (`sdk_runtime.py`), exposed to the SDK as MCP
tools named `mcp__tutor__<capability>` (`ClaudeAgentAdapter.launch_spec`, `_sdk_tools`).

### THE GAP this spec closes
**No tool call is recorded anywhere.** `ClaudeAgentAdapter.run` keeps only assistant text and
throws away every tool interaction:
```python
# sdk_runtime.py — current run()
async for message in query(prompt=..., options=options):
    if isinstance(message, AssistantMessage):
        text.extend(block.text.strip() for block in message.content
                    if isinstance(block, TextBlock) and block.text.strip())
return text            # ← ToolUseBlock / ToolResultBlock are dropped on the floor
```
So the frontend's "the tutor looked at your code" lines have **no data source**, and there is
no per-turn record of what each agent consulted.

### What the UI does with tool calls (the two-view contract — already decided)
- **Conversation view** shows ONLY the two **grounding** tools — `read_code_slice`,
  `read_workspace` (the ones done *to the learner's own work*). The frontend already filters to
  these (`frontend_sample/tutor.html`, `GROUNDING_TOOLS`).
- **Map view** shows the reasoning graph (concepts/misconceptions), **no tools at all**.
- The **other six** tools (`read_axis_evidence, read_probe_history, read_transcript,
  read_turn_context, read_event_trace, search_repository`) are captured and stored but shown in
  neither view today — they back a future dev/debug page. **Capture ALL of them; let the view
  filter.** The backend must never hard-code the grounding subset — that split is a UI concern.

---

## 1. Goal

Capture every tool call an agent makes in a turn, persist it keyed to that turn, and ship it in
the projection snapshot — so the conversation's grounding lines are real and a full trace exists.
Capture must be **best-effort and unable to break a turn** (observability, never authority).

---

## 2. Design decisions (and why)

- **Capture point = `ClaudeAgentAdapter.run` (the SDK boundary), not the gateway.** Only here is
  the model's actual sequence of `ToolUseBlock`s visible in order. The gateway executes calls but
  has no turn identity (no `turn_id`/`journey_id`), so keying there is impossible.
- **The agent seam returns more than text.** Today `AgentRun = Callable[[dict,str], list[str]]`.
  Change it to return an `AgentOutput{blocks, tool_calls}`. `_invoke` NORMALIZES: if a seam
  returns a bare `list`, wrap it as `AgentOutput(list, [])`. This keeps every existing test fake
  (which returns `list[str]`) working unchanged.
- **Keying:** `(journey_id, unit_id, turn_id, step, agent, ordinal)`. For non-learner steps that
  have no learner `turn_id` (map, distill) use a synthetic id (`"map:0"`, `f"distill:{unit_id}"`).
- **Store lean.** Persist `capability`, `arguments_json` (tutor tools take no args except
  `search_repository`'s `{query}`), a `refused` flag, and `ordinal`. **Do NOT store tool results**
  (code slices are large; the conversation label like "L42–46" is derived from wakeup context by
  the FE, not from the stored result).
- **Recording is additive and its own transaction** (mirrors the existing recorders), and bumps
  `projection_revision` so the next poll ships it. It does not need to be atomic with the routing
  commit — an orphaned tool row after a rolled-back turn is harmless observability.
- **No change to the rented-context law.** `packets.py`, `CapabilityPolicy`, and the gateway are
  untouched. We record what the model *did*; we grant nothing new.

---

## 3. Execution steps (in order)

### STEP 1 — `schema.sql` + `db.py`: the table and its migration
1. In `schema.sql` add (near the other journey-layer tables):
```sql
CREATE TABLE IF NOT EXISTS tool_calls (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id   INTEGER REFERENCES journeys(id) ON DELETE CASCADE,
    unit_id      INTEGER REFERENCES units(id),
    turn_id      TEXT NOT NULL,
    step         TEXT NOT NULL,
    agent        TEXT NOT NULL,
    capability   TEXT NOT NULL,
    arguments_json TEXT NOT NULL DEFAULT '{}',
    refused      INTEGER NOT NULL DEFAULT 0,
    ordinal      INTEGER NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_journey ON tool_calls(journey_id, id);
```
2. In `db.py`: bump `SCHEMA_VERSION = 5` → `6`; add a `version == 6` branch in `_apply_migration`
   that is a no-op comment (the `CREATE TABLE IF NOT EXISTS` above runs on every init via
   `executescript`, so fresh AND existing DBs get the table). Follow the exact shape of the
   existing `version == 4` / `version == 5` branches.

### STEP 2 — `domain.py`: the transport dataclass
Add:
```python
@dataclass(frozen=True, slots=True)
class ToolCall:
    capability: str
    arguments: dict[str, Any]
    refused: bool
    ordinal: int

@dataclass(frozen=True, slots=True)
class AgentOutput:
    blocks: list[str]
    tool_calls: list[ToolCall]
```
(Confirm `domain.py`'s imports; add `from dataclasses import dataclass` / `from typing import Any`
if absent.)

### STEP 3 — `sdk_runtime.py`: capture in `run`
Rewrite `ClaudeAgentAdapter.run` to collect tool calls alongside text and return an `AgentOutput`.
The MCP tool name is `mcp__tutor__<capability>` — strip that prefix. Match a `ToolResultBlock`'s
`is_error` back to its `ToolUseBlock` by `tool_use_id` to set `refused`. **Wrap capture so it can
never raise** — a parsing surprise must not fail the agent turn.
```python
async def run(self, wakeup, instruction) -> AgentOutput:
    options = self.build_options(wakeup, instruction)
    from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock, query
    try:
        from claude_agent_sdk import ToolResultBlock            # name may vary by SDK version
    except ImportError:
        ToolResultBlock = None
    text: list[str] = []
    uses: list[tuple[str, str, dict]] = []   # (tool_use_id, capability, arguments)
    errored: set[str] = set()                # tool_use_ids that returned is_error
    async for message in query(prompt=json.dumps(wakeup, sort_keys=True), options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    text.append(block.text.strip())
                elif isinstance(block, ToolUseBlock):
                    name = str(block.name)
                    cap = name.removeprefix("mcp__tutor__")
                    args = dict(block.input or {})
                    uses.append((str(block.id), cap, args))
        elif ToolResultBlock is not None:
            for block in getattr(message, "content", []) or []:
                if isinstance(block, ToolResultBlock) and getattr(block, "is_error", False):
                    errored.add(str(block.tool_use_id))
    tool_calls = [ToolCall(cap, args, (tid in errored), i)
                  for i, (tid, cap, args) in enumerate(uses)]
    return AgentOutput(text, tool_calls)
```
Keep the existing `AgentSdkUnavailableError` import-guard behavior. Update the module docstring
line that says run "returns its text blocks only."

### STEP 4 — `session.py`: normalize the seam + forward tool calls
1. Change the alias and adapter wrapper:
```python
AgentRun = Callable[[dict[str, Any], str], "AgentOutput | list[str]"]

def agent_run_from_adapter(adapter):
    def run(wakeup, instruction):
        return asyncio.run(adapter.run(wakeup, instruction))   # now returns AgentOutput
    return run
```
2. Make `_invoke` return an `AgentOutput`, normalizing a bare list for old fakes:
```python
def _invoke(self, step, wakeup) -> AgentOutput:
    instruction = self.instructions.get(step, "")
    if not instruction.strip():
        raise ValidationError(f"no agent instruction configured for {step}")
    result = self.agent_run(wakeup, instruction)
    if isinstance(result, list):
        result = AgentOutput(result, [])
    if (not isinstance(result, AgentOutput)
            or any(not isinstance(b, str) for b in result.blocks)):
        raise ValidationError("agent runner must return text blocks (list or AgentOutput)")
    return result
```
3. Every caller of `_invoke` now uses `.blocks` for text and forwards `.tool_calls`. After each
   `_invoke`, call the new recorder (STEP 5) with the turn's identity. The identity available per
   method:
   - `run_mapping`: no journey yet — capture, commit the map to get `journey_id` from the returned
     `TurnResult`, THEN record with `turn_id="map:0"`, `unit_id=None`, `agent="MAPPER"`.
   - `run_question` / `run_teaching` / `run_grade`: have `journey_id, unit_id, turn_id, step`.
     Resolve `agent` from `contracts.WAKEUP_AGENTS[step]`.
   - `run_distill`: `journey_id = orchestrator.journeys.journey_for_unit(unit_id)`,
     `turn_id=f"distill:{unit_id}"`, `agent="DISTILLER"`.
   Recording is a plain call (not inside these methods' return path logic); a failure to record
   must be swallowed/logged, never propagated (best-effort).

### STEP 5 — `recorders.py` + `orchestrator.py`: the recorder
1. In `recorders.py` add a `ToolCallRecorder` following the file's existing pattern (ctor
   `(db, config)`, writes wrapped in `db.transaction()`):
```python
class ToolCallRecorder:
    def record(self, *, journey_id, unit_id, turn_id, step, agent, tool_calls) -> None:
        if not tool_calls:
            return
        with self.db.transaction():
            for tc in tool_calls:
                self.db.connection.execute(
                    "INSERT INTO tool_calls(journey_id,unit_id,turn_id,step,agent,capability,"
                    "arguments_json,refused,ordinal) VALUES(?,?,?,?,?,?,?,?,?)",
                    (journey_id, unit_id, turn_id, step, agent, tc.capability,
                     _json(tc.arguments), 1 if tc.refused else 0, tc.ordinal))
```
2. In `orchestrator.py`: construct a `ToolCallRecorder` in `__init__` (optional, like the other
   recorders) and add:
```python
def record_tool_calls(self, *, journey_id, unit_id, turn_id, step, agent, tool_calls) -> int:
    self.tool_calls_recorder.record(journey_id=journey_id, unit_id=unit_id, turn_id=turn_id,
        step=step, agent=agent, tool_calls=tool_calls)
    with self.db.transaction():
        return self.journeys.bump_revision(journey_id)   # so the next poll ships them
```
   `SessionRunner` calls this after `_invoke` (STEP 4.3). Gate on the recorder being present so
   omitting it is byte-for-byte the old behavior (same optional-wiring pattern as `graph`/`archive`).
3. Wire it in `factory.py::build_session` (pass the recorder into the orchestrator).

### STEP 6 — `journey_reader.py`: ship it in the snapshot
In `JourneyReader.read`, add to the returned dict:
```python
"tool_calls": self.db.query(
    "SELECT id,unit_id,turn_id,step,agent,capability,arguments_json,refused,ordinal,created_at "
    "FROM tool_calls WHERE journey_id=? ORDER BY id", (journey_id,)),
```
No transport change (revision-gated already). The frontend filters to `GROUNDING_TOOLS`; the map
ignores `tool_calls` entirely.

---

## 4. Details a cold agent will trip on
- **Tool name prefix:** SDK `ToolUseBlock.name` is `mcp__tutor__read_code_slice`; store the
  stripped `read_code_slice`. If a name lacks the prefix (shouldn't happen — builtins are blocked),
  store it raw.
- **Block type names vary by SDK version:** import `ToolUseBlock`/`ToolResultBlock` defensively
  (guard `ToolResultBlock` with try/except as shown); if results can't be read, leave `refused=0`.
- **`search_repository` is the only tool with arguments** (`{"query": ...}`); all others record
  `{}`. That's why `arguments_json` exists but is usually `{}`.
- **Best-effort contract:** wrap STEP 3 capture and STEP 4.3 recording so neither can raise into
  the turn. A missing tool trace must never fail tutoring.
- **Do not add capture to the gateway or change `CapabilityPolicy`** — capture is passive.

## 5. Tests (`tests_v2/`)
- A fake seam returning `AgentOutput(blocks, [ToolCall("read_code_slice",{},False,0),
  ToolCall("read_probe_history",{},False,1)])` through a grade turn → two `tool_calls` rows keyed
  to that `turn_id`; snapshot `tool_calls` contains both; `projection_revision` advanced.
- A fake seam returning a bare `list[str]` still works (normalization) and writes zero tool rows —
  proves backward-compatibility with existing fakes.
- `refused=1` persists when a `ToolCall.refused` is True.
- `run_mapping` capture lands under the created journey with `turn_id="map:0"`.
- Existing `tests_v2/` all still pass (the seam change is the main risk surface).

## 6. Definition of done
- `cd agentic_tutor && .venv/bin/python -m pytest tests_v2/ -q` green (new + existing).
- `SCHEMA_VERSION == 6`; a fresh DB and a pre-existing v5 DB both gain `tool_calls`.
- Snapshot from `JourneyReader.read` includes a `tool_calls` list.
- No diff to `packets.py`, `routing.py`, `contracts.py`, `CapabilityPolicy`, or the gateway.

## 7. Non-goals / future
- No dev/debug page yet — the full six-tool trace is stored, not rendered. The conversation shows
  only the grounding two (frontend filter already in place).
- No storage of tool *results* (only that a tool was called, with args + refused).
- No new tools, no capability changes, no wakeup/context changes.
- SSE/push transport is unchanged; polling already ships the new field.

## 8. Invariants (must hold at the end)
1. Rented-context law untouched; capture is passive observation of what the model did.
2. Read-only tool surface unchanged; writes stay blocked.
3. Capture/record is best-effort: it can never raise into or roll back a tutoring turn.
4. The grounding-vs-full split is a UI decision; the backend stores ALL calls and never hard-codes
   the grounding subset.
