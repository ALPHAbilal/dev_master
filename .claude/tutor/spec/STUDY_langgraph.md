# STUDY — how LangGraph builds an agent (and what we borrow)

Source read directly (shallow clones in scratchpad/study/):
  langgraph/libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py  (create_react_agent)
  langgraph/libs/prebuilt/langgraph/prebuilt/tool_node.py            (ToolNode)
No assumptions below — every claim is from those files.

---

## 1. WHAT create_react_agent ACTUALLY IS

It builds a **StateGraph** (a graph of nodes with a routing function) that loops:

```
  [pre_model_hook?] → agent (call_model) → [post_model_hook?] → should_continue
        ↑                                                          │
        └──────────────────  tools  ◄──────────────────────────────┘
                                     (or → generate_structured_response → END)
```

- **agent node** = `call_model`: the single LLM call.
- **pre_model_hook**: optional node BEFORE the LLM. Its documented job: manage the
  message history (trim/summarize) and prepare the model's input.
- **post_model_hook**: optional node AFTER the LLM. Its documented job:
  "human-in-the-loop, guardrails, validation, or other post-processing."
- **should_continue**: a plain routing function — no tool calls → END (or post /
  structured); tool calls present → go to the tools node. Code decides next.
- **generate_structured_response**: a SEPARATE final LLM call that coerces the
  output to a schema (`response_format`), stored under `structured_response`.
- **tools node (ToolNode)**: runs tool calls, with `handle_tool_errors` config and
  a tool-call INTERCEPTOR that can validate a call before `execute()`.
- **interrupt_before / interrupt_after** on `"agent"`/`"tools"`: pause for human
  confirmation before/after an action.
- **remaining_steps**: a budget in state; if < 2 with tool calls pending, the
  agent stops with "need more steps" instead of looping forever.

---

## 2. IT MAPS ALMOST 1:1 TO OUR AGENT CARD

```
 LangGraph                         →  OUR AGENT_CARD / ENGINE
 ───────────────────────────────────────────────────────────────────────
 pre_model_hook (trim/prepare input)  →  PRE: ASSEMBLE (build the minimal packet)
 llm_input_messages vs messages       →  the snapshot (a VIEW) vs the stones (truth)
 agent node (call_model)              →  BODY (the one agent call)
 post_model_hook (guardrails/validate)→  POST: VALIDATE + ENFORCE
 response_format + structured node    →  the STAMP + schema-on-demand
 should_continue (routing fn)         →  ③ ROUTE / NEXT (code picks next step)
 tools node + interceptor             →  GRANT + tool-level pre-check
 handle_tool_errors                   →  ESCALATE (graceful failure)
 interrupt_before/after               →  HANDBACK = STOP (yield to human) / GATE
 remaining_steps budget               →  (GAP — see §4)
 StateGraph + checkpointer/store      →  our ENGINE + the stones
```

Reading their code is strong external validation: the pre/body/post split, the
routing function, structured output as a checked artifact, and human-interrupt as
a first-class rail are exactly the shape we derived independently.

---

## 3. FIVE THINGS WORTH BORROWING (concrete)

1. **`llm_input_messages` vs `messages` — the read-only injection pattern.**
   Their pre-hook can feed the model a trimmed/summarized view WITHOUT overwriting
   stored history. This is precisely our "wakeup packet is a VIEW of the stones,
   never a write." Borrow the discipline explicitly: ASSEMBLE only READS; it may
   summarize for the model but must never mutate a stone. (Validates demoting
   `snapshot` to a per-turn view.)

2. **Structured output as a SEPARATE, checked step — not trust in the main call.**
   They make a distinct LLM call whose only job is to fit the schema. Lesson for
   JUDGE/MAPPER: the STAMP can be produced (or re-coerced) as its own step and is
   always schema-validated. Never assume the reasoning call also formats perfectly.

3. **Human-interrupt is a GRAPH rail, not a prompt instruction.**
   `interrupt_before/after` lives in the harness, not in the agent's words. This
   backs our decision that HANDBACK=STOP is a [CONFIG] rail, not something we ask
   the agent to remember.

4. **A tool-call INTERCEPTOR that can validate before execute().**
   Every tool call passes a checkpoint that may reject it. This is our GRANT +
   per-tool pre-check — and it says: don't just grant a tool, gate each *use* of
   it (e.g. a read must be within the unit's line range).

5. **`handle_tool_errors` as config.**
   Tool failure handling is declared once, at the harness, not scattered in the
   prompt. Fold into our ESCALATE rail as a [CONFIG] policy.

---

## 4. A GAP THEY EXPOSE IN OUR DESIGN

**A global step budget.** LangGraph carries `remaining_steps` to stop runaway
loops. We have `hop_budget` (how many inferences ONE question may chain) but no
ceiling on the whole descent — a pathological run could push child after child
forever. Borrow a `remaining_steps`-style guard: a max stack depth / max steps
per unit, enforced in code (a POST/route invariant), failing safe with a "park +
handoff" instead of looping.

---

## 5. THE BIG STRATEGIC OPTION

LangGraph's StateGraph **is** a generic version of our engine: our steps ≈ their
nodes, our router ≈ their conditional edges (`should_continue`), our stones ≈
their state + checkpointer/store, our schemas ≈ their `response_format`, our
harness ≈ their pre/post hooks + interrupts.

So there are two build paths:
  A. BUILD OUR OWN small engine (full control, no dependency, matches our docs
     exactly). Our specs are already the spec for this.
  B. BUILD ON LANGGRAPH: each tutor step = a node, the router = conditional edges,
     stones = state + store, stamps = response_format, harness = pre/post hooks +
     interrupt. Less engine code to write; inherits checkpointing, streaming,
     persistence, human-in-the-loop for free — at the cost of a big dependency and
     learning its abstractions.

Not deciding here. But it's now a real, informed fork: our engine is not exotic —
it's a specialized StateGraph, which means (B) is genuinely on the table.

---

## 6. WHAT WE DO NOT COPY

- Their agent is ONE model looping over tools. We run FOUR specialized agents
  orchestrated by our engine. In LangGraph terms each of ours is a node/subgraph;
  our multi-agent orchestration is the layer create_react_agent does NOT provide
  (that's LangGraph's lower-level StateGraph, or "supervisor"/"swarm" patterns).
- We keep our stone/step vocabulary; we don't adopt their message-list state model
  wholesale — our state is structured rows (units/axes/...), not a chat transcript.
```
