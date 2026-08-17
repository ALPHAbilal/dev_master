# Tutor — Claude Agent SDK Implementation Mapping

How every piece of the design (`tutor-simulation.md`) lands on a concrete Claude Agent
SDK primitive. This is the build spec: if a design idea has no row here, it isn't
buildable yet and we stop and solve it first.

SDK facts current as of the Python `claude-agent-sdk` (v0.2.x, Claude Code 2.1.x),
fetched 2026-08-16 from code.claude.com/docs/en/agent-sdk.

---

## 1. The one architectural decision the SDK forces

**L and M are two SEPARATE top-level sessions, NOT parent + subagent.**

The SDK's subagent model (`AgentDefinition` + the `Agent` tool) is parent-spawns-child:
the child runs in isolation and only its *final message* returns to the parent, which
may summarize it. That is the wrong shape for us — M and L are peers with independent
lifecycles, and the channel between them is the DB, not a return value.

So our Python **orchestrator** owns the loop and runs two independent conversations:

```
orchestrator (our code, the deterministic spine)
  ├─ L session   ClaudeSDKClient(options_L)   ← talks to learner, one per SLICE
  └─ M session   query(options_M)             ← plans, one per PLANNING TURN
        both reach state only through our in-process MCP tools (the db() gateway)
        both are steered only through our hooks (routing + injection)
```

