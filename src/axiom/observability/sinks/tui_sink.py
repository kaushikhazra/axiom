"""
TuiSink — lossy live terminal display sink.

Uses an unbounded collections.deque (size enforced manually in put()) guarded by
threading.Lock. The lock makes the compound check-then-mutate atomic — prevents
two threads both seeing full=True and double-injecting gap_markers.

Drains on a dedicated daemon thread that prints records to stderr.
Optional at runtime: not registered when tui_enabled=False (--no-tui or CI).

Invariant 3 (design.md §5.3): TuiSink receives span_start records from
LiveNotificationProcessor.on_start for "in progress" display, and span_end
records from JsonlExportProcessor.on_end for completion display.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable

from axiom.observability.schema import make_gap_marker

logger = logging.getLogger(__name__)


class TuiSink:
    """Lossy live TUI sink backed by a bounded deque + drain thread.

    put() is non-blocking: under the deque lock, if full, two oldest records are
    dropped, a gap_marker(drop_count=2) is appended, then the new record is appended.
    """

    def __init__(
        self,
        buffer: int = 200,
        render_fn: Callable[[dict], None] | None = None,
    ) -> None:
        """
        Args:
            buffer: deque maxlen (configurable, default 200).
            render_fn: optional callable for rendering records. Defaults to
                       printing a summary line to stderr. Used in tests to
                       capture rendered output.
        """
        self._buffer = buffer
        self._deque: deque[dict] = deque()  # no maxlen — managed manually in put()
        self._deque_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._render_fn = render_fn or self._default_render

        self._drain_thread = threading.Thread(
            name="TuiSinkDrainer", target=self._drain_loop, daemon=True
        )
        self._drain_thread.start()

    # ------------------------------------------------------------------
    # Sink Protocol
    # ------------------------------------------------------------------

    def put(self, record: dict) -> None:
        """Enqueue record. Non-blocking. Drops oldest 2 + gap_marker(drop_count=2) when full.

        When the buffer is at capacity we must insert both a gap_marker AND the new
        record — that requires 2 free slots but only 1 is available. We therefore drop
        the two oldest records, emit a single gap_marker(drop_count=2), then append
        the record. This keeps the deque at exactly self._buffer items and accurately
        accounts for every drop (no silent losses).

        Using deque() without maxlen so that deque.append() never auto-drops silently.
        """
        with self._deque_lock:
            if len(self._deque) >= self._buffer:
                # Need 2 slots: one for gap_marker, one for record.
                # Drop the two oldest to make room.
                self._deque.popleft()
                if (
                    self._deque
                ):  # guard: buffer=1 edge case — first popleft may empty it
                    self._deque.popleft()
                gap = make_gap_marker(
                    run_id=record.get("run_id"),
                    sink_id="tui",
                    drop_count=2,
                )
                self._deque.append(gap)
            self._deque.append(record)

    def shutdown(self) -> None:
        """Signal drain thread to stop; wait up to 2s."""
        self._stop_event.set()
        self._drain_thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Internal drain loop
    # ------------------------------------------------------------------

    def _drain_loop(self) -> None:
        """Continuously drain the deque and render records until stop_event."""
        while not self._stop_event.is_set():
            record = self._pop()
            if record is not None:
                try:
                    self._render_fn(record)
                except Exception as exc:
                    logger.error("TuiSink: render error: %s", exc)
            else:
                # Nothing to drain — sleep briefly to avoid busy-spin
                time.sleep(0.01)

        # Drain remaining after stop_event is set
        while True:
            record = self._pop()
            if record is None:
                break
            try:
                self._render_fn(record)
            except Exception as exc:
                logger.error("TuiSink: render error during shutdown: %s", exc)

    def _pop(self) -> dict | None:
        """Thread-safe pop from the left of the deque."""
        with self._deque_lock:
            if self._deque:
                return self._deque.popleft()
            return None

    @staticmethod
    def _default_render(record: dict) -> None:
        """Default renderer: print a one-line summary to stderr."""
        import sys

        rtype = record.get("record_type", "unknown")
        if rtype == "span_start":
            print(
                f"[axiom] >> {record.get('span_name', '?')} started "
                f"(run={record.get('run_id', '?')[:8]})",
                file=sys.stderr,
            )
        elif rtype == "span_end":
            dur = record.get("duration_ms", 0)
            status = record.get("status", "?")
            print(
                f"[axiom] << {record.get('span_name', '?')} {status} {dur:.1f}ms",
                file=sys.stderr,
            )
        elif rtype == "gap_marker":
            n = record.get("drop_count", "?")
            print(f"[axiom] !! [{n} record(s) dropped]", file=sys.stderr)
