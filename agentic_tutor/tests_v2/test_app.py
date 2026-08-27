"""Step 3 tests: the API handlers drive the whole loop in-process (no network, no FastAPI)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import ApiHandlers, TutorConfig, build_session

_SAMPLE = "def load(path):\n    return read(path)\n\n\ndef read(path):\n    return {}\n"


def _map_blocks():
    unit = {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6, "depth": 0, "parent": None,
            "axes": ["COMPREHEND"]}
    return [json.dumps({"kind": "return.map", "target": "run.py", "mode": "initial",
                        "continues_after": None, "objective_covered": True, "units": [unit],
                        "order": ["loader"]})]


def _distill_blocks():
    return [json.dumps({
        "kind": "return.distill", "unit": "loader", "title": "Loader",
        "logical_document": {"id": "learner-main", "display_name": "solution.py"},
        "final_verdict": "OWNED", "axes_tested": ["COMPREHEND"],
        "tests": [{"axis": "COMPREHEND", "prompt": "what does load do?", "expected": "reads"}],
        "evidence": ["transcript:t1"], "event_log": "events.jsonl",
        "workspace_snapshot": "workspace-snapshot.py", "resume_at": None,
        "learner_diff": {"can": ["read a loader"], "cant": [], "misconceptions": []},
        "handoff": {"next_unit": "loader", "dive_depth": 0, "why": "done", "watch": "nothing"},
    })]


def _agent():
    def run(wakeup, instruction):
        step = wakeup["step"]
        if step == "wakeup.map":
            return _map_blocks()
        if step in {"wakeup.probe", "wakeup.test"}:
            return ["What does load(path) do?"]
        if step == "wakeup.grade":
            return [json.dumps({"kind": "return.grade", "axis": "COMPREHEND", "verdict": "SOLID",
                                "category": "correct-deep", "evidence_ref": "events:1",
                                "hidden_gap": None,
                                "map_text": {"title": "load reads a file",
                                             "summary": "Proved COMPREHEND"}})]
        if step == "wakeup.distill":
            return _distill_blocks()
        raise AssertionError(f"unexpected step {step}")
    return run


def _handlers():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    (root / "run.py").write_text(_SAMPLE, encoding="utf-8")
    config = TutorConfig(root / "state.sqlite", root / "workspace", root / "archive", "s1",
                         codebase_root=root)
    ctx = build_session(config, _agent())
    return temp, ctx, ApiHandlers(ctx)


def test_full_loop_over_the_api_surface():
    temp, ctx, api = _handlers()
    try:
        init = api.init_session(target="run.py", document_id="learner-main",
                                display_name="solution.py", language="python")
        assert init["workspace_revision"] == 0

        # /session/map: maps then stops holding a live question.
        mapped = api.start_map()
        assert mapped["status"] == "awaiting_learner"
        jid, turn_id, unit_id, axis = (mapped["journey_id"], mapped["turn_id"],
                                       mapped["unit_id"], mapped["axis"])
        assert mapped["question"] == "What does load(path) do?"

        # A poll from the beginning returns a fresh snapshot at the current revision.
        snap = api.poll(jid, since_revision=None)
        assert snap["changed"] is True and snap["snapshot"] is not None
        rev = snap["revision"]

        # /answer echoes the driver-minted turn id; single axis → OWNED → distill → done.
        done = api.answer(jid, turn_id=turn_id, unit_id=unit_id, axis=axis,
                          question=mapped["question"], answer="It reads the file and returns it.")
        assert done["status"] == "done"
        assert done["projection_revision"] >= rev

        # The distill really ran through the API path: the proof artifact is on disk.
        assert (ctx.config.archive_root / "loader" / "manifest.json").is_file()

        # A poll gated on the pre-answer revision now sees the advanced projection.
        after = api.poll(jid, since_revision=rev)
        assert after["revision"] >= done["projection_revision"]
    finally:
        ctx.db.close()
        temp.cleanup()


def test_workspace_write_is_revision_guarded_through_the_api():
    temp, ctx, api = _handlers()
    try:
        api.init_session(target="run.py", document_id="learner-main",
                         display_name="solution.py", language="python")
        first = api.workspace_write(expected_revision=0, content="print('hi')\n")
        assert first["changed"] is True and first["workspace_revision"] == 1

        # A stale expected_revision is a client error surfaced as a raised ValidationError-kind.
        raised = False
        try:
            api.workspace_write(expected_revision=0, content="print('stale')\n")
        except Exception:
            raised = True
        assert raised, "a stale workspace write must be refused"
    finally:
        ctx.db.close()
        temp.cleanup()
