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
    routing.py            build_l_block() = Part E context router (injected via render, not
                          a hook); gate_wall_decision() = the PreToolUse wall logic (pure)
    hooks.py              SDK wiring for the PreToolUse gate wall (optional SDK import)
  tests/                  zero-dependency tests (+ fixtures/frontier_pinned_qa.json)
  run_tests.py            `python3 run_tests.py` — no pytest needed
```

## Status (per the build order in tutor-sdk-mapping.md §5)

- [x] **1. DB + db() gateway** — 7 tables; every op menu-able, schema-gated, ships a
  receipt; refusals commit nothing.
- [x] **2. ContextManager** — append / collapse / render; F1/F2/F7 unified.
- [x] **3. Routing + gate wall** — `build_l_block()` (Part E, injected via render since we
  own history — not a UserPromptSubmit hook), frontier.json load/validate, and the
  PreToolUse gate wall (`gate_wall_decision` / `pretooluse_decision`).
- [ ] 4. L alone on one hand-authored frontier.json — walk sim Turns 1–4 live (needs SDK).
- [ ] 5. M alone on real probes rows — write a schema-valid frontier.md.
- [ ] 6. The orchestrator loop (F1 wipe + F4 subhole handoff).
- [ ] 7. SCAN / COVERAGE (one-time target decomposition).

## Key invariants (enforced in code, not prose)

- **One gateway, every op** — including hot-path `record_probe`. No first-class tools,
  no side doors (H1). Adding an op = one entry in `operations.REGISTRY`.
- **The library never lies** — `store_mapping` rejects a trigger/solution/why-less
  mapping; `close_gap` refuses without a positive mapping first.
- **The gate is real** — `open_gate` sets the wall; the PreToolUse hook (step 3) will
  deny spec-reads and target-writes while it's OPEN.
- **We own the history** — the SDK never persists our conversation; ContextManager does.

## Run the tests

```
cd agentic_tutor && python3 run_tests.py
```
