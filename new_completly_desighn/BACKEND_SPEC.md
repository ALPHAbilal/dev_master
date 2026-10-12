# Backend spec: `tutor_graph`

Draft 0.2 · 2026-10-12 · builds `LEGO.md` (draft 0.19) behind the contract in `FRONTEND.md` (draft 0.5), on Supabase, with Claude as `BUILD_WITH_CLAUDE.md` maps it. Replaces draft 0.1, which is in `archive/new_completly_desighn/`.

**Naming rule:** no abbreviations; every ID appears with its name (task T3, issue I1, concept 15, box 2). On the learner's screen, no IDs at all (`FRONTEND.md`, brand rule).

---

## 0. Where we stand

### Decided

```
 database        Supabase Postgres is the only store of truth; Supabase Auth signs learners in
 server          one Python service (FastAPI) on Fly, in Frankfurt, next to the database
                 (eu-central-1)
 model           Claude Haiku 5.5 (claude-haiku-5-5) for every agent
 agents          orchestrator, evaluator, tutor on the Claude API; the two crafters on the Agent SDK
 agentic layer   LEGO.md 0.19 as written: cards, pieces, plates, the question tree, the task sheet,
                 the stuck ladder, checkpoints
 contract        FRONTEND.md §7–§8; the frontend is built and runs it in demo mode
 context         fresh agents per task; instructions are never history; no caching, no compaction
 phase 1         no code runs on the server; the learner pastes code and output
 migration       a new package next to tutor_v2; tutor_v2 is deleted at the switch
```

### Before the build starts

```
 1  restore the Supabase project     it is paused (status INACTIVE)            needs your OK
 2  one Haiku 5.5 test call          confirms structured outputs and the size  needs the API key
                                     of our answer format
 3  a sign-in screen                 the frontend reads a Supabase session     frontend, small
                                     but cannot create one yet
```

### My proposals for the open holes of LEGO.md §16

```
 hole                                         proposal
 ───────────────────────────────────────────  ──────────────────────────────────────────────────
 an exact match of the learner's words is     code compares after folding case, spaces, quote
 fragile                                      marks and dashes
 a proof spread over two turns                learner_words becomes a list of up to 3 quotes;
                                              each one must be found
 the proof is pasted code                     a message's attachments count as the learner's
                                              words
 the words prove they were said, not that     accepted: code checks where the words come from;
 they prove the box                           the evaluator's verdict is the judgment
 "kind" is a number                           kind becomes a name: "debugging", not 7
 one turn mixes kinds; kinds flip             accepted: one kind per turn, the main one; the
                                              tutor's instructions follow it
 a box explained inside an issue ticks only   evaluate may judge an unticked box inside an issue
 on the next turn                             too, so it ticks at once
 the issue → concept link is a guess          accepted: it is the orchestrator's label
 the tutor's new pieces are not written       written during the build (§20, step 3), as config
```

---

## 1. The system

```
 FRONTEND · Vercel               BACKEND tutor_graph · Fly, Frankfurt                  SUPABASE · eu-central-1
 ─────────────────               ─────────────────────────────────────                 ───────────────────────
 sidebars · map ·      HTTPS     api ── the Supabase session's token                   Auth: sign-in, tokens
 conversation ·      ────────►    │                                                    Postgres 17, schema "tutor"
 editor · codebase · ◄────────    ├─ engine · code only ─────────── reads, writes ───►
 import page         events       │    where · checks · cards · tree · effects ·
                                  │    sheet · stuck · story · checkpoints
                                  ├─ agents · Claude API · Haiku 5.5
                                  │    orchestrator ── evaluate ──► evaluator
                                  │    tutor, streamed
                                  └─ preparing · Agent SDK · Haiku 5.5
                                       copy → concept crafter → task crafter → order
                                  repository copies on the Fly volume, read-only
```

```
 WHO              DOES
 ───────────────  ─────────────────────────────────────────────────────────────────────────────
 code             decides where we are, which card, which pieces, which branches exist; checks
                  every answer; writes every change at once, in one transaction
 orchestrator     names one leaf, plus a kind, plus a why when stuck; calls the evaluator
 evaluator        judges one box or one issue against the learner's own words
 tutor            talks to the learner with the pieces code snapped in
 crafters         write the concepts and the tasks, once per codebase
```

---

## 2. Package layout

