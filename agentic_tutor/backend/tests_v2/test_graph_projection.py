"""Step 4a tests: the live semantic-map producer (agent nodes/edges per turn)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    Database, GraphProjection, Router, SemanticGraphService, SessionRunner, TurnOrchestrator,
    TutorConfig, WakeupBuilder, WorkspaceService,
)
from tutor_v2.contracts import GRADE_CATEGORIES, MAP_NODE_CATEGORIES
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
            map_text = ({"title": f"map:{grade_category}", "summary": f"summary:{grade_category}"}
                        if grade_category in MAP_NODE_CATEGORIES else None)
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": verdict,
                                "category": grade_category, "evidence_ref": "events:1",
                                "hidden_gap": hidden_gap, "map_text": map_text})]
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
        takeaways = [n for n in nodes if n["kind"] == "takeaway"]
        assert takeaways, "a correct-deep grade should mint a takeaway"
        # The node text is the agent's map_text verbatim, not code-derived.
        assert takeaways[0]["title"] == "map:correct-deep"
        assert "probe:" in takeaways[0]["evidence_refs_json"]
        summary = db.one("SELECT summary FROM semantic_nodes WHERE journey_id=? AND kind='takeaway'", (jid,))
        assert summary == {"summary": "summary:correct-deep"}
    finally:
        db.close()
        temp.cleanup()


def test_working_code_wrong_reasoning_emits_a_mechanism_node():
    """The _GRADE_EMISSION change routes this category to a mechanism node."""
    assert _GRADE_EMISSION["working-code-wrong-reasoning"] == ("mechanism", "revealed_gap_in")
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["COMPREHEND"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        projection.on_grade(journey_id=jid, unit_id=unit_id, axis="MECHANISM", turn_id="t1",
                            category="working-code-wrong-reasoning", hidden_gap=None, probe_id=7,
                            map_text={"title": "map:working-code-wrong-reasoning",
                                      "summary": "reasoning gap"})
        nodes = _agent_nodes(db, jid)
        assert any(n["kind"] == "mechanism" and n["title"] == "map:working-code-wrong-reasoning"
                   for n in nodes)
        rels = {e["relationship_type"] for e in _edges(db, jid)}
        assert "revealed_gap_in" in rels
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
        assert any(n["kind"] == "misconception" and n["title"] == "map:misconception"
                   for n in nodes), "the agent's map_text title should appear as a live node"
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


# -- orchestrator-wired projection: distill + cross-turn edges -------------------

def _orch_setup():
    """Build a projection-wired orchestrator over the shared sample, for direct driving."""
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(target="run.py", document_id="learner-main",
                                            display_name="solution.py", language="python")
    graph = SemanticGraphService(db, config)
    projection = GraphProjection(graph)
    orch = TurnOrchestrator(db, config, Router(db, config), graph=graph, graph_projection=projection)
    return temp, db, config, orch, graph, projection


def _unit(slug, axes, lo=1, hi=6):
    return {"slug": slug, "file": "run.py", "lo": lo, "hi": hi, "depth": 0, "parent": None, "axes": axes}


def _map_only(units):
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": units,
                        "order": [u["slug"] for u in units]})]


def _grade_blocks(axis, verdict, category, gap=None):
    map_text = ({"title": f"map:{category}", "summary": f"summary:{category}"}
                if category in MAP_NODE_CATEGORIES else None)
    return [json.dumps({"kind": "return.grade", "axis": axis, "verdict": verdict,
                        "category": category, "evidence_ref": "events:1", "hidden_gap": gap,
                        "map_text": map_text})]


def _edges(db, jid):
    return db.query("SELECT from_node_id,to_node_id,relationship_type FROM semantic_edges "
                    "WHERE journey_id=? ORDER BY id", (jid,))


def test_proof_disproves_prior_gap_dot_code_owned():
    """Disproval is code-owned: proving an axis flips that axis's active gap dot. No distill."""
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["COMPREHEND"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        # A misconception grade mints an active misconception dot on COMPREHEND.
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                              question="What does load do?", save_resume_question=True)
        gap = {"slug": "m", "why": "belief", "axis": "COMPREHEND", "anchor": {"kind": "conceptual"}}
        dive = orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                                  question="What does load do?", answer="wrong",
                                  grade_blocks=_grade_blocks("COMPREHEND", "SHAKY", "misconception", gap))
        misc = db.one("SELECT id,status FROM semantic_nodes WHERE journey_id=? AND kind='misconception'", (jid,))
        assert misc["status"] == "active"
        # The misconception grade opened a child detour; own and finish it to resume the parent.
        child_id = dive.decision.unit_id
        assert child_id != unit_id
        orch.present_question(journey_id=jid, unit_id=child_id, axis="COMPREHEND", turn_id="tc",
                              question="What is iteration?")
        orch.submit_answer(journey_id=jid, unit_id=child_id, axis="COMPREHEND", turn_id="tc",
                           question="What is iteration?", answer="Repeated evaluation.",
                           grade_blocks=_grade_blocks("COMPREHEND", "SOLID", "correct-deep"))
        orch.finish_child(child_unit_id=child_id)
        # A later correct-deep grade on the SAME axis must disprove it — deterministically.
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t2",
                              question="What does load really do?")
        orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t2",
                           question="What does load really do?", answer="reads then returns",
                           grade_blocks=_grade_blocks("COMPREHEND", "SOLID", "correct-deep"))
        after = db.one("SELECT status FROM semantic_nodes WHERE id=?", (misc["id"],))
        assert after == {"status": "disproved"}
        # The disproved_by edge points FROM the gap TO the takeaway that disproved it.
        proof = db.one("SELECT id FROM semantic_nodes WHERE journey_id=? AND unit_id=? "
                       "AND kind='takeaway'", (jid, unit_id))
        edge = db.one("SELECT from_node_id,to_node_id FROM semantic_edges WHERE journey_id=? "
                      "AND relationship_type='disproved_by'", (jid,))
        assert edge == {"from_node_id": misc["id"], "to_node_id": proof["id"]}
    finally:
        db.close()
        temp.cleanup()


