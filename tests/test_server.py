"""
Unit tests for axiom.interface.web.server (M10, design.md §3-§7).

Monkeypatches WebSession with a fake -- server.py's own responsibility is
routing/validation, not turn execution (already covered by
test_agui_bridge.py) or Agent wiring (test_agent.py, test_session_manager.py).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from axiom.agent import TurnResult
from axiom.interface.web import server as server_module
from axiom.interface.web import approval_bridge


class _FakeSession:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.set_provider_calls: list = []
        self.closed = False

    def handle_turn(self, user_input: str) -> TurnResult:
        return TurnResult(text=f"echo:{user_input}")

    def set_provider(self, provider) -> None:
        if provider is not None and provider not in ("claude", "local", "committee"):
            raise ValueError(f"unknown provider: {provider!r}")
        self.set_provider_calls.append(provider)

    def close(self) -> None:
        self.closed = True

    @property
    def _agent(self):
        class _A:
            observability_config = None

        return _A()


@pytest.fixture(autouse=True)
def _patch_session(monkeypatch):
    monkeypatch.setattr(server_module, "WebSession", _FakeSession)
    server_module._sessions.clear()
    yield
    server_module._sessions.clear()


@pytest.fixture
def client():
    """Context-managed TestClient: keeps ONE persistent anyio portal/event
    loop for every request in a test, matching real single-process uvicorn
    deployment (design.md §2) -- without the `with`, each .post() call can
    run on a different loop, which breaks a session's asyncio.Queue on its
    second use (a test-harness artifact, not a production bug: a real
    server has exactly one event loop for its whole process lifetime)."""
    app = server_module.create_app({"provider": "claude"})
    with TestClient(app) as c:
        yield c


def _run_agent_input(thread_id: str, message: str) -> dict:
    """D19 -- the real ag_ui.core.RunAgentInput wire shape (camelCase, via
    its alias_generator=to_camel), matching what @ag-ui/client's HttpAgent
    actually POSTs. Only a single UserMessage is needed for these tests --
    server.py's _latest_user_text() reads the newest one."""
    return {
        "threadId": thread_id,
        "runId": "run-1",
        "state": None,
        "messages": [{"id": "m1", "role": "user", "content": message}],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }


class TestRunTurn:
    def test_empty_message_returns_400(self, client: TestClient) -> None:
        resp = client.post("/api/agent/run", json=_run_agent_input("t1", "   "))
        assert resp.status_code == 400

    def test_valid_turn_streams_sse_events(self, client: TestClient) -> None:
        resp = client.post("/api/agent/run", json=_run_agent_input("t1", "hi"))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "RUN_STARTED" in resp.text
        assert "RUN_FINISHED" in resp.text
        assert "echo:hi" in resp.text.replace("\\", "")  # delta may be JSON-escaped

    def test_same_thread_id_reuses_session(self, client: TestClient) -> None:
        client.post("/api/agent/run", json=_run_agent_input("reuse-me", "a"))
        assert len(server_module._sessions) == 1
        client.post("/api/agent/run", json=_run_agent_input("reuse-me", "b"))
        assert len(server_module._sessions) == 1

    def test_different_thread_ids_get_separate_sessions(
        self, client: TestClient
    ) -> None:
        client.post("/api/agent/run", json=_run_agent_input("t-a", "a"))
        client.post("/api/agent/run", json=_run_agent_input("t-b", "b"))
        assert len(server_module._sessions) == 2

    def test_only_latest_user_message_is_used(self, client: TestClient) -> None:
        body = _run_agent_input("t1", "ignored")
        body["messages"] = [
            {"id": "m1", "role": "user", "content": "first"},
            {"id": "m2", "role": "assistant", "content": "reply"},
            {"id": "m3", "role": "user", "content": "second"},
        ]
        resp = client.post("/api/agent/run", json=body)
        assert resp.status_code == 200
        assert "echo:second" in resp.text.replace("\\", "")
        assert "first" not in resp.text


class TestApproval:
    def test_resolve_unknown_id_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/approval/no-such-id", json={"approved": True})
        assert resp.status_code == 404

    def test_resolve_known_id_returns_ok(self, client: TestClient) -> None:
        from concurrent.futures import Future

        future: Future = Future()
        approval_bridge._pending["known-id"] = future
        try:
            resp = client.post("/api/approval/known-id", json={"approved": True})
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
            assert future.result() is True
        finally:
            approval_bridge._pending.pop("known-id", None)

    def test_double_resolve_returns_409(self, client: TestClient) -> None:
        from concurrent.futures import Future

        future: Future = Future()
        approval_bridge._pending["dup-id"] = future
        try:
            client.post("/api/approval/dup-id", json={"approved": True})
            resp = client.post("/api/approval/dup-id", json={"approved": False})
            assert resp.status_code == 409
        finally:
            approval_bridge._pending.pop("dup-id", None)


class TestProvider:
    def test_valid_provider_returns_200(self, client: TestClient) -> None:
        resp = client.post(
            "/api/provider", json={"threadId": "t1", "provider": "local"}
        )
        assert resp.status_code == 200
        assert resp.json() == {"provider": "local"}

    def test_invalid_provider_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/api/provider", json={"threadId": "t1", "provider": "bogus"}
        )
        assert resp.status_code == 400

    def test_null_provider_is_valid(self, client: TestClient) -> None:
        resp = client.post("/api/provider", json={"threadId": "t1", "provider": None})
        assert resp.status_code == 200


class TestTraceEndpoint:
    def test_returns_503_when_no_session_has_observability(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/trace-endpoint", params={"threadId": "t1"})
        assert resp.status_code == 503

    def test_missing_thread_id_is_a_422(self, client: TestClient) -> None:
        # design.md D21 -- threadId is a required query param, not optional.
        resp = client.get("/api/trace-endpoint")
        assert resp.status_code == 422

    def test_lazily_creates_session_on_mount(self, client: TestClient) -> None:
        # The core D21 fix: a page load (no chat turn sent yet) must still
        # be ABLE to resolve a session for its own threadId, not 503
        # forever because _sessions is empty.
        assert len(server_module._sessions) == 0
        client.get("/api/trace-endpoint", params={"threadId": "fresh-tab"})
        assert "fresh-tab" in server_module._sessions