```
agentic_tutor/backend/tutor_graph/
├── __main__.py              starts the server: one Uvicorn worker
├── settings.py              environment variables (§3.4)
├── api/
│   ├── app.py               the routes of §15, auth, errors
│   ├── snapshot.py          builds the contract's Snapshot and LadderTask from the database
│   └── streams.py           the two event streams: the workspace stream, the preparing stream
├── engine/                  code only; never calls a model
│   ├── where.py             the stack: where we are, the card (B or C), depth, focus
│   ├── facts.py             every fact a piece can ask for (LEGO §12, facts)
│   ├── checks.py            the yes/no questions code asks the graph (LEGO §12, checks)
│   ├── cards.py             which pieces go on which plate, per card (LEGO §7)
│   ├── tree.py              builds this turn's answer format from the question tree (LEGO §3)
│   ├── answer_checks.py     checks the orchestrator's answer (§6.4)
│   ├── effects.py           every effect, in one transaction (§9)
│   ├── sheet.py             the task sheet (§10)
│   ├── stuck.py             the stuck ladder (§11)
│   ├── story.py             effect → story line
│   ├── checkpoints.py       one checkpoint per turn; pull_checkpoints (§12)
│   ├── words.py             finds the learner's quoted words in their turns (§7.3)
│   └── turn.py              one learner turn, end to end (§5)
├── agents/
│   ├── claude.py            the one seam to the Claude API: calls, retries, refusals, cost log
│   ├── orchestrator.py      its plate, its tool loop, its structured answer (§6)
│   ├── evaluator.py         its plate, its verdict; the only reader of the answer key (§7)
│   ├── tutor.py             its system prompt, history, tools, streaming, stop (§8)
│   ├── tools.py             read_concept · read_file · search_repo · read_journey · Read · Grep
│   └── pieces.py            loads the config pieces; fills their studs
├── tasks/
│   ├── lifecycle.py         open (card A) · close (card E) · next
│   └── discoveries.py       saved side questions and concept gaps → the concept bank
├── preparing/               the crafting line (LEGO §13)
│   ├── job.py               runs the four steps; publishes the preparing events
│   ├── copy_repository.py   clone, scrub secrets, outline (reused importer.py, structure.py)
│   ├── concept_crafter.py   Agent SDK + write_concept
│   ├── task_crafter.py      Agent SDK + write_task
│   ├── order.py             code: the ladder
│   └── validate.py          the checks after each crafter
├── db/
│   ├── pool.py              psycopg 3 async pool; transaction() helper
│   ├── queries.py           all SQL lives here
│   └── migrations/          SQL migrations for Supabase (§4)
├── reused/                  from tutor_v2, unchanged: auth.py · importer.py · structure.py
└── tests/

agentic_tutor/backend/config/
├── models.yaml              per agent: model, effort, max tokens, tool rounds
├── tree.yaml                the questions, their options and short descriptions (LEGO §3)
├── kinds.yaml               the ten kinds of work: name, description, tutor pieces (LEGO §4)
├── stuck.yaml               the levels, their whys, each why's tutor piece (LEGO §9)
├── cards.yaml               per card: the fixed and gated pieces of each plate (LEGO §7)
├── pieces/
│   ├── orchestrator/*.md    base · on_task · in_issue · stuck · saved_waiting · deep
│   ├── evaluator/*.md       task_box · closes_when
│   └── tutor/*.md           base and every piece of LEGO §12
├── tools/*.md               one guide per tool: what · when · when not · how
├── story.yaml               story line kind → its words (the screen draws the marks)
└── crafters/                concepts.md · tasks.md
```

---

## 3. Configuration

### 3.1 `config/models.yaml`

```yaml
orchestrator:    { model: claude-haiku-5-5, effort: medium, max_tokens: 4000, max_tool_rounds: 8 }
evaluator:       { model: claude-haiku-5-5, effort: medium, max_tokens: 1500, max_tool_rounds: 4 }
tutor:           { model: claude-haiku-5-5, effort: medium, max_tokens: 4000, max_tool_rounds: 4 }
concept_crafter: { model: claude-haiku-5-5, effort: high,   max_turns: 200 }
task_crafter:    { model: claude-haiku-5-5, effort: high,   max_turns: 200 }
```

### 3.2 A piece is one Markdown file

```markdown
---
piece: teach_one_concept
for: tutor
studs: [current_focus, closes_when, misconception_to_watch]
---
Teach the one idea in {current_focus}. Stop when the learner {closes_when}.
Watch for this wrong idea: {misconception_to_watch}.
```

Code fills every `{stud}` from `engine/facts.py`. A piece names its studs; nobody picks facts by hand (LEGO §5).

### 3.3 The tree, the kinds, the ladder

