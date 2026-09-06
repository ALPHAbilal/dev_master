"""Wiring-layer tests: runnable session, auto-graph, idempotency, archive hooks."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    ArchiveReader, Database, JourneyArchiveService, JourneyReader, Router,
    SemanticGraphService, SessionRunner, TurnOrchestrator, TutorConfig, WakeupBuilder,
    WorkspaceService,
)

_SAMPLE = "def load(path):\n    return read(path)\n\n\ndef read(path):\n    return {}\n"


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(
        target="run.py", document_id="learner-main", display_name="solution.py", language="python"
    )
    router = Router(db, config)
    orchestrator = TurnOrchestrator(
        db, config, router,
        graph=SemanticGraphService(db, config),
        archive=JourneyArchiveService(db, config),
    )
    wakeups = WakeupBuilder(db, config)
    return temp, db, config, router, orchestrator, wakeups


def _map_blocks():
    unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6, "depth": 0, "parent": None, "axes": ["COMPREHEND"]}
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": [unit],
                        "order": ["loader"]})]


def _make_agent():
    """A deterministic scripted agent covering every step the session invokes."""
    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does load(path) do, and why is reading delegated?"]
        if step == "wakeup.grade":
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                                "category": "correct-deep", "evidence_ref": "events:1", "hidden_gap": None,
                                "map_text": {"title": "load reads a file", "summary": "Proved COMPREHEND"}})]
        raise AssertionError(f"unexpected step {step}")
    return run


def test_full_runnable_session_maps_grades_and_auto_attaches_graph():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orchestrator, _make_agent())
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        # Auto-graph fired on mapping: parser nodes exist without a manual ingest call.
        parser_nodes = db.query(
            "SELECT id FROM semantic_nodes WHERE journey_id=? AND provenance='parser'", (jid,))
        assert parser_nodes, "structure graph should auto-attach for the pointed root"

        question = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                        turn_id="t1", save_resume_question=True)
        result = session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                   turn_id="t1", question=question, answer="It reads then returns config.")
        assert result.decision.next_step == "wakeup.distill"
        assert db.one("SELECT verdict FROM axes WHERE unit_id=? AND axis='COMPREHEND'", (unit_id,)) == {"verdict": "SOLID"}
    finally:
        db.close()
        temp.cleanup()


def test_replayed_grade_turn_is_idempotent():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orchestrator, _make_agent())
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        question = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                        turn_id="t1", save_resume_question=True)
        first = session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                  turn_id="t1", question=question, answer="Reads then returns.")
        # Replay the same turn: same decision, and no duplicate probe or answer row.
        second = session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                   turn_id="t1", question=question, answer="Reads then returns.")
        assert second.decision.next_step == first.decision.next_step
        assert db.one("SELECT COUNT(*) AS n FROM probes WHERE unit_id=?", (unit_id,)) == {"n": 1}
        assert db.one("SELECT COUNT(*) AS n FROM conversation_messages WHERE journey_id=? AND role='learner'", (jid,)) == {"n": 1}
    finally:
        db.close()
        temp.cleanup()


def test_finish_root_finalizes_archive_via_wiring():
    temp, db, config, router, orchestrator, wakeups = _setup()
    try:
        session = SessionRunner(config, wakeups, orchestrator, _make_agent())
        mapped = session.run_mapping()
        jid, unit_id = mapped.journey_id, mapped.decision.unit_id
        question = session.run_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                                        turn_id="t1", save_resume_question=True)
        session.run_grade(journey_id=jid, unit_id=unit_id, axis="COMPREHEND",
                          turn_id="t1", question=question, answer="Reads then returns.")
        session.finish_root(root_unit_id=unit_id)
        # The composite archive was written by the finish_root wiring, no manual call.
        archived = ArchiveReader(config).read_journey("loader")
        assert archived["source"] == "archive"
        assert [u["slug"] for u in archived["units"]] == ["loader"]
        # Episode checkpoint present too.
        assert (config.archive_root / "loader" / "episodes" / "0001-owned").is_dir()
    finally:
        db.close()
        temp.cleanup()
