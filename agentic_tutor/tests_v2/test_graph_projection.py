"""Step 4a tests: the live semantic-map producer (agent nodes/edges per turn)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    Database, GraphProjection, Router, SemanticGraphService, SessionRunner, TurnOrchestrator,
    TutorConfig, WakeupBuilder, WorkspaceService,
)
from tutor_v2.contracts import GRADE_CATEGORIES
from tutor_v2.graph_projection import _GRADE_EMISSION

_SAMPLE = "def load(path):\n    return read(path)\n\n\ndef read(path):\n    return {}\n"


def test_every_grade_category_is_handled():
    """Totality guard: no category can be added without an explicit emission decision."""
    assert set(_GRADE_EMISSION) == set(GRADE_CATEGORIES)


def _setup(grade_category="correct-deep", hidden_gap=None):
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(target="run.py", document_id="learner-main",
                                            display_name="solution.py", language="python")
    graph = SemanticGraphService(db, config)
    router = Router(db, config)
    orchestrator = TurnOrchestrator(
        db, config, router,
        graph=graph,
        graph_projection=GraphProjection(graph),
    )
    wakeups = WakeupBuilder(db, config)
    agent = _make_agent(grade_category, hidden_gap)
    session = SessionRunner(config, wakeups, orchestrator, agent)
    return temp, db, config, session


def _map_blocks():
    unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6, "depth": 0, "parent": None,
            "axes": ["COMPREHEND"]}
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": [unit],
                        "order": ["loader"]})]


def _make_agent(grade_category, hidden_gap):
    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["Explain load(path)."]
        if step == "wakeup.teach":
            return ["load reads the file at path and returns its parsed contents."]
        if step == "wakeup.grade":
            verdict = "SOLID" if grade_category == "correct-deep" else "SHAKY"
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": verdict,
                                "category": grade_category, "evidence_ref": "events:1",
                                "hidden_gap": hidden_gap})]
        raise AssertionError(f"unexpected step {step}")
    return run


def _agent_nodes(db, jid):
    return db.query(
        "SELECT kind,title,evidence_refs_json FROM semantic_nodes "
        "WHERE journey_id=? AND provenance='agent' ORDER BY id", (jid,))


def test_teaching_emits_a_live_concept_node_with_message_evidence():
    temp, db, config, session = _setup()
    try:
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        session.run_teaching(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1")
        nodes = _agent_nodes(db, jid)
        concepts = [n for n in nodes if n["kind"] == "concept"]
        assert concepts, "teaching should mint a concept node"
        assert "message:" in concepts[0]["evidence_refs_json"], "concept must cite its messages"
    finally:
        db.close()
        temp.cleanup()


def test_correct_grade_emits_a_takeaway_node():
    temp, db, config, session = _setup(grade_category="correct-deep")
    try:
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        q = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                 turn_id="t1", save_resume_question=True)
        before = db.one("SELECT projection_revision AS r FROM journeys WHERE id=?", (jid,))["r"]
        session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                          question=q, answer="It reads then returns.")
        after = db.one("SELECT projection_revision AS r FROM journeys WHERE id=?", (jid,))["r"]
        assert after > before, "the live map write must ride the projection revision"
        nodes = _agent_nodes(db, jid)
        assert any(n["kind"] == "takeaway" and "probe:" in n["evidence_refs_json"] for n in nodes)
    finally:
        db.close()
        temp.cleanup()


def test_misconception_grade_emits_a_misconception_node():
    gap = {"slug": "path-mutation", "why": "believes load mutates path", "axis": "COMPREHEND",
           "anchor": {"kind": "conceptual"}}
    temp, db, config, session = _setup(grade_category="misconception", hidden_gap=gap)
    try:
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        q = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                 turn_id="t1", save_resume_question=True)
        session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                          question=q, answer="load changes path in place.")
        nodes = _agent_nodes(db, jid)
        assert any(n["kind"] == "misconception" and n["title"] == "believes load mutates path"
                   for n in nodes), "the misconception belief should appear as a live node"
    finally:
        db.close()
        temp.cleanup()


def test_no_emission_category_adds_no_agent_node():
    temp, db, config, session = _setup(grade_category="off-topic")
    try:
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        q = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                 turn_id="t1", save_resume_question=True)
        session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                          question=q, answer="what's for lunch?")
        # off-topic is an explicit no-emission category: no agent node from this grade.
        assert _agent_nodes(db, jid) == []
    finally:
        db.close()
        temp.cleanup()
