"""Stage 0–1 tests: v2 imports, schema, migrations, transactions, invariants."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from tutor_v2 import Database, InvariantError, TutorConfig


def _unit(db: Database, session: str = "s1") -> int:
    with db.transaction():
        cursor = db.connection.execute(
            "INSERT INTO units(session_id,slug,title,file,lo,hi) VALUES(?,?,?,?,?,?)",
            (session, "entry", "Entry point", "run.py", 1, 4),
        )
    return int(cursor.lastrowid)


def test_v2_imports_without_sdk_or_ui_dependency():
    config = TutorConfig.in_project(Path("C:/example"), "demo")
    assert config.database_path.name == "tutor.sqlite"
    assert config.workspace_root.name == "workspace"
    assert config.archive_root.name == "archive"


def test_fresh_database_has_authoritative_mutable_stones_and_version():
    db = Database()
    tables = {row["name"] for row in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"schema_migrations", "units", "axes", "stack", "meta", "probes", "learner", "handoff", "events"} <= tables
    assert {"journeys", "conversation_messages", "journey_events",
            "semantic_nodes", "semantic_edges", "learner_notes"} <= tables
    assert db.one("SELECT MAX(version) AS version FROM schema_migrations") == {"version": 6}


def test_file_database_enables_wal_and_reopens_cleanly():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "state" / "tutor.sqlite"
        db = Database(path)
        assert db.one("PRAGMA journal_mode")["journal_mode"] == "wal"
        db.close()
        reopened = Database(path)
        assert reopened.one("SELECT MAX(version) AS version FROM schema_migrations") == {"version": 6}
        reopened.close()


def test_v1_events_migrate_to_monotonic_ids_without_losing_rows():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "legacy.sqlite"
        legacy = Database(path)
        unit_id = _unit(legacy)
        legacy.connection.execute("PRAGMA foreign_keys = OFF")
        legacy.connection.executescript("""
            ALTER TABLE events RENAME TO events_v2;
            CREATE TABLE events (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                unit_id INTEGER NOT NULL,
                axis TEXT,
                document_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                result_json TEXT,
                revision_hash TEXT,
                created_at TEXT NOT NULL
            );
        """)
        legacy.connection.execute(
            "INSERT INTO events VALUES(7,'s1',?,NULL,'doc','ui','{}',NULL,NULL,'now')",
            (unit_id,),
        )
        legacy.connection.execute("DROP TABLE events_v2")
        legacy.connection.execute("DELETE FROM schema_migrations WHERE version >= 2")
        legacy.connection.commit()
        legacy.close()
        db = Database(path)
        assert db.one("SELECT MAX(version) AS version FROM schema_migrations") == {"version": 6}
        assert db.one("SELECT id FROM events") == {"id": 7}
        assert "AUTOINCREMENT" in db.one(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'"
        )["sql"].upper()
        db.close()


def test_sqlite_constraints_reject_invalid_axis_and_unit_range():
    db = Database()
    try:
        db.execute(
            "INSERT INTO units(session_id,slug,title,file,lo,hi) VALUES(?,?,?,?,?,?)",
            ("s1", "bad", "Bad", "x.py", 4, 3),
        )
        assert False, "line range check must reject hi < lo"
    except sqlite3.IntegrityError:
        pass

    unit_id = _unit(db)
    try:
        db.execute("INSERT INTO axes(unit_id,axis) VALUES(?,?)", (unit_id, "NOT_AN_AXIS"))
        assert False, "axis check must reject unknown axes"
    except sqlite3.IntegrityError:
        pass


def test_transaction_rolls_back_every_statement_on_failure():
    db = Database()
    try:
        with db.transaction():
            db.connection.execute(
                "INSERT INTO units(session_id,slug,title,file,lo,hi) VALUES(?,?,?,?,?,?)",
                ("s1", "will-rollback", "Rollback", "x.py", 1, 2),
            )
            raise RuntimeError("simulate process failure before commit")
    except RuntimeError:
        pass
    assert db.one("SELECT id FROM units WHERE slug='will-rollback'") is None


def test_parked_stack_cannot_have_two_homes():
    db = Database()
    unit_id = _unit(db)
    try:
        with db.transaction():
            db.connection.execute(
                "INSERT INTO stack(session_id,unit_id,depth,is_top) VALUES(?,?,?,?)",
                ("s1", unit_id, 0, 1),
            )
            db.connection.execute(
                "INSERT INTO handoff(session_id,payload_json,parked_stack) VALUES(?,?,?)",
                ("s1", '{"resume_stack":[]}', 1),
            )
        assert False, "one-home rule must reject duplicate parked stack"
    except InvariantError:
        pass
    assert db.one("SELECT id FROM stack") is None
    assert db.one("SELECT session_id FROM handoff") is None
    db.execute(
        "INSERT INTO handoff(session_id,payload_json,parked_stack) VALUES(?,?,?)",
        ("s1", '{"next_unit":"entry"}', 0),
    )
    assert db.one("SELECT session_id FROM handoff") == {"session_id": "s1"}


def test_only_one_live_top_frame_is_allowed():
    db = Database()
    first = _unit(db)
    with db.transaction():
        second = db.connection.execute(
            "INSERT INTO units(session_id,slug,title,file,lo,hi,ordinal) VALUES(?,?,?,?,?,?,?)",
            ("s1", "child", "Child", "x.py", 5, 8, 1),
        ).lastrowid
    try:
        with db.transaction():
            db.connection.execute("INSERT INTO stack(session_id,unit_id,depth,is_top) VALUES(?,?,?,?)", ("s1", first, 0, 1))
            db.connection.execute("INSERT INTO stack(session_id,unit_id,depth,is_top) VALUES(?,?,?,?)", ("s1", second, 1, 1))
        assert False, "only one frame may be top"
    except InvariantError:
        pass
    assert db.query("SELECT id FROM stack") == []


def test_journey_layer_enforces_state_and_cascades_on_journey_delete():
    db = Database()
    unit_id = _unit(db)
    with db.transaction():
        journey_id = db.connection.execute(
            "INSERT INTO journeys(session_id,root_unit_id) VALUES(?,?)", ("s1", unit_id)
        ).lastrowid
        db.connection.execute(
            "INSERT INTO conversation_messages(journey_id,unit_id,role,message_kind,content,turn_id,sequence) "
            "VALUES(?,?,?,?,?,?,?)",
            (journey_id, unit_id, "tutor", "question", "What does this do?", "t1", 1),
        )
        db.connection.execute(
            "INSERT INTO journey_events(journey_id,unit_id,event_type) VALUES(?,?,?)",
            (journey_id, unit_id, "journey_started"),
        )
    # Journey defaults to LIVE and rejects an unsupported state.
    assert db.one("SELECT state FROM journeys WHERE id=?", (journey_id,)) == {"state": "LIVE"}
    try:
        db.execute("UPDATE journeys SET state='BOGUS' WHERE id=?", (journey_id,))
        assert False, "journey state is constrained"
    except sqlite3.IntegrityError:
        pass
    # Deleting the journey cascades to its conversation and lifecycle facts.
    db.execute("DELETE FROM journeys WHERE id=?", (journey_id,))
    assert db.query("SELECT id FROM conversation_messages") == []
    assert db.query("SELECT id FROM journey_events") == []


def test_conversation_sequence_is_unique_per_journey():
    db = Database()
    unit_id = _unit(db)
    with db.transaction():
        journey_id = db.connection.execute(
            "INSERT INTO journeys(session_id,root_unit_id) VALUES(?,?)", ("s1", unit_id)
        ).lastrowid
    db.execute(
        "INSERT INTO conversation_messages(journey_id,unit_id,role,message_kind,content,turn_id,sequence) "
        "VALUES(?,?,?,?,?,?,?)",
        (journey_id, unit_id, "tutor", "question", "first", "t1", 1),
    )
    try:
        db.execute(
            "INSERT INTO conversation_messages(journey_id,unit_id,role,message_kind,content,turn_id,sequence) "
            "VALUES(?,?,?,?,?,?,?)",
            (journey_id, unit_id, "learner", "answer", "dup", "t2", 1),
        )
        assert False, "sequence must be unique within a journey"
    except sqlite3.IntegrityError:
        pass
