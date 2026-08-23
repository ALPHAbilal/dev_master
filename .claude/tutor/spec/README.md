# TUTOR — THE SPEC (agentic redesign)

The up-to-date design of the tutor's agentic layer. All these docs are aligned to
the **two-arrow engine** and the **12-stone** data model. Read in this order.

## Read in this order

1. **MASTER.md** — START HERE. The pillar diagram (full flow + who owns each
   step), THE CORE ENGINE (the two-arrow cycle), the five pillars, and the
   SURGERY LOG (every settled design change, including continuity).

2. **WALKTHROUGH.md** — one real unit (`_pinned_qa_group`) walked end-to-end
   with the actual value of every variable at every turn. Read this whenever an
   abstract term in another doc doesn't click. Its storage names predate the
   12-stone model: do not implement its old `codebase-map/` or markdown-handoff
   paths; current ownership and persistence rules are in MASTER/STONES/DATA.

3. **PROCESS.md** — the learning process alone (variables, parameters, the state
   machine, the 15-category learner taxonomy). No agents, no DB — the pure spec
   everything else is derived from.

4. **STONES.md** — the 12 data stores (units · axes · stack · meta · probes ·
   learner · archive · handoff · codebase · schemas · workspace · events). One
   home per fact; automatic events move to archive when a unit closes.

5. **DATA.md** — the production-grade data layer: the stores × steps relation
   grid, real DB columns + example rows, folder file shapes, lifecycle, and the
   open decision list.

6. **CATALOGS.md** — the executable step contracts: wakeup.\* (code→agent),
   return.\* (agent→code), routing (code→code), and live action hooks.

   **ANATOMY.md** — the timing inside one turn: minimal wakeup injection →
   runtime capability loop → emit → code reception. It supports MASTER.md;
   MASTER.md remains authoritative if documents disagree.

   **TECHNICAL_UNIVERSE.md** — the intentionally small Claude Agent SDK surface:
   scoped custom MCP tools, guarded live writes, and deterministic hooks.

   **IMPLEMENTATION_PLAN.md** — the backend-only, staged build sequence for the
   12-stone SQLite architecture. Build and test one stage at a time; no frontend
   is in scope until the backend harness passes.

7. **AGENT_CARD.md** — the blueprint every agent is derived from: stable agent
   behaviour, wakeup-time instructions, capabilities during work, and emit
   requirements. The legacy pre/body/post diagrams need alignment to ANATOMY.md;
   [PROMPT] remains what the AI reads and [CONFIG] remains code-side policy.

   **agents/** — the four filled cards, each derived from AGENT_CARD.md:
   - **agents/MAPPER.md**   — builds the ladder (SCAN), lazy/batched (10 at a time)
   - **agents/TEACHER.md**  — PROBE/TEACH/TEST, learner-facing (POINT is code UI)
   - **agents/JUDGE.md**    — grades an answer → verdict + category
   - **agents/DISTILLER.md**— saves the proof + resets

   **STUDY_langgraph.md** — how LangGraph's create_react_agent works and what we
   borrow (pre/post hooks, structured output, step budget). We build our own.

   **AXES.md** — the 7 axes and each one's evidence_bar (the un-fakeable proof
   TEST generates and JUDGE grades against), with the fake-tells.

   **INTERFACE.md** — known facts about the VS-Code-like interface (real codebase
   access, real in-editor highlighting → POINT is a code UI action). Details later.

8. **AGENTIC_REDESIGN.md** — the original living design doc / rationale. Some of
   it predates the engine split; kept for history and the §6 open decisions.

## The model in one breath

The tutor is a two-arrow cycle: **① code wakes an agent** (keyed by STEP — sets
minimal injection and scoped capabilities) → **② the agent returns SAY and/or a
stamp** (verdict + learner route signal, currently named `category`) → **③ code
routes** and moves the stack (dive down / climb up), then fires the next wakeup.
Live action hooks either handle objective facts in code or wake an agent and
return through the same cycle. New data = a new stone + a line on a template —
never a new engine.

## Status
- Engine + pillar + stones + catalogs + data layer: LIVE, mutually consistent.
- Still open: evidence_bar per axis, hop_budget mechanics, reset grain,
  schema-file format, popped-frame handling. (See each doc's OPEN section.)
- Not yet built: nothing here is code. This is the spec.
