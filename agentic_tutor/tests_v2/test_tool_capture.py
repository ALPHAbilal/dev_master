"""Tool-call capture tests: the conversation's grounding lines + full trace.

The agent seam may return an ``AgentOutput`` (text + captured ``ToolCall`` list) or a legacy
bare ``list[str]``. Capture is best-effort observability: it must never fail a turn, and a
bare-list seam writes zero tool rows.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    Database, GraphProjection, JourneyReader, Router, SemanticGraphService, SessionRunner,
    ToolCall, ToolCallRecorder, TurnOrchestrator, TutorConfig, WakeupBuilder, WorkspaceService,
)
from tutor_v2.domain import AgentOutput

_SAMPLE = "def load(path):\n    return read(path)\n\n\ndef read(path):\n    return {}\n"


def _setup(with_recorder: bool = True):
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(target="run.py", document_id="learner-main",
                                            display_name="solution.py", language="python")
    graph = SemanticGraphService(db, config)
    orchestrator = TurnOrchestrator(
        db, config, Router(db, config),
        graph=graph,
        graph_projection=GraphProjection(graph),
        tool_calls_recorder=ToolCallRecorder(db, config) if with_recorder else None,
    )
    return temp, db, config, orchestrator, WakeupBuilder(db, config)


def _map_blocks():
    unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6, "depth": 0, "parent": None,
            "axes": ["COMPREHEND"]}
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": [unit],
                        "order": ["loader"]})]


_GRADE = json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                     "category": "correct-deep", "evidence_ref": "events:1", "hidden_gap": None,
                     "map_text": {"title": "load reads a file", "summary": "Proved COMPREHEND"}})


def _agent_with_tools(tools_for_step=None, refused_ordinal=None):
    """Deterministic seam: returns AgentOutput with tool calls, or bare list for other steps."""
    tools_for_step = tools_for_step or frozenset()

    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does load(path) do?"]
        if step == "wakeup.grade":
            if step not in tools_for_step:
                return [_GRADE]
            calls = [
                ToolCall("read_code_slice", {}, False, 0),
                ToolCall("read_probe_history", {}, False, 1),
            ]
            if refused_ordinal is not None:
                calls[refused_ordinal] = ToolCall("read_workspace", {}, True, refused_ordinal)
            return AgentOutput([_GRADE], calls)
        raise AssertionError(f"unexpected step {step}")

    return run


def _ask_and_grade(session, jid, unit_id):
    session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1")
    return session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                             question="What does load(path) do?", answer="It reads the file.")


def test_grade_turn_with_tool_calls_persists_and_ships():
    temp, db, config, orch, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orch, _agent_with_tools({"wakeup.grade"}))
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        before = db.one("SELECT projection_revision AS r FROM journeys WHERE id=?", (jid,))["r"]
        _ask_and_grade(session, jid, unit_id)
        rows = db.query("SELECT * FROM tool_calls WHERE journey_id=? AND turn_id='t1' ORDER BY ordinal", (jid,))
        assert [r["capability"] for r in rows] == ["read_code_slice", "read_probe_history"]
        assert all(r["refused"] == 0 for r in rows)
        assert all(r["agent"] == "JUDGE" and r["step"] == "wakeup.grade" for r in rows)
        assert all(r["arguments_json"] == "{}" for r in rows)
        # The revision advanced so the next poll ships the new rows.
        after = db.one("SELECT projection_revision AS r FROM journeys WHERE id=?", (jid,))["r"]
        assert after > before
        # The snapshot ships them; the backend never filters to the grounding subset.
        snapshot = JourneyReader(db, config).read(jid)
        caps = [row["capability"] for row in snapshot["tool_calls"] if row["turn_id"] == "t1"]
        assert caps == ["read_code_slice", "read_probe_history"]
    finally:
        db.close()
        temp.cleanup()


def test_bare_list_seam_still_works_and_writes_no_tool_rows():
    temp, db, config, orch, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orch, _agent_with_tools())
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        _ask_and_grade(session, jid, unit_id)
        assert db.query("SELECT * FROM tool_calls WHERE journey_id=?", (jid,)) == []
        # Normalization: the legacy seam's text still drove the full turn.
        assert db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? "
                      "AND kind='takeaway'", (jid,))["n"] == 1
    finally:
        db.close()
        temp.cleanup()


def test_refused_tool_call_persists():
    temp, db, config, orch, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orch,
                                _agent_with_tools({"wakeup.grade"}, refused_ordinal=1))
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        _ask_and_grade(session, jid, unit_id)
        rows = db.query("SELECT capability,refused FROM tool_calls WHERE journey_id=? "
                        "AND turn_id='t1' ORDER BY ordinal", (jid,))
        assert rows == [{"capability": "read_code_slice", "refused": 0},
                        {"capability": "read_workspace", "refused": 1}]
    finally:
        db.close()
        temp.cleanup()


def test_mapping_capture_lands_under_created_journey_as_map_zero():
    temp, db, config, orch, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orch, _agent_with_tools({"wakeup.map"}))

        def run(wakeup, instruction):
            if wakeup["step"] == "wakeup.map":
                return AgentOutput(_map_blocks(), [ToolCall("search_repository",
                                                            {"query": "load("}, False, 0)])
            raise AssertionError("mapping test only wakes the MAPPER")

        session.agent_run = run
        mapped = session.run_mapping()
        row = db.one("SELECT * FROM tool_calls WHERE journey_id=?", (mapped.journey_id,))
        assert row["turn_id"] == "map:0"
        assert row["agent"] == "MAPPER" and row["unit_id"] is None
        assert row["capability"] == "search_repository"
        assert json.loads(row["arguments_json"]) == {"query": "load("}
    finally:
        db.close()
        temp.cleanup()


def test_missing_recorder_is_byte_for_byte_old_behavior():
    temp, db, config, orch, wakeups = _setup(with_recorder=False)
    try:
        session = SessionRunner(config, wakeups, orch, _agent_with_tools({"wakeup.grade"}))
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        result = _ask_and_grade(session, jid, unit_id)
        assert db.query("SELECT * FROM tool_calls WHERE journey_id=?", (jid,)) == []
        assert db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? "
                      "AND kind='takeaway'", (jid,))["n"] == 1
        assert result.decision is not None
    finally:
        db.close()
        temp.cleanup()


def test_replay_does_not_duplicate_tool_rows():
    """Crash-recovery replay of a turn must not double-write its tool rows."""
    temp, db, config, orch, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orch, _agent_with_tools({"wakeup.grade"}))
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        _ask_and_grade(session, jid, unit_id)
        first = db.query("SELECT * FROM tool_calls WHERE journey_id=? AND turn_id='t1'", (jid,))
        assert len(first) == 2
        # Re-record the same (journey, turn) — the (journey, turn_id) guard makes it a no-op.
        orch.record_tool_calls(
            journey_id=jid, unit_id=unit_id, turn_id="t1", step="wakeup.grade",
            agent="JUDGE", tool_calls=[ToolCall("read_code_slice", {}, False, 0),
                                       ToolCall("read_probe_history", {}, False, 1)])
        second = db.query("SELECT * FROM tool_calls WHERE journey_id=? AND turn_id='t1'", (jid,))
        assert len(second) == 2, "replay must not duplicate tool rows"
    finally:
        db.close()
        temp.cleanup()
