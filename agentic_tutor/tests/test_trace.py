"""Trace tests: the operator record, and the rule that keeps M out of the learner's view."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tutor import DB, dispatch
from ui.agentrun import LEARNER_FACING
from ui.server import App, handle
from ui.trace import TurnTrace


def _trace(agent="M/PLAN") -> TurnTrace:
    return TurnTrace(agent=agent, model="claude-haiku-4-5-20251001",
                     system_prompt="[EVIDENCE]\n  (none)", first_message="Plan one slice.",
                     tools_allowed=["db"], context_note="Cold.")


# --------------------------------------------------------------------------
# M is invisible to the learner — the design's hardest rule
# --------------------------------------------------------------------------
def test_only_L_may_speak_to_the_learner():
    assert LEARNER_FACING == {"L"}
    for m in ("M/SURVEY", "M/PLAN", "M/SUBHOLE"):
        assert m not in LEARNER_FACING


def test_drive_forwards_prose_only_for_learner_facing_agents():
    """Reading agentrun's rule directly: `visible` gates every emit of model prose."""
    src = (Path(__file__).resolve().parent.parent / "ui" / "agentrun.py").read_text()
    assert "visible = agent in LEARNER_FACING" in src
    assert "if visible:" in src, "prose must be gated, not emitted unconditionally"


# --------------------------------------------------------------------------
# what a turn records
# --------------------------------------------------------------------------
def test_a_turn_keeps_its_instructions_verbatim():
    tr = _trace()
    d = tr.as_dict()
    assert d["system_prompt"] == "[EVIDENCE]\n  (none)"      # not summarised
    assert d["first_message"] == "Plan one slice."
    assert d["tools_allowed"] == ["db"]
    assert d["agent"] == "M/PLAN" and d["model"].startswith("claude-")


def test_tool_calls_keep_their_full_arguments():
    tr = _trace()
    tr.tool("db", {"op": "write_spec", "args": {"slice_slug": "s1", "body": "x" * 300}})
    step = tr.as_dict()["steps"][0]
    assert step["kind"] == "tool" and step["tool"] == "db"
    assert "write_spec" in step["args"] and "x" * 300 in step["args"]   # untruncated
    assert step["at"]


def test_results_receipts_and_errors_are_all_kept():
    tr = _trace()
    tr.tool("db", {"op": "menu"})
    tr.result("tutor state — operations available to you now: ...")
    tr.receipt("spec: s1 -> s1.md")
    tr.error("529 Overloaded")
    kinds = [s["kind"] for s in tr.as_dict()["steps"]]
    assert kinds == ["tool", "result", "receipt", "error"]


def test_counts_tally_tools_by_name():
    tr = _trace()
    tr.tool("Grep", {"pattern": "def "})
    tr.tool("Read", {"file_path": "a.py"})
    tr.tool("Read", {"file_path": "b.py"})
    tr.text("thinking out loud")
    c = tr.as_dict()["counts"]
    assert c["Read"] == 2 and c["Grep"] == 1 and c["text"] == 1


def test_finish_stamps_the_outcome():
    tr = _trace()
    assert tr.as_dict()["ended_at"] == ""
    tr.finish("M/PLAN finished — frontier published")
    d = tr.as_dict()
    assert d["ended_at"] and "frontier published" in d["outcome"]


# --------------------------------------------------------------------------
# the route
# --------------------------------------------------------------------------
def _app() -> App:
    d = Path(tempfile.mkdtemp())
    return App(DB(str(d / "session.db")), str(d / "ws"))


def test_trace_route_starts_empty_and_serialises_turns():
    app = _app()
    r = handle(app, "GET", "/api/trace")
    assert r.status == 200 and r.body["turns"] == []

    app.trace.append(_trace("M/SURVEY"))
    body = handle(app, "GET", "/api/trace").body
    assert len(body["turns"]) == 1
    assert body["turns"][0]["agent"] == "M/SURVEY"
    json.dumps(body)                                  # must be JSON-serialisable


def test_trace_is_not_bundled_into_state():
    """State is polled every second while a turn runs; the verbatim record is large."""
    app = _app()
    app.trace.append(_trace())
    assert "trace" not in handle(app, "GET", "/api/state").body


def test_both_runners_accept_a_trace_and_record_into_it():
    for mod in ("survey", "plan"):
        src = (Path(__file__).resolve().parent.parent / "ui" / f"{mod}.py").read_text()
        assert "trace: list | None = None" in src, f"{mod} must accept a trace"
        assert "trace.append(tr)" in src, f"{mod} must register its turn"
        assert "TurnTrace(" in src, f"{mod} must build a turn record"
