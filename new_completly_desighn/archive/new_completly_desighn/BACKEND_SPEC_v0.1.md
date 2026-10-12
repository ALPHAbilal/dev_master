# Backend Spec: `tutor_graph`

> **Build specification | draft v0.1 | 2026-10-09**
> Implements `learning_graph_orchestration_architecture.md` v1.1 and replaces `agentic_tutor/backend/tutor_v2`.
> Read the architecture file first. This file says **how to build it**.

---

## 0. What This Spec Is Built On

### Decided by you

| # | decision |
|---|---|
| D1 | **Supabase Postgres** is the source of truth. The "files" agents read are served by our custom tools. The learner's repo is the only set of real files. |
| D2 | **The orchestrator's output is if/else.** `continue` means continue, with no kit and no explanation. Any other decision carries **short template names**, which the engine resolves to full text from config. |
| D3 | **The orchestrator's own context is assembled by code from the graph position.** Code picks the instruction pieces that match the current position. All instruction pieces live in **config**, not in code. |
| D4 | **Node status has three parts:** lifecycle, attention, and readiness (computed). |
| D5 | **Runtimes:** the crafters run on the **Claude Agent SDK**. The orchestrator and the tutor call the **Claude API** directly. |
| D6 | **Model:** **Claude Haiku 5.5** (`claude-haiku-5-5`) for every agent, set per agent in config. |
| D7 | **Phase 1:** the learner's code and results reach the agents **only as text**, attached from the frontend's Editor. No code runs on the server. |
| D8 | **A task is done when its purpose is met:** answers are correct, or the pasted code is correct, as judged by the orchestrator. Phase 1 has **no done-check tests**. |
| D9 | **Detours have no depth limit.** The orchestrator adapts to the learner. |
| D10 | **No help tracking for now.** |
| D11 | **Side questions are recorded on the graph and handled with the pieces that already exist**: answer briefly and save it (like I3), or follow it as an ordinary detour. There is no new kind of node (§9.5). |
| D12 | **A new package next to tutor_v2**, then a switch, then tutor_v2 is deleted. **A new API**; the frontend is updated in its own later step. |
| D13 | **Code removes impossible decisions before each orchestrator call** (the decision menu, §7.5). `verify_learning` and `complete_task` are possible only when the focus is the task itself, never inside a detour (V13, V14). |

### Assumed by me, waiting for your confirmation

| # | assumption | why |
|---|---|---|
| A1 | **Lifecycle** is OPEN, RESOLVED or DROPPED. **Attention** is focused, paused_on_stack or set_aside. **Readiness** is computed. | It answers your "OPEN vs ACTIVE" question: ACTIVE was really about attention. |
| A2 | The task crafter still writes a **locked reference solution** per task. The orchestrator may read it to judge "built correctly", and the tutor may read it only through a gate (§8.6). There is no `check/` folder. | It makes D8 checkable. |
| A3 | **Config is a folder of text files in the repo.** One environment variable, `CONFIG_DIR`, points to it. | Templates are long, which suits files better than environment variables. Files are also versioned in git and editable without touching code. |
| A4 | `continue` may carry **evidence-only changes** (new evidence, a concept seen), but never a kit and never an explanation. | Without this, on-track progress ("✓ Did reproduced the bug") would never reach the learner's map. **This is the one assumption that changes D2. Please decide.** |
| A5 | The package is named `tutor_graph`. | `tutor_v3` is already the name of your CLI skill. |
| A6 | **The orchestrator is called fresh on every turn.** Its memory is the graph. | This is stricter than "fresh per task", and cheaper. |
| A7 | **A workspace is one user plus one imported repo.** It replaces tutor_v2's separate `codebases` and `sessions` tables. | One bank per learner per codebase (§16 of the design). |
| A8 | **The tutor's answer-key gate** opens only with the `show_answer` template, and only after **2 or more recorded failed attempts** on the current node. | §24 left the bottom-out rule open. This is the smallest rule that keeps "never before trying". |

---

## 1. The System in One Picture

```text
 FRONTEND (later step)                        BACKEND  tutor_graph  (one FastAPI process)
 ─────────────────────                        ───────────────────────────────────────────────
 story map · conversation · editor ──HTTP──►  API ── auth (Supabase JWT) ── per-workspace lock
                 ▲                                │
                 └────────── SSE ◄────────────────┤
                                                  ▼
                                       ┌─────── ONE LEARNER TURN ───────┐
                                       │ 1 save the learner message      │
                                       │ 2 ORCHESTRATOR (Haiku 5.5)      │◄── config/orchestrator/*
                                       │   base + position pieces        │    (pieces chosen by code
                                       │   + graph view + message        │     from the graph position)
                                       │   → submit_decision             │
                                       │ 3 validate → commit (one txn):  │
                                       │   graph changes, evidence,      │
                                       │   change records + story lines, │
                                       │   revision + 1                  │
                                       │ 4 TUTOR (Haiku 5.5, streamed)   │◄── config/tutor/* (templates
                                       │   append-only conversation      │    resolved from short names)
                                       │   + <tutor_kit> if not continue │
                                       │ 5 save the reply, revision + 1  │
                                       └────────────────────────────────┘
                                                  │
   CRAFTING JOB (at import, once) ── Agent SDK: concept crafter → task crafter → code: ladder builder
                                                  │
                     Supabase Postgres  ◄─────────┴─────────►  repo copy on the Fly volume (read-only)
```

---

## 2. Package Layout

