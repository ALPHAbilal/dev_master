"""Transport acceptance: real engine, deterministic agent, HTTP and TCP SSE."""
import json
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import httpx
import jwt
import pytest
import uvicorn
from fastapi.testclient import TestClient

from tutor_v2.app import create_app
from tutor_v2.auth import DevVerifier, SupabaseVerifier, verifier_from_env
from tutor_v2.domain import AgentOutput, ToolCall
from tutor_v2.registry import ControlPlane
from tests_v2.test_app import _agent, _map_blocks, _SAMPLE


def agent(wakeup, instruction):
    if wakeup["step"] == "wakeup.map":
        mapped = json.loads(_map_blocks()[0])
        mapped["units"][0]["axes"] = ["COMPREHEND", "MECHANISM"]
        return [json.dumps(mapped)]
    if wakeup["step"] == "wakeup.aside":
        return ["The path identifies the file to read."]
    return AgentOutput(_agent()(wakeup, instruction), [ToolCall("read_code_slice", {}, False, 0)])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "run.py").write_text(_SAMPLE)
    plane = ControlPlane(tmp_path / "state", agent)
    return repo, plane, create_app(plane, stream_interval=0.02)


def register(client, repo, user="alice"):
    response = client.post("/codebases", headers={"X-User-Id": user},
                           json={"name": "Demo", "source": str(repo)})
    assert response.status_code == 200, response.text
    return {"X-User-Id": user, "X-Codebase-Id": response.json()["codebase_id"]}


def initialize(client, headers):
    opened = client.post(f'/codebases/{headers["X-Codebase-Id"]}/open', headers=headers)
    assert opened.status_code == 200, opened.text
    response = client.post("/session", headers=headers, json={"target": "run.py",
        "document_id": "learner-main", "display_name": "solution.py", "language": "python"})
    assert response.status_code == 200, response.text
    return opened.json()["session_id"]


def test_control_plane_and_cross_tenant_ids(setup):
    repo, _, app = setup
    with TestClient(app) as client:
        assert client.get("/codebases").status_code == 401
        a = register(client, repo)
        b = register(client, repo, "bob")
        assert initialize(client, a) != initialize(client, b)
        listed = client.get("/codebases", headers=a).json()
        assert len(listed) == 1
        assert set(listed[0]) == {"id", "name", "session_id", "unit_count"}
        assert listed[0]["id"] == a["X-Codebase-Id"]
        stolen = {**a, "X-Codebase-Id": b["X-Codebase-Id"]}
        assert client.post("/session/resume", headers=stolen).status_code == 404
        assert client.post(f'/codebases/{b["X-Codebase-Id"]}/open', headers=a).status_code == 404
        assert client.post("/session/resume", headers={"X-User-Id": "alice"}).status_code == 400
        mapped = client.post("/session/map", headers=a).json()
        path = f'/journey/{mapped["journey_id"]}'
        assert client.get(path, headers=b).status_code == 404
        assert client.get(path + "/stream", headers=b).status_code == 404
        for action in ("aside", "park"):
            body = {"unit_id": mapped["unit_id"]}
            if action == "aside":
                body.update(request_id="foreign", question="Explain")
            assert client.post(path + "/" + action, headers=b, json=body).status_code == 404
        assert client.post(path + "/park", headers=a, json={"unit_id": 99999}).status_code == 404
        aside = client.post(path + "/aside", headers=a, json={"request_id": str(uuid.uuid4()),
            "unit_id": mapped["unit_id"], "question": "What is path?"})
        assert aside.status_code == 200, aside.text
        body = {key: mapped[key] for key in ("turn_id", "unit_id", "axis", "question")}
        body["answer"] = "It reads the file and returns it."
        response = client.post(path + "/answer", headers=a, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "awaiting_learner"
        assert client.get("/codebases", headers=a).json()[0]["unit_count"] == 1


def test_supabase_identity_is_verified_each_request(setup):
    _, plane, _ = setup
    secret = "test-secret-only-" * 4
    issuer = "https://example.supabase.co/auth/v1"
    app = create_app(plane, verifier=SupabaseVerifier(secret=secret, issuer=issuer))
    claims = {"sub": "alice", "exp": int(time.time()) + 300, "aud": "authenticated", "iss": issuer}
    def headers(payload=claims, key=secret):
        return {"Authorization": "Bearer " + jwt.encode(payload, key, algorithm="HS256"), "X-User-Id": "alice"}
    with TestClient(app) as client:
        assert client.get("/codebases", headers=headers()).status_code == 200
        assert client.get("/codebases", headers={**headers(), "X-User-Id": "bob"}).status_code == 401
        for bad in ({**claims, "exp": 1}, {**claims, "aud": "wrong"}, {**claims, "iss": "wrong"}):
            assert client.get("/codebases", headers=headers(bad)).status_code == 401
        assert client.get("/codebases", headers=headers(key="incorrect-key-" * 4)).status_code == 401
        assert client.get("/codebases", headers={"X-User-Id": "alice"}).status_code == 401


def test_dev_mode_is_explicit(monkeypatch):
    for name in ("AUTH_MODE", "SUPABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_JWKS_URL", "SUPABASE_JWT_ISSUER"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError):
        verifier_from_env()
    monkeypatch.setenv("AUTH_MODE", "dev")
    assert isinstance(verifier_from_env(), DevVerifier)
    assert verifier_from_env().verify(None, "alice") == "alice"


def test_jwks_signature_verification(setup, monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import rsa
    _, plane, _ = setup
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="test-key", use="sig", alg="RS256")
    verifier = SupabaseVerifier(jwks_url="https://example.invalid/jwks", issuer="test-issuer")
    monkeypatch.setattr(verifier.jwks, "fetch_data", lambda: {"keys": [jwk]})
    claims = {"sub": "alice", "exp": int(time.time()) + 300, "aud": "authenticated", "iss": "test-issuer"}
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})
    with TestClient(create_app(plane, verifier=verifier)) as client:
        assert client.get("/codebases", headers={"X-User-Id": "alice", "Authorization": "Bearer " + token}).status_code == 200
        forged = jwt.encode({**claims, "sub": "bob"}, "untrusted-secret-" * 4, algorithm="HS256")
        assert client.get("/codebases", headers={"X-User-Id": "bob", "Authorization": "Bearer " + forged}).status_code == 401


