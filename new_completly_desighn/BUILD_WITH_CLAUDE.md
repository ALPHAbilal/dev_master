# Building the LEGO design with Claude

Checked 2026-10-11 against two sources:

- **the official Claude API reference bundled with Claude Code** (its model list is dated 2026-09-25), and
- **live documentation**, gathered by a research agent and checked line by line against that reference.

**Claude Haiku 5.5 was released on 2026-10-07, after the bundled reference was written.** Every Haiku 5.5 fact below comes from live documentation only. Confirm each one at build time with `client.models.retrieve("claude-haiku-5-5")` and a first test call.

Companion to `LEGO.md` (draft 0.21).

---

## 1. Which surface for which agent

```
 agent          surface                                      why
 ─────────────  ───────────────────────────────────────────  ──────────────────────────────────────
 orchestrator   Messages API + tool use (our own loop, or    one fresh call per turn; our own tools;
                the SDK's Tool Runner) + structured outputs  code controls every gate
 evaluator      Messages API + structured outputs, with a    a small, strict verdict; runs inside the
                short tool loop for pull_checkpoints         orchestrator's evaluate call
 tutor          Messages API, streaming, one append-only     a long conversation; free text to the
                conversation per task                        learner
 crafters       Claude Agent SDK (package claude-agent-sdk)  built-in Read, Glob, Grep on a copy of
                                                             the repository + our own tools; offline
```

**Tool Runner and the Agent SDK are different things.** The Tool Runner (`client.beta.messages.tool_runner`, part of the normal `anthropic` package) loops over tools *we* define. The Agent SDK is Claude Code packaged as a library, with its own built-in tools. We use the first for the three live agents and the second only for the crafters.

---

## 2. Each LEGO piece, and how Claude supports it

```
 LEGO piece                       how it is built                                  status
 ───────────────────────────────  ───────────────────────────────────────────────  ──────────
 the question tree (§3)           output_config.format = { type: "json_schema",    confirmed
 = the orchestrator's answer        schema }; branches as anyOf; enum and const
                                    for the options
 allowed schema features          enum · const · anyOf · allOf · $ref/$defs ·      confirmed
                                  nested objects · arrays
 NOT allowed                      recursive schemas · minimum/maximum ·            confirmed
                                  minLength/maxLength · additionalProperties
                                  other than false (every object needs false)
 a schema that changes            each new schema is compiled once, then cached    confirmed
                                  for 24 hours
 validating the answer            client.messages.parse() checks it against the   confirmed
                                  schema
 tools + structured answer        both in one request: the model calls tools,     confirmed
 in the same call                 then gives the structured final answer
 evaluate (a tool that runs       a normal tool we define, strict: true; our code  confirmed
 another model call)              runs the evaluator call and returns its verdict
                                  as the tool_result
 several tool calls at once       on by default; return ALL results in ONE user   confirmed
                                  message; a failed tool gets is_error: true
 forcing a tool                   tool_choice "any" / "tool" returns a 400 on      confirmed
                                  Opus 5.5, Sonnet 5.5 and Fable 5.1; unknown on   (Haiku 5.5:
                                  Haiku 5.5 → we never rely on forcing             unknown)
 Read · Grep for the              on the Messages API these are OUR tools,         by design
 orchestrator and the evaluator   limited to the temporary folder (the Agent SDK
                                  has them built in, but we don't use it there)
 the instructions for this turn   the tutor's top-level system prompt, rebuilt     decided
                                  by code every turn; history = everything said
                                  and done (messages, tool calls, results,
                                  replies); old thinking is not sent back,
                                  because the newest models reject old thinking
                                  once the system prompt has changed
 the tutor's conversation         fresh for every task, like every agent (your     decided
                                  decision), so it never gets near the model's
                                  limit: no compaction needed
 old thinking                     a thinking block is only valid while everything  confirmed
                                  before it (system prompt included) is unchanged  for the
                                  (a 400 for new accounts) → we never send old     newest models
                                  thinking back; old messages, tool calls and
                                  results are kept as they are
 effort per agent                 output_config.effort: low · medium · high ·      confirmed
                                  xhigh · max; we set one effort per agent
 refusals                         stop_reason "refusal" + stop_details; check it   confirmed
                                  before reading the content (our "broken
                                  answer" rule: retry once, then no change)
 retries                          the SDK retries 408, 409, 429 and 5xx itself     confirmed
                                  (2 times by default); catch typed errors,
                                  most specific first
 counting tokens                  client.messages.count_tokens (free): watch the   confirmed
                                  tutor's conversation before the 100K price step
```

---

## 3. Later, not now: speed and cost

Your decision: caching and schema reuse are optimizations for later, and now they would be over-engineering. The design stays as `LEGO.md` has it: gated tools and an answer format built for each turn. The one fact to remember for later: Claude caches a prompt as a prefix (tools, then system, then messages), so a tool list or a system prompt that changes every turn can't be cached.

---

## 4. Decided: instructions are never history

The tutor's instructions for this turn go in its system prompt, and code rebuilds them every turn. Its history keeps everything that was said and done in the task: the learner's messages, its tool calls and their results, and its replies. Old thinking is not sent back. This works on every model, so it needs no special feature and no test (see `LEGO.md` §11.5).

---

## 5. Claude Haiku 5.5, from live documentation (confirm at build time)

```
 model ID          claude-haiku-5-5
 context window    1M tokens
 maximum output    128K tokens
 price             $0.10 input · $0.50 output per million tokens, up to 100K-token prompts
                   $0.50 input · $2.50 output above 100K
 thinking          adaptive, steered by effort (default: medium)
 released          2026-10-07
```

The research agent suggested a stronger model for the evaluator if its accuracy matters most. Your decision is Haiku 5.5 for every agent. We measure that choice with the task 3 scenario before changing anything.

---

## 6. Corrections to the research report

The research agent's report was checked against the official reference, and these points were wrong or unsupported:

```
 the report said                                   the official reference says
 ────────────────────────────────────────────────  ────────────────────────────────────────────
 compaction: "five strategies, snip compact,       that describes Claude Code's own CLI, not
 auto-triggers at 83.5%"                           the API; the API has beta compact-2026-01-12
                                                   (around 150K tokens) and context editing
 mid-conversation system messages: "not            supported on Opus 5, Opus 5.5, Opus 4.8,
 supported"                                        Fable 5/5.1, Sonnet 5.5 (not Sonnet 5)
 tool_choice "any" / "tool" as normal options      a 400 on Opus 5.5, Sonnet 5.5, Fable 5.1
 Tool Runner loop: "for msg in runner"             runner.until_done() in Python
 Haiku 5.5 latency "10 to 50 milliseconds"         no source; dropped
 limits "16 union types", "20 strict tools",       not in the official reference; treat as
 "24 optional parameters"                          unverified until a test call proves them
 Agent SDK "client.usage_stats", version 0.2.131   not verified; check the package at build time
 an "idempotency_key" header                       not documented; not used
```

---

## 7. Still to verify with a first test call

```
 · Haiku 5.5: structured outputs (live docs say yes)
 · Haiku 5.5: forced tool_choice                                  → we don't rely on it either way
 · the size limits of anyOf schemas for our question tree
 · the Agent SDK's current version and its options for the crafters
```
