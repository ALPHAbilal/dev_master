# Agentic Layer — Spec v0.2

Status: draft for review · 2026-10-07
Replaces the agent design in `TASK_DRIVEN_TUTOR_SPEC.md` (§3 Roles, §7 Agents, §8 Workflow).
Everything about **learning** stays as defined there: concepts, the 4 rungs, tasks and tiers, rules A/B/C,
pace, stretch zone, edge cases.
Worked example on a real repo: `TUTOR_UX_WALKTHROUGH.md` (`chatbot_final_version/app.py`).

```
 LEGEND   [ code ]   ⟨ LLM · tier ⟩   ( learner )   ▓ file in the workspace
```

---

## 0. In one picture

```
                 ┌───────────────────────────────────────────────┐
                 │ WORKSPACE · everything is a file              │
                 │ repo/  concepts/  tasks/  ladder.md           │
                 │ learner/  session/                            │
                 └──────▲────────────────▲───────────────▲───────┘
                        │ writes         │ reads/writes  │ reads (mounted files only)
         ┌──────────────┴────┐  ┌────────┴───────┐  ┌────┴───────────────┐
         │ CRAFTER pipeline  │  │ ENGINE (code)  │  │ TUTOR loop         │
         │ 1 → 2 → 3         │  │ decides, gates │  │ one per task       │
         │ builds the map    │  │ sets the knobs │  │ the learner's voice│
         └───────────────────┘  └───▲────────▲───┘  └────────────────────┘
                                    │        │
                          proposals │        │ verdicts
                        ┌───────────┴──┐  ┌──┴───────────┐
                        │ ORCHESTRATOR │  │ EXAMINER     │
                        │ small LLM    │  │ the judge    │
                        └──────────────┘  └──────────────┘
```

---

## 1. Principles

| # | principle | means |
|---|---|---|
| P1 | **Context as files, never injected** | Outputs are written to files. The next agent gets file tools (list · read · search) and pulls only what it needs. No agent ever has a whole collection pasted into its prompt. |
| P2 | **One job per agent** | Each agent has its own prompt, its own tools and its own state. A new kind of work means a new agent, not a "mode" bolted onto an old one. |
| P3 | **Agents are loops** | The tutor is a loop that lives for one task. The crafters run as a pipeline with strict handoffs. |
| P4 | **LLMs propose, code decides** | The orchestrator and the examiner *propose* and *judge*. Only the engine (code) changes state, mounts files, or switches tools. |
| P5 | **One task = one continuous conversation** | Inside a task, the learner never sees a restart. Rung changes, detours and resumes only change the loop's knobs. |
| P6 | **Gates are the teaching rules** | "Never give the answer before an attempt" is enforced by the answer file *not being mounted*, not by a promise in the prompt. |
| P7 | **Use code when it applies** | Running code, tests, validation, file plumbing and state are code. LLMs only do what needs language or judgment. |

---

## 2. The cast

| agent | kind | model | runs | reads | writes | never |
|---|---|---|---|---|---|---|
| CRAFTER 1 · Concepts | LLM | mid (fan-out) + strong (merge) | once per repo | `repo/` | `concepts/` | sees a learner |
| CRAFTER 2 · Tasks | LLM | strong | after Crafter 1 passes validation | `repo/`, `concepts/` | `tasks/` | sees a learner |
| CRAFTER 3 · Ladder | LLM | small | after Crafter 2 passes validation | `tasks/`, `concepts/` | `ladder.md` | sees a learner |
| ORCHESTRATOR | LLM | small | on every learner message | the message, `session/frame.md`, `learner/journey/INDEX.md` | one proposal | mounts anything, talks to the learner |
| TUTOR | LLM loop | mid | one loop per task | mounted files only | turns, hidden checks, journey file | grades, decides what comes next |
| EXAMINER | LLM | mid · strong for pr_review | after every attempt | the attempt + run results | a verdict | talks to the learner, teaches |
| ENGINE | code | – | always | everything | state, mounts, knobs | uses an LLM to decide |

---

## 3. The workspace

