# agentic_tutor

The two-agent tutoring core: **Agent M** (planner, never talks to the learner) and
**Agent L** (teacher, the only agent the learner sees). The learner builds the *real*
target codebase by hand, one slice at a time, behind gates.

Design docs (read these first):
- `../docs/tutor-simulation.md` — the pedagogy, as a turn-by-turn trace (Parts A–G).
- `../docs/tutor-sdk-mapping.md` — how each design piece maps to a Claude Agent SDK
  primitive; the build spec and the 7-step build order.

## Layout

```
agentic_tutor/
  schema.sql              the 7 tables (target, slices, concepts, gates, probes,
                          mappings, vocab) + a tiny meta kv. No global `phase` row.
  tutor/
    db.py                 SQLite open + schema bootstrap + row-dict helpers
    operations.py         THE state surface — every mutation is one Operation, each
                          carrying: role, menu-line, state-filter, schema, and a commit
                          that returns (text = ack+consequence, receipt = one-liner)
    gateway.py            db() gateway: dispatch() (pure, testable) = menu -> describe ->
                          commit; make_db_tool() wraps it as an SDK @tool (optional import)
    context_manager.py    ContextManager: owns each agent's history; F1 wipe / F2 turn
                          deltas / F7 debris-collapse are one mechanism here
    frontier.py           load/validate frontier.json (the M->L handoff); empty-key reject
    library.py            the CODE-owned library writes: seed_vocab (frontier lists ->
                          vocab table at slice start) + render_target_md (target.md is
                          generated from the DB spine, never hand-written)
    routing.py            build_l_block() = Part E context router (injected via render, not
                          a hook); gate_wall_decision() = the PreToolUse wall logic (pure)
    routing_m.py          Agent M's side of the same pattern: pick_m_turn() (deterministic
                          wakeups: no target -> SURVEY, filled subhole cell -> SUBHOLE,
                          empty frontier -> PLAN), build_m_block() (the three injected sets,
                          G2/G2a), tools_for_turn() (repo tools only on SURVEY/SUBHOLE)
    hooks.py              SDK wiring for the PreToolUse gate wall (optional SDK import)
  ui/                   the learner-facing interface. Imports tutor read-only; writes
                        ONLY through gateway.dispatch; reaches agents ONLY via Runner.
                        Nothing in tutor/ knows this package exists.
    session.py            adopt a codebase (folder in place / uploaded zip) -> one
                          session root via set_target; the file tree; secret-file filter
    state.py              DB -> the UI payload (spine, DAG, vocab, gate, evidence) and
                          who_is_active(), delegated to routing_m.pick_m_turn
    runner.py             THE SEAM: Runner.turn(text) -> [Event]. ScriptedRunner (no
                          model, what the UI is tested against) + SdkRunner (steps 4-6)
    server.py             stdlib http.server; handle() is a pure, socket-free router
    app.html              the whole front end: one file, no npm, no framework
  tests/                  zero-dependency tests (+ fixtures/frontier_pinned_qa.json)
  run_tests.py            `python3 run_tests.py` — no pytest needed
```

## Run the interface

```
cd agentic_tutor && python3 -m ui            # http://127.0.0.1:8765
```

The first screen asks for a codebase — a folder on this machine or a dropped zip.
Nothing is hardcoded; until `set_target` commits, that screen is the whole app. After
that you get the transcript, a live active-agent line (`M/SURVEY` / `M/PLAN` /
`M/SUBHOLE` / `L`), the spine, the concept DAG, the vocabulary door, any open gate, and
the file tree with the gated file marked as yours. The chat runs on `ScriptedRunner`
until build-order steps 4-6 land; `SdkRunner` says so plainly rather than faking it.

## Status (per the build order in tutor-sdk-mapping.md §5)

- [x] **1. DB + db() gateway** — 7 tables; every op menu-able, schema-gated, ships a
  receipt; refusals commit nothing.
- [x] **2. ContextManager** — append / collapse / render; F1/F2/F7 unified.
- [x] **3. Routing + gate wall** — `build_l_block()` (Part E, injected via render since we
  own history — not a UserPromptSubmit hook), frontier.json load/validate, and the
  PreToolUse gate wall (`gate_wall_decision` / `pretooluse_decision`).
- [x] **3b. M routing** — `pick_m_turn` / `build_m_block` / `tools_for_turn`: M's three
  turns as one agent + three injected sets (G2a survey block, lazy specs, [EVIDENCE]
  pointer via meta kv). The pure half of steps 5–7; only the SDK loop remains for them.
- [ ] 4. L alone on one hand-authored frontier.json — walk sim Turns 1–4 live (needs SDK).
- [ ] 5. M alone on real probes rows — write a schema-valid frontier.md.
- [ ] 6. The orchestrator loop (F1 wipe + F4 subhole handoff).
- [ ] 7. **M/SURVEY** — the one-time survey turn (target decomposition into the spine).

## Key invariants (enforced in code, not prose)

- **One gateway, every op** — including hot-path `record_probe`. No first-class tools,
  no side doors (H1). Adding an op = one entry in `operations.REGISTRY`.
- **The library never lies** — `store_mapping` rejects a trigger/solution/why-less
  mapping; `close_gap` refuses without a positive mapping first.
- **One fact, one place** — gates store no paths (the wall joins `slices`); the spine
  lives only in `slices`; OWNED comes only from `close_gap` (`set_concept_state`
  refuses it); READY/BUILT are computed (`set_slice_state` only re-LOCKs); `open_gate`
  refuses a NULL/missing spec (lazy specs: M/PLAN writes file + path in one act).
- **The gate is real** — `open_gate` sets the wall; the PreToolUse hook (step 3) will
  deny spec-reads and target-writes while it's OPEN.
- **We own the history** — the SDK never persists our conversation; ContextManager does.

## Run the tests

```
cd agentic_tutor && python3 run_tests.py
```
