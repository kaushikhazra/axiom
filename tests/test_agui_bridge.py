"""
Unit tests for axiom.interface.web.agui_bridge.stream_turn (M10, design.md
§4, D14 -- the dryrun-design-1 C1 fix: mid-turn events must reach the
frontend WHILE the turn is still running, not only after it completes).

Uses a lightweight fake session (duck-typing WebSession's
handle_turn()/event_queue surface) rather than a real Agent -- stream_turn()
only ever touches those two attributes, confirmed by reading agui_bridge.py.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from axiom.agent import TurnResult
from axiom.interface.web.agui_bridge import stream_turn
from axiom.tools.port import ToolResult


class _FakeSession:
    def __init__(self, handle_turn_fn) -> None:
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._handle_turn_fn = handle_turn_fn

    def handle_turn(self, user_input: str) -> TurnResult:
        return self._handle_turn_fn(user_input)


def _decode_events(sse_lines: list[str]) -> list[dict]:
    """Each yielded string is 'data: {...}\n\n' -- unwrap to the dict."""
    events = []
    for line in sse_lines:
        assert line.startswith("data: ")
        assert line.endswith("\n\n")
        events.append(json.loads(line[len("data: ") : -2]))
    return events


class TestBasicTurnNoMidTurnEvents:
    async def test_event_sequence_and_text_reassembly(self) -> None:
        def handle_turn(user_input: str) -> TurnResult:
            return TurnResult(text="hello world")

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "thread-1")]
        events = _decode_events(raw)

        types = [e["type"] for e in events]
        assert types[0] == "RUN_STARTED"
        assert types[-1] == "RUN_FINISHED"
        assert "TEXT_MESSAGE_START" in types
        assert "TEXT_MESSAGE_END" in types
        assert "CUSTOM" not in types  # no approval, no canvas

        content_events = [e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        reassembled = "".join(e["delta"] for e in content_events)
        assert reassembled == "hello world"
        # Same messageId across start/content*/end.
        message_ids = {
            e["messageId"]
            for e in events
            if e["type"]
            in ("TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END")
        }
        assert len(message_ids) == 1

    async def test_run_started_and_finished_share_thread_and_run_id(self) -> None:
        session = _FakeSession(lambda u: TurnResult(text="x"))
        raw = [chunk async for chunk in stream_turn(session, "hi", "thread-42")]
        events = _decode_events(raw)
        started = next(e for e in events if e["type"] == "RUN_STARTED")
        finished = next(e for e in events if e["type"] == "RUN_FINISHED")
        assert started["threadId"] == "thread-42"
        assert finished["threadId"] == "thread-42"
        assert started["runId"] == finished["runId"]

    async def test_empty_response_text_yields_no_content_events(self) -> None:
        session = _FakeSession(lambda u: TurnResult(text=""))
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        assert not any(e["type"] == "TEXT_MESSAGE_CONTENT" for e in events)
        # Start/end still bracket the (empty) message.
        assert any(e["type"] == "TEXT_MESSAGE_START" for e in events)
        assert any(e["type"] == "TEXT_MESSAGE_END" for e in events)


class TestMidTurnEventDelivery:
    """The actual dryrun-design-1 C1 regression test: an event pushed onto
    the queue WHILE handle_turn() is still running (via the same
    call_soon_threadsafe pattern approval_bridge.py's real emit_event uses)
    must be yielded BEFORE the turn's own text output -- proving the
    generator genuinely drains concurrently, not only after the turn task
    completes."""

    async def test_mid_turn_custom_event_arrives_before_text(self) -> None:
        loop = asyncio.get_running_loop()
        order: list = []

        def handle_turn(user_input: str) -> TurnResult:
            # Runs on asyncio.to_thread's worker thread -- mirrors exactly
            # how approval_bridge.emit_event pushes from a worker thread.
            import time

            time.sleep(0.05)
            order.append("handle_turn_about_to_push_event")
            loop.call_soon_threadsafe(
                session.event_queue.put_nowait,
                {
                    "type": "TOOL_APPROVAL_REQUEST",
                    "approval_id": "abc",
                    "tool_name": "write_file",
                    "arguments": {},
                },
            )
            time.sleep(0.05)
            order.append("handle_turn_returning")
            return TurnResult(text="done")

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)

        custom_events = [e for e in events if e["type"] == "CUSTOM"]
        approval_events = [
            e
            for e in custom_events
            if e["value"].get("type") == "TOOL_APPROVAL_REQUEST"
        ]
        assert len(approval_events) == 1
        assert approval_events[0]["value"]["approval_id"] == "abc"

        # The CUSTOM event's position in the yielded sequence must be
        # BEFORE the text content -- proving it was drained while
        # handle_turn was still sleeping (mid-turn), not queued up and
        # only flushed after handle_turn returned.
        custom_index = next(i for i, e in enumerate(events) if e["type"] == "CUSTOM")
        text_start_index = next(
            i for i, e in enumerate(events) if e["type"] == "TEXT_MESSAGE_START"
        )
        assert custom_index < text_start_index

    async def test_multiple_mid_turn_events_all_delivered_in_order(self) -> None:
        loop = asyncio.get_running_loop()

        def handle_turn(user_input: str) -> TurnResult:
            for i in range(3):
                loop.call_soon_threadsafe(
                    session.event_queue.put_nowait,
                    {"type": "TOOL_APPROVAL_REQUEST", "approval_id": f"id-{i}"},
                )
            return TurnResult(text="ok")

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        custom_events = [e for e in events if e["type"] == "CUSTOM"]
        assert [e["value"]["approval_id"] for e in custom_events] == [
            "id-0",
            "id-1",
            "id-2",
        ]


class TestCanvasEmission:
    async def test_tool_output_canvas_block_emitted_before_text(self) -> None:
        def handle_turn(user_input: str) -> TurnResult:
            return TurnResult(
                text="wrote the file",
                tool_outputs=[("write_file", ToolResult(output="3 lines written"))],
            )

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        canvas_events = [
            e for e in events if e["type"] == "CUSTOM" and e["name"] == "CANVAS_BLOCK"
        ]
        assert len(canvas_events) == 1
        assert canvas_events[0]["value"]["source"] == "tool_output"
        assert canvas_events[0]["value"]["content"] == "3 lines written"

        canvas_index = events.index(canvas_events[0])
        text_start_index = next(
            i for i, e in enumerate(events) if e["type"] == "TEXT_MESSAGE_START"
        )
        assert canvas_index < text_start_index

    async def test_denied_tool_output_not_routed_to_canvas(self) -> None:
        def handle_turn(user_input: str) -> TurnResult:
            return TurnResult(
                text="denied",
                tool_outputs=[
                    (
                        "write_file",
                        ToolResult(output="", denied=True, error="denied by user"),
                    )
                ],
            )

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        assert not any(
            e["type"] == "CUSTOM" and e["name"] == "CANVAS_BLOCK" for e in events
        )

    async def test_errored_tool_output_not_routed_to_canvas(self) -> None:
        def handle_turn(user_input: str) -> TurnResult:
            return TurnResult(
                text="failed",
                tool_outputs=[
                    ("run_shell", ToolResult(output="", error="command not found"))
                ],
            )

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        assert not any(
            e["type"] == "CUSTOM" and e["name"] == "CANVAS_BLOCK" for e in events
        )

    async def test_non_canvas_tool_name_not_routed_to_canvas(self) -> None:
        def handle_turn(user_input: str) -> TurnResult:
            return TurnResult(
                text="read it",
                tool_outputs=[("read_file", ToolResult(output="file contents"))],
            )

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        assert not any(
            e["type"] == "CUSTOM" and e["name"] == "CANVAS_BLOCK" for e in events
        )

    async def test_long_code_fence_in_response_text_routed_to_canvas(self) -> None:
        long_code = "\n".join(f"line{i}" for i in range(20))

        def handle_turn(user_input: str) -> TurnResult:
            return TurnResult(text=f"here:\n```python\n{long_code}\n```\ndone")

        session = _FakeSession(handle_turn)
        raw = [chunk async for chunk in stream_turn(session, "hi", "t")]
        events = _decode_events(raw)
        canvas_events = [
            e for e in events if e["type"] == "CUSTOM" and e["name"] == "CANVAS_BLOCK"
        ]
        assert len(canvas_events) == 1
        assert canvas_events[0]["value"]["source"] == "response_text"
        content_events = [e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        reassembled = "".join(e["delta"] for e in content_events)
        assert long_code not in reassembled
        assert "[see canvas: python block]" in reassembled


class TestTurnTaskExceptionPropagation:
    async def test_exception_from_handle_turn_propagates(self) -> None:
        def handle_turn(user_input: str) -> TurnResult:
            raise RuntimeError("boom")

        session = _FakeSession(handle_turn)
        with pytest.raises(RuntimeError, match="boom"):
            [chunk async for chunk in stream_turn(session, "hi", "t")]
