# Handoff: Continue Here

Written 2026-10-09, to continue on another laptop. Updated the same day (session 2): descriptive names, the decision menu, the labels (§5) and every unclear point found while reviewing (§4). Claude's memory doesn't move between machines; this file and the files it points to carry the whole context.

## 1. Start Here (you, and Claude)

Read these in order:

1. `HANDOFF.md`: this file. Where we are and what you still need to answer.
2. `learning_graph_orchestration_architecture.md` (v1.1): **the whole new design**. §0–§14 are your original design; §15–§26 are the decisions from the design review.
3. `BACKEND_SPEC.md` (draft v0.1): **how to build the new backend** (`tutor_graph`, which replaces `tutor_v2`).
4. `t3-tutor-loop.html`: your T3 scenario, updated for the decisions.
5. `t3-orchestrator-map.html`: the shared map. Point at things by id: step `5`, node `I2`, change `5.3`, evidence `E6`. It's also published at https://claude.ai/artifact/466SmMUkuN4Q5j2KXDJMT5.
6. `archive/README.md`: what was archived and why. Don't build from `archive/`.

**To resume with Claude on the new laptop**, open Claude Code in `dev_master` and say:

> Read `new_completly_desighn/HANDOFF.md`, then the architecture spec and `BACKEND_SPEC.md`. We continue from "Questions you still need to answer".

## 2. Where We Are

- [x] Understood the current system (`tutor_v2`: 7-axis units, MAPPER/TEACHER/JUDGE/DISTILLER, the Router).
- [x] Read and reviewed the new design; built the orchestrator map as a shared alignment tool.
- [x] Wrote every decision into the architecture spec (invariants 11–19, §15–§26).
- [x] Merged the useful parts of Spec v0.2 into it and archived all superseded design docs.
- [x] Answered the architecture questions (decisions D1–D12 below).
- [x] Wrote `BACKEND_SPEC.md`.
- [x] Renamed every short or cryptic name to a descriptive one, in all five files (session 2).
- [x] Added the decision menu: code shows the orchestrator only the decisions possible from the current state (D13, V13, V14, `BACKEND_SPEC.md` §7.5).
- [x] Listed what every label means (§5) and every unclear point found while reviewing (§4, U1–U22).
- [ ] **You:** answer the questions in §4.
- [ ] Build M0 → M8 (`BACKEND_SPEC.md` §16).
- [ ] The frontend update, as its own step after the backend.

## 3. Decisions Already Made (short list)

Full text: architecture spec §15–§26 and `BACKEND_SPEC.md` §0.

| area | decision |
|---|---|
| Detours | They are the orchestrator's **own nodes**. A crafted concept is only an optional link, never where a detour has to go. |
| Side questions | Recorded as ordinary issue nodes and handled with **existing pieces**: answer and save (like I3), or follow as a detour. No new kind of node. |
| Crafters | Run **once per codebase**. Discoveries go into the bank labeled "discovered" and never re-run the crafters. |
| Context | **Fresh tutor and fresh orchestrator per task**, and the learner never sees the break. Context comes as **files** the orchestrator makes readable. |
| Tools | Every file comes with a tool, and every tool comes with a guide (what / when / how; "why this turn" goes in the kit). **Custom tools by default**; primitive SDK tools only for open exploration (the crafters). |
| Traps | **None**, and the learner is never asked what they already know. |
| Phase 1 | **No code runs on the server.** The learner works in their own VS Code and pastes code and results as text. **No test files:** a task is done when its purpose is met, judged by the orchestrator. |
| Concepts | The bank can be huge. Size follows the four tests (claim, proof, split, merge). A concept's status is computed from evidence. |
| Learner map | Keep tutor_v2's story map: one plain line per recorded change, indented by detour depth, with "picking up:" on return and "You are here". |
| Backend | **Supabase Postgres** · orchestrator and tutor on the **Claude API**, crafters on the **Agent SDK** · **Claude Haiku 5.5** (`claude-haiku-5-5`) for every agent · a new package next to tutor_v2 · a new API. |
| Orchestrator output | **if/else**: `{"decision":"continue"}`, or a full decision with **short template names** that the engine resolves from config. Its own instructions are **picked by code from the graph position**. |
| Depth / help | No depth limit (the orchestrator adapts). No help tracking for now. |
| Names | Descriptive everywhere: `decision`, `graph_changes`, `tutor_kit`, `add_evidence`, `start_detour` … The template table (`BACKEND_SPEC.md` §8.3) keeps the old names next to the new ones. |
| Decision menu | Code removes impossible decisions before each orchestrator call. `verify_learning` and `complete_task` only on the task, never inside a detour (D13, V13, V14, `BACKEND_SPEC.md` §7.5). |