This is what makes the F1 wipe trivial (below) and keeps the M/L wall absolute (neither
is in the other's context — they never share a session).

---

## 2. The mapping table

| Design piece (sim doc) | SDK primitive | How |
|---|---|---|
| **7 DB tables** | our code + SQLite | unchanged; the SDK never sees the DB directly |
| **Function-tool mindset (H1)** | `@tool` + `create_sdk_mcp_server` | in-process MCP server, no subprocess, no shell. Every mutation is a tool call. |
| **`db()` gateway + menu disclosure (F6)** | ONE `@tool` named `db` | its schema is one arg. Call with none → returns the state-filtered menu as text; call with an op name → returns that op's schema-as-text; call with args → validates + commits. The full op docs never sit in the tool list. **This is the ONLY tutor-state tool** — see Q#8 below. |
| **Every op through the menu (Q#8, DECIDED)** | no extra tools | even hot-path ops (`record_probe`) go through `db()`. One gateway, one pattern, zero exceptions — the tool list stays constant and tiny. Menu round-trips are made cheap by F7 (they get collapsed to a receipt next turn anyway). |
| **Post-tool injection: ack + consequence (F5)** | `PostToolUse` hook → `hookSpecificOutput.additionalContext` | the hook reads the tool result, appends the steering line ("cap hit: stop"). This is EXACTLY the documented use of `additionalContext`. |
| **Per-turn routing: frontier + blocks (Part E)** | `ContextManager.render()` + `routing.build_l_block()` | NOT a UserPromptSubmit hook — because we own history (§3) we assemble the prompt ourselves, so injection is part of render(). `build_l_block` is a pure `state → text` function of DB + frontier. |
| **Reactive injection: DB delta / keyword (F3)** | same `build_l_block()` | it reads live DB state (open gate, vocab status, subhole cell) each turn; keyword scan on the learner message folds in here too. |
| **First-turn vs continue set (F2)** | `render(opening, continue)` picks by `is_first_turn` | deterministic: the ContextManager knows whether the slice has any learner/assistant turns yet. |
| **The GATE wall (Turn 4)** | `PreToolUse` hook, `permissionDecision: "deny"` | while a gates row is OPEN: deny `Read` of the spec path, deny `Write`/`Edit` of the target file. Verbatim the ".env protection" example pattern. |
| **Vocab door** | `PreToolUse` hook on the L send-tool | deny an outgoing question that contains a vocab-hold term. |
| **Fresh context per slice / planning turn (F1)** | orchestrator-owned history (see §3) | we assemble each turn's context ourselves and call stateless `query()`. Wiping = starting the next turn's assembly from the stores instead of the prior message list. |
| **Mid-slice history persists** | orchestrator keeps L's message list | within a slice we carry the running list across turns; at gate PASS we drop it. |
| **M keeps context across a subhole** | orchestrator keeps M's message list | subhole = same slice → reuse M's accumulated list. New slice → start M's list empty. |
| **Frontier archive at gate PASS** | our code, on the PostToolUse for `pass_gate` | move frontier.md → history/NNN, write fresh empty frontier. Pure code, no agent. (`PreCompact` is available too but we don't need it for this.) |
| **M/L wall** | two separate sessions | structural: neither appears in the other's transcript. M's only inputs are DB rows we hand it in its prompt; it has no learner-facing tools. |
| **M research tool (online+offline)** | `WebFetch`/`WebSearch` + `Read`/`Grep` in `options_M.allowed_tools` | L gets `Read`/`Grep` only (offline codebase search), no web. |
| **Roads / teaching-support keys** | prompt content, not SDK | G1/G2 cores are the `system_prompt`; frontier.md arrives via the UserPromptSubmit injection. |

---

## 3. F7 — our custom context manager (DECIDED)

**F7** wants: after a `db()` menu→describe→execute procedure completes, delete *only*
those exchanges next turn and replace them with a one-line receipt — while keeping the
rest of the slice's conversation intact.

The SDK does not expose mid-session transcript editing (`resume` replays the whole
history; `PreCompact` only gives a model-generated summary). So **we do not use SDK
session persistence for the conversation at all — we own the history ourselves.**

**The custom context manager** (our code, one class, the heart of the agentic layer):

```
ContextManager(role)               # one per live agent (L for the slice, M for its turns)
  .messages                        # OUR canonical list of turns — the source of truth
  .append(turn)                    # add a learner/assistant/tool turn
  .collapse(procedure_id, receipt) # replace a menu→describe→execute run with one receipt line
  .render()                        # produce the exact prompt for the next stateless query()
```

Each turn the orchestrator:
1. **collapses** any completed `db()` procedure from last turn into its receipt
   (the tool op already returned the receipt string — F5/F6 make sure every op ships one),
2. **renders** the trimmed history + the injected frontier/blocks,
3. calls `query()` **stateless** (`CLAUDE_CODE_SKIP_PROMPT_HISTORY` in `env`, no `resume`)
   with that rendered prompt,
4. **appends** the new turns back into `.messages`.

This collapses F1, F2, and F7 into ONE mechanism — *we* decide, every turn, exactly what
is in context:
- **F1 wipe** = drop the `ContextManager` at slice-BUILT / planning-done and make a new one.
- **F2 turn deltas** = `render()` picks the opening vs continue framing from turn index.
- **F7 debris trim** = `.collapse()` runs before every `render()`.

Cost: we assemble context instead of letting the SDK do it. That cost *is* the product —
context engineering is the whole point, and owning the list is the only way to get
surgical control. The SDK still gives us the model call, the tools, and the hooks; we
just stop delegating memory to it.

---

## 4. Skeleton (the shape, not the final code)

```python
from claude_agent_sdk import (
    ClaudeAgentOptions, query,
    tool, create_sdk_mcp_server, HookMatcher,
)

# --- the ONE gateway tool (F6 + Q8): every op goes through here ---
@tool("db", "Interact with tutor state. Call with no args to see options.",
      {"op": str, "args": dict})
async def db(a):
    op = a.get("op")
    if not op:                       return menu(role=current_role())     # state-filtered menu
    if "args" not in a:              return describe(op)                  # op's schema as text
    return commit(op, a["args"])     # validate + write + return ack + RECEIPT string (F5/F7)

server = create_sdk_mcp_server(name="tutor", tools=[db])   # exactly one tool — no exceptions

# --- the ONE hook that must be a hook: the gate wall (intercepts the model's
#     own Read/Write mid-turn). Injection is NOT a hook — render() does it (§3). ---
def pre_tool_use(inp, _id, _ctx):              # the GATE wall
    return pretooluse_decision(db, inp)        # deny spec-read / target-write while gate OPEN

def options(role):                             # role = "L" or "M"
    return ClaudeAgentOptions(
        system_prompt=L_CORE if role=="L" else M_CORE,      # G1 / G2
        mcp_servers={"tutor": server},
        allowed_tools=(["mcp__tutor__db", "Read", "Grep"] if role=="L"
                       else ["mcp__tutor__db", "Read", "Grep", "WebFetch", "WebSearch"]),
        env={"CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"},       # we own history, not the SDK
        hooks=make_hooks(db),                  # {"PreToolUse": [gate wall]}
    )

# --- the orchestrator loop: WE own the message lists (F1/F2/F7 = one mechanism) ---
async def run_slice(slice):
    L = ContextManager("L")                    # fresh history for this slice (F1)
    M = ContextManager("M")                    # M's history, kept across this slice's subholes
    while not gate_passed(slice):
        L.collapse()                           # F7: trim last turn's db() debris → receipts
        f = load_frontier("library/frontier.json")
        prompt = L.render(opening_block=build_l_block(db, f, True),      # F2 turn 1
                          continue_block=build_l_block(db, f, False))    # F2 later + Part E
        async for m in query(prompt=prompt, options=options("L")):
            L.append(m); handle(m)
        if subhole_filled():                   # F4: M plans, keeps its own accumulated context
            M.collapse_completed_procedures()
            async for m in query(prompt=M.render(inject=evidence_and_overlays()),
                                 options=options("M")):
                M.append(m)
    archive_frontier(slice); write_empty_frontier()    # code does the rollover
    # a brand-new ContextManager("M") next call = fresh M plans the next slice
```

---

## 5. Build order (proposed)

1. **DB + the `db()` gateway tool** (7 tables, every op — including `record_probe` — with
   menu-line + schema + ack + receipt strings. The F5/F6/F7/Q8 contract baked in from birth:
   one tool, every op menu-able, every op ships a receipt.)
2. **The `ContextManager`** (§3): append / collapse / render. Unit-test the collapse →
   receipt trim and the F2 opening-vs-continue rendering with fake message lists — no model.
3. **The three hooks** against a stub frontier: UserPromptSubmit injection, PreToolUse
   gate wall, PostToolUse consequence. Prove routing works with a hand-written frontier.md.
4. **L alone**, one slice, hand-authored frontier.md, driven through the ContextManager —
   walk Turns 1–4 of the sim for real.
5. **M alone**, fed real probes rows — prove it writes a valid frontier.md (schema-gated).
6. **The orchestrator loop** joining them + the F1 wipe + F4 subhole handoff.
7. **SCAN/COVERAGE** (one-time target decomposition) last — it only fills tables the
   loop already consumes.

Each step is runnable and testable before the next. Nothing is built that the trace in
`tutor-simulation.md` doesn't call for.
