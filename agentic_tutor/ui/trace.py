"""trace — the operator's record of every agent turn, verbatim.

The learner's transcript shows what L said. This shows everything else: the exact
system prompt an agent was given, the exact first message, which tools it was allowed,
every tool call with its full arguments, every result that came back, and what the turn
finally committed.

Two audiences, two records, and they must not be mixed:

    transcript  what the LEARNER sees. L speaks here. M never does — M is invisible
                by design ("you never talk to the learner"), so an M turn contributes
                at most a one-line notice that it happened.
    trace       what YOU see when studying the system. Everything, unedited.

Nothing here is summarised or truncated on the way in; the UI decides what to fold.
Pure stdlib.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


@dataclass
class Step:
    """One observable event inside a turn."""
    kind: str                    # 'text' | 'tool' | 'result' | 'receipt' | 'error'
    at: str = field(default_factory=_now)
    text: str = ""               # model prose, a receipt line, an error
    tool: str = ""               # tool name, for kind='tool'
    args: str = ""               # full arguments, pretty JSON
    output: str = ""             # what the tool returned, for kind='result'


@dataclass
class TurnTrace:
    """One complete agent invocation, from the prompt it got to what it committed."""
    agent: str                             # 'M/SURVEY' | 'M/PLAN' | 'L'
    model: str
    system_prompt: str                     # verbatim — the injected block, as sent
    first_message: str                     # verbatim
    tools_allowed: list[str] = field(default_factory=list)
    context_note: str = ""                 # why this turn has the history it has (F1/F2)
    started_at: str = field(default_factory=_now)
    ended_at: str = ""
    steps: list[Step] = field(default_factory=list)
    outcome: str = ""

    # --- writing ------------------------------------------------------------
    def text(self, s: str) -> None:
        self.steps.append(Step("text", text=s))

    def tool(self, name: str, args) -> None:
        self.steps.append(Step("tool", tool=name, args=_pretty(args)))

    def result(self, out: str) -> None:
        self.steps.append(Step("result", output=out))

    def receipt(self, r: str) -> None:
        self.steps.append(Step("receipt", text=r))

    def error(self, e: str) -> None:
        self.steps.append(Step("error", text=e))

    def finish(self, outcome: str) -> None:
        self.ended_at = _now()
        self.outcome = outcome

    # --- reading ------------------------------------------------------------
    def as_dict(self) -> dict:
        d = asdict(self)
        d["counts"] = self.counts()
        return d

    def counts(self) -> dict:
        n: dict[str, int] = {}
        for s in self.steps:
            key = s.tool if s.kind == "tool" else s.kind
            n[key] = n.get(key, 0) + 1
        return n


def _pretty(args) -> str:
    if isinstance(args, str):
        return args
    try:
        return json.dumps(args, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(args)
