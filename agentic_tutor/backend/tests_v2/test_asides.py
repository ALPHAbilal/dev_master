"""Aside layer: off-record side questions recorded without touching the graded ladder."""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

from tutor_v2 import (
    ApiHandlers, BASE_ASIDE_INSTRUCTION, CapabilityUnavailableError, Database, EventRecorder,
    JourneyRecorder, Router, TurnOrchestrator, TutorConfig, TutorToolGateway, ValidationError,
    WakeupBuilder, WorkspaceService, build_aside_instruction, build_session,
)

_LADDER = ("units", "axes", "stack", "probes", "meta", "events", "learner", "handoff")


def _setup():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    codebase = root / "codebase"; codebase.mkdir()
    (codebase / "run.py").write_text("\n".join(f"line{i}" for i in range(1, 13)) + "\n", encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=codebase)
    db = Database(config.database_path)
    WorkspaceService(db, config).initialize(
        target="run.py", document_id="m", display_name="s.py", language="python")
    orch = TurnOrchestrator(db, config, Router(db, config))
    mapped = orch.commit_map([json.dumps({
        "kind": "return.map", "target": "run.py", "mode": "initial", "continues_after": None,
        "objective_covered": True,
        "units": [{"slug": "main", "file": "run.py", "lo": 1, "hi": 2, "depth": 0,
                   "parent": None, "axes": ["COMPREHEND"]}],
        "order": ["main"]})])
    return temp, db, config, orch, mapped.journey_id, mapped.decision.unit_id


def _code_ref():
    return {"kind": "code", "label": "run.py", "snippet": "line1\nline2",
            "source": {"file": "run.py", "lo": 1, "hi": 2}}


def test_begin_aside_records_offrecord_question_thread_and_anchor():
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        rid = str(uuid.uuid4())
        res = orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=rid,
                               question="why line1?", refs=[_code_ref()])
        assert res.status == "PENDING" and res.reply_message_id is None
        msg = db.one("SELECT role,message_kind,thread_kind,thread_id,refs_json "
                     "FROM conversation_messages WHERE id=?", (res.learner_message_id,))
        assert msg["role"] == "learner" and msg["message_kind"] == "aside_question"
        assert msg["thread_kind"] == "aside" and msg["thread_id"] == res.thread_id
        assert json.loads(msg["refs_json"])[0]["source"] == {"file": "run.py", "lo": 1, "hi": 2}
        assert db.one("SELECT status FROM aside_turns WHERE id=?", (rid,)) == {"status": "PENDING"}
        assert db.one("SELECT COUNT(*) AS n FROM aside_threads WHERE id=?", (res.thread_id,)) == {"n": 1}
        anchors = db.query("SELECT event_type FROM journey_events WHERE journey_id=? AND event_type='aside'", (jid,))
        assert len(anchors) == 1
        assert (config.archive_root.parent / "asides" / res.thread_id / "manifest.json").is_file()
    finally:
        db.close(); temp.cleanup()


def test_commit_aside_completes_and_is_idempotent():
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        rid = str(uuid.uuid4())
        orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=rid, question="why?", refs=[])
        res = orch.commit_aside(journey_id=jid, request_id=rid, aside_blocks=["Because line1 is first."])
        assert res.status == "COMPLETE" and res.reply_message_id is not None
        reply = db.one("SELECT role,message_kind,content FROM conversation_messages WHERE id=?",
                       (res.reply_message_id,))
        assert reply["role"] == "tutor" and reply["message_kind"] == "aside_reply"
        assert reply["content"] == "Because line1 is first."
        assert db.one("SELECT status FROM aside_turns WHERE id=?", (rid,)) == {"status": "COMPLETE"}
        before = db.one("SELECT COUNT(*) AS n FROM conversation_messages")["n"]
        again = orch.commit_aside(journey_id=jid, request_id=rid, aside_blocks=["totally different"])
        assert again.reply_message_id == res.reply_message_id
        assert db.one("SELECT COUNT(*) AS n FROM conversation_messages")["n"] == before
    finally:
        db.close(); temp.cleanup()


def test_followup_reuses_thread_without_a_second_anchor():
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        first = orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=str(uuid.uuid4()),
                                 question="why line1?", refs=[])
        orch.commit_aside(journey_id=jid, request_id=first.request_id, aside_blocks=["first answer"])
        follow = orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=str(uuid.uuid4()),
                                  question="and line2?", refs=[], thread_id=first.thread_id)
        assert follow.thread_id == first.thread_id
        assert db.one("SELECT COUNT(*) AS n FROM aside_threads WHERE journey_id=?", (jid,)) == {"n": 1}
        anchors = db.query("SELECT id FROM journey_events WHERE journey_id=? AND event_type='aside'", (jid,))
        assert len(anchors) == 1  # follow-ups do not add a new map anchor
    finally:
        db.close(); temp.cleanup()


