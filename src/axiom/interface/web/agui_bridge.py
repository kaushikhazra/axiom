"""
AG-UI event bridge — M10 (design.md §4, D1, D7, D14, D15): translates one
WebSession.handle_turn() call into a sequence of AG-UI protocol events.

D14 (dryrun-design-1 C1 fix): stream_turn() runs the turn as a background
asyncio.Task and concurrently drains session.event_queue, so mid-turn
events (currently: tool-approval requests) reach the frontend while the
turn is still in progress -- the original linear
"await the whole turn, then yield" shape could never deliver those.

D7: US-02 ships chunked delivery of the already-complete response text, not
real per-token model streaming (that needs adapter-level changes, out of
scope for M10 -- see design.md Future Work).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from ag_ui.core import (
    CustomEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from ag_ui.encoder import EventEncoder

from axiom.agent import TurnResult
from axiom.interface.web.canvas_routing import CanvasBlock, split_for_canvas
from axiom.interface.web.session_manager import SENTINEL, WebSession

# design.md §2 -- default 0.02s.
_CHUNK_DELAY_SECS = 0.02

_CANVAS_TOOL_NAMES = {"write_file", "run_shell"}


def _new_id() -> str:
    return uuid.uuid4().hex


def _chunk_response(text: str) -> list[str]:
    """Word-boundary chunking (D7) -- not real token streaming, just enough
    granularity for the UI to render incrementally. Splits on whitespace,
    re-attaching a trailing space to each chunk except the last so the
    reassembled text matches the original exactly.

    Filters empty chunks (e.g. from double spaces in the source text) --
    AG-UI's TextMessageContentEvent.delta requires a non-empty string
    (MinLen(1)); dropping an empty delta loses no information since
    concatenating with "" is a no-op for the frontend's reassembly."""
    if not text:
        return []
    words = text.split(" ")
    chunks = [w + " " for w in words[:-1]] + [words[-1]]
    return [c for c in chunks if c]


def _tool_canvas_blocks(turn_result: TurnResult) -> list[CanvasBlock]:
    """D13: the write_file/run_shell filter lives HERE (interface layer),
    not in Agent -- TurnResult only carries raw ToolResults (design.md D15),
    keeping agent.py free of any axiom.interface import (dryrun-design-3 C1).
    Excludes denied calls and calls that errored -- neither has output worth
    showing on a canvas."""
    return [
        CanvasBlock.from_tool_result(name, result)
        for name, result in turn_result.tool_outputs
        if name in _CANVAS_TOOL_NAMES and not result.denied and result.error is None
    ]


async def stream_turn(
    session: WebSession, user_input: str, thread_id: str
) -> AsyncIterator[str]:
    """Yields SSE-encoded AG-UI event strings for one turn. Caller (server.py)
    forwards each yielded string directly as an SSE chunk."""
    encoder = EventEncoder()
    run_id = _new_id()
    yield encoder.encode(RunStartedEvent(threadId=thread_id, runId=run_id))

    # D14: run the turn on a worker thread as a Task, so this generator can
    # keep awaiting session.event_queue concurrently instead of blocking on
    # the whole turn before yielding anything.
    turn_task: asyncio.Task = asyncio.create_task(
        asyncio.to_thread(session.handle_turn, user_input)
    )
    loop = asyncio.get_running_loop()
    turn_task.add_done_callback(
        lambda _: loop.call_soon_threadsafe(session.event_queue.put_nowait, SENTINEL)
    )

    while True:
        item = await session.event_queue.get()
        if item is SENTINEL:
            break
        # item shape: {"type": "TOOL_APPROVAL_REQUEST", "approval_id": ..., ...}
        # (approval_bridge.py) -- the frontend subscribes directly to the
        # agent's raw AG-UI event stream and matches on event.name (D18,
        # ApprovalPrompt.tsx), not a CopilotKit frontend-tool registration.
        yield encoder.encode(CustomEvent(name=item["type"], value=item))

    turn_result: TurnResult = turn_task.result()  # re-raises any exception

    # US-06 -- canvas, both halves, only now that the turn has completed.
    tool_blocks = _tool_canvas_blocks(turn_result)
    chat_text, text_blocks = split_for_canvas(turn_result.text)  # D8
    for block in tool_blocks + text_blocks:  # D13, D8
        yield encoder.encode(CustomEvent(name="CANVAS_BLOCK", value=block.to_dict()))

    message_id = _new_id()
    yield encoder.encode(TextMessageStartEvent(messageId=message_id, role="assistant"))
    for chunk in _chunk_response(chat_text):  # D7
        yield encoder.encode(TextMessageContentEvent(messageId=message_id, delta=chunk))
        await asyncio.sleep(_CHUNK_DELAY_SECS)
    yield encoder.encode(TextMessageEndEvent(messageId=message_id))

    yield encoder.encode(RunFinishedEvent(threadId=thread_id, runId=run_id))