```text
agentic_tutor/backend/tutor_graph/
├── __main__.py            uvicorn entrypoint (one worker, like tutor_v2)
├── settings.py            environment variables (§3.2)
├── config_loader.py       loads CONFIG_DIR: templates, pieces, tool guides, story patterns, models
├── db/
│   ├── migrations/        SQL migrations for Supabase Postgres (§4)
│   ├── pool.py            psycopg 3 async pool; transaction() helper
│   └── queries.py         all SQL lives here
├── graph/
│   ├── model.py           Node, Edge, Evidence, Change dataclasses
│   ├── rules.py           state rules + validation of a decision (§5)
│   ├── apply.py           applies a validated decision in one transaction
│   ├── knowledge.py       computed concept status (§5.4)
│   └── view.py            the compact graph view for the orchestrator (§7.3)
├── orchestrator/
│   ├── positions.py       graph position → instruction pieces (deterministic, §7.2)
│   ├── menu.py            graph state → the decisions possible this turn (§7.5)
│   ├── context.py         assembles the orchestrator call
│   ├── decision.py        the decision schema + parsing (§7.4)
│   └── run.py             tool loop until submit_decision
├── tutor/
│   ├── conversation.py    append-only message store, raw content blocks
│   ├── kit.py             template names → <tutor_kit> block (§8.3)
│   ├── tools.py           tutor tools + gates (§8.5)
│   └── run.py             streamed call, tool loop, compaction (§8.7)
├── tasks/
│   ├── lifecycle.py       open · close · next · park · resume (§9)
│   └── discoveries.py     pending discoveries → bank at close (§9.4)
├── story/
│   └── story_lines.py     change → story line (§10)
├── crafting/
│   ├── job.py             background job + progress events
│   ├── prepare_repo.py    scrub secrets, outline, entry points
│   ├── concept_crafter.py Agent SDK run + write_concept tool
│   ├── task_crafter.py    Agent SDK run + write_task tool
│   ├── ladder_builder.py  plain code: the ladder
│   └── validate.py        VALIDATE 1/2/3
├── claude_client.py       Claude API client: retries, refusal handling, token logging
├── api/
│   ├── app.py             FastAPI app, routes (§12)
│   ├── sse.py             SSE helpers
│   └── schemas.py         request/response models
├── reused/                copied from tutor_v2, unchanged: auth.py, importer.py, structure.py
└── tests/

agentic_tutor/backend/config/        ← CONFIG_DIR (A3)
├── models.yaml            per agent: model, effort, max_tokens, compaction threshold
├── orchestrator/
│   ├── base.md            role, rules, and how to use submit_decision
│   ├── positions.yaml     position name → condition → piece file (§7.2)
│   └── pieces/*.md        one piece per position
├── tutor/
│   ├── base.md            the tutor's fixed system prompt
│   ├── templates/*.md     one file per template; the file name IS the template name (§8.3)
│   └── state.yaml         state keys and how each value is rendered
├── tools/*.md             one guide per tool: what · when · when not · how (§8.5)
├── crafters/
│   ├── concepts.md        concept crafter instructions, including the four size tests
│   └── tasks.md           task crafter instructions
└── story.yaml             change kind → story line pattern (§10)
```

---

## 3. Configuration

### 3.1 `config/models.yaml`

```yaml
orchestrator:    { model: claude-haiku-5-5, effort: medium, max_tokens: 4000,  max_tool_rounds: 6 }
tutor:           { model: claude-haiku-5-5, effort: medium, max_tokens: 8000,  compact_at_tokens: 80000 }
concept_crafter: { model: claude-haiku-5-5, effort: high,   max_turns: 200 }
task_crafter:    { model: claude-haiku-5-5, effort: high,   max_turns: 200 }
```

**Why 80,000:** Haiku 5.5 costs $0.10 / $0.50 per million tokens while a prompt stays under 100,000 tokens, and 5× more above that. Every agent prompt must stay under 100K (§13.3).

### 3.2 Environment variables

| variable | purpose |
|---|---|
| `DATABASE_URL` | Supabase Postgres (pooler URL) |
| `SUPABASE_URL` | JWT issuer and JWKS (reused `auth.py`, ES256) |
| `AUTH_MODE` | `supabase`, or `dev` for local runs only |
| `ANTHROPIC_API_KEY` | model calls (the Claude API and the Agent SDK) |
| `CONFIG_DIR` | the config folder (A3) |
| `CODEBASE_ROOT` | where imported repos are cloned (Fly volume) |
| `ALLOWED_ORIGINS`, `ALLOWED_ORIGIN_REGEX` | CORS (as tutor_v2) |
| `DEV_USER_IDS` | user ids allowed on `/dev/*` routes (§12.3) |

`config_loader.py` loads and checks the config once at startup:
- every template named in `positions.yaml`, `story.yaml` or a tool guide exists;
- every file parses.

The server refuses to start on a broken config.

---

## 4. Data Model (Supabase Postgres)

Every table has `workspace_id`, and row-level security keys on the owner.

