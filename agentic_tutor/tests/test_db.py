"""Schema + DB helper tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tutor import DB


def test_schema_creates_seven_tables():
    db = DB()
    names = {r["name"] for r in db.query(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"target", "slices", "concepts", "gates",
            "probes", "mappings", "vocab", "meta"} <= names


def test_meta_kv_roundtrip():
    db = DB()
    assert db.meta_get("active_slice") is None
    db.meta_set("active_slice", "pinned-qa-group")
    assert db.meta_get("active_slice") == "pinned-qa-group"
    db.meta_set("active_slice", "run-loop")            # upsert
    assert db.meta_get("active_slice") == "run-loop"


def test_check_constraints_reject_bad_states():
    db = DB()
    import sqlite3
    try:
        db.execute("INSERT INTO concepts(slug,name,state) VALUES('x','X','BOGUS')")
        assert False, "CHECK constraint should have rejected BOGUS state"
    except sqlite3.IntegrityError:
        pass