def test_begin_aside_rejects_non_uuid_and_completed_journey():
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        _raises(lambda: orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id="not-a-uuid",
                                         question="q", refs=[]))
        JourneyRecorder(db, config).set_state(jid, "OWNED", completed=True)
        _raises(lambda: orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=str(uuid.uuid4()),
                                         question="q", refs=[]))
    finally:
        db.close(); temp.cleanup()


def test_aside_never_touches_the_graded_ladder():
    """begin + commit + follow-up must leave every engine stone byte-for-byte unchanged."""
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        before = {t: db.query(f"SELECT * FROM {t}") for t in _LADDER}
        state_before = db.one("SELECT state FROM journeys WHERE id=?", (jid,))
        first = orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=str(uuid.uuid4()),
                                 question="why line1?", refs=[_code_ref()])
        orch.commit_aside(journey_id=jid, request_id=first.request_id, aside_blocks=["an answer"])
        orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=str(uuid.uuid4()),
                         question="follow up?", refs=[], thread_id=first.thread_id)
        after = {t: db.query(f"SELECT * FROM {t}") for t in _LADDER}
        for table in _LADDER:
            assert before[table] == after[table], f"aside mutated the {table} stone"
        # the journey's lesson STATE is untouched (only the additive revision counter moves)
        assert db.one("SELECT state FROM journeys WHERE id=?", (jid,)) == state_before
    finally:
        db.close(); temp.cleanup()


def test_build_aside_packet_is_closed_and_read_pin_only():
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        rid = str(uuid.uuid4())
        orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=rid,
                         question="why line1?", refs=[_code_ref()])
        packet = WakeupBuilder(db, config).build_aside(journey_id=jid, request_id=rid)
        assert packet["step"] == "wakeup.aside" and packet["agent"] == "TEACHER"
        assert packet["capabilities"] == ["read_pin"]
        assert "axis" not in packet
        ctx = packet["context"]
        assert set(ctx) == {"journey_id", "thread_id", "request_id", "unit", "question",
                            "pins", "history", "history_truncated"}
        assert ctx["unit"]["axes"] == ["COMPREHEND"]
        assert ctx["pins"][0]["path"] == "pins/pin_01.txt"
        # no grading/ladder leakage into the aside context
        for leaked in ("axis", "verdict", "stack", "recent_probes", "learner", "workspace"):
            assert leaked not in ctx
    finally:
        db.close(); temp.cleanup()


def test_read_pin_capability_reads_only_scoped_pins():
    temp, db, config, orch, jid, unit_id = _setup()
    try:
        rid = str(uuid.uuid4())
        orch.begin_aside(journey_id=jid, unit_id=unit_id, request_id=rid, question="q", refs=[_code_ref()])
        packet = WakeupBuilder(db, config).build_aside(journey_id=jid, request_id=rid)
        workspace = WorkspaceService(db, config)
        gateway = TutorToolGateway(config, workspace, EventRecorder(db, config, workspace), packet)
        assert gateway.call("read_pin", {"path": "pins/pin_01.txt"}) == {"content": "line1\nline2"}
        # a capability the aside never grants is refused
        _raises(lambda: gateway.call("read_workspace", {}), CapabilityUnavailableError)
        # a path escaping the thread dir is refused
        _raises(lambda: gateway.call("read_pin", {"path": "../../secret"}), ValidationError)
    finally:
        db.close(); temp.cleanup()


def test_build_aside_instruction_injects_only_firing_axes():
    two = build_aside_instruction(["MECHANISM", "RATIONALE"])
    assert "MECHANISM — how it works" in two and "RATIONALE — why it's built this way" in two
    assert "ROBUSTNESS" not in two
    assert build_aside_instruction([]) == BASE_ASIDE_INSTRUCTION


