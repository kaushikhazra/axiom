"""
AG-UI event bridge — M10 (design.md §4, D1, D7, D14, D15): translates one
WebSession.handle_turn() call into a sequence of AG-UI protocol events.

D14 (dryrun-design-1 C1 fix): stream_turn() runs the turn as a background
asyncio.Task and concurrently drains session.event_queue, so mid-turn
events (currently: tool-approval requests) reach the frontend while the
turn is still in progress -- the original linear
"await the whole turn, then yield" shape could never deliver those.

Response text is emitted as a SINGLE delta, as soon as the turn completes.
This supersedes design.md D7's chunked delivery: the adapters do not stream
tokens, so splitting the finished string into fake per-word deltas only added
latency (10.5s on a 400-word answer) without adding information. Stream only
when the backend is genuinely streaming -- see the note at the emit site.
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
from axiom.interface.web.session_manager import SENTINEL, WebSession


def _new_id() -> str:
    return uuid.uuid4().hex


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

    # The whole response goes to chat. The canvas pane was removed (#17), taking
    # split_for_canvas() and the CANVAS_BLOCK events with it -- long fenced
    # blocks now render inline in chat, which is why #16 (markdown rendering)
    # had to land first: the canvas was previously the ONLY path that displayed
    # them correctly.
    #
    # TurnResult.tool_outputs is consequently unread here: write_file/run_shell
    # results are no longer surfaced anywhere in the UI. The field is retained
    # as core data (agent.py D15) rather than removed, since core never knew
    # about the canvas -- only this interface layer did.
    chat_text = turn_result.text

    # One delta, emitted the moment the text exists. The turn has already
    # completed by this point (turn_task.result() above), so chat_text is
    # whole -- there is nothing left to stream. The previous implementation
    # re-split it into one delta per word and slept _CHUNK_DELAY_SECS (0.02s)
    # between them to imitate typing; on a 364-word answer that added 10.5s
    # of pure latency to a response that was already finished, and the cost
    # grew linearly with length. Windows made it worse still: the ~15.6ms
    # timer granularity turned each 0.02s sleep into ~0.029s.
    #
    # Superseding design.md D7's chunked delivery: stream only when the
    # backend actually streams. When the adapters gain real token streaming,
    # the deltas must come FROM that stream (yielded as tokens arrive, before
    # the turn completes) rather than being synthesized here from a finished
    # string -- that is real streaming and belongs above, not in this block.
    #
    # Empty text still yields start+end with no content event: AG-UI's
    # TextMessageContentEvent.delta requires a non-empty string (MinLen(1)).
    message_id = _new_id()
    yield encoder.encode(TextMessageStartEvent(messageId=message_id, role="assistant"))
    if chat_text:
        yield encoder.encode(
            TextMessageContentEvent(messageId=message_id, delta=chat_text)
        )
    yield encoder.encode(TextMessageEndEvent(messageId=message_id))

    yield encoder.encode(RunFinishedEvent(threadId=thread_id, runId=run_id))