```yaml
# tree.yaml (excerpt)
question_1:
  asks: what does the message show?
  options:
    progress:   moves forward on the current work, or asks about it
    problem:    wrong, blocked, unsure, or not moving
    turns_away: asks about something off the current path

# kinds.yaml (excerpt)
debugging:  { description: finding why it fails, tutor: [guide_debugging] }
a_concept:  { description: an idea they need,    tutor: [teach_one_concept, experiment_first] }

# stuck.yaml (excerpt)
levels:
  - { from_turns: 2, whys: { didnt_get_it: reframe_explanation, hasnt_said_view: ask_their_view } }
  - { from_turns: 3, whys: { step_too_big: smaller_step, lost_where_to_look: point_to_place } }
  - { from_turns: 4, whys: { needs_one_done: worked_example, too_many_paths: offer_choices } }
any_level: { frustrated: encourage_pause }
```

Changing a description, a level or a piece is a config change, never a code change.

### 3.4 Environment variables

```
 DATABASE_URL            Supabase Postgres, through the session pooler
 SUPABASE_URL            the token issuer; its public keys sign learners' tokens (reused auth.py)
 AUTH_MODE               supabase, or dev for local runs only
 ANTHROPIC_API_KEY       every model call: the Claude API and the Agent SDK
 CONFIG_DIR              the config folder
 REPOSITORY_ROOT         where codebases are cloned, on the Fly volume
 ALLOWED_ORIGINS         the frontend's origins (CORS)
```

**The startup check.** The server refuses to start when the config is broken:

- every piece named in `cards.yaml`, `kinds.yaml` or `stuck.yaml` exists;
- every stud is a fact that `facts.py` knows;
- the tree builds a valid answer format for every situation.

---

## 4. Data · Supabase Postgres

All tables live in a schema named `tutor`. Supabase's data API does not expose it. Row-level security is on, with no policies, so only the backend's database role can read or write. Every table carries `workspace_id`, and every query filters on the signed-in owner.

### 4.1 The codebase

```
 workspaces         id · owner_id → auth.users · name · git_url · repository_path
                    · preparing (running | ready | failed) · revision · created_at
 preparing_steps    workspace_id · step (copying | concepts | tasks | ordering)
                    · state (running | done | failed) · count · error · started_at · finished_at
 concepts           workspace_id · number · name · claim · proof · prerequisites (numbers)
                    · source (crafted | discovered) · created_at
 concept_sections   workspace_id · concept_number · section (what_it_is | examples |
                    misconceptions | other_ways) · position · text
 concept_anchors    workspace_id · concept_number · file · symbol · line_text · text_hash
 tasks              workspace_id · id (T3) · number · ladder_position · title · goal · tier · files
                    · status (done | current | later) · opened_at · closed_at
 boxes              workspace_id · task_id · number · concept_number (empty = the job box) · text
                    · suggested_position
 answer_keys        workspace_id · task_id · text           read by one function only (§7.4)
```

### 4.2 The learning

```
 box_ticks          workspace_id · task_id · box_number · ticked_at_turn · learner_words
 concept_progress   workspace_id · task_id · concept_number · checked · times_it_came_up
 difficulties       workspace_id · task_id · concept_number · turn · what_went_wrong
                    · learner_words · had_it_then_missed · issue_id
 issues             workspace_id · id (I1) · number · opened_in_task · parent_issue_id · title
                    · kind_of_work · closes_when · why_for_learner · concept_number · misconception
                    · status (open | saved | cleared | already_knew) · opened_at_turn · closed_at_turn
 stack              workspace_id · position · task_id or issue_id · return_note
                    bottom = the task; top = where we are
 progress           workspace_id · task_id · turn · issue_id · did
 stuck_counters     workspace_id · focus (a task or an issue) · turns_without_progress
 journeys           workspace_id · task_id · text           written by the tutor at the close
```

### 4.3 The conversation and its record

```
 turns              workspace_id · task_id · turn · client_message_id
                    · status (received | decided | answered | stopped | failed)
                    · card_at_start · card_at_end · leaf · kind_of_work · why_stuck
                    · orchestrator_answer (json) · answer_problems (json) · tutor_pieces · created_at
 messages           id · workspace_id · task_id · turn · role (learner | tutor) · text
                    · attachments (json) · content_blocks (json: the tutor's text, tool calls and
                    their results; never thinking) · created_at
 verdicts           workspace_id · task_id · turn · target (a box or an issue)
                    · verdict (met | not_met | unclear) · learner_words · words_found
 story_lines        id · workspace_id · task_id · issue_id · turn · depth · kind · text · picking_up
 checkpoints        workspace_id · task_id · turn · leaf · body (json: what the learner said, the
                    leaf, the verdicts, the tool calls, the reply, where we were)
 model_calls        workspace_id · task_id · turn · agent · model · input_tokens · output_tokens
                    · cost_usd · stop_reason · milliseconds
 tool_calls         workspace_id · task_id · turn · agent · tool · arguments (json) · refused
```

