"""runner — the ONE seam between the interface and the agents.

The UI never calls the SDK, never touches ContextManager, never writes the DB. It
calls `Runner.turn(text) -> [Event]` and renders what comes back. That keeps the
interface honest and lets the real agent loop (build order steps 4-6) be dropped in
behind the same three methods without the UI changing.

  ScriptedRunner — replays a canned turn list. No model, no tokens, no network.
                   This is what the UI is developed and tested against.
  SdkRunner      — the real loop. Not built yet (steps 4-6); it raises a message
                   saying so rather than pretending to teach.

An Event is what the learner's screen can show: agent prose, a state change receipt,
or a notice that control moved to another agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from tutor.db import DB


@dataclass
class Event:
    kind: str            # 'say' | 'receipt' | 'handoff' | 'error'
    text: str
    agent: str = "L"

    def as_dict(self) -> dict:
        return asdict(self)


class Runner:
    """The interface's whole view of the agent system."""

    name = "runner"

    def turn(self, learner_text: str) -> list[Event]:
        raise NotImplementedError

    def frontier_empty(self) -> bool:
        """Drives the active-agent indicator (see state.who_is_active)."""
        return True


@dataclass
class ScriptedRunner(Runner):
    """Replays scripted replies in order; repeats the last one when the script runs out."""

    db: DB
    script: list[list[Event]] = field(default_factory=list)
    _i: int = 0
    _frontier_empty: bool = True

    name = "scripted"

    def turn(self, learner_text: str) -> list[Event]:
        if not self.script:
            return [Event("say", "(scripted runner has no script loaded)", "L")]
        events = self.script[min(self._i, len(self.script) - 1)]
        self._i += 1
        return events

    def frontier_empty(self) -> bool:
        return self._frontier_empty

    def set_frontier_empty(self, value: bool) -> None:
        self._frontier_empty = value


@dataclass
class SdkRunner(Runner):
    """The real L/M loop. Build order steps 4-6 — not implemented yet."""

    db: DB
    name = "sdk"

    def turn(self, learner_text: str) -> list[Event]:
        return [Event(
            "error",
            "The live agent loop is not built yet (build order steps 4-6: the L runner, "
            "the M runner, and the orchestrator). The interface is running against the "
            "scripted runner until then.",
            "system")]


def default_script() -> list[list[Event]]:
    """A minimal walk so the interface is demonstrably alive before the loop exists."""
    return [
        [Event("say", "Before I explain anything: look at the file you're about to write. "
                      "What do you think it has to produce?", "L")],
        [Event("say", "That's a guess worth testing. Write the smallest version that "
                      "could be wrong, and we'll find out where it breaks.", "L"),
         Event("receipt", "probe: recorded (predict, PARTIAL)", "L")],
        [Event("handoff", "L handed a shaky prerequisite to M and is holding.", "M/SUBHOLE")],
    ]
