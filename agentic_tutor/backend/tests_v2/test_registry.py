"""Control plane: multi-tenant (user, codebase) sessions resolved over the untouched engine."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tutor_v2 import ApiHandlers, ControlPlane, ValidationError


def _agent():
    def run(wakeup, instruction):
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
        raise AssertionError(f"unexpected step {step}")
    return run


def _codebase_dir(root: Path, name: str) -> str:
    d = root / name
    d.mkdir()
    (d / "run.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    return str(d)


def _map_session(plane: ControlPlane, *, user_id: str, codebase_id: str):
    ctx = plane.open(user_id=user_id, codebase_id=codebase_id)
    api = ApiHandlers(ctx)
    api.init_session(target="run.py", document_id="m", display_name="s.py", language="python")
    api.start_map()
    return ctx


def test_two_codebases_map_into_independent_sessions():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plane = ControlPlane(state_root=root / "state", agent_run=_agent())
        cb_a = plane.create_codebase(user_id="u1", name="alpha", root_path=_codebase_dir(root, "alpha"))
        cb_b = plane.create_codebase(user_id="u1", name="beta", root_path=_codebase_dir(root, "beta"))

        ctx_a = _map_session(plane, user_id="u1", codebase_id=cb_a)
        ctx_b = _map_session(plane, user_id="u1", codebase_id=cb_b)
        try:
            sid_a, sid_b = ctx_a.config.session_id, ctx_b.config.session_id
            assert sid_a != sid_b
            # each session owns exactly its own unit; neither sees the other's
            assert ctx_a.db.one("SELECT COUNT(*) AS n FROM units WHERE session_id=?", (sid_a,)) == {"n": 1}
            assert ctx_a.db.one("SELECT COUNT(*) AS n FROM units WHERE session_id=?", (sid_b,)) == {"n": 1}
            assert ctx_a.db.one("SELECT COUNT(*) AS n FROM units") == {"n": 2}  # shared DB, both sessions
        finally:
            ctx_a.db.close(); ctx_b.db.close()


def test_same_user_and_codebase_reuse_one_session():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plane = ControlPlane(state_root=root / "state", agent_run=_agent())
        cb = plane.create_codebase(user_id="u1", name="alpha", root_path=_codebase_dir(root, "alpha"))
        first = plane.open(user_id="u1", codebase_id=cb)
        second = plane.open(user_id="u1", codebase_id=cb)
        try:
            assert first.config.session_id == second.config.session_id
        finally:
            first.db.close(); second.db.close()


def test_different_users_get_isolated_sessions_and_listing():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plane = ControlPlane(state_root=root / "state", agent_run=_agent())
        cb_u1 = plane.create_codebase(user_id="u1", name="alpha", root_path=_codebase_dir(root, "a1"))
        cb_u2 = plane.create_codebase(user_id="u2", name="alpha", root_path=_codebase_dir(root, "a2"))
        ctx1 = _map_session(plane, user_id="u1", codebase_id=cb_u1)
        try:
            # u1 cannot open u2's codebase
            _raises(lambda: plane.open(user_id="u1", codebase_id=cb_u2))
            # listing is per-user and reflects the mapped unit count
            listing = plane.list_codebases(user_id="u1")
            assert [c["name"] for c in listing] == ["alpha"]
            assert listing[0]["session_id"] == ctx1.config.session_id
            assert listing[0]["unit_count"] == 1
            assert plane.list_codebases(user_id="u2")[0]["unit_count"] == 0  # u2 never mapped
        finally:
            ctx1.db.close()


def _raises(fn):
    try:
        fn()
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")