```
 /workspace/<repo>/
 ├── repo/                          the learner's code (learning branch), secrets scrubbed
 ├── concepts/                      ← CRAFTER 1 · one file per concept
 │   ├── C05_dict_get.md
 │   └── C15_loop_scope.md
 ├── tasks/                         ← CRAFTER 2 · one folder per task
 │   └── T3_guest_error/
 │       ├── task.md                goal, tier, concepts, files
 │       ├── check/test_t3.py       the done-check
 │       └── reference.patch        the answer key (gated, see §7)
 ├── ladder.md                      ← CRAFTER 3 · the task order
 ├── learner/
 │   ├── board.md                   rungs per concept (ENGINE only)
 │   └── journey/
 │       ├── INDEX.md               one line per closed task (titles only)
 │       └── T3.md                  summary of that task's loop
 └── session/                       the CURRENT loop's working memory (ENGINE-managed)
     ├── frame.md                   task · concept · rung · active knobs
     ├── question.md                the open question
     ├── check.json                 its hidden check (hidden from the learner and the orchestrator)
     ├── attempt.md                 the learner's last attempt
     ├── run_result.json            what the sandbox produced
     ├── verdict.json               the examiner's verdict
     ├── paused.md                  the exact paused question during a detour
     ├── summary.md                 compacted older turns (long tasks)
     └── scratch/                   scratch-pad files
```

**Concept file** (`concepts/C15_loop_scope.md`):

```markdown
---
id: C15
name: loop variables outlive the loop (function scope)
kind: language
anchors:
  - { symbol: ChatbotAssistant.chat, text: "for label, link in self._record_process_links(", hash: 9f2c }
  - { symbol: ChatbotAssistant.chat, text: "and label != 'candidate':", hash: 41ab }
prereqs: [C04]
traps:
  javascript: "for (let x …) is block-scoped in JS; in Python x lives on after the loop"
---
## What it is
## Examples (used by example_first)
## Common misconceptions
```

Anchors are **symbol + line text + hash**, not line numbers, so they survive edits.
Line numbers are worked out when a file is mounted, for display only.

**Task file** (`tasks/T3_guest_error/task.md`):

```markdown
---
id: T3
tier: debug
goal: "Guests always get 'Une erreur s'est produite'"
concepts: [C15, C17, C13]
files: [app.py]
check: check/test_t3.py
reference: reference.patch
real_bug: true
---
## Story (what the learner is told)
## Change point (why this task exists)
```

---

## 4. Crafter pipeline

```
 repo ─► [ scrub secrets · outline · find entry points ]
              │
              ▼
 ⟨ CRAFTER 1 · concepts ⟩ ──► ▓ concepts/ ──► [ VALIDATE 1 ] ──fail──► back to Crafter 1
                                                   │ pass
                                                   ▼
 ⟨ CRAFTER 2 · tasks ⟩ ─────► ▓ tasks/ ─────► [ VALIDATE 2 ] ──fail──► back to Crafter 2
                                                   │ pass
                                                   ▼
 ⟨ CRAFTER 3 · ladder ⟩ ────► ▓ ladder.md ──► [ VALIDATE 3 ] ──fail──► back to Crafter 3
                                                   │ pass
                                                   ▼
                                        map ready → first tutor loop can open
```

**Handoff rule:** a crafter starts only when the previous crafter's output has passed validation.
It receives that output **as files plus tools**. It is never pasted into its prompt (P1).

### 4.1 CRAFTER 1 — Concepts

| | |
|---|---|
| **Input** | `repo/` (scrubbed) + an outline (classes, functions, entry points) made by code |
| **Tools** | `list_files` · `read_file` · `search` · `outline` · `write_concept` · `list_concepts` |
| **Output** | `concepts/*.md` |
| **Done when** | every reachable line from the entry points has been read |

SOP:
1. Start at the entry points (for `app.py`: `POST /chat`, `GET /chatbot`) and follow the real call path.
2. For **every line read**, ask: *"What must a person know to understand this line?"*
3. Write each answer as a concept, **in no particular order**, with its anchor.
4. **Merge and connect.** Same idea in several places → one concept with several anchors.
   Link prerequisites (no cycles). Add traps per learner background.
5. Big repos can fan out one sub-run per module or section, with a single merge step at the end.

### 4.2 CRAFTER 2 — Tasks

| | |
|---|---|
| **Input** | `repo/` + `concepts/` (as files, reached via tools) |
| **Tools** | `read_file` · `search` · `list_concepts` · `read_concept` · `write_task` · `run_check` |
| **Output** | `tasks/<id>/` (task.md, check, reference.patch) |
| **Done when** | every tier has at least one task, and every concept appears in at least one task |

SOP:
1. **Find change points**, meaning places where a real change makes sense:
   TODO comments · hardcoded values · a correct line that can be broken on purpose (debug) ·
   missing pieces · real weaknesses · open problems.
2. **Turn each change point into a task:** goal (one line), tier, the concepts the *correct solution*
   touches (looked up in `concepts/`), files, a done-check test, and the reference patch.
3. Debug tier: plant the bug, or mark `real_bug: true` when the bug already exists in the repo.
4. Output is a **bag of tasks**. Ordering is Crafter 3's job.