```text
workspaces        id · owner_id (auth.users) · name · git_url · repo_path
                  · status (crafting|ready|failed) · revision bigint · created_at
crafting_runs     id · workspace_id · stage (prepare_repo|concept_crafter|validate1|task_crafter|validate2|ladder_builder|done)
                  · status · counts jsonb · error · started_at · finished_at

concepts          workspace_id · id ("C15" | "D1") · name · kind · claim · proof
                  · prereqs text[] · source (crafted|discovered) · found_in jsonb · created_at
concept_sections  workspace_id · concept_id · section (what_it_is|examples|misconceptions|other_ways)
                  · ordinal · text · source (crafted|discovered) · found_in jsonb · evidence_id
concept_anchors   workspace_id · concept_id · file · symbol · line_text · hash

tasks             workspace_id · id ("T3") · tier · goal · story · why · concepts text[] · files text[]
                  · real_bug bool · reference_solution text (locked) · ladder_position int

task_runs         id · workspace_id · task_id · status (open|parked|resolved)
                  · opened_at · closed_at · journey_text

nodes             id uuid · workspace_id · short_id ("T3" | "I1") · kind (task|issue)
                  · category · title · lifecycle (OPEN|RESOLVED|DROPPED) · attention (focused|paused_on_stack|set_aside)
                  · parent_id · bank_concept_id · closes_when · return_note · misconception_seen
                  · created_run_id · created_turn · resolved_turn
focus_stack       task_run_id · position int · node_id          (bottom = the task's root node)
edges             workspace_id · from_node · to_node · type (detour|side|depends_on)

evidence          workspace_id · id ("E11") · target_kind (node|concept) · target_id
                  · signal (understands|gap|unclear) · observation
                  · source (message|attachment) · message_id · turn_id · created_at

turns             id · task_run_id · seq · client_message_id (idempotency) · learner_message_id
                  · positions text[] · decision jsonb · validation jsonb · kit jsonb
                  · tutor_message_id · status (received|decided|answered|failed) · created_at
messages          id · workspace_id · task_run_id · role (learner|tutor) · seq
                  · text · attachments jsonb · content_blocks jsonb (raw, replayed unchanged)
                  · mode (normal|side) · created_at
changes           id ("5.3" = turn.seq . ordinal) · task_run_id · turn_id · kind · payload jsonb
                  · story_line text · depth int · node_ids · evidence_ids · created_at
pending_discoveries  workspace_id · task_run_id · discovery_type (misconception|alternative_explanation|new_concept)
                  · concept_id · text · evidence_id
tool_calls        turn_id · agent · tool · args jsonb · refused bool · ordinal
llm_calls         turn_id · agent · model · input_tokens · output_tokens · cache_read_tokens
                  · stop_reason · cost_usd · created_at
```

**How the design's "files" are served:**

| design path | served by a tool from |
|---|---|
| `concepts/C15` | `concepts` + `concept_sections` + `concept_anchors` |
| `tasks/T3/task.md` | `tasks` (never `reference_solution`, §8.6) |
| `learner/graph/knowledge.md` | the computed view `concept_knowledge` (§5.4) |
| `learner/graph/open-issues.md` | `nodes` with lifecycle OPEN outside the current run |
| `learner/journey/T3.md` | `task_runs.journey_text` |
| `learner/journey/T3.transcript.md` | `messages` of that run |
| `session/*` | `focus_stack`, `nodes`, `changes`, `messages` of the open run |
| `repo/…` | the real files under `repo_path` (read-only) |

---

## 5. The Graph: State Rules

### 5.1 Node state (A1)

| part | values | stored? |
|---|---|---|
| lifecycle | OPEN → RESOLVED, or OPEN → DROPPED | yes |
| attention | focused (exactly one per open run) · paused_on_stack (on the focus stack, waiting) · set_aside | yes |
| readiness | blocked when a `depends_on` target is still OPEN; otherwise ready | **no**, always computed |

### 5.2 Graph changes (inside a decision)

| change | fields | effect |
|---|---|---|
| `create_issue` | `temp_id, category, title, parent_id, closes_when?, concept_id?` | new OPEN issue node. Code assigns the short id (I4) and maps `temp_id` to it. |
| `set_focus` | `node_id` | the node becomes the focus and is pushed on the stack |
| `pause` | `node_id, return_note` | the node leaves focus and stays on the stack with a return note |
| `save_for_later` | `node_id` | the node is set aside: saved for later, like I3 in T3 |
| `resolve` | `node_id` | lifecycle RESOLVED; popped if it is on the stack |
| `drop_wrong_diagnosis` | `node_id, reason` | lifecycle DROPPED (a wrong diagnosis); popped if it is on the stack |
| `add_evidence` | `target_id (node or concept id), observation, signal (understands\|gap\|unclear), source (message\|attachment)` | new evidence. Code assigns the E-id. |
| `link_to_concept` | `node_id, concept_id (or null)` | sets or clears the bank link, at any time |
| `note_misconception` | `node_id, misconception` | a misconception seen in the learner's own words |
| `add_dependency` | `node_id, depends_on_id` | a `depends_on` edge (feeds readiness) |
| `queue_discovery` | `discovery_type (misconception\|alternative_explanation\|new_concept), concept_id?, text, evidence_id` | queued; written to the bank at close (§9.4) |

### 5.3 Validation rules

All of these are code. A decision that breaks any rule is rejected as a whole, and nothing from it is applied.