def test_distill_does_not_double_the_takeaway_dot():
    """Grade correct-deep then distill the same axis: takeaway is a singleton, not two dots."""
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["COMPREHEND"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                              question="What?", save_resume_question=True)
        orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                           question="What?", answer="reads a file",
                           grade_blocks=_grade_blocks("COMPREHEND", "SOLID", "correct-deep"))
        projection.on_distill(journey_id=jid, unit_id=unit_id, axes_tested=["COMPREHEND"],
                              event_ref=f"unit_distilled:{unit_id}")
        n = db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? "
                   "AND kind='takeaway' AND axis='COMPREHEND'", (jid,))["n"]
        assert n == 1, "sealing an axis must find-or-create, never insert a second dot"
    finally:
        db.close()
        temp.cleanup()


def test_singleton_misconception_dedupes_per_axis():
    """Two misconception grades on the same (unit, axis) produce ONE misconception dot."""
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["COMPREHEND"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        for turn in ("t1", "t2"):
            projection.on_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                turn_id=turn, category="misconception", hidden_gap=None,
                                probe_id=7, map_text={"title": "map:misconception",
                                                      "summary": "summary:misconception"})
        n = db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? "
                   "AND kind='misconception' AND axis='COMPREHEND'", (jid,))["n"]
        assert n == 1, "misconception dots are singletons keyed by (unit, axis)"
    finally:
        db.close()
        temp.cleanup()


def test_prerequisite_dots_still_multiply():
    """prerequisite is intentionally NOT a singleton: two grades on one axis make two dots."""
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["COMPREHEND"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        for turn in ("t1", "t2"):
            projection.on_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                turn_id=turn, category="different-prereq", hidden_gap=None,
                                probe_id=7, map_text={"title": f"prereq:{turn}",
                                                      "summary": f"summary:{turn}"})
        n = db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? "
                   "AND kind='prerequisite' AND axis='COMPREHEND'", (jid,))["n"]
        assert n == 2, "prerequisite dots keep inserting: one axis can uncover several"
    finally:
        db.close()
        temp.cleanup()


def test_child_detour_and_parent_resume_add_cross_turn_edges():
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["RATIONALE"])]))
        jid, parent_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=parent_id, axis="RATIONALE", turn_id="t1",
                              question="Why this structure?", save_resume_question=True)
        gap = {"slug": "prereq", "why": "needs a prerequisite", "axis": "COMPREHEND",
               "anchor": {"kind": "conceptual"}}
        dive = orch.submit_answer(journey_id=jid, unit_id=parent_id, axis="RATIONALE", turn_id="t1",
                                  question="Why this structure?", answer="unsure",
                                  grade_blocks=_grade_blocks("RATIONALE", "MISSING", "misconception", gap))
        child_id = dive.decision.unit_id
        assert child_id != parent_id
        # A code-owned detoured_to edge from the parent anchor to the child anchor.
        assert any(e["relationship_type"] == "detoured_to" for e in _edges(db, jid))
        # Finish the child so the parent resumes; that mints a returned_to edge.
        orch.present_question(journey_id=jid, unit_id=child_id, axis="COMPREHEND", turn_id="t2",
                              question="What is iteration?")
        orch.submit_answer(journey_id=jid, unit_id=child_id, axis="COMPREHEND", turn_id="t2",
                           question="What is iteration?", answer="Repeated evaluation.",
                           grade_blocks=_grade_blocks("COMPREHEND", "SOLID", "correct-deep"))
        orch.finish_child(child_unit_id=child_id)
        assert any(e["relationship_type"] == "returned_to" for e in _edges(db, jid))
    finally:
        db.close()
        temp.cleanup()


def test_replayed_grade_turn_adds_no_duplicate_node():
    temp, db, config, orch, graph, projection = _orch_setup()
    try:
        mapped = orch.commit_map(_map_only([_unit("main", ["COMPREHEND"]), _unit("next", ["RATIONALE"])]))
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                              question="What?", save_resume_question=True)
        blocks = _grade_blocks("COMPREHEND", "SOLID", "correct-deep")
        orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                           question="What?", answer="reads a file", grade_blocks=blocks)
        first = db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? AND kind='takeaway'", (jid,))["n"]
        # Replaying the same evaluated turn must not duplicate the node.
        orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                           question="What?", answer="reads a file", grade_blocks=blocks)
        second = db.one("SELECT COUNT(*) AS n FROM semantic_nodes WHERE journey_id=? AND kind='takeaway'", (jid,))["n"]
        assert first == 1 and second == 1
    finally:
        db.close()
        temp.cleanup()
