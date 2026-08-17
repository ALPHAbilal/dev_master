"""ContextManager — the orchestrator owns each agent's history (F1/F2/F7 in one place).

The SDK has no mid-session transcript editing, so we do NOT delegate conversation
memory to it. This class is our canonical message list. Each turn the orchestrator:

    cm.collapse()                      # F7: swap completed db() procedures for receipts
    prompt = cm.render(opening, cont)  # F2: opening framing turn 1, continue framing after
    ... call the model stateless with `prompt` ...
    cm.append(Turn('assistant', ...))  # write the new turns back

  - F1 (wipe)   = drop the ContextManager and make a new one at slice boundary.
  - F2 (deltas) = render() picks opening vs continue by `is_first_turn`.
  - F7 (trim)   = collapse() replaces a menu->describe->execute run with its receipt line.

Pure Python, no SDK, no model — unit-testable with plain Turn lists.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Turn kinds:
#   learner   — the human's message (L only)
#   assistant — the agent's own text
#   tool      — one db() exchange (menu / describe / commit); collapsible
#   receipt   — the one-line survivor a completed tool procedure collapses to
KIND_ROLE = {"learner": "user", "assistant": "assistant", "tool": "tool", "receipt": "note"}


@dataclass
class Turn:
    kind: str
    text: str
    procedure_id: str | None = None     # tool turns carry the procedure they belong to
    receipt: str | None = None          # set on the commit turn; what the run collapses to


@dataclass
class ContextManager:
    role: str                           # 'L' or 'M'
    turns: list[Turn] = field(default_factory=list)
    _completed: set[str] = field(default_factory=set)   # procedure_ids ready to collapse

    # --- writing ------------------------------------------------------------
    def append(self, turn: Turn) -> None:
        self.turns.append(turn)

    def append_learner(self, text: str) -> None:
        self.append(Turn("learner", text))

    def append_assistant(self, text: str) -> None:
        self.append(Turn("assistant", text))

    def append_tool(self, text: str, procedure_id: str, receipt: str | None = None) -> None:
        """Record one db() exchange. `receipt` set on the commit step marks the run done."""
        self.append(Turn("tool", text, procedure_id=procedure_id, receipt=receipt))
        if receipt is not None:
            self._completed.add(procedure_id)

    # --- F7: collapse completed tool procedures to receipts -----------------
    def collapse(self) -> None:
        if not self._completed:
            return
        new: list[Turn] = []
        seen: set[str] = set()
        for t in self.turns:
            pid = t.procedure_id
            if t.kind == "tool" and pid in self._completed:
                if pid not in seen:                     # first turn of this run -> the receipt
                    seen.add(pid)
                    receipt = _receipt_of(self.turns, pid)
                    new.append(Turn("receipt", f"✓ {receipt}", procedure_id=pid))
                # subsequent turns of the run are dropped
                continue
            new.append(t)
        self.turns = new
        self._completed.clear()

    # --- F2: is this the opening turn of the slice? -------------------------
    @property
    def is_first_turn(self) -> bool:
        return not any(t.kind in ("learner", "assistant") for t in self.turns)

    # --- rendering the next prompt -----------------------------------------
    def render(self, opening_block: str = "", continue_block: str = "") -> str:
        """Assemble the exact prompt for the next stateless model call.

        History (already collapsed) first, then the injected routing block: the
        opening block on turn 1 of the slice, the continue block on every later turn.
        """
        lines: list[str] = []
        for t in self.turns:
            tag = KIND_ROLE.get(t.kind, t.kind).upper()
            lines.append(f"[{tag}] {t.text}")
        block = opening_block if self.is_first_turn else continue_block
        if block:
            lines.append("")
            lines.append(block.strip())
        return "\n".join(lines).strip()

    # --- introspection (tests / debugging) ---------------------------------
    def tool_turn_count(self) -> int:
        return sum(1 for t in self.turns if t.kind == "tool")

    def receipts(self) -> list[str]:
        return [t.text for t in self.turns if t.kind == "receipt"]


def _receipt_of(turns: list[Turn], pid: str) -> str:
    for t in turns:
        if t.procedure_id == pid and t.receipt is not None:
            return t.receipt
    return pid