### 4.4 From the tables to the contract

```
 CONTRACT FIELD            BUILT FROM
 ────────────────────────  ──────────────────────────────────────────────────────────────────
 workspace                 workspaces, plus tasks done and tasks total
 ladder[].sheet            boxes + box_ticks + concept_progress; a concept box's text is sent
                           only once ticked, as null before
 ladder[].issues           issues opened in that task
 where                     stack: its top is the focus; the last turn's status says whether the
                           tutor is answering
 story                     story_lines
 conversation              messages: text and attachments only
 revision                  workspaces.revision, + 1 on every committed change
```

---

## 5. One learner turn

```
 POST /workspaces/{id}/messages   { client_message_id, text, attachments }
 ──────────────────────────────────────────────────────────────────────────────────────────────
  1  lock the workspace: one turn at a time (a Postgres advisory lock)
  2  the same client_message_id again → return that turn; nothing runs twice
  3  save the learner's message and the turn: received                       transaction 1
     → answer 202 { turn } at once; the rest runs in the background
  4  code reads the graph: where we are → card B or C; the checks; the facts
  5  ORCHESTRATOR, with the plate of the card the turn starts in (§6)
     its evaluate calls run the EVALUATOR (§7); met on a box → the box ticks
     at once                                                                  transaction 2
  6  code checks the answer (§6.4); broken → one more try, with the problems
     listed; still broken → no change, logged
  7  EFFECTS, all at once (§9): progress · difficulty · issue opened, saved or
     cleared · back one step · stuck counter · task sheet · story lines ·
     checkpoint · turn decided · revision + 1                                 transaction 3
  8  task done? the job box ☑ and every concept checked → card E
  9  TUTOR, with the plate of the card the turn ends in (§8); the reply
     streams to the learner; stop ends it where it is
 10  save the reply · turn answered or stopped · revision + 1                 transaction 4
 11  card E → close the task, open the next one (card A); the tutor speaks first
 12  unlock
```

**Failure rules**

- The learner's message is saved before any model call, so it is never lost.
- The graph is committed before the tutor speaks. If the tutor fails, the same `client_message_id` re-runs step 9 only, and nothing is applied twice.
- A model call never runs inside a transaction.
- After the SDK's own retries, an error or a refusal means: the orchestrator → no change; the tutor → a short neutral reply. Both are logged.
- At startup, unfinished turns resume: received → from step 4; decided → from step 9.

---

## 6. The orchestrator

### 6.1 Its plate

```
                                             ON THE TASK · B     IN AN ISSUE · C
 ──────────────────────────────────────────  ──────────────────  ──────────────────
 orchestrator.base                           ■                   ■
 the card's piece: on_task or in_issue       ■                   ■
 the question tree with option descriptions  ■ questions 1–3     ■ questions 0–3
 the kinds of work, with descriptions        ■                   ■
 facts: task_goal · task_sheet · stack ·     ■                   ■
   recent_progress · stuck_level
 facts: next_box                             ■                   —
 facts: current_focus · closes_when ·        —                   ■
   return_to
 tools and their guides                      ■                   ■
 the learner's message with attachments,     ■                   ■
   and the tutor's last reply
 gated: orchestrator.stuck + this level's    ◇ level 1 and up    ◇ level 1 and up
   whys
 gated: orchestrator.saved_waiting + the     ◇ if any saved      ◇ if any saved
   saved issues
 gated: orchestrator.deep                    —                   ◇ 4 levels deep
 ──────────────────────────────────────────  ──────────────────  ──────────────────
 about 2,500 – 4,500 tokens                  NEVER: the answer key, the tutor's instructions
```

### 6.2 Its answer format, built by code every turn

`engine/tree.py` turns `tree.yaml` and the graph into one JSON schema for this turn, sent as the structured output format:

- every branch is one alternative (`anyOf`); a branch that can't exist this turn is not in it;
- every list of allowed values is closed (`enum`): the kinds of work, this level's whys, the probe targets, the saved issues, the concept bank, this task's turns;
- every object is closed (`additionalProperties: false`); no recursion, no minimum or maximum.

```
 situation                          the format contains
 ─────────────────────────────────  ──────────────────────────────────────────────────────────
 on the task, level 0, none saved   shows: progress | problem (unsure | wrong_idea | missing)
                                    | turns_away (go_now: no | yes, a new issue)
 in an issue                        + still_an_issue first; false only after "met" this turn
 stuck level 1 and up               + problem: stuck, with this level's whys
 a saved issue exists               + turns_away: yes, a saved issue
```