def _e2e_handlers():
    """A wired session whose fake agent handles map, probe, and the aside step."""
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)

    def agent(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return [json.dumps({
                "kind": "return.map", "target": "run.py", "mode": "initial",
                "continues_after": None, "objective_covered": True,
                "units": [{"slug": "loader", "file": "run.py", "lo": 1, "hi": 2, "depth": 0,
                           "parent": None, "axes": ["COMPREHEND"]}],
                "order": ["loader"]})]
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does it do?"]
        if step == "wakeup.aside":
            # the instruction was assembled from the unit's axes (COMPREHEND fires here)
            assert "COMPREHEND — what it does" in instruction
            assert wakeup["capabilities"] == ["read_pin"]
            return ["It assigns two numbers."]
        raise AssertionError(f"unexpected step {step}")

    ctx = build_session(config, agent)
    return temp, ctx, ApiHandlers(ctx)


def test_api_aside_end_to_end_records_reply_without_touching_lesson_state():
    temp, ctx, api = _e2e_handlers()
    try:
        api.init_session(target="run.py", document_id="learner-main",
                         display_name="s.py", language="python")
        mapped = api.start_map()
        jid, unit_id = mapped["journey_id"], mapped["unit_id"]
        rid = str(uuid.uuid4())
        ref = {"kind": "code", "label": "run.py", "snippet": "a = 1\nb = 2",
               "source": {"file": "run.py", "lo": 1, "hi": 2}}
        ack = api.aside(jid, request_id=rid, unit_id=unit_id, question="why two lines?", refs=[ref])
        assert ack["operation"] == "aside" and ack["status"] == "complete"
        assert ack["reply_message_id"] is not None
        assert "turn_id" not in ack and "axis" not in ack  # NOT a DriverState
        # the reply shows up in the polled snapshot as an off-record aside message
        snap = api.poll(jid, since_revision=None)["snapshot"]
        aside_msgs = [m for m in snap["conversation"] if m["thread_kind"] == "aside"]
        assert any(m["role"] == "tutor" and m["message_kind"] == "aside_reply" for m in aside_msgs)
        assert any(m["role"] == "learner" and m["message_kind"] == "aside_question" for m in aside_msgs)
        # idempotent: same request_id returns the same reply, records nothing new
        ack2 = api.aside(jid, request_id=rid, unit_id=unit_id, question="why two lines?", refs=[ref])
        assert ack2["reply_message_id"] == ack["reply_message_id"]
        # the graded ladder is still pristine: no probe rows exist
        assert ctx.db.one("SELECT COUNT(*) AS n FROM probes")["n"] == 0
    finally:
        ctx.db.close(); temp.cleanup()


def test_graded_answer_refs_reach_the_judge_and_persist_on_the_answer():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    seen = {}

    def agent(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return [json.dumps({
                "kind": "return.map", "target": "run.py", "mode": "initial",
                "continues_after": None, "objective_covered": True,
                "units": [{"slug": "loader", "file": "run.py", "lo": 1, "hi": 2, "depth": 0,
                           "parent": None, "axes": ["COMPREHEND"]}],
                "order": ["loader"]})]
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does it do?"]
        if step == "wakeup.grade":
            seen["current_evidence"] = wakeup["context"]["current_evidence"]
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                                "category": "correct-deep", "evidence_ref": "events:1",
                                "hidden_gap": None,
                                "map_text": {"title": "t", "summary": "s"}})]
        if step == "wakeup.distill":
            return [json.dumps({
                "kind": "return.distill", "unit": "loader", "title": "Loader",
                "logical_document": {"id": "learner-main", "display_name": "s.py"},
                "final_verdict": "OWNED", "axes_tested": ["COMPREHEND"],
                "tests": [{"axis": "COMPREHEND", "prompt": "p", "expected": "e"}],
                "evidence": ["transcript:t1"], "event_log": "events.jsonl",
                "workspace_snapshot": "workspace-snapshot.py", "resume_at": None,
                "learner_diff": {"can": [], "cant": [], "misconceptions": []},
                "handoff": {"next_unit": "loader", "dive_depth": 0, "why": "done", "watch": "none"}})]
        raise AssertionError(step)

    from tutor_v2 import ApiHandlers, build_session
    ctx = build_session(config, agent)
    api = ApiHandlers(ctx)
    try:
        api.init_session(target="run.py", document_id="learner-main",
                         display_name="s.py", language="python")
        mapped = api.start_map()
        ref = {"kind": "code", "label": "run.py", "snippet": "a = 1\nb = 2",
               "source": {"file": "run.py", "lo": 1, "hi": 2}}
        api.answer(mapped["journey_id"], turn_id=mapped["turn_id"], unit_id=mapped["unit_id"],
                   axis=mapped["axis"], question=mapped["question"], answer="assigns two vars",
                   refs=[ref])
        # the JUDGE saw the normalized refs as current evidence
        assert seen["current_evidence"]["refs"][0]["source"] == {"file": "run.py", "lo": 1, "hi": 2}
        # and they persisted on the durable learner answer (decoded in the projection)
        snap = api.poll(mapped["journey_id"], since_revision=None)["snapshot"]
        answers = [m for m in snap["conversation"] if m["message_kind"] == "answer"]
        assert answers and answers[0]["refs"][0]["source"] == {"file": "run.py", "lo": 1, "hi": 2}
    finally:
        ctx.db.close(); temp.cleanup()


def _raises(fn, error=ValidationError):
    try:
        fn()
    except error:
        return
    raise AssertionError(f"expected {error.__name__}")