## 4. Questions You Still Need to Answer

Two groups. First, the assumptions and questions from `BACKEND_SPEC.md` §0 (**decide A4 first**). Then the unclear points found while reviewing the design.

### 4.1 Assumptions and questions

My recommendation is in the last column; change any you disagree with.

| # | question | my recommendation |
|---|---|---|
| **A4** | **May `continue` carry evidence?** (no kit, no explanation; only "the learner showed X") **This is the most important one.** If not, on-track progress ("✓ Did reproduced the bug") never reaches the learner's map. | yes |
| A1 | Status: lifecycle **OPEN / RESOLVED / DROPPED**, attention **focused / paused_on_stack / set_aside**, readiness computed. (This answers your "OPEN vs ACTIVE" question: ACTIVE was really attention.) | yes |
| A2 | The task crafter keeps a **locked reference solution** per task, so the orchestrator can judge "built correctly". The tutor sees it only through the gate. | yes |
| A3 | **Config = a folder of text files** in the repo, with `CONFIG_DIR` pointing to it (rather than environment variables). | yes |
| A5 | Package name **`tutor_graph`** (`tutor_v3` is already your CLI skill's name). | yes |
| A6 | The orchestrator is called **fresh on every turn**; its memory is the graph. | yes |
| A7 | **A workspace = one user + one imported repo.** It replaces tutor_v2's `codebases` + `sessions`. | yes |
| A8 | The tutor's **answer key** opens only with the `show_answer` template, after **2 or more failed attempts** on the current node. | yes |
| Q9 | Templates exist for knowledge, codebase, debugging and testing situations. Problem solving, implementation, tools/environment, verification and self-regulation (§5 categories 4, 5, 6, 8, 10) have **none**. Write them now, or let them come up during the build? | during the build |
| Q10 | Should the orchestrator map get a **"learner view" switch** that shows the story lines for the same step? | yes, before M4 |

### 4.2 Unclear points found while reviewing (U1–U22)

Places where the design is silent or contradicts itself. A dash means there is no proposal yet. "§" without a file name means `BACKEND_SPEC.md`.

| # | unclear point | where | proposal |
|---|---|---|---|
| U1 | `change_approach` is listed as a decision but never defined: no rule, no story line, no T3 example. | `BACKEND_SPEC.md` §7.4 | — |
| U2 | `verify_learning` has no story line, and how it differs from `continue` with a probe is not written down. | §7.4, §10 | — |
| U3 | Nothing in code reads `assessments`. They only feed the designer view and mostly repeat `decision`. | §7.4 | — |
| U4 | One learner moment can be recorded three times: `add_evidence` (gap), `note_misconception`, then `queue_discovery`. Which one is the source of truth? | §5.2, T3 step 4 | — |
| U5 | A concept gets evidence two ways: directly, or through a resolved node linked to it. When to use which is not written. | §5.4 | — |
| U6 | `add_dependency` vs a nested detour: T3 step 5 is DEPENDENCY_MISSING but uses a nested detour (I2). T3 never uses `add_dependency`. | arch §4, T3 step 5 | — |
| U7 | `closes_when` is optional, and V6 doesn't check it: a node can resolve with any `understands` evidence. | §5.3 V6 | — |
| U8 | The orchestrator picks `state_keys` every turn, though each template seems to need the same keys every time. | §7.4, §8.4 | — |
| U9 | Arch §18 says the tutor kit includes tools; the backend keeps one fixed tool list (prompt cache, arch §26.9). | arch §18 | update arch §18 |
| U10 | The story line `⚠ Found a gap {designer_note}` shows the private `designer_note` to the learner. | §10 | add `found_because` to `create_issue`: one plain sentence for the learner, also used by the sidebar line "↪ You came here because …" (arch §21) |
| U11 | A side question alone (answer briefly, save it) needs a kit, but `continue` can't carry one and the focus doesn't change. Which decision? | §9.5, T3 step 9 | — |
| U12 | Dropping the current focus (`drop_wrong_diagnosis`) leaves no focus, but V3 needs exactly one. Which decision carries the drop, and where does the focus go? | §5.3 V3 | — |
| U13 | Who decides which **template names** the `[menu]` allows? (The decisions half is settled by the decision menu, §7.5.) | §7.1 | — |
| U14 | The position pieces have one line each in the spec; their real instruction text doesn't exist yet. | §7.2 | — |
| U15 | The T3 page turns `bridge_back` off at step 8, which is a `continue`, but `continue` can't change the kit. Either some templates last one turn and code turns them off, or step 8 needs another decision. | T3 step 8, §8.1 | — |
| U16 | `D1` means two things: decision D1 (Supabase) and the discovered concept D1. | `BACKEND_SPEC.md` §0, arch §17 | rename one of them |
| U17 | The T3 pages and arch §21 still say "done when check/test_t3.py passes", but phase 1 has no done-check (D8). | T3 pages, arch §21 | update them |
| U18 | The orchestrator can read the answer key and writes free text into the tutor kit (`closes_when`, `misconception`, `return_note`, `reason_this_turn`). That is a path around the answer-key gate that code never checks. | §8.6 | — |
| U19 | The answer-key gate (A8) opens after 2 `gap` evidence. If the orchestrator records misses as `unclear`, it never opens. | §8.6 | — |
| U20 | Arch §6 and §8 still use OPEN / READY / ACTIVE / BLOCKED / SUSPENDED. If you accept A1, those sections are out of date. | arch §6, §8 | update them after A1 |
| U21 | Arch §25 says the orchestrator probably needs a mid-tier model; D6 uses Haiku 5.5 everywhere, and it is measured only at M7. | arch §25, D6 | — |
| U22 | The T3 pages use a `scratch_pad` tool; the backend tool list has none. | T3 pages, §8.5 | — |

## 5. Labels: What Each One Means

**Labels the system really uses.** They appear in the orchestrator's context and output, in the database and in the designer view.

| label | what it is | who makes it | example |
|---|---|---|---|
| `T3` | a task | the task crafter | T3 = guests always get "Une erreur s'est produite" |
| `C15` | a concept in the bank | the concept crafter | C15 = loop variables outlive the loop |
| `D1` | a concept discovered during a task (see U16) | code, when the task closes | D1 = a test can swap the real OpenAI client for a fake one |
| `I1` | an issue: a stuck point found while the learner works | code, when the orchestrator creates it | I1 = a loop variable only exists if the loop ran |
| `E9` | a piece of evidence: something the learner showed | code | E9 = found question_label (line 610) |
| `3.4` | a change: turn 3, change 4 | code | 3.4 = add_evidence on C15 |
| turn | one learner message and everything it causes | code | — |

**Labels only for reading the design.** No agent ever sees them.

| label | what it is | where |
|---|---|---|
| `A1`–`A8` | assumptions waiting for your yes or no | §4.1 above, `BACKEND_SPEC.md` §0 |
| `D1`–`D13` | decisions you made | `BACKEND_SPEC.md` §0 |
| `Q9`, `Q10` | open questions | §4.1 above |
| `U1`–`U22` | unclear points found while reviewing | §4.2 above |
| `V1`–`V14` | validation rules: checks code runs on every orchestrator output | `BACKEND_SPEC.md` §5.3 |
| `§21` | a section number in a document | — |
| step 3 | one moment of the written T3 example (steps 0–10). The real system calls it a turn. | `t3-tutor-loop.html` |

## 6. Things to Know

- **Haiku 5.5** was released 2026-10-07: `claude-haiku-5-5`, $0.10 / $0.50 per million tokens while a prompt stays **under 100K tokens**, 5× more above. So the tutor compresses its conversation at 80K. Its docs don't say whether it accepts mid-conversation system messages, so the kit goes at the end of the user turn.
- **Network:** on the old laptop, WSL had no network, and pushes and `fly` commands ran from Windows PowerShell.
- **Two git repos:** `dev_master` (this repo, which also tracks the `agentic_tutor/` files) and the nested `agentic_tutor/` repo (GitHub `ALPHAbilal/agentic-tutor`). The nested one is what Vercel and Fly deploy. A push there makes Vercel rebuild the frontend.
- **tutor_v2 is still the running system** until the M8 switch. The docs that describe it stay in `agentic_tutor/docs/` (`INTEGRATION_NOTES.md`, `SPEC_*.md`).
