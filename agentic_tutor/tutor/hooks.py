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

import json
from pathlib import Path

from .db import DB
from .routing import gate_wall_decision, post_commit_guidance


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


def posttooluse_note(db: DB, input_data: dict) -> dict:
    """Pure PostToolUse logic → SDK hook output dict. Testable without the SDK.

    The mid-turn injection channel: after L commits a record_probe through db(), the
    router (post_commit_guidance) picks the ONE instruction that applies to the state
    the probe just created — ladder rung on a MISS, close protocol on a HIT, hard stop
    at the push cap. This is how late-phase guidance reaches L without being dumped
    into the turn-1 block.
    """
    tool = input_data.get("tool_name", "")
    if not tool.endswith("db"):
        return {}
    op = (input_data.get("tool_input") or {}).get("op") or ""
    if op not in ("record_probe", "store_mapping", "close_gap", "pass_gate", "record_review"):
        return {}
    gap = _current_gap(db)
    note = post_commit_guidance(db, gap, op)
    if not note:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[tutor router] {note}",
        },
    }


def _current_gap(db: DB) -> dict | None:
    """The published frontier's gap, or None. Read raw — a schema miss just means no note."""
    path = Path(db.meta_get("library_root", "library")) / "frontier.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("gap")
    except (OSError, ValueError, AttributeError):
        return None


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

    async def post_tool_use(input_data, tool_use_id, context):
        return posttooluse_note(db, input_data)

    return {"PreToolUse": [HookMatcher(hooks=[pre_tool_use])],
            "PostToolUse": [HookMatcher(hooks=[post_tool_use])]}
