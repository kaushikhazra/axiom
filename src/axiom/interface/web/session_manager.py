"""
WebSession — M10 (design.md §3, D3, D14): one per browser connection. Owns
exactly one long-lived Agent (multi-turn safe via Agent.run_turn(), never
Agent.run()) AND the per-session event queue mid-turn signals (currently:
tool-approval requests) travel over.

Must be constructed from a running asyncio event loop (asyncio.get_running_
loop() at __init__ time) -- server.py constructs one inside an async route/
connection handler, never at import time or from a sync context.
"""

from __future__ import annotations

import asyncio
from typing import Any

from axiom.agent import Agent, TurnResult
from axiom.interface.web.approval_bridge import make_ui_approval_fn

# Sentinel placed on event_queue by stream_turn()'s turn-task done_callback
# (agui_bridge.py) to signal "no more mid-turn events for this turn."
SENTINEL = object()


class WebSession:
    def __init__(self, **agent_kwargs: Any) -> None:
        self._loop = asyncio.get_running_loop()
        self.event_queue: asyncio.Queue = asyncio.Queue()
        agent_kwargs["approval_fn"] = make_ui_approval_fn(self.emit_event)
        self._agent = Agent(**agent_kwargs)

    def emit_event(self, event: dict) -> None:
        """Thread-safe -- may be called from the worker thread running a
        turn (D14, via GuardrailsGate's approval_fn, itself invoked deep
        inside Agent.run_turn()'s call stack). Never called directly from
        the main event-loop thread."""
        self._loop.call_soon_threadsafe(self.event_queue.put_nowait, event)

    def handle_turn(self, user_input: str) -> TurnResult:
        return self._agent.run_turn(user_input)

    def close(self) -> None:
        self._agent.end_session()

    def set_provider(self, provider: str | None) -> None:
        self._agent.set_provider(provider)
