# TUTOR — TECHNICAL UNIVERSE

Status: IMPLEMENTATION REFERENCE. The small technical surface the first version
needs. Add a capability only when a step contract requires it.

## 1. RUNTIME

```text
Claude Agent SDK
  ClaudeSDKClient       persistent agent session / streamed events
  ClaudeAgentOptions    model, prompt, working directory, permissions, tools
  create_sdk_mcp_server custom in-process tutor tools
  @tool                 explicit tool name, schema, description, handler
  hooks                 deterministic interception of tool and user events
```

Use one long-lived `ClaudeSDKClient` for an interactive learning session. The
orchestrator sends a wakeup; the client streams tool calls and results; the
agent emits SAY and/or a stamp; code routes the result.

## 2. CAPABILITY POLICY

```text
DEFAULT: expose no broad Claude Code toolset.

ALLOW:   narrow custom MCP tools with explicit schema, scope, and policy.
BLOCK:   broad Write/Edit, unrestricted Bash, Task/subagents, and unrestricted
         web access unless a later step contract explicitly needs one.

IMPORTANT: allowed_tools auto-approves tools; it does not remove other built-in
tools. Use disallowed_tools to actually remove unwanted built-ins.
```

Every capability is a runtime capability-loop operation:

```text
agent -> custom tool call -> guarded handler -> result/rejection -> same agent
```

The handler may perform a live update while the agent is alive. Every write is
validated, authorized, committed, and logged by the handler before its result
returns to the agent.

## 3. INITIAL TOOL UNIVERSE

These are application tools, not promises that every agent gets all of them.
Each wakeup grants only the subset named by its step contract.

```text
READ CONTEXT
  tutor.read_turn_context       current unit, axis, phase, scoped learner facts
  tutor.read_code_slice         exact code range for a unit
  tutor.read_transcript         relevant learner words/action evidence
  tutor.read_axis_evidence      evidence bar + verdict history
  tutor.read_probe_history      recent Q&A for one unit/axis
  tutor.read_handoff            warm-start context

LIVE WORK / ACTIONS
  tutor.observe_learner_action  command, edit, test output, UI event; recorder
                                 appends to events before policy handling
  tutor.read_workspace           read the one logical learner document
  tutor.write_workspace          guarded edit to the same logical document
  tutor.log_question            records a probe/test question
  tutor.save_resume_question    saves the interrupted parent question
  tutor.record_action_event     persists an allowed observable event

JUDGMENT + ROUTING PROPOSALS
  tutor.record_verdict          validates/stores axis verdict + evidence
  tutor.propose_subhole         proposes a prerequisite child with why
  tutor.queue_sibling           records a non-blocking related hole

DISTILL + MEMORY
  tutor.save_archive            saves titled proof/snapshot and seals events
  tutor.update_learner_model    applies a validated learner diff
  tutor.write_handoff           replaces the warm-start note

CODE-ONLY CONTINUITY (not agent-callable)
  checkpoint_continuation       atomically moves live stack to handoff after a
                                safe boundary and records next_step/awaiting/refs
  restore_continuation          restores stack + workspace revision and creates
                                the ordinary scoped wakeup packet
```

## 4. WHO MAY USE WHAT

```text
MAPPER      read_code_slice / repository-search equivalent
            -> returns a map batch; no learner-facing tools

TEACHER     read_turn_context, read_code_slice, observe_learner_action,
            read_workspace, log_question, save_resume_question
            -> emits SAY; never grades or globally routes

JUDGE       read_transcript, read_code_slice, read_axis_evidence,
            read_probe_history, record_verdict, propose_subhole, queue_sibling
            -> emits verdict/category; never talks to the learner

DISTILLER   read_turn_context, read_probe_history, read_workspace, save_archive,
            update_learner_model, write_handoff
            -> emits a distillation summary; never globally routes

CODE        owns global routing, stack push/pop, unit-state transitions, and
            capability grants, checkpoint/restore. A custom tool may make a
            guarded local write; it cannot bypass these global decisions.
```

## 5. HOOKS = CONDITIONAL FEEDBACK

```text
UserPromptSubmit  gate/normalize a learner message before the agent sees it
PreToolUse        allow, block, or modify a requested tool operation
PostToolUse       audit result, refresh state, or emit factual feedback
```

Use hooks only for deterministic policy. If an action requires interpreting the
learner's intent, words, or reasoning, send its evidence to TEACHER or JUDGE;
code does not classify it.

## 6. TOOL DESIGN LAW

```text
One tool = one meaningful capability.

Every tool definition states:
  name | exact input schema | purpose/when to use | allowed scope |
  validation | result shape | audit event | failure/rejection message

New need -> add a narrow tool + grant it in the relevant wakeup contract.
Never solve a missing capability by giving an agent unrestricted Bash or DB/file
write access.
```

## 7. LATER, NOT NOW

```text
Native Read/Glob/Grep: can be introduced for repository analysis if custom
                         read tools become too limiting.
Bash:                  only a sandboxed, allowlisted test-runner capability.
WebSearch/WebFetch:    only a sourced research step, never default tutoring.
Write/Edit:            only a separate learner-workspace capability; never the
                         target codebase or tutor state directly.
Task/subagents:        defer; the Tutor already has explicit roles and routing.
```