### 4.3 CRAFTER 3 — Ladder

| | |
|---|---|
| **Input** | `tasks/` + `concepts/` (as files, reached via tools) |
| **Tools** | `list_tasks` · `read_task` · `read_concept` · `write_ladder` |
| **Output** | `ladder.md` |
| **Rules** | tier order (understand → change → debug → modify → assemble → build → solo) · prerequisites first · each task adds ≤ 2 new concepts beyond the tasks before it |

### 4.4 Engine validation between stages

| stage | checks (all code) |
|---|---|
| VALIDATE 1 | every anchor's text really exists at its symbol · no prereq cycles · no duplicate ids |
| VALIDATE 2 | each check **fails** on the starting code and **passes** with the reference patch · every listed concept exists |
| VALIDATE 3 | every task appears once · the rules in 4.3 hold |

---

## 5. Tutor loop

### 5.1 Lifecycle

```
 ═══ TASK T3 · one loop · one continuous conversation ═════════════════════════════════► CLOSE
   OPEN          turn ─► turn ─► turn ─► … ─► task check ✓                                  │
   fresh            ▲       ▲       ▲                                                       │
   context          └───────┴───────┴── ENGINE re-sets the knobs at every event             │
                                                                                            ▼
                                                              writes learner/journey/T3.md
 ═══ TASK T4 · NEW loop · fresh context ══════════════════════════════════════════════════►
```

### 5.2 The 4 knobs

```
 KNOB 1  CONTEXT        fresh │ continue │ partial (older turns compacted into session/summary.md)
 KNOB 2  FILES          which workspace files are mounted (readable by the tutor) right now
 KNOB 3  INSTRUCTIONS   which instruction blocks are loaded on top of the tutor's base prompt
 KNOB 4  TOOLS          which tools are switched on
```

**Tutor tool catalogue** (the engine switches these on and off):
`read_file` · `search` (mounted paths only) · `run_snippet` (private sandbox) · `scratch_pad` (shared with the
learner) · `run_tests` · `read_diff` · `write_suggestion` (ally only) · `write_journey` (close only)

**Instruction blocks:** `base` · `rung:predict` · `rung:perturb` · `rung:produce` · `rung:transfer` ·
`example_first` · `detour` · `resume` · `bottom_out` · `review` · `challenge` · `why_this_line` · `ally` · `solo` ·
`connect_past` · `offer_switch` · `brief_aside` · `close`

### 5.3 What is mounted when a loop opens

```
 context       fresh
 files         tasks/<T>/task.md · concepts/<each concept T needs>.md · repo/<T's files>
               learner/board.md (only the rows for T's concepts) · learner/journey/INDEX.md
 instructions  base + the mode the engine chose for the first concept (§5 of v0.1)
 tools         read_file · search · run_snippet
```

### 5.4 Events → knobs

**Engine events** (deterministic: they come from verdicts, runs and counters):

| event | context | files | instructions | tools |
|---|---|---|---|---|
| loop opens | fresh | default mounts (5.3) | base + first mode | read_file, search, run_snippet |
| HIT → next concept | continue | swap to the next concept's file | rung template | same |
| MISS: misconception | continue | + `session/attempt.md`, `run_result.json` | rung − 1 | same |
| MISS at predict, or a brand-new concept | continue | + the concept's *Examples* section | example_first | + scratch_pad |
| MISS: missing prerequisite | continue | + prereq concept, `session/paused.md` | detour | + scratch_pad |
| detour HIT | continue | − prereq concept | resume | − scratch_pad |
| learner must write code | continue | + `check/` | rung:produce | + run_tests, read_diff |
| 3rd MISS on a rung | continue | **+ `reference.patch`** | bottom_out | same |
| large paste in the diff | continue | + the diff | why_this_line | read_diff |
| build tier | fresh | default | ally | + write_suggestion |
| solo tier | fresh | task story only | solo | read_file, search |
| context over budget | **partial** | + `session/summary.md`, older turns dropped | same | same |
| task check passes + pr_review done | close | – | close | write_journey only |

**Orchestrator events** (they come from what the learner *says*, see §6):

| accepted proposal | context | files | instructions | tools |
|---|---|---|---|---|
| `mount_journey(T)` | continue | + `learner/journey/T.md` | connect_past | same |
| `challenge(C)` | continue | – | challenge (one transfer question, no hints) | same |
| `ask_back` | continue | – | answer with a smaller question (2nd time: hint → provisional) | same |
| `frustration` | continue | – | offer_switch (do-first or bottom-out) | same |
| `off_topic` | continue | – | brief_aside, then return to the open question | same |
| `dispute` | continue | – | – (EXAMINER rejudges) | same |
| `park` | close as *parked* | `session/` saved as is | – | – |