### 6.3 Its tools

```
 TOOL               INPUT                       WHAT CODE DOES
 ─────────────────  ──────────────────────────  ─────────────────────────────────────────────
 read_concept       concept                     a concept, from its sections and anchors
 read_file          path, around_line           120 lines of the repository copy
 search_repo        pattern                     at most 50 matches in the repository copy
 read_journey       task                        a closed task's journey
 evaluate           target, turns               runs the evaluator (§7) and returns its
                                                checked verdict
 pull_checkpoints   which                       writes checkpoints into this call's temporary
                                                folder; returns the file's path (§12)
 Read · Grep        path · pattern              only inside that temporary folder
```

Every tool's description is its guide, from `config/tools/`. Inputs are closed, like the answer format: `target` and `turns` list only what exists.

### 6.4 Code checks its answer

```
 still_an_issue is false        only after the evaluator said met this turn
 a gap that blocks              has a return_note
 a wrong idea                   its learner_words are found in this turn (§7.3)
 tutor_files                    every path exists and passes the gates (§16)
 progress                       its turns exist in this task
 ──────────────────────────────────────────────────────────────────────────────────────────
 a broken answer                one more try, with the problems listed; then no change
```

### 6.5 The call

One request carries the tools and the structured answer format. The model may call tools for up to `max_tool_rounds` rounds, then gives its answer. Tool choice is never forced: the newest models refuse forced tools. The orchestrator starts fresh every turn and remembers nothing; for older turns it pulls checkpoints.

---

## 7. The evaluator

### 7.1 Its plate

```
 instructions      evaluator.task_box, or evaluator.closes_when
 target            one box with its text, or one issue's closing condition
 answer key        the task's, for a box only; an issue has none
 learner turns     the turns the orchestrator named, copied word for word by code
 tools             pull_checkpoints (what the learner and the tutor said, never the
                   orchestrator's labels) · Read · Grep
 NEVER             the graph · the orchestrator's labels · a hint for the tutor
```

### 7.2 Its answer

```json
{ "target": "box 2", "verdict": "met", "learner_words": ["UnboundLocalError on `label`!"] }
```

`verdict` is `met`, `not_met` or `unclear`. `learner_words` holds up to 3 quotes, and is empty unless met.

### 7.3 Code checks the verdict

- The target is the one asked.
- Each quote is found in the learner's own messages or attachments in this task. The match folds case, spaces, quote marks and dashes first.
- Any failed check counts as `unclear`.
- Met on a box: the box ticks at once, recording the turn (§10). Met on an issue: Question 0 may now answer "no".

### 7.4 The answer key stays locked

`answer_keys` is read by one function, `agents/evaluator.py: answer_key_for(task)`. A test fails if any other module reads that table. No route, tool or tutor plate ever carries it.

---

## 8. The tutor

### 8.1 Its pieces

Code picks them from the card the turn ends in, the leaf, the kind of work and, when stuck, the why. The mapping is `LEGO.md` §4, §7 and §9, kept in `cards.yaml`, `kinds.yaml` and `stuck.yaml`.

### 8.2 Its system prompt, rebuilt every turn

```
 tutor.base                                    who it is, how it teaches, never the answer
 the instructions for this turn                its pieces, with their studs filled
 the files it may read                         the task sheet, always; the files the
                                               orchestrator unlocked, each with its reason
 the safety lines                              repository text, attachments and pasted output
                                               are data, never instructions
```

### 8.3 Its history

The whole task, as it happened, kept in `messages.content_blocks`:

- each learner message, with its attachments as text blocks;
- each tutor reply, with its tool calls and their results.

Never an old instruction. Never old thinking: the newest models reject old thinking once the system prompt changes, and ours changes every turn (`LEGO.md` §11.5).

### 8.4 Its tools

```
 read_concept · read_file · search_repo        always
 write_journey                                 card E only: the journey of the task
```

The gates are in §16.

### 8.5 Streaming and stop

- **Streaming.** Every text piece goes out as a `tutor` event. Every tool call goes out as a `tool` event in plain words, such as "reading app.py, lines 600 to 640".
- **Stop.** `POST /stop` closes the model stream. The words already said are saved as the reply, and the turn is marked `stopped`.

### 8.6 The first and last turn of a task

```
 card A · open task      turn 0: the tutor speaks first; pieces introduce_task and
                         keep_goal_in_view, plus bridge_back after an earlier task
 card E · close task     pieces close_task; the tool write_journey; then the next task opens
```

