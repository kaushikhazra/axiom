"""
Unit tests for axiom.interface.web.session_manager.WebSession (M10,
design.md §3, D3, D14).

Monkeypatches Agent with a fake -- WebSession's own responsibility is
wiring (approval_fn injection, thread-safe event emission, delegation),
not Agent's turn-execution logic, which already has its own test coverage
(test_agent.py). Keeps these tests fast and properly scoped to one layer.
"""

from __future__ import annotations

import asyncio

import pytest

from axiom.interface.web import session_manager
from axiom.interface.web.session_manager import SENTINEL, WebSession


class _FakeAgent:
    """Records constructor kwargs and every method call for assertions."""

    last_instance: "_FakeAgent | None" = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.run_turn_calls: list[str] = []
        self.end_session_called = False
        self.set_provider_calls: list[str | None] = []
        _FakeAgent.last_instance = self

    def run_turn(self, user_input: str):
        self.run_turn_calls.append(user_input)
        return f"turn-result:{user_input}"

    def end_session(self) -> None:
        self.end_session_called = True

    def set_provider(self, provider: str | None) -> None:
        self.set_provider_calls.append(provider)


@pytest.fixture(autouse=True)
def _patch_agent(monkeypatch):
    monkeypatch.setattr(session_manager, "Agent", _FakeAgent)


class TestConstruction:
    async def test_injects_approval_fn_into_agent_kwargs(self) -> None:
        WebSession(provider="claude", working_dir="/tmp")
        agent = _FakeAgent.last_instance
        assert "approval_fn" in agent.kwargs
        assert callable(agent.kwargs["approval_fn"])
        # Original kwargs preserved alongside the injected one.
        assert agent.kwargs["provider"] == "claude"
        assert agent.kwargs["working_dir"] == "/tmp"

    async def test_captures_running_loop(self) -> None:
        session = WebSession()
        assert session._loop is asyncio.get_running_loop()


class TestEmitEvent:
    async def test_pushes_event_onto_queue(self) -> None:
        session = WebSession()
        session.emit_event({"type": "TOOL_APPROVAL_REQUEST", "approval_id": "x"})
        # call_soon_threadsafe schedules for the next loop iteration --
        # yield control once so it actually runs.
        await asyncio.sleep(0)
        item = session.event_queue.get_nowait()
        assert item == {"type": "TOOL_APPROVAL_REQUEST", "approval_id": "x"}

    async def test_callable_from_a_worker_thread(self) -> None:
        """The real usage: approval_bridge's _ui_prompt_approval calls this
        from asyncio.to_thread's worker thread, not the event-loop thread."""
        session = WebSession()
        await asyncio.to_thread(session.emit_event, {"type": "X"})
        await asyncio.sleep(0)
        assert session.event_queue.get_nowait() == {"type": "X"}


class TestDelegation:
    async def test_handle_turn_delegates_to_agent_run_turn(self) -> None:
        session = WebSession()
        result = session.handle_turn("hello")
        assert result == "turn-result:hello"
        assert _FakeAgent.last_instance.run_turn_calls == ["hello"]

    async def test_close_delegates_to_agent_end_session(self) -> None:
        session = WebSession()
        session.close()
        assert _FakeAgent.last_instance.end_session_called is True

    async def test_set_provider_delegates_to_agent(self) -> None:
        session = WebSession()
        session.set_provider("local")
        assert _FakeAgent.last_instance.set_provider_calls == ["local"]


class TestSentinel:
    def test_sentinel_is_a_unique_object(self) -> None:
        assert SENTINEL is not None
        assert SENTINEL is session_manager.SENTINEL
