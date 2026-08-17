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
    """The real L turn (build order steps 4+6), behind the same seam as the script.

    Holds ONE ContextManager, bound to the slice the frontier names. A different
    slug on the next turn means the slice rolled over — the old manager is dropped
    and a fresh one made. That drop IS the F1 wipe; nothing else clears history.
    At each fresh start the frontier's vocab lists are seeded (code's job, F3).
    """

    db: DB
    model: str = ""
    trace: list | None = None
    emit: object = None                 # optional streaming sink: Callable[[Event], None]
    _cm: object = None                  # ContextManager for the CURRENT slice
    _slug: str | None = None

    name = "sdk"

    def turn(self, learner_text: str) -> list[Event]:
        from .lesson import DEFAULT_MODEL, LessonError, load_current_frontier, run_lesson_sync

        out: list[Event] = []

        def sink(ev: Event) -> None:
            out.append(ev)
            if self.emit:
                self.emit(ev)           # stream to the transcript as it happens

        try:
            frontier = load_current_frontier(self.db)
        except LessonError as e:
            sink(Event("error", str(e), "L"))
            return out

        if self._cm is None or self._slug != frontier.slice_slug:    # F1: new slice, new mind
            from tutor.context_manager import ContextManager
            from tutor.library import seed_vocab
            self._cm, self._slug = ContextManager("L"), frontier.slice_slug
            seed_vocab(self.db, frontier)

        run_lesson_sync(self.db, self._cm, learner_text, sink,
                        self.model or DEFAULT_MODEL, self.trace)
        return out

    def frontier_empty(self) -> bool:
        from .lesson import LessonError, load_current_frontier
        try:
            load_current_frontier(self.db)
            return False
        except LessonError:
            return True


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
