"""hooks — SDK wiring for the interceptors that MUST be hooks (optional SDK import).

Under orchestrator-owned history (tutor-sdk-mapping.md §3), per-turn context injection
is done by ContextManager.render() + routing.build_l_block(), NOT a UserPromptSubmit
hook. What genuinely needs an SDK hook is interception of the model's OWN tool calls
mid-turn:

  PreToolUse (the gate wall) — deny Read of the spec / Write of the target while a gate
                               is OPEN. This is the blank-page wall; it cannot live in
                               render() because it must intercept the model's file tools.
  PostToolUse (delta note)   — after a file tool runs, surface a one-line reminder if the
                               gate state is relevant. Consequence for db() ops is already
                               in the tool return (F5); this only covers cross-call file
                               steering the tool return can't see.

`make_hooks(db)` returns the SDK `hooks=` mapping; it imports the SDK lazily so the rest
of the package (and its tests) run with no SDK installed.
"""
from __future__ import annotations

from .db import DB
from .routing import gate_wall_decision


def pretooluse_decision(db: DB, input_data: dict) -> dict:
    """Pure PreToolUse logic → SDK hook output dict. Testable without the SDK."""
    tool = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {}) or {}
    decision, reason = gate_wall_decision(db, tool, tool_input)
    if decision == "deny":
        return {
            "systemMessage": f"[gate wall] {reason}",
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }
    return {}


def make_hooks(db: DB):
    """Build the SDK `hooks=` mapping bound to this db. Raises if the SDK is absent."""
    try:
        from claude_agent_sdk import HookMatcher
    except ImportError as e:  # pragma: no cover - only with the SDK installed
        raise RuntimeError(
            "claude-agent-sdk is not installed; pretooluse_decision() works without it "
            "but make_hooks() needs the SDK."
        ) from e

    async def pre_tool_use(input_data, tool_use_id, context):
        return pretooluse_decision(db, input_data)

    return {"PreToolUse": [HookMatcher(hooks=[pre_tool_use])]}
