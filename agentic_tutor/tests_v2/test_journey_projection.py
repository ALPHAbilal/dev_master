"""Stage 9/10/12 tests: live snapshot, archive round-trip, polling feed."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    ArchiveReader, Database, JourneyArchiveService, JourneyReader, PollingProjectionFeed,
    Router, SemanticGraphService, StructureExtractor, TurnOrchestrator, TutorConfig,
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
    return temp, db, config, Router(db, config)


def _map_blocks():
    unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6, "depth": 0, "parent": None, "axes": ["COMPREHEND"]}
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": [unit],
                        "order": ["loader"]})]


def _grade(axis, verdict, category):
    return [json.dumps({"kind": "return.grade", "axis": axis, "verdict": verdict,
                        "category": category, "evidence_ref": "events:1", "hidden_gap": None})]


def _drive_to_owned(orch, db, config):
    mapped = orch.commit_map(_map_blocks())
    jid, unit_id = mapped.journey_id, mapped.decision.unit_id
    # Attach the parser structure graph for the unit.
    extraction = StructureExtractor(config.codebase_root).extract("run.py")
    SemanticGraphService(db, config).ingest_structure(journey_id=jid, unit_id=unit_id, extraction=extraction)
    orch.present_question(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                          question="What does load do?", save_resume_question=True)
    result = orch.submit_answer(journey_id=jid, unit_id=unit_id, axis="COMPREHEND", turn_id="t1",
                                question="What does load do?", answer="Reads and returns config.",
                                grade_blocks=_grade("COMPREHEND", "SOLID", "correct-deep"))
    assert result.decision.next_step == "wakeup.distill"
    return jid, unit_id


def test_live_snapshot_contains_units_graph_conversation_and_evidence():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        jid, unit_id = _drive_to_owned(orch, db, config)
        snapshot = JourneyReader(db, config).read(jid)
        assert snapshot["source"] == "live"
        assert snapshot["journey"]["state"] == "LIVE"
        assert [u["slug"] for u in snapshot["units"]] == ["loader"]
        assert any(n["provenance"] == "parser" for n in snapshot["semantic_nodes"])
        assert len(snapshot["conversation"]) == 2  # tutor question + learner answer
        assert len(snapshot["evidence"]["probes"]) == 1
        assert snapshot["axis_wording"]["COMPREHEND"] == "What it does"
    finally:
        db.close()
        temp.cleanup()


def test_polling_feed_reports_change_then_no_change():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        jid, _ = _drive_to_owned(orch, db, config)
        feed = PollingProjectionFeed(JourneyReader(db, config))
        first = feed.poll(jid, since_revision=None)
        assert first.changed and first.snapshot is not None
        again = feed.poll(jid, since_revision=first.revision)
        assert not again.changed and again.snapshot is None and again.revision == first.revision
    finally:
        db.close()
        temp.cleanup()


def test_finalized_journey_archive_reads_back_in_the_same_shape():
    temp, db, config, router = _setup()
    try:
        orch = TurnOrchestrator(db, config, router)
        jid, root_unit_id = _drive_to_owned(orch, db, config)
        # Finish the root so the journey is OWNED, then finalize the composite archive.
        orch.finish_root(root_unit_id=root_unit_id)
        archive = JourneyArchiveService(db, config)
        archive.checkpoint_episode(journey_id=jid, episode_number=1, kind="owned")
        receipt = archive.finalize(jid)
        assert receipt.manifest_path.is_file()

        reader = ArchiveReader(config)
        assert reader.list_journeys() == ["loader"]
        archived = reader.read_journey("loader")
        assert archived["source"] == "archive"
        assert [u["slug"] for u in archived["units"]] == ["loader"]
        assert len(archived["conversation"]) == 2
        # conversation.jsonl streamed alongside the manifest
        lines = (receipt.directory / "conversation.jsonl").read_text().strip().splitlines()
        assert len(lines) == 2
    finally:
        db.close()
        temp.cleanup()