| rule | check |
|---|---|
| V1 | It matches the decision schema (§7.4). `continue` has no `tutor_kit` and no `designer_note`. Other decisions have a `tutor_kit`. |
| V2 | Ids exist in this workspace. Every `ref` used is created in the same decision. |
| V3 | After applying: exactly one focus, unless the decision is `complete_task` or `park_task`. |
| V4 | `start_detour`: the new focus is a node created now or an existing OPEN node. The old focus gets a `pause` with a non-empty `return_note`. |
| V5 | `return_from_detour`: the orchestrator does not choose. **Code picks the closest paused node on the stack that is ready** (architecture §7A). It fails if there is none. |
| V6 | `resolve` needs at least one `understands` evidence on that node from **this** turn or an earlier turn of this run. |
| V7 | `complete_task` (the root task): there is `understands` evidence of the task's purpose in this run, **and** every concept in `tasks.concepts` computes to `known` (§5.4). |
| V8 | Tutor kit template names exist in `config/tutor/templates/`. State keys exist in `state.yaml`. Every readable path exists and passes the gates (§8.6). |
| V9 | `link_to_concept`, `add_evidence` on a concept, and `queue_discovery` with a concept: the concept exists. |
| V10 | `queue_discovery` cites an evidence id that exists. |
| V11 | **A4:** `continue` may contain only `add_evidence`, `note_misconception`, `link_to_concept` and `queue_discovery`. |
| V12 | `drop_wrong_diagnosis` and `resolve` on the root task only through `complete_task`. |
| V13 | `verify_learning`: the focus is the root task (stack depth 1), and there is `understands` evidence of the task's purpose in this run. |
| V14 | `complete_task`: the focus is the root task (stack depth 1). Inside a detour, return first. This adds to V7. |

There is **no depth limit** (D9).

### 5.4 Concept status, computed (never stored)

A SQL view, `concept_knowledge`, computes each concept's status from its evidence. That evidence is either on the concept directly, or on a RESOLVED node whose `bank_concept_id` is that concept:

| status | rule |
|---|---|
| no evidence | no evidence at all |
| known | the latest evidence is `understands` |
| missing | the latest evidence is `gap` |
| uncertain | the latest evidence is `unclear` |

A late link, a removed link or new contrary evidence recomputes the status automatically. There is no help level (D10).

---

## 6. One Learner Turn

`POST /workspaces/{id}/messages` with `{client_message_id, text, attachments[], mode}`.

```text
 0  take the workspace write lock (409 if a turn is already running)
 1  idempotency: if client_message_id exists, resume that turn from its status
 2  save the learner message → turn.status = received                 (own small txn)
 3  ORCHESTRATOR: build context (§7) → call → submit_decision
      invalid (§5.3)? → one retry with the validation errors appended
      still invalid, refused, or API error → decision = {"decision":"continue"} (logged)
 4  COMMIT (one transaction):
      apply changes · write evidence · write `changes` rows with story lines + depth
      · turn.status = decided · workspace.revision + 1
 5  TUTOR (streamed to the client, §8): conversation + new user turn
      (learner text + attachments + <tutor_kit> block if the decision is not continue)
 6  save the tutor reply (raw content blocks) · turn.status = answered · revision + 1
 7  if the decision was `complete_task` → close the task (§9.2) → open the next one (§9.3)
    if it was `park_task` → park (§9.6)
 8  release the lock
```

**Failure rules**

- Step 2 is durable before any model call, so the learner's message is never lost (the same pattern as tutor_v2).
- The graph is committed **before** the tutor runs. If the tutor fails, a retry with the same `client_message_id` re-runs only step 5. It never re-runs the orchestrator, and nothing is applied twice.
- Model calls never happen inside a database transaction.

---

## 7. The Orchestrator

### 7.1 Each call is fresh (A6)

No conversation carries over between turns. Its memory is the graph.

```text
system:   config/orchestrator/base.md                                   (fixed, cached)
tools:    search_bank · read_concept · read_reference · read_file
          · search_repo · read_journey · submit_decision               (fixed, cached)
user:     [position pieces]   chosen by code (§7.2)
          [graph view]        rendered by code (§7.3)
          [last tutor message]
          [learner message + attachments]
          [menu]              the decisions possible now (§7.5) + template names, one line each
```

### 7.2 Position pieces: code picks them from the graph (D3)

`config/orchestrator/positions.yaml` maps each position to a condition and a piece. Code evaluates every condition on each turn, and every piece whose condition holds is added in this order:

| position | condition (computed by code) | piece |
|---|---|---|
| `opening` | first turn of a task run | how to read a task's first reply |
| `on_task` | stack depth = 1 (the focus is the root) | stay with the task; a question is evidence, not a gap |
| `in_detour` | stack depth ≥ 2 | keep the return path; resolve when `closes_when` is met |
| `deep` | stack depth ≥ 4 | check you are still serving the root; prefer resolving upward |
| `back_from_detour` | the previous decision was `return_from_detour` | bridge from the return note before anything new |
| `stuck` | 3 or more turns on the same focus with no new `understands` evidence | change the approach (`reframe_explanation`), or show the answer under the gate (`show_answer`) |
| `goal_met` | `understands` evidence of the purpose exists, but some needed concept is not `known` | verify the missing concepts with one probe each |
| `saved_waiting` | a set_aside (saved) node exists in this run | notice when the learner wants to go back to it; it then becomes an ordinary detour |
| `back_from_park` | first turn after a park | open from the return note |
| `carried` | OPEN nodes carried from earlier tasks | notice when the learner's words touch one |

### 7.3 The graph view (code-rendered, compact)

```text
TASK T3 (fix) · goal: guests get a real answer again · needs C15 C17 C13
STACK  T3 › I1 › [I2]            ← focus in brackets
  I2  issue·codebase · "Why the loop on line 684 runs 0 times for a guest" · concept: none
      closes_when: (not set)
  I1  paused_on_stack · return_note: "you get last([]); now connect it to label" · concept: C15
  T3  paused_on_stack · return_note: "you have the traceback; line 722 reads label"
OPEN ELSEWHERE  —
CONCEPTS  C15 missing · C17 known · C13 no evidence
RECENT EVIDENCE  E5 I1 understands · explained x after the loop
```

### 7.4 The decision (D2: if/else)

**On track, nothing to change:**

```json
{"decision": "continue"}
```

**On track with evidence (A4):**