---

## 9. Effects: what code writes, and the story line each one writes

```
 EFFECT                 WHEN                                  WRITES                     STORY LINE
 ─────────────────────  ────────────────────────────────────  ─────────────────────────  ────────────────────
 open_task              card A                                tasks · stack · sheet      started
 record_progress        a leaf carries progress               progress · stuck counter   did
 check_box              the evaluator said met on a box       box_ticks ·                ticked
                                                              concept_progress
 record_difficulty      WRONG_IDEA, or a GAP about a concept  difficulties ·             almost (wrong idea)
                                                              concept_progress
 open_issue             a GAP that blocks · WANTS_TO_GO       issues · stack             found_a_gap, then
                                                                                         went_to_learn_first
                                                                                         or needed_first
 save_issue             a GAP that can wait · SIDE_QUESTION   issues                     saved_for_later
 back_one_step          BACK                                  issues · stack             cleared or
                                                                                         already_knew, then
                                                                                         came_back
 raise or reset stuck   every turn                            stuck_counters             —
 checkpoint             every turn                            checkpoints                —
 close_task             card E                                tasks · journeys ·         done
                                                              concepts (discoveries)
```

Every effect of a turn commits in one transaction, together with its story lines and `revision + 1`. The story line's depth is the stack's depth at that moment. Its words come from `story.yaml`; the screen draws the marks.

---

## 10. The task sheet

- **One sheet per task, written by code only.** A new task's sheet is always fresh.
- **A box ticks** when the evaluator says met. The tick records the turn, so the ticks also show the order the boxes were ticked in.
- **A concept is checked** when all of its boxes are ticked.
- **It goes back to unchecked** when a WRONG_IDEA or a GAP about it comes after. A `had_it_then_missed` row then keeps the turn, the issue and the angle.
- **times_it_came_up** grows on every turn that touches the concept: a leaf names it, the focus issue is linked to it, or one of its boxes is judged.
- **The task is done** when the job box is ticked and every concept is checked.
- **Who reads it:** the tutor (always) and the orchestrator (every turn). The evaluator never does. The learner gets the view of §4.4: no difficulties, and no box text before the tick.

---

## 11. The stuck ladder

- **A counter per focus** (the task, or an issue) counts the turns with no progress: no progress line, no box ticked, no met. A WRONG_IDEA counts as no progress.
- **Turns become a level:** 0–1 turns → level 0, 2 → level 1, 3 → level 2, 4 or more → level 3. The thresholds and each level's set of whys live in `stuck.yaml`.
- **Any progress** resets the counter.
- **At level 1 and up**, the tree grows the stuck branch with this level's whys. The orchestrator picks one, and code snaps that why's tutor piece.
- **The answer itself is never given**, at any level.

---

## 12. Checkpoints

**One checkpoint per turn,** signed with the orchestrator's leaf: what the learner said, the leaf, the verdicts, the tool calls, the reply, and where we were.

**`pull_checkpoints(which)`** writes them into the call's own temporary folder as Markdown, and returns the file's path. The agent then reads that folder with Read and Grep.

```
 which                                       gives
 ──────────────────────────────────────────  ──────────────────────────────────────────────
 last N turns                                the last N checkpoints
 since the focus opened                      every turn since the task or the issue opened
 every turn signed with one leaf             for example every STUCK turn
 every turn about an issue or a box          for example issue I1, or box 3
```

- **The evaluator's copy** holds only what the learner and the tutor said.
- **The folder is deleted** when the call ends.

---

## 13. Tasks: open, close, next

- **Open, card A.** Code puts the task on the stack, creates a fresh sheet and writes "started"; the tutor speaks first, as turn 0.
- **Close, card E.** Code writes "done". The tutor closes the task and writes the journey. Then:
  - the sheet is kept as the task's record;
  - each saved side question, and each concept gap with no concept in the bank, becomes a raw concept in the bank, labeled discovered (`LEGO.md` §10);
  - the next task on the ladder opens with fresh agents.
- **Saved issues stay open across tasks.** WANTS_TO_GO can pick a saved issue up in a later task; it then joins the stack of the current task.
- **All tasks done:** `where` becomes empty, and the composer has nowhere to send.

---

## 14. Preparing a codebase

