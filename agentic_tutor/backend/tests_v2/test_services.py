"""Stage 2 tests: code-owned workspace, event, archive, handoff, and reads."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import (
    ArchiveService,
    Database,
    EventRecorder,
    HandoffService,
    StaleWorkspaceRevisionError,
    StateReader,
    TutorConfig,
    ValidationError,
    WorkspaceService,
)


def _services():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "session-a")
    db = Database(config.database_path)
    workspace = WorkspaceService(db, config)
    events = EventRecorder(db, config)
    return temp, db, config, workspace, events


def _unit(db: Database, session_id: str = "session-a", slug: str = "main") -> int:
    with db.transaction():
        return int(db.connection.execute(
            "INSERT INTO units(session_id,slug,title,file,lo,hi) VALUES(?,?,?,?,?,?)",
            (session_id, slug, "Main", "solution.py", 1, 8),
        ).lastrowid)


def test_workspace_initializes_one_visible_file_and_guards_revisions():
    temp, db, _, workspace, _ = _services()
    try:
        initial = workspace.initialize(
            target="demo", document_id="learner-main", display_name="solution.py",
            language="python", content="print('one')\n",
        )
        assert initial.revision == 0
        assert (Path(temp.name) / "workspace" / "solution.py").read_text() == "print('one')\n"
        saved = workspace.write(expected_revision=0, content="print('two')\n")
        assert saved.changed and saved.workspace.revision == 1
        loaded, content = workspace.read()
        assert loaded.revision == 1 and content == "print('two')\n"
        try:
            workspace.write(expected_revision=0, content="wrong")
            assert False, "old revisions must be rejected"
        except StaleWorkspaceRevisionError:
            pass
    finally:
        db.close()
        temp.cleanup()


def test_event_recorder_requires_session_owned_unit_and_returns_normalized_rows():
    temp, db, _, workspace, events = _services()
    try:
        workspace.initialize(target="demo", document_id="learner-main", display_name="solution.py", language="python")
        unit_id = _unit(db)
        event_id = events.record(
            unit_id=unit_id, document_id="learner-main", kind="command",
            payload={"command": "pytest -q"}, result={"exit": 1}, revision_hash="abc",
        )
        row = events.list_for_unit(unit_id)[0]
        assert row["id"] == event_id
        assert row["payload"] == {"command": "pytest -q"}
        assert row["result"] == {"exit": 1}
        try:
            events.record(unit_id=999, document_id="learner-main", kind="ui", payload={})
            assert False, "foreign units must not receive session events"
        except ValidationError:
            pass
    finally:
        db.close()
        temp.cleanup()


def test_archive_seals_events_and_snapshot_before_removing_live_rows():
    temp, db, config, workspace, events = _services()
    try:
        workspace.initialize(target="demo", document_id="learner-main", display_name="solution.py", language="python", content="answer = 42\n")
        unit_id = _unit(db)
        event_id = events.record(unit_id=unit_id, document_id="learner-main", kind="edit", payload={"diff": "+answer"})
        archive = ArchiveService(db, config, workspace, events)
        receipt = archive.seal(
            unit_id=unit_id, unit_slug="main", title="Main entry point — first proof",
            final_verdict="OWNED", axes_tested=["RATIONALE"], tests=[], evidence=[f"events:{event_id}"],
        )
        manifest = json.loads((receipt.directory / "manifest.json").read_text())
        assert manifest["event_ids"] == [event_id]
        assert (receipt.directory / "events.jsonl").read_text().strip()
        assert (receipt.directory / "workspace-snapshot.py").read_text() == "answer = 42\n"
        assert events.list_for_unit(unit_id) == []
    finally:
        db.close()
        temp.cleanup()


def test_each_test_event_keeps_its_exact_workspace_revision_for_the_archive():
    temp, db, config, workspace, events = _services()
    try:
        workspace.initialize(
            target="demo", document_id="learner-main", display_name="solution.py",
            language="python", content="answer = 0\n",
        )
        unit_id = _unit(db)

        first = workspace.write(expected_revision=0, content="answer = 41\n").workspace
        first_test = events.record(
            unit_id=unit_id, document_id="learner-main", kind="test",
            payload={"command": "pytest -q"}, result={"exit": 1},
        )
        second = workspace.write(expected_revision=first.revision, content="answer = 42\n").workspace
        second_test = events.record(
            unit_id=unit_id, document_id="learner-main", kind="test",
            payload={"command": "pytest -q"}, result={"exit": 0},
        )

        # Running a test records the exact saved revision; it never resets the learner file.
        assert workspace.read()[1] == "answer = 42\n"
        rows = events.list_for_unit(unit_id)
        assert [row["id"] for row in rows] == [first_test, second_test]
        assert [row["revision_hash"] for row in rows] == [first.revision_hash, second.revision_hash]
        assert [row["payload"]["workspace_checkpoint"]["revision"] for row in rows] == [1, 2]

        receipt = ArchiveService(db, config, workspace, events).seal(
            unit_id=unit_id, unit_slug="main", title="Main", final_verdict="OWNED",
            axes_tested=["RATIONALE"], tests=[], evidence=[],
        )
        manifest = json.loads((receipt.directory / "manifest.json").read_text())
        assert receipt.checkpoint_hashes == tuple(sorted([first.revision_hash, second.revision_hash]))
        assert {item["hash"] for item in manifest["workspace_checkpoints"]} == {
            first.revision_hash, second.revision_hash,
        }
        checkpoint_files = sorted((receipt.directory / "workspace-revisions").iterdir())
        assert [path.read_text() for path in checkpoint_files] == ["answer = 41\n", "answer = 42\n"]
    finally:
        db.close()
        temp.cleanup()


def test_archive_repeat_uses_original_event_ids_and_preserves_later_events():
    temp, db, config, workspace, events = _services()
    try:
        workspace.initialize(target="demo", document_id="learner-main", display_name="solution.py", language="python")
        unit_id = _unit(db)
        first = events.record(unit_id=unit_id, document_id="learner-main", kind="ui", payload={"kind": "opened"})
        archive = ArchiveService(db, config, workspace, events)
        park = {"axis": "RATIONALE", "note": "await learner answer"}
        archive.seal(unit_id=unit_id, unit_slug="main", title="Main", final_verdict="PARKED", axes_tested=[], tests=[], evidence=[], resume_at=park)
        later = events.record(unit_id=unit_id, document_id="learner-main", kind="message", payload={"text": "after closure"})
        receipt = archive.seal(unit_id=unit_id, unit_slug="main", title="ignored on repeat", final_verdict="PARKED", axes_tested=[], tests=[], evidence=[], resume_at=park)
        assert receipt.event_ids == (first,)
        remaining = events.list_for_unit(unit_id)
        assert [row["id"] for row in remaining] == [later]
    finally:
        db.close()
        temp.cleanup()


def test_handoff_and_scoped_state_reader_use_sqlite_not_files():
    temp, db, config, workspace, _ = _services()
    try:
        workspace.initialize(target="demo", document_id="learner-main", display_name="solution.py", language="python")
        handoff = HandoffService(db, config)
        assert handoff.load() is None
        handoff.save({"next_unit": "main", "why": "first unit"})
        assert handoff.load().payload["next_unit"] == "main"
        summary = StateReader(db, config).session_summary()
        assert summary["meta"]["target"] == "demo"
        assert not (Path(temp.name) / "handoff").exists()
    finally:
        db.close()
        temp.cleanup()