```json
{"decision": "continue",
 "graph_changes": [{"change": "add_evidence", "target_id": "T3", "observation": "reproduced the bug as a guest",
                    "signal": "understands", "source": "attachment"}]}
```

**Anything else**, here T3 step 3:

```json
{
  "decision": "start_detour",
  "assessments": [{"kind": "GAP_DISCOVERED", "category": "knowledge"}],
  "graph_changes": [
    {"change": "create_issue", "temp_id": "new1", "category": "knowledge", "parent_id": "T3",
     "title": "A loop variable only exists if the loop ran",
     "closes_when": "they explain why label is unbound for a guest", "concept_id": "C15"},
    {"change": "note_misconception", "node_id": "new1",
     "misconception": "expects label to exist because it is written in the loop"},
    {"change": "add_evidence", "target_id": "C17", "observation": "made the hidden error visible",
     "signal": "understands", "source": "attachment"},
    {"change": "add_evidence", "target_id": "C15", "observation": "did not know label can be left unset",
     "signal": "gap", "source": "message"},
    {"change": "pause", "node_id": "T3", "return_note": "you have the traceback; line 722 reads label"},
    {"change": "set_focus", "node_id": "new1"}
  ],
  "tutor_kit": {
    "templates": ["teach_one_concept", "experiment_first"],
    "state_keys": ["current_focus", "return_to", "misconception_to_watch", "closes_when"],
    "readable_files": [{"path": "concepts/C15", "reason_this_turn": "I1 links to C15: use its Examples"}]
  },
  "designer_note": "label is unset because the loop never ran for a guest"
}
```

| key | meaning |
|---|---|
| `decision` | `continue` · `start_detour` · `return_from_detour` · `verify_learning` · `change_approach` · `complete_task` · `park_task` |
| `assessments` | what the orchestrator detected, a list (several per turn are allowed); each has a `kind` and a `category` |
| `graph_changes` | the changes to the graph (§5.2) |
| `tutor_kit` | `templates` · `state_keys` · `readable_files`, each file with a `path` and its `reason_this_turn` |
| `designer_note` | one line, for the designer's view only. The learner never sees it. |

`submit_decision` is a **strict** tool (the schema is enforced). Code then enforces the if/else (V1, V11). The run allows at most `max_tool_rounds` reading-tool rounds before it must submit.

### 7.5 The decision menu: code removes impossible decisions (D13)

Before each call, code works out which decisions are possible from the current state, and the `[menu]` lists only those. The orchestrator can't pick an impossible one. The validation rules (§5.3) still run after the call, as the safety net.

```text
                     ON THE TASK (stack = [T3])        IN A DETOUR (stack = [T3, I1, …])
                     ──────────────────────────        ─────────────────────────────────
continue             ✓                                 ✓
start_detour         ✓                                 ✓  nested; no depth limit (D9)
return_from_detour   ✗  nothing to return to (V5)      ✓
verify_learning      ✓  only when the goal is met      ✗  (V13)
change_approach      ✓                                 ✓
complete_task        ✓  only when the goal is met      ✗  (V14)
                        and every concept is known (V7)
park_task            ✓  always                         ✓  always
```

"The goal is met" means there is `understands` evidence of the task's purpose in this run.

**One source of truth.** `orchestrator/menu.py` builds the menu from the same conditions as V5, V7, V13 and V14, so the menu and the validation can never disagree. A decision that is not on the menu fails those same rules.

**Why:** an impossible option costs a rejected call and a retry (§6, step 3). Removing it before the call is cheaper, and the orchestrator has fewer ways to go wrong.

---

## 8. The Tutor

### 8.1 One conversation per task run, append-only

```text
system:   config/tutor/base.md                                        (fixed, cached)
tools:    read_concept · read_file · search_repo · read_journey · read_transcript
          · read_reference · write_journey                            (fixed, cached)
messages: [user: learner turn 1 + <tutor_kit>] [assistant] [tool_use/result] … [user: turn n (+ <tutor_kit>)]
```

- Earlier turns are **never edited**. Haiku 5.5 invalidates thinking blocks when history changes. Assistant content blocks are stored raw and replayed unchanged.
- The kit goes **at the end of the user turn**, not in a mid-conversation system message, because Haiku 5.5's documentation doesn't say it supports those. If support is confirmed later, switching is one line in `kit.py`.
- On `continue`, there's no kit block. The latest kit stays in force, both for the tutor and for the tool gates.

### 8.2 The default readable set at task open

These are readable without a kit line:
- `tasks/T3/task.md`
- the concepts the task needs
- the repo files the task lists
- `learner/graph/knowledge.md`, only the rows for those concepts
- `learner/journey/INDEX.md`

The tutor kit's `readable_files` list adds to this set for the current focus.

### 8.3 Templates: the template name IS the file name (D2)

| name | file | old name |
|---|---|---|
| `introduce_task` | `templates/introduce_task.md` | intro · task_intro |
| `keep_goal_in_view` | `templates/keep_goal_in_view.md` | frame · task_frame |
| `guide_debugging` | `templates/guide_debugging.md` | debug · guide_debugging |
| `teach_one_concept` | `templates/teach_one_concept.md` | detour · detour_concept |
| `experiment_first` | `templates/experiment_first.md` | example · experiment_first (the learner runs it in their own editor, D7) |
| `guided_trace` | `templates/guided_trace.md` | trace · guided_trace |
| `bridge_back` | `templates/bridge_back.md` | bridge · resume_bridge |
| `guide_fix` | `templates/guide_fix.md` | fix · guide_fix |
| `answer_side_question` | `templates/answer_side_question.md` | side · park_side_question |
| `probe_understanding` | `templates/probe_understanding.md` | probe |
| `close_task` | `templates/close_task.md` | close |
| `reframe_explanation` | `templates/reframe_explanation.md` | reframe. **New**: no existing piece covers being stuck (architecture §4, STAGNATING) |
| `show_answer` | `templates/show_answer.md` | answer. **New**: no existing piece shows the answer; it sits behind the gate (A8) |

