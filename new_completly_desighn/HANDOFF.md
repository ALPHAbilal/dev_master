# Handoff: Continue Here

Written 2026-10-09, to continue on another laptop. Claude's memory doesn't move between machines; this file and the files it points to carry the whole context.

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
| Orchestrator output | **if/else**: `{"d":"continue"}`, or a full decision with **short template names** that the engine resolves from config. Its own instructions are **picked by code from the graph position**. |
| Depth / help | No depth limit (the orchestrator adapts). No help tracking for now. |

## 4. Questions You Still Need to Answer

These come from `BACKEND_SPEC.md` §0. My recommendation is in the last column; change any you disagree with.

| # | question | my recommendation |
|---|---|---|
| **A4** | **May `continue` carry evidence?** (no kit, no explanation; only "the learner showed X") **This is the most important one.** If not, on-track progress ("✓ Did reproduced the bug") never reaches the learner's map. | yes |
| A1 | Status: lifecycle **OPEN / RESOLVED / DROPPED**, attention **focus / paused / idle**, readiness computed. (This answers your "OPEN vs ACTIVE" question: ACTIVE was really attention.) | yes |
| A2 | Crafter 2 keeps a **locked reference solution** per task, so the orchestrator can judge "built correctly". The tutor sees it only through the gate. | yes |
| A3 | **Config = a folder of text files** in the repo, with `CONFIG_DIR` pointing to it (rather than environment variables). | yes |
| A5 | Package name **`tutor_graph`** (`tutor_v3` is already your CLI skill's name). | yes |
| A6 | The orchestrator is called **fresh on every turn**; its memory is the graph. | yes |
| A7 | **A workspace = one user + one imported repo.** It replaces tutor_v2's `codebases` + `sessions`. | yes |
| A8 | The tutor's **answer key** opens only with the `answer` template, after **2 or more failed attempts** on the current node. | yes |
| Q9 | Templates exist for knowledge, codebase, debugging and testing situations. Problem solving, implementation, tools/environment, verification and self-regulation (§5 categories 4, 5, 6, 8, 10) have **none**. Write them now, or let them come up during the build? | during the build |
| Q10 | Should the orchestrator map get a **"learner view" switch** that shows the story lines for the same step? | yes, before M4 |

## 5. Things to Know

- **Haiku 5.5** was released 2026-10-07: `claude-haiku-5-5`, $0.10 / $0.50 per million tokens while a prompt stays **under 100K tokens**, 5× more above. So the tutor compresses its conversation at 80K. Its docs don't say whether it accepts mid-conversation system messages, so the kit goes at the end of the user turn.
- **Network:** on the old laptop, WSL had no network, and pushes and `fly` commands ran from Windows PowerShell.
- **Two git repos:** `dev_master` (this repo, which also tracks the `agentic_tutor/` files) and the nested `agentic_tutor/` repo (GitHub `ALPHAbilal/agentic-tutor`). The nested one is what Vercel and Fly deploy. A push there makes Vercel rebuild the frontend.
- **tutor_v2 is still the running system** until the M8 switch. The docs that describe it stay in `agentic_tutor/docs/` (`INTEGRATION_NOTES.md`, `SPEC_*.md`).