```
 STEP        WHO                         DOES                                     CHECKED BY CODE
 ──────────  ──────────────────────────  ───────────────────────────────────────  ─────────────────────────────
 copying     code                        shallow clone (https only, size limit,   the clone exists; secrets
                                         the reused SSRF block); drop .env files, (.env files, keys,
                                         keys and certificates; outline the code  certificates) removed
 concepts    concept crafter · Agent     reads the copy with Read, Glob, Grep;    each concept: a name, a claim,
             SDK · Haiku 5.5             writes concepts through write_concept    a proof, at least one
                                                                                  misconception, anchors found
                                                                                  in the code; no duplicates, no
                                                                                  prerequisite cycles
 tasks       task crafter · Agent SDK    reads the copy and the concepts; writes  each task: title, goal, tier,
             · Haiku 5.5                 tasks through write_task: title, goal,   files that exist; the job box;
                                         tier, files, the job box, each concept   every concept has a box; a box
                                         with its boxes in a suggested order,     belongs to one concept; the
                                         the answer key                           answer key is present
 ordering    code                        tier order, prerequisites first, at      every task appears once
                                         most 2 new concepts per task
```

**The Agent SDK runs locked down:**
- allowed: Read, Glob, Grep, and our own write tools;
- blocked: Bash, Write, Edit, the web tools and subagents;
- no user settings are loaded;
- the working folder is the repository copy, read-only.

**Box text is written for the learner, never the answer.** It names what the learner must show, as in "explains why label is unbound for a guest". The screen hides it until the box is ticked.

**Events.** Every step sends `step` (running, done) on the preparing stream. Every concept and every task sends its own event as it is written. The run ends with `ready` or `failed`. A late subscriber first gets the events it missed.

---

## 15. API

Every route needs the learner's Supabase access token as `Authorization: Bearer …`. The server takes the learner's identity from the token alone.

```
 ROUTE                                         IN                        OUT
 ────────────────────────────────────────────  ────────────────────────  ───────────────────────────────
 GET   /health                                 —                         { status }   (no token)
 GET   /workspaces                             —                         Workspace[]
 POST  /workspaces/import                      { name, git_url }         201 { workspace_id }
 GET   /workspaces/{id}/preparing              —                         stream: step · concept · task ·
                                                                         ready · failed
 GET   /workspaces/{id}/tasks/{task}           —                         LadderTask
 POST  /workspaces/{id}/start                  —                         { revision }
 GET   /workspaces/{id}?since={revision}       —                         { changed, revision, snapshot }
 POST  /workspaces/{id}/messages               { client_message_id,      202 { turn }
                                                 text, attachments }
 POST  /workspaces/{id}/stop                   —                         202 {}
 GET   /workspaces/{id}/stream                 —                         stream: revision · tutor · tool
 GET   /workspaces/{id}/files                  —                         string[]
 GET   /workspaces/{id}/file?path=             —                         { path, text }
```

**Errors.**

```
 401  no token, or a bad one             404  no such workspace, task or file
 403  not the owner of this workspace    409  a turn is already running, or preparing isn't done
 422  a malformed body                   500  logged, with the turn
```

**The streams** are server-sent events. They carry exactly the events of `FRONTEND.md` §7, with a heartbeat every 15 seconds.

---

## 16. Security