The engine renders the block. Here is T3 step 3:

```text
<tutor_kit>
[teach_one_concept] Pause the task. Teach one idea only. Don't solve the task here.
[experiment_first] Start with a tiny example the learner runs in their own editor. Ask for a prediction first.
current_focus: I1 · A loop variable only exists if the loop ran
return_to: T3 · you have the traceback; line 722 reads label
misconception_to_watch: expects label to exist because it is written in the loop
closes_when: they explain why label is unbound for a guest
readable now: concepts/C15 (I1 links to C15: use its Examples)
</tutor_kit>
```

### 8.4 State keys (`config/tutor/state.yaml`)

`task_goal` · `known_concepts` · `current_focus` · `return_to` · `misconception_to_watch` · `closes_when` · `probe_target` · `open_issues` · `journey_so_far`. Code fills each value from the graph.

### 8.5 Tools: every tool's description is its guide

Each guide is loaded from `config/tools/<name>.md` and gives what · when · when not · how. The "why this turn" part comes only from the kit.

| tool | args | returns | gate (refused, with a reason, when...) |
|---|---|---|---|
| `read_concept` | `id, section` | one section | the concept isn't in the readable set |
| `read_file` | `path, line, around=20` | the lines around one line | outside the repo, or not in the task's files and not listed in the kit |
| `search_repo` | `query` | up to 20 hits | never |
| `read_journey` | `task` | the journey entry | not listed in the kit |
| `read_transcript` | `task, last_n` | the last n messages of that run | not listed in the kit |
| `read_reference` | `task` | the reference solution | the A8 gate is closed |
| `write_journey` | `text` | ok | not a close turn |

Every call is logged in `tool_calls`, including refused ones.

### 8.6 Gates (architecture §24)

| resource | open when |
|---|---|
| reference solution, **tutor** | the tutor kit has `show_answer` **and** 2 or more `gap` evidence on the current focus in this run (A8) |
| reference solution, **orchestrator** | always (it judges "built correctly", D8, A2) |
| `write_journey` | the turn is the close turn (§9.2) |
| a past journey or transcript | listed in this turn's kit |

### 8.7 Streaming, compaction and refusals

- **Streaming:** the reply streams to the client as SSE `tutor.delta` events.
- **Compaction:** when the run's conversation passes `compact_at_tokens` (80K), the engine:
  1. writes a summary (`session/summary`) with one Haiku call;
  2. starts a **new** conversation whose first user turn holds the summary as a readable file and the current kit.

  The learner sees nothing change (architecture §18).
- **Refusals:** on `stop_reason: "refusal"`, the learner gets a short neutral reply, the turn is marked `failed`, and the refusal category is logged. Haiku 5.5 has no server-side fallback model.

---

## 9. The Task Lifecycle

### 9.1 Open

1. Create a `task_run` and the root node (crafted, focus).
2. Run a first tutor turn with no learner message, using the kit `introduce_task` + `keep_goal_in_view`. After a previous task, the kit is `bridge_back` + `introduce_task`, with `journey/<previous>` readable: the existing bridge piece, fed the last task's journey.

The orchestrator and the tutor both start fresh.

### 9.2 Close (`complete_task` passed V7)

1. A tutor turn with the kit `close_task`. `write_journey` is open, and the tutor writes the journey entry.
2. Code then, in one transaction:
   - resolves the root;
   - writes the INDEX line (from the journey);
   - applies the pending discoveries (§9.4);
   - leaves OPEN nodes as carried (they keep `created_run_id`, so they show as "open elsewhere" later);
   - sets the run to `resolved`.

### 9.3 Next

The engine opens the first task in `ladder_position` order that has no resolved run. It opens with fresh agents (§9.1). In the conversation API, the learner's thread just continues; a divider marks the new task.

### 9.4 Discoveries (architecture §17)

`queue_discovery` changes are queued in `pending_discoveries`. At close, code writes them:

| discovery_type | written to |
|---|---|
| `misconception` | a `concept_sections` row (misconceptions), `source = discovered`, `found_in = {task, turn, node}`, plus `evidence_id` |
| `alternative_explanation` | a `concept_sections` row (other_ways), labeled the same way |
| `new_concept` | a new `concepts` row with the next D-id, `source = discovered`. The node that found it gets `bank_concept_id = D…` |

Crafted rows are never updated.

### 9.5 Side questions (D11): the existing pieces, nothing new

A side question becomes an ordinary **issue** node, recorded on the graph and shown on the map. The orchestrator handles it with pieces that already exist, picking by situation:

| situation | handled with | in T3 |
|---|---|---|
| not blocking; the learner just wondered | answer briefly with the `answer_side_question` template, then `save_for_later` (set_aside) | step 9: I3 "how the test fakes OpenAI" |
| the learner wants to go there now | an ordinary detour: `start_detour`, `pause` with a `return_note`, then `teach_one_concept` / `guided_trace` / `experiment_first` | the same as I1 |
| it is really part of the task | `continue` | step 1: "where does this message come from?" |

A saved issue is carried while it stays open, and any later task can pick it up (architecture §20).

