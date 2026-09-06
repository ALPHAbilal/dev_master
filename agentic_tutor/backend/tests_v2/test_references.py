"""Reference (pin) validation + the per-thread pin file store."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import Database, PinStore, ReferenceValidator, TutorConfig, ValidationError


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    codebase = root / "codebase"
    codebase.mkdir()
    (codebase / "run.py").write_text("def main():\n    return 42\n\nprint(main())\n", encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "ws", root / "archive", "s1", codebase_root=codebase)
    db = Database(config.database_path)
    with db.transaction():
        unit_id = int(db.connection.execute(
            "INSERT INTO units(session_id,slug,title,file,lo,hi) VALUES(?,?,?,?,?,?)",
            ("s1", "main", "Main", "run.py", 1, 2)).lastrowid)
        journey_id = int(db.connection.execute(
            "INSERT INTO journeys(session_id,root_unit_id) VALUES(?,?)", ("s1", unit_id)).lastrowid)
        message_id = int(db.connection.execute(
            "INSERT INTO conversation_messages(journey_id,unit_id,role,message_kind,content,turn_id,sequence) "
            "VALUES(?,?,?,?,?,?,?)",
            (journey_id, unit_id, "tutor", "teaching", "recall that out.append(q) mutates in place", "t1", 1)
        ).lastrowid)
    return temp, db, config, journey_id, message_id


def _code_ref():
    return {"kind": "code", "label": "run.py", "snippet": "def main():\n    return 42",
            "source": {"file": "run.py", "lo": 1, "hi": 2}}


def _test_ref():
    return {"kind": "test", "label": "test_main.py", "snippet": "assert main() == 42",
            "source": {"editor_id": "tab-1", "text": "def t():\n    assert main() == 42\n"}}


def _convo_ref(message_id):
    return {"kind": "convo", "label": "conversation", "snippet": "out.append(q)",
            "source": {"message_id": message_id}}


def test_valid_mixed_refs_normalize_preserving_order_and_ids():
    temp, db, config, journey_id, message_id = _setup()
    try:
        refs = [_code_ref(), _test_ref(), _convo_ref(message_id)]
        out = ReferenceValidator(db, config).validate(refs, journey_id=journey_id)
        assert [r["id"] for r in out] == ["pin_01", "pin_02", "pin_03"]
        assert [r["kind"] for r in out] == ["code", "test", "convo"]
        assert out[0]["source"] == {"file": "run.py", "lo": 1, "hi": 2}
        assert out[2]["source"] == {"message_id": message_id}
    finally:
        db.close(); temp.cleanup()


def test_code_ref_rejected_when_snippet_does_not_match_source():
    temp, db, config, journey_id, _ = _setup()
    try:
        bad = _code_ref(); bad["snippet"] = "def main():\n    return 999"
        _expect_invalid(db, config, [bad], journey_id)
    finally:
        db.close(); temp.cleanup()


def test_code_ref_rejects_path_traversal_escape():
    temp, db, config, journey_id, _ = _setup()
    try:
        bad = _code_ref(); bad["source"] = {"file": "../secret.py", "lo": 1, "hi": 2}
        _expect_invalid(db, config, [bad], journey_id)
    finally:
        db.close(); temp.cleanup()


def test_convo_ref_rejected_for_message_outside_journey():
    temp, db, config, journey_id, message_id = _setup()
    try:
        bad = _convo_ref(message_id + 999)
        _expect_invalid(db, config, [bad], journey_id)
    finally:
        db.close(); temp.cleanup()


def test_test_ref_rejected_when_snippet_absent_from_editor_text():
    temp, db, config, journey_id, _ = _setup()
    try:
        bad = _test_ref(); bad["snippet"] = "never appears"
        _expect_invalid(db, config, [bad], journey_id)
    finally:
        db.close(); temp.cleanup()


def test_unknown_kind_and_extra_key_and_overflow_rejected():
    temp, db, config, journey_id, _ = _setup()
    try:
        v = ReferenceValidator(db, config)
        _raises(lambda: v.validate([{"kind": "dom", "label": "x", "snippet": "y", "source": {}}], journey_id=journey_id))
        extra = _code_ref(); extra["extra"] = 1
        _raises(lambda: v.validate([extra], journey_id=journey_id))
        _raises(lambda: v.validate([_code_ref()] * 33, journey_id=journey_id))
        _raises(lambda: v.validate("nope", journey_id=journey_id))
    finally:
        db.close(); temp.cleanup()


def test_pin_store_materializes_files_and_manifest_and_reads_back():
    temp, db, config, journey_id, message_id = _setup()
    try:
        refs = ReferenceValidator(db, config).validate(
            [_code_ref(), _convo_ref(message_id)], journey_id=journey_id)
        store = PinStore(config)
        manifest = store.materialize(thread_id="thread-abc", refs=refs)
        assert [m["path"] for m in manifest] == ["pins/pin_01.txt", "pins/pin_02.txt"]
        assert "run.py:1-2" in manifest[0]["description"]
        # the frozen file content is exactly the snippet, readable through the store
        assert store.read(thread_id="thread-abc", rel_path="pins/pin_01.txt") == "def main():\n    return 42"
        # manifest.json is on disk
        base = config.archive_root.parent / "asides" / "thread-abc"
        assert json.loads((base / "manifest.json").read_text()) == manifest
        # escaping the thread dir is refused
        _raises(lambda: store.read(thread_id="thread-abc", rel_path="../../secret"))
    finally:
        db.close(); temp.cleanup()


def _expect_invalid(db, config, refs, journey_id):
    _raises(lambda: ReferenceValidator(db, config).validate(refs, journey_id=journey_id))


def _raises(fn):
    try:
        fn()
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")