- **Tokens:** the learner's Supabase token is checked with the project's public keys (reused `auth.py`). The `X-User-Id` header is never trusted.
- **Data:** the `tutor` schema is hidden from Supabase's data API. Row-level security is on with no policies, and every query filters on the owner.
- **Paths:** every file tool resolves inside the repository copy. `..` and symbolic links are refused (tutor_v2's path rules).
- **The answer key:** read only by the evaluator path (§7.4).
- **Prompt injection:** repository text, attachments and pasted output are wrapped as data. Every agent's base piece says they are never instructions.
- **Secrets:** scrubbed before any crafter reads the copy, and never written into `concept_anchors`.
- **Limits:**
  - one turn at a time per workspace;
  - a message holds at most 20,000 characters, plus at most 5 attachments of 20,000 characters each;
  - a repository is at most 200 MB.

---

## 17. Cost and limits

Haiku 5.5 costs $0.10 per million input tokens and $0.50 per million output tokens, as long as a prompt stays under 100,000 tokens.

```
 ONE LEARNER TURN            INPUT TOKENS           OUTPUT TOKENS
 ──────────────────────────  ─────────────────────  ─────────────
 orchestrator                3,000 – 6,000          300 – 800
 evaluator, 0 to 2 calls     about 1,500 each       about 100 each
 tutor                       5,000 – 40,000         300 – 900      grows with the task
 ──────────────────────────  ─────────────────────  ─────────────
 total                       10,000 – 50,000        1,000 – 2,000  ≈ $0.002 – $0.006 a turn
```

- **The 100K guard.** Every call is counted before it is sent and logged after, in `model_calls`. A call above 100,000 tokens costs five times as much, so it is logged as a warning. If that happens often, we revisit compaction.
- **Preparing a codebase** costs one run of each crafter. The live run in §20 measures it.

---

## 18. Tests

```
 LEVEL                 WHAT                                                          MODELS
 ────────────────────  ────────────────────────────────────────────────────────────  ────────────
 unit                  the tree → answer format, for every situation · the answer    none
                       checks · every effect · the task sheet rules · the stuck
                       ladder · story lines · the words matcher · the gates · the
                       answer key read by one function only
 contract              the snapshot matches FRONTEND.md §7 field by field; a concept  none
                       box's text is null until ticked
 the T3 replay         scripted agents play the 11 turns of LEGO.md §8; the          scripted
                       snapshot after each turn must equal the frontend's demo
                       data, lib/api/demo.ts
 failures              a broken answer → one retry → no change · the tutor fails →   scripted
                       only step 9 re-runs · stop mid-reply · a refusal · a restart
                       mid-turn
 preparing             a small fixture repository: concepts and tasks pass their     scripted
                       checks; the ladder obeys its rules
 live                  real Haiku 5.5 on a small repository: the decisions, the      real, costs
                       cost per turn, the largest prompt                             money; by hand
```

**One seam reaches the models:** `agents/claude.py`. Every test except the live one runs offline.

---

## 19. From tutor_v2: kept, rewritten, deleted

```
 auth.py · importer.py · structure.py          kept as they are, in reused/
 the per-workspace lock, the event helper,     the pattern is kept, rewritten
 the replay log for late subscribers
 the Agent SDK permission setup                the pattern is kept, for the crafters
 Dockerfile (Node and the Claude CLI for the   adapted; deployed as a second Fly app until
 Agent SDK) · fly.toml                         the switch
 everything else in tutor_v2                   deleted at the switch
```

---

## 20. Build order

```
 STEP                WHAT                                                    DONE WHEN
 ──────────────────  ──────────────────────────────────────────────────────  ─────────────────────────────────
 1  foundations      restore Supabase · the migrations · the package ·       the server starts; the config
                     the config loader · auth · /health                       check passes
 2  the read side    snapshot, ladder, task and file routes, on a T3 seed     the frontend in live mode shows
                     loaded into Postgres                                     T3 from the backend
 3  the engine       where · checks · cards · the tree → format · the         unit tests green; the T3 replay
                     answer checks · effects · sheet · stuck · story ·        passes with scripted leaves
                     checkpoints · the piece texts
 4  the agents       claude.py; orchestrator, evaluator and tutor with        the T3 replay passes end to end
                     scripted models                                          with scripted agents
 5  live turns       messages, stream and stop routes; resuming unfinished    the frontend plays T3 against the
                     turns                                                    backend, agents scripted
 6  real models      the Haiku 5.5 test call; then real agents on the T3      you read a real T3 session; the
                     seed                                                     cost per turn is recorded
 7  preparing        the import route, the job, both crafters, the checks,    a small real repository prepares
                     the ordering, the preparing stream                       end to end
 8  ship             a second Fly app, Vercel in live mode, the sign-in       you learn one task on your own
                     screen                                                   repository
 9  the switch       tutor_v2 deleted                                         your call
```

---

## 21. Risks

```
 RISK                                          WHAT WE DO
 ────────────────────────────────────────────  ──────────────────────────────────────────────────
 Haiku 5.5 judges too weakly as orchestrator   step 6 measures it on real turns; the model is one
 or evaluator                                  line per agent in models.yaml
 the answer format is too large for            the test call checks it first; if needed, a
 structured outputs                            flatter format with the same checks in code
 a long task passes 100K tokens                logged; then we revisit compaction
 a free Supabase project pauses when idle      it is paused today; for real learners, the paid
                                               plan or regular use
 one machine only: the lock and the events     enough for now; later the events move to Postgres
 live in the process                           notifications
 a large repository costs a lot to prepare     the size limit; the cost is logged per step
 pasted code is self-reported                  accepted in phase 1; the evaluator judges what was
                                               written
```

---

## 22. Decisions waiting for you

```
 1  restore the Supabase project now           a. yes                                 ← my pick
                                               b. at step 1 of the build
 2  how learners sign in                       a. GitHub, since they import GitHub    ← my pick
                                                  repositories
                                               b. a link by email
 3  the proposals in §0 for LEGO.md's holes    a. accept all                          ← my pick
                                               b. go through them one by one
 4  where the new backend runs                 a. a second Fly app during the build,  ← my pick
                                                  then the switch
                                               b. replace tutor_v2 in the current app
```