The frontend's existing "Side question" switch is stored on the message as `mode: side`. The orchestrator sees it as part of the message: a hint, not a rule.

### 9.6 Park and resume

- **Park:** a `park_task` decision, or `POST /park`. The run becomes `parked`, and the stack, nodes and conversation stay as they are.
- **Resume:** `POST /resume` opens fresh agents on the same run. The first tutor turn uses `bridge_back` with the focus's return note. The story shows `↩ Came back to … · picking up: …`.

---

## 10. The Story Map (architecture §21)

When a change is committed, `story/story_lines.py` turns it into **one plain-English line**. The patterns come from `config/story.yaml`, and the line is written in the same transaction as the change.

| change | line pattern |
|---|---|
| run opened | `• Started {task.goal}` |
| `add_evidence` (`understands`) on a node | `✓ Did {observation}` |
| `add_evidence` (`understands`) on a concept | `✓ Proved {observation}` |
| `add_evidence` (`gap`) | `~ Almost {observation}` |
| `create_issue` + `set_focus` at depth 1 | `⚠ Found a gap {designer_note}` then `↳ Went to learn first — {title}` |
| `create_issue` + `set_focus` deeper | `↳ Needed first — {title}` |
| `save_for_later` | `○ Saved for later {title}` |
| `resolve` | `★ Cleared — {title}` |
| `return_from_detour` (code-picked) | `↩ Came back to {title}`, plus `picking up: {return_note}` on the next line |
| a `note_misconception` belief later contradicted by `understands` evidence | `✓ Cleared up — {belief}` (struck through) |
| `drop_wrong_diagnosis` | `✕ Not the problem after all — {title}` |
| run resolved | `★ Done — {goal} · you now know {concepts}` |
| the current focus (computed at read time, not stored) | `◉ You are here — {last tutor question}` |

**Contract:**
- One line per change.
- `depth` is the stack depth when the change was committed.
- Every line keeps `node_ids`, `evidence_ids` and `turn_id`, so the frontend can open the conversation at that turn.
- No internal word (OPEN, focus, GAP_DISCOVERED) ever appears in a line.

---

## 11. The Crafting Pipeline (architecture §22)

A background job starts on import. One job per workspace, in the same process; progress goes out as SSE.

| stage | runs on | does |
|---|---|---|
| prepare_repo | code | clone (reused `importer.py`); drop secret files (`.env*`, keys); outline Python files with the reused `structure.py`; list candidate entry points |
| concept crafter | Agent SDK + Haiku 5.5 | built-in `Read`, `Glob`, `Grep` (cwd = the repo copy, read-only) + MCP tools `write_concept`, `list_concepts`. Follows `config/crafters/concepts.md` (the four size tests). |
| VALIDATE 1 | code | per concept, at write time: schema, claim, proof, at least one misconception, every anchor's text found under its symbol (hash stored). At the end: no prerequisite cycles, no duplicates. |
| task crafter | Agent SDK + Haiku 5.5 | `Read`, `Glob`, `Grep` + `list_concepts`, `read_concept`, `write_task` (goal, tier, story, why, concepts, files, `reference_solution`, `real_bug`) |
| VALIDATE 2 | code | concepts and files exist; a reference solution is present. Warnings: a tier with no task, a concept with no task. **Nothing runs** (D7, D8). |
| ladder builder | **code** | tier order, then prerequisites first, then at most 2 new concepts per task (greedy; a violation is logged, not fatal) → `ladder_position` |
| VALIDATE 3 | code | every task appears once |

**What the Agent SDK is allowed to use:**
- Allowed: only `Read`, `Glob`, `Grep` and our MCP tools.
- Blocked: `Bash`, `Write`, `Edit`, `WebFetch`, `WebSearch` and `Task`.
- Same setup as tutor_v2's `ClaudeAgentAdapter` (`setting_sources=[]`).

Repository text is data, never instructions, and the crafter prompts say so.

**Progress events** on `GET /workspaces/{id}/crafting/stream`:
`stage {name}` · `concept {id, name}` · `task {id, goal}` · `done` · `failed {stage, error}`.

---

## 12. API

### 12.1 Learner routes

All require the Supabase JWT (reused `auth.py`).

| route | body / query | returns |
|---|---|---|
| `GET /health` | — | `{status: "ok"}` (no auth) |
| `GET /workspaces` | — | the user's workspaces: status, current task, progress |
| `POST /workspaces/import` | `{name, git_url}` | `{workspace_id}` and starts crafting |
| `GET /workspaces/{id}/crafting/stream` | — | SSE (§11) |
| `POST /workspaces/{id}/start` | — | SSE: the first task's opening turn |
| `POST /workspaces/{id}/messages` | `{client_message_id, text, attachments[], mode}` | SSE: `tutor.delta` · `tutor.done {message_id}` · `task.closed {task}` · `task.opened {task}` · `error` |
| `GET /workspaces/{id}/conversation` | `before, limit` | messages across all tasks, with task dividers |
| `GET /workspaces/{id}/story` | `task` | story lines (§10) plus the computed "You are here" |
| `GET /workspaces/{id}/sidebar` | — | ladder tasks, each with its nodes nested |
| `GET /workspaces/{id}/tree` · `/file` | `path` | the repo explorer (read-only) |
| `POST /workspaces/{id}/park` · `/resume` | — | parked state / SSE resume turn |
| `GET /workspaces/{id}/events` | — | SSE `revision {n}`; clients refetch story, sidebar and conversation |

An attachment is `{kind: "code" | "output" | "text", label, text}`, sent as text only (D7). The frontend's Editor → **Attach** produces `code`.