def test_restart_preserves_turn_ids_and_codebase_selection(setup):
    repo, plane, app = setup
    with TestClient(app) as client:
        headers = register(client, repo)
        initialize(client, headers)
        mapped = client.post("/session/map", headers=headers).json()
        other = register(client, repo)  # Same user, different codebase is also isolated.
        initialize(client, other)
        assert client.get(f'/journey/{mapped["journey_id"]}', headers=other).status_code == 404
    with TestClient(create_app(plane)) as client:
        body = {key: mapped[key] for key in ("turn_id", "unit_id", "axis", "question")}
        body["answer"] = "Reads the file."
        response = client.post(f'/journey/{mapped["journey_id"]}/answer', headers=headers, json=body)
        assert response.status_code == 200, response.text
        assert response.json()["turn_id"] != mapped["turn_id"]


def test_entrypoint_and_cors(tmp_path, monkeypatch):
    from tutor_v2.__main__ import build_app
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("STATE_ROOT", str(tmp_path))
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://tutor.example.vercel.app")
    with TestClient(build_app()) as client:
        response = client.options("/session", headers={"Origin": "https://tutor.example.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,X-User-Id,X-Codebase-Id"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://tutor.example.vercel.app"
        assert client.get("/codebases", headers={"X-User-Id": "alice"}).json() == []


@contextmanager
def serve(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=2))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("HTTP server did not start")
        time.sleep(0.01)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}", timeout=10) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive(), "SSE disconnect prevented shutdown"


def events(response):
    name = None
    for line in response.iter_lines():
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: "):
            yield name, json.loads(line[6:])


def test_real_sse_scan_and_revision_after_write(setup):
    repo, _, app = setup
    with serve(app) as client, ThreadPoolExecutor() as pool:
        headers = register(client, repo)
        initialize(client, headers)
        with client.stream("GET", "/session/map/stream", headers=headers) as scan:
            assert scan.status_code == 200
            assert scan.headers["content-type"].startswith("text/event-stream")
            assert scan.headers["x-accel-buffering"] == "no"
            future = pool.submit(client.post, "/session/map", headers=headers)
            records = list(events(scan))
            mapped_response = future.result(timeout=10)
            assert mapped_response.status_code == 200, mapped_response.text
            mapped = mapped_response.json()
        assert records[0][0] == "thinking"
        assert ("unit", {"slug": "loader", "file": "run.py", "lo": 1, "hi": 6}) in records
        assert records[-1] == ("done", {"journey_id": mapped["journey_id"]})
        with client.stream("GET", "/session/map/stream",
                           headers={**headers, "Last-Event-ID": "999999"}) as replay:
            # An obsolete cursor from a previous server process cannot hide this scan.
            assert list(events(replay))[-1] == records[-1]
        path = f'/journey/{mapped["journey_id"]}'
        with client.stream("GET", path + "/stream", headers=headers) as stream:
            iterator = events(stream)
            name, initial = next(iterator)
            assert name == "revision"
            name, tool = next(iterator)
            assert name == "tool" and set(tool) == {"turn_id", "capability", "agent", "step"}
            body = {key: mapped[key] for key in ("turn_id", "unit_id", "axis", "question")}
            body["answer"] = "It reads and returns the file."
            response = client.post(path + "/answer", headers=headers, json=body)
            assert response.status_code == 200, response.text
            for name, payload in iterator:
                if name == "revision":
                    assert payload["revision"] > initial["revision"]
                    break
        # Closing an infinite stream leaves the server responsive and able to shut down.
        assert client.get(path, headers=headers).status_code == 200