**Precedence when several events fire in the same turn:** `park` > `dispute` > engine events > other proposals.

### 5.5 One turn, step by step

```
 ( learner message )
        │
        ├────────────────────────────────────┬──────────────────────────────────┐
        ▼                                    ▼                                  │
 [ ENGINE ] is this an attempt?       ⟨ ORCHESTRATOR · small ⟩                  │ in parallel
   yes → [ sandbox ] run check.json     reads: message · frame.md · INDEX.md    │
       → ⟨ EXAMINER ⟩ verdict.json      picks ONE proposal from the menu        │
        │                                    │                                  │
        └──────────────────┬─────────────────┘                                  │
                           ▼
 [ ENGINE ] 1. apply the verdict rules (A/B/C, rungs, stack, counters) → events
            2. validate the proposal against the gates (§7) → accept or reject
            3. resolve precedence · set the 4 knobs · update frame.md · mount/unmount
            4. log every mount with its reason
                           ▼
 ⟨ TUTOR · mid ⟩  same conversation, new knobs → next turn + hidden check → session/check.json
```

### 5.6 Closing a loop

On close, the tutor runs with the `close` block and the `write_journey` tool only, and writes:

```markdown
# T3 · Guests get "Une erreur s'est produite"
concepts: C15 predict→produce · C04 (detour) · C17 perturb
what clicked: "the loop variable belongs to the whole function"
missed: thought last([]) returns None (JS habit)
fix: app.py ChatbotAssistant.chat · label → question_label
```

The engine then appends one line to `learner/journey/INDEX.md` and clears `session/`.

---

## 6. Orchestrator

A small, cheap LLM that **understands what the learner said** and turns it into one proposal from a menu.
It never acts on that proposal itself.

| | |
|---|---|
| **Input** | the learner's message · `session/frame.md` · `learner/journey/INDEX.md` · **the menu the engine offers this turn** |
| **Tools** | `read_file` on those two files only |
| **Output** | `{ proposal, args, evidence, confidence }` |
| **Never** | mounts or unmounts, speaks to the learner, sees the answer key, picks something outside the menu |

**The menu is gated by the engine.** The orchestrator only sees proposals whose conditions hold right now:

| proposal | means | offered only when |
|---|---|---|
| `mount_journey(T)` | the learner refers to a past task | T is closed, same repo |
| `challenge(C)` | "I already know C" | C is in this task · not owned · tier ≠ solo |
| `ask_back` | the learner asks a question instead of answering | a question is open |
| `frustration` | the learner signals frustration | tier ≠ solo, no challenge running |
| `off_topic` | unrelated question | always |
| `dispute` | the learner contests a verdict | the last verdict was *judged* (a run-based verdict can't be disputed) |
| `park` | "stop", "later", "I'm done for today" | always |
| `none` | nothing special | always |

Example (in task T4, the learner writes *"wait, is this the same scope problem as the label bug?"*):

```json
{
  "proposal": "mount_journey",
  "args": { "task": "T3" },
  "evidence": "\"same scope problem as the label bug\" matches INDEX: T3 guests get the error (loop scope)",
  "confidence": "high"
}
```

The engine checks that T3 is closed and in the same repo → accepted → mounts `learner/journey/T3.md` + `connect_past`.

---

## 7. Engine

Plain code. It owns all state and is the only component that changes anything.

**Owns:** `learner/board.md` · `session/*` · the loop lifecycle · mounts · knobs · the sandbox · validation · logs.

**Gates** (what may be mounted or switched on, and when):

| resource | available only when | never when |
|---|---|---|
| `reference.patch` (answer key) | bottom_out · pr_review (examiner) | any time before the learner's attempts on that rung |
| `session/check.json` | examiner · tutor (its own check) | orchestrator |
| `learner/journey/<T>.md` | accepted `mount_journey` · review | – |
| `scratch_pad` | example_first · detour · foundation | solo |
| hint-giving instruction blocks | ally · bottom_out · 2nd `ask_back` | solo · challenge |
| `write_suggestion` (tutor writes code) | ally (build tier) | everywhere else |
| `write_journey` | close | during the loop |

**Log:** every mount, unmount, knob change and rejected proposal is written with its reason.
This log is the evidence for the acceptance criteria in §11.

---

## 8. Examiner

Carried over from v0.1 because an LLM can't verify its own work well. The tutor writes the check
*before* the attempt, and a different agent judges it.

| | |
|---|---|
| **Input** | `session/question.md` · `check.json` · `attempt.md` · `run_result.json` · hints given · active traps |
| **Tools** | `read_file` · `read_diff` · `run_on_branch` |
| **Output** | `session/verdict.json`: `HIT` / `MISS` / `provisional` · evidence · cause · confidence |
| **Modes** | verdict · pr_review · solo_intent · explain · rejudge |

A run beats the examiner's judgment. When the run decides, the examiner only adds the **cause** of a MISS:
misconception (named) · missing prerequisite (which concept) · missing concept (with an anchor).

---

## 9. Between tasks

```
 T3 loop closes ─► journey/T3.md + INDEX.md updated ─► [ ENGINE ] next task from ladder.md (stretch zone)
                                                            │
 spaced reviews due? ─► short REVIEW loop first (fresh)  ◄──┤
                                                            ▼
                                                  T4 loop opens · FRESH context
   default mounts (5.3) — no past task content, only INDEX.md titles
        │
   learner: "is this like the label bug?"  ─► ORCHESTRATOR: mount_journey(T3)
                                           ─► ENGINE: allowed → mount journey/T3.md + connect_past
```

---

## 10. Models and cost per learner turn

| agent | tier | why |
|---|---|---|
| Crafter 1 | mid per section, strong for the merge | many lines; merging needs judgment |
| Crafter 2 | strong | good tasks and tests are the hardest thing to generate |
| Crafter 3 | small | ordering against explicit rules |
| Orchestrator | small | classification from a short menu |
| Tutor | mid | it is the learner's experience |
| Examiner | mid · strong for pr_review and solo_intent | judgment on code |

```
 per learner turn   1 small (orchestrator) + 1 mid (tutor) + 0–1 mid (examiner, only on attempts)
 crafter pipeline   once per repo (plus re-runs on changes)
```

---

## 11. Acceptance criteria

- No agent receives a whole collection (`concepts/`, `tasks/`, `journey/`) in its prompt. Collections are reached only through file tools, on mounted paths.
- Inside one task the learner sees one conversation. Every rung change, detour and resume is a knob change, never a new loop.
- A new task always opens a fresh loop. Past-task content is mounted only through an accepted `mount_journey`.
- The orchestrator can only return a proposal from the menu it was offered. It never mounts, unmounts or speaks to the learner.
- `reference.patch` is never mounted to the tutor before bottom_out. Every mount is logged with its reason.
- Every closed loop writes `learner/journey/<T>.md` and appends to `INDEX.md`.
- Each crafter starts only after the previous crafter's output has passed validation.
- Every concept anchor is symbol + text + hash. Secrets are scrubbed before Crafter 1 reads anything.

---

## 12. What changed from v0.1

| v0.1 | v0.2 |
|---|---|
| ENGINE builds a JSON packet each turn and pastes it into a stateless tutor | the tutor is a **loop per task** that pulls what it needs from mounted **files** |
| one agent + mode overlays for every case | **4 knobs** (context, files, instructions, tools) set by the engine per event |
| one CARTOGRAPHER with modes | **3 crafters** in a strict handoff, each with its own prompt, tools and state |
| the engine guessed everything from verdicts | an **orchestrator** (small LLM) reads what the learner *says* and proposes; the engine decides |
| "never reveal the answer" was a prompt rule | the answer file **is not mounted** until bottom_out |
| anchors were line numbers | anchors are **symbol + text + hash** |

---

## 13. Open decisions

1. **Crafter: one-shot or a loop?** Run once per repo (plus refresh on commits), or a standing loop that also reads signals from tutor loops, such as "concept missing" or "check broken"?
2. **Crafter 2 ordering.** Does Crafter 2 produce a strictly unordered bag, or a rough order that Crafter 3 enforces?
3. **Crafter 3: agent or code?** Its rules (tier order, prerequisites, ≤ 2 new concepts) are explicit, so a topological sort could do it (P7).
4. **Orchestrator on every message, or behind a cheap pre-filter?** Every message is simplest. A code pre-filter (references to the past, "stop", "I know", disputes) would save a call on most turns.
5. **"I don't know":** does it count toward the 3-miss bottom-out?
6. **Examiner causes:** keep the 3 causes, or add `no_attempt`, `vague`, `saw_answer` and `partial` (from the what-if scenarios)?
7. **Existing engine (v0.1 §11):** real code to extend, or greenfield?
8. **Sandbox:** a stub layer for external services (OpenAI, network) or extracted functions only? The walkthrough shows `app.py` can't run without stubs.
