"""
WsBridgeSink — localhost-only, token-authenticated WebSocket bridge sink.

Runs its asyncio WebSocket server on a dedicated background thread with its own
event loop — never shares the main asyncio loop. This isolation makes synchronous
shutdown possible from atexit/SIGTERM handlers.

Security invariants (design.md §9):
- Binds 127.0.0.1 ONLY — never 0.0.0.0
- Token authentication required on every connection
- Unauthenticated connections receive close code 4001 before any data is sent

Shutdown pattern (design.md §2.7):
- shutdown() is SYNC — submits _do_shutdown() via run_coroutine_threadsafe,
  blocks on future.result(timeout=2.0), then stops the event loop.

Optional at runtime: not instantiated when ObservabilityConfig.ws_port is None.

websockets >= 10.0 is required (see pyproject.toml). The handler uses the
websockets >= 12.0 API (path via websocket.request.path) with a fallback for
older versions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from typing import TYPE_CHECKING

from axiom.observability.schema import make_gap_marker

if TYPE_CHECKING:
    from axiom.observability.config import ObservabilityConfig

logger = logging.getLogger(__name__)


class WsBridgeSink:
    """WebSocket bridge sink — streams JSONL records to authenticated localhost clients.

    Each connected client owns a bounded deque (no maxlen — managed manually)
    guarded by a per-client threading.Lock. put() is non-blocking: when the
    buffer is full, 2 oldest items are dropped, a gap_marker(drop_count=2) is
    inserted, and the new record is appended (no silent auto-drops via maxlen).

    All items in per-client deques are stored as {"_line": str, "_raw": dict}
    wrappers — consistent format for both gap_markers and regular records.
    """

    def __init__(self, config: ObservabilityConfig) -> None:
        if config.ws_port is None:
            raise ValueError(
                "WsBridgeSink requires ws_port to be set in ObservabilityConfig"
            )

        self._host = config.ws_host  # must be 127.0.0.1
        self._port = config.ws_port
        self._token = config.ws_token
        self._ws_buffer = config.ws_buffer

        # Per-client state: client_id -> (deque, lock)
        # deque contains {"_line": str, "_raw": dict} wrappers — no maxlen
        self._clients: dict[int, tuple[deque, threading.Lock]] = {}
        self._clients_lock = threading.Lock()
        self._next_client_id = 0

        # WebSocket server object — stored for graceful shutdown
        self._ws_server = None

        # Dedicated event loop + thread
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._ws_thread = threading.Thread(
            name="WsBridgeThread", target=self._run_loop, daemon=True
        )
        self._server_task: asyncio.Task | None = None
        self._ws_thread.start()

        # Schedule server startup on the dedicated loop
        future = asyncio.run_coroutine_threadsafe(self._start_server(), self._loop)
        try:
            future.result(timeout=5.0)
        except Exception as exc:
            logger.error("WsBridgeSink: server startup error: %s", exc)

    # ------------------------------------------------------------------
    # Sink Protocol
    # ------------------------------------------------------------------

    def put(self, record: dict) -> None:
        """Enqueue record for each connected client. Non-blocking.

        When a client's buffer is full (len >= ws_buffer), 2 oldest items are
        dropped, a gap_marker(drop_count=2) is inserted, then the record is
        appended. No silent drops via deque maxlen — every drop is signaled.
        All items stored as {"_line": serialized, "_raw": dict} wrappers.
        """
        try:
            line = json.dumps(record, default=str)
        except Exception as exc:
            logger.error("WsBridgeSink: JSON serialization error: %s", exc)
            return

        wrapped = {"_line": line, "_raw": record}

        with self._clients_lock:
            client_ids = list(self._clients.keys())

        for cid in client_ids:
            with self._clients_lock:
                entry = self._clients.get(cid)
            if entry is None:
                continue
            dq, lock = entry
            with lock:
                if len(dq) >= self._ws_buffer:
                    # Need 2 slots: gap_marker + record.
                    # Drop 2 oldest to make room (no silent maxlen auto-drop).
                    dq.popleft()
                    if dq:  # guard: ws_buffer=1 edge case — first popleft may empty it
                        dq.popleft()
                    gap = make_gap_marker(
                        run_id=record.get("run_id"),
                        sink_id="ws",
                        drop_count=2,
                    )
                    gap_line = json.dumps(gap, default=str)
                    dq.append({"_line": gap_line, "_raw": gap})
                dq.append(wrapped)

    def shutdown(self) -> None:
        """Synchronously shut down the WS server and stop the dedicated loop."""
        if self._loop is None or self._loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._do_shutdown(), self._loop)
            future.result(timeout=2.0)
        except TimeoutError:
            logger.error("WsBridgeSink: shutdown timed out after 2s")
        except Exception as exc:
            logger.error("WsBridgeSink: shutdown error: %s", exc)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._ws_thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Internal asyncio server
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Entry point for the dedicated WS thread — runs the event loop forever."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _start_server(self) -> None:
        """Start the WebSocket server on the dedicated loop."""
        try:
            import websockets  # type: ignore[import]
        except ImportError:
            logger.error(
                "WsBridgeSink: 'websockets' package not installed; WS sink disabled"
            )
            return

        self._ws_server = await websockets.serve(
            self._handle_client,
            self._host,
            self._port,
        )
        self._server_task = asyncio.ensure_future(self._ws_server.wait_closed())

    async def _handle_client(self, websocket) -> None:
        """Handle a single WebSocket client connection with token auth.

        Compatible with websockets >= 12.0 (path via websocket.request.path)
        with fallback for older versions (websocket.path attribute).
        """
        import urllib.parse

        # websockets >= 12.0 API: path via websocket.request.path
        # Fallback: websocket.path (older versions)
        try:
            raw_path = websocket.request.path
        except AttributeError:
            raw_path = getattr(websocket, "path", "/")

        query = urllib.parse.urlparse(raw_path).query
        params = urllib.parse.parse_qs(query)
        tokens = params.get("token", [])
        if not tokens or tokens[0] != self._token:
            await websocket.close(code=4001, reason="Unauthorized")
            logger.error("WsBridgeSink: unauthenticated connection rejected")
            return

        # Register client — deque without maxlen (managed manually in put())
        with self._clients_lock:
            cid = self._next_client_id
            self._next_client_id += 1
            self._clients[cid] = (
                deque(),  # no maxlen — size enforced in put()
                threading.Lock(),
            )

        try:
            while True:
                # Drain queued lines for this client
                with self._clients_lock:
                    entry = self._clients.get(cid)
                if entry is None:
                    break
                dq, lock = entry
                items = []
                with lock:
                    while dq:
                        items.append(dq.popleft())

                for item in items:
                    try:
                        # All items are {"_line": ..., "_raw": ...} wrappers
                        line = item["_line"]
                        await websocket.send(line)
                    except Exception as exc:
                        logger.error(
                            "WsBridgeSink: send error for client %d: %s", cid, exc
                        )
                        return

                await asyncio.sleep(0.01)
        except Exception as exc:
            logger.error("WsBridgeSink: client %d error: %s", cid, exc)
        finally:
            with self._clients_lock:
                self._clients.pop(cid, None)

    async def _do_shutdown(self) -> None:
        """Gracefully close the WebSocket server and all client connections.

        Calls server.close() which sends WebSocket close frames to all connected
        clients, then awaits wait_closed() for up to 1 second. Also cancels the
        server_task (wait_closed future) to unblock any pending awaiter.
        """
        # Close the server gracefully — sends WS close frames to all clients
        if self._ws_server is not None:
            self._ws_server.close()
            try:
                await asyncio.wait_for(self._ws_server.wait_closed(), timeout=1.0)
            except Exception:
                pass  # timeout or other error — event loop will clean up

        # Cancel the wait_closed() task if still pending
        if self._server_task is not None:
            self._server_task.cancel()
            try:
                await self._server_task
            except (asyncio.CancelledError, Exception):
                pass  # expected
