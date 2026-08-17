"""The db() gateway — ONE tool, menu disclosure inside (F6 + Q8).

Three-step disclosure so full op schemas never sit in the model's tool list:
    db()                      -> the state-filtered MENU (op names + one-liners)
    db(op="record_probe")     -> that op's SCHEMA as text
    db(op=..., args={...})    -> VALIDATE + COMMIT, returns ack+consequence and stashes
                                 the one-line receipt (F5/F7)

`dispatch()` is pure Python and fully testable without the SDK. `make_db_tool()`
wraps it with the SDK's @tool decorator only if the SDK is importable, so the whole
package imports and tests cleanly on a machine with no SDK installed.
"""
from __future__ import annotations

from dataclasses import dataclass

from .db import DB
from .operations import REGISTRY, OpError, menu_for, validate


@dataclass
class Disclosure:
    """What a db() call produced: the text the model sees + the receipt (if a commit)."""
    text: str
    receipt: str | None = None      # set only on a successful commit (drives F7 collapse)
    committed: bool = False


def dispatch(db: DB, role: str, op: str | None = None, args: dict | None = None,
             check: bool = False) -> Disclosure:
    """check=True: validate the args and say what WOULD happen. Nothing is written.

    Without this an agent that wants to confirm a call's shape has only one way to
    find out — make the call. A real M/SURVEY run did exactly that, committing a
    slice and a concept both titled "IGNORE - schema probe artifact" to learn the
    schema. A dry run is cheaper than a polluted spine.
    """
    # step 1 — no op: the menu
    if not op:
        ops = menu_for(db, role)
        body = "\n".join(f"  {o.name} — {o.summary}" for o in ops)
        return Disclosure(
            text=f"tutor state — operations available to you now:\n{body}\n"
                 f"Call db(op=\"<name>\") to see one's args, then db(op, args) to run it.")

    if op not in REGISTRY:
        return Disclosure(text=f"no such operation: {op}. Call db() for the menu.")

    operation = REGISTRY[op]
    if operation.role not in (role, "both"):
        return Disclosure(text=f"'{op}' is not available to agent {role}.")

    # step 2 — op but no args: the schema
    if args is None:
        if not operation.available(db):
            return Disclosure(text=f"'{op}' is not applicable in the current state.")
        return Disclosure(text=operation.describe())

    # step 3 — op + args: validate + commit
    try:
        if not operation.available(db):
            raise OpError(f"'{op}' is not applicable in the current state")
        clean = validate(operation, args)
        if check:
            return Disclosure(
                text=f"DRY RUN — args are valid for {op}; nothing was written.\n"
                     f"accepted: {clean}\nCall again without check to commit.")
        result = operation.run(db, clean)
    except OpError as e:
        # refusal: nothing committed, no receipt persists
        return Disclosure(text=f"REFUSED: {e}")
    return Disclosure(text=result.text, receipt=result.receipt, committed=True)


# --------------------------------------------------------------------------
# SDK wrapper (optional import)
# --------------------------------------------------------------------------
def make_db_tool(db: DB, role: str, on_commit=None):
    """Build the in-process MCP `db` tool bound to this db + role.

    on_commit(receipt): optional callback so the orchestrator's ContextManager can
    stash the receipt for F7 collapse. Raises at call time if the SDK is absent.
    """
    try:
        from claude_agent_sdk import tool
    except ImportError as e:  # pragma: no cover - exercised only with the SDK installed
        raise RuntimeError(
            "claude-agent-sdk is not installed; dispatch() works without it but "
            "make_db_tool() needs the SDK. `pip install claude-agent-sdk`."
        ) from e

    @tool("db", "Interact with tutor state. Call with no args to see what you can do. "
                "Pass check=true to validate a call without writing anything.",
          {"op": str, "args": dict, "check": bool})
    async def _db(a: dict):
        d = dispatch(db, role, op=a.get("op"), args=a.get("args"),
                     check=bool(a.get("check")))
        if d.committed and d.receipt and on_commit:
            on_commit(d.receipt)
        return {"content": [{"type": "text", "text": d.text}]}

    return _db