### 12.2 What the learner never sees

Orchestrator output, assessments, positions, kits and internal states never appear on learner routes.

### 12.3 Designer routes (`DEV_USER_IDS` only)

| route | returns |
|---|---|
| `GET /dev/workspaces/{id}/turns?task=` | per turn: learner message, positions used, decision JSON, validation result, kit, tokens and cost |
| `GET /dev/workspaces/{id}/graph?task=&turn=` | the graph as it was at that turn (by replaying `changes`). This is the live version of `t3-orchestrator-map.html`. |

---

## 13. Security and Limits

1. **Auth:** Supabase JWT (ES256 via JWKS), as tutor_v2. Every query filters on the workspace owner, plus row-level security in Postgres.
2. **Paths:** every file tool resolves inside `repo_path`, and symlinks and `..` are refused (the tutor_v2 jail). Import keeps the reused SSRF block and https-only git URLs.
3. **Token budget:** every model call is logged in `llm_calls`. The orchestrator's prompt targets 20K tokens or less. The tutor compacts at 80K. A call over 100K is logged as a warning, because it costs 5×.
4. **Prompt injection:** repository text, attachments and pasted output are wrapped as data. Each agent's base prompt says they are never instructions.
5. **Secrets:** scrubbed before any crafter reads the repo. They are never written to `concept_anchors.line_text`.
6. **Concurrency:** one write per workspace at a time (the tutor_v2 lock pattern), and one Uvicorn worker.

---

## 14. Reuse and Delete

| from tutor_v2 | fate |
|---|---|
| `auth.py` | **reused** unchanged |
| `importer.py` | **reused** unchanged |
| `structure.py` | **reused** for the crafting prepare_repo outline |
| `app.py` per-workspace write lock, SSE `event()` helper, scan replay log | **pattern reused**, rewritten |
| `sdk_runtime.py` permission setup (`allowed_tools`, `disallowed_tools`, `setting_sources`) | **pattern reused** for the crafters |
| `Dockerfile` (Node + Claude CLI for the Agent SDK), `fly.toml` | **adapted**; deployed as a second Fly app until the switch |
| `routing.py`, `packets.py`, `contracts.py`, `orchestrator.py`, `session.py`, `driver.py`, `recorders.py`, `semantics.py`, `graph_projection.py`, `journey_*`, `references.py`, `aside_instructions.py`, `registry.py`, `db.py`, `schema.sql`, `learner_model.py`, `services.py`, `parsing.py`, `domain.py`, `api.py`, `factory.py`, `transport.py`, `streaming.py` | **deleted** at the switch |

---

## 15. Tests and Acceptance

| level | what | model |
|---|---|---|
| unit | every rule V1–V14; the decision menu (§7.5); each position condition; each story pattern; kit rendering; every tool gate; `concept_knowledge` | none |
| replay **T3** | a scripted orchestrator (the 11 decisions of T3) and a scripted tutor drive 11 turns. Check the graph, the focus stack, the evidence ids and the story lines against architecture §21 line by line. | fakes |
| acceptance **§20** | in T4, the learner asks about the fake client. The carried I3 is refocused, resolved, and the learner is returned to T4. No crafter runs, no task is created. | fakes |
| crafting | a small fixture repo → concepts pass VALIDATE 1, tasks pass VALIDATE 2, the ladder obeys the rules | fakes for the SDK |
| failure | invalid decision → retry → continue; tutor failure → retry re-runs only the tutor; refusal → neutral reply | fakes |
| live smoke | one real task on a small repo with Haiku 5.5. Record decisions, cost per turn and the largest prompt. | **real** (costs money; run by hand) |

The agents are reached through one seam, `claude_client.py`, so every test except the live smoke runs offline (the tutor_v2 pattern).

---

## 16. Build Order

| step | delivers | done when |
|---|---|---|
| M0 | package skeleton, settings, config loader + a starter config, Postgres migrations on Supabase, reused auth | the server starts; the config check passes |
| M1 | the graph: model, rules V1–V14, apply, `concept_knowledge`, story projection | unit tests green |
| M2 | the orchestrator: positions, decision menu, graph view, decision schema, run loop | the T3 decisions validate and commit (fakes) |
| M3 | the tutor: conversation store, kit, tools + gates, streaming, compaction | gates and streaming tests green (fakes) |
| M4 | the turn pipeline + learner API + SSE | **the T3 replay passes end to end** |
| M5 | the task lifecycle: open, close, next, park, resume, discoveries, side questions | **the §20 acceptance passes** |
| M6 | crafting: prepare_repo, the concept and task crafters on the Agent SDK, the ladder builder, validation, progress stream | the fixture repo crafts end to end |
| M7 | designer routes, the live smoke with Haiku 5.5, cost report; deploy as a second Fly app | the smoke run is reviewed by you |
| M8 | the switch: point the frontend at the new app (frontend step), then delete tutor_v2 | your call |

---

## 17. Risks

| risk | what we do |
|---|---|
| Haiku 5.5 may diagnose or judge evidence too weakly for the orchestrator | M7 measures it on real turns. The model is one line in `models.yaml`. |
| Haiku 5.5 may not accept mid-conversation system messages | The kit already goes in the user turn (§8.1). |
| Large repos can push the crafters past 100K tokens (5× price) | Log it in M6. Fan the concept crafter out per module if needed (architecture §16). |
| Pasted code is self-reported (D7) | Evidence keeps its `source`, so the orchestrator knows what was pasted. A later phase can add a real run. |
| `continue` without evidence (if A4 is rejected) | The on-track story lines disappear. Decide A4 before M1. |
