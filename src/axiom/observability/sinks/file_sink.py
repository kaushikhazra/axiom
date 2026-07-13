"""
FileSink — bounded-durable JSONL file sink.

Owns a queue.Queue(maxsize=D) drained by a dedicated non-daemon thread
(FileSinkDrainer). Uses RotatingFileHandler as the rotation backend only
(not for its logging API — raw JSONL lines are written via handler.stream).

Design constraints (design.md §2.5):
- put() is non-blocking: enqueue or drop-oldest + gap_marker
- Drainer is a non-daemon thread (joins cleanly at process exit)
- Poison-pill shutdown: sentinel enqueued by shutdown(), drainer exits on receipt
- File permissions: 0o600 immediately after open
- Periodic fsync: every FSYNC_RECORDS writes OR FSYNC_SECS seconds
- Gap marker imported from axiom.observability.schema.make_gap_marker
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import logging.handlers
from typing import TYPE_CHECKING

from axiom.observability.schema import make_gap_marker

if TYPE_CHECKING:
    from axiom.observability.config import ObservabilityConfig

logger = logging.getLogger(__name__)

# Sentinel object — the sole exit mechanism for the drainer loop
_SENTINEL = object()


class FileSinkDrainer(threading.Thread):
    """Dedicated non-daemon thread that drains the FileSink queue to disk.

    Runs a blocking-get loop. Exits ONLY when it dequeues _SENTINEL.
    No stop_event, no timeout polling — pure poison-pill design (design.md §2.5).
    """

    def __init__(
        self,
        q: queue.Queue,
        handler: logging.handlers.RotatingFileHandler,
        fsync_records: int,
        fsync_secs: float,
    ) -> None:
        super().__init__(name="FileSinkDrainer", daemon=False)
        self._q = q
        self._handler = handler
        self._fsync_records = fsync_records
        self._fsync_secs = fsync_secs

    def run(self) -> None:
        write_count = 0
        last_fsync = time.monotonic()

        while True:
            item = self._q.get()

            if item is _SENTINEL:
                # Final flush before exit
                try:
                    self._handler.stream.flush()
                    os.fsync(self._handler.stream.fileno())
                except Exception as exc:
                    logger.error("FileSinkDrainer: final fsync error: %s", exc)
                return

            # Write line — dereference stream fresh every iteration (rotation safety)
            try:
                self._handler.stream.write(item + "\n")
                write_count += 1
            except Exception as exc:
                logger.error("FileSinkDrainer: write error: %s", exc)
                continue

            # Check rotation — use stream.tell() to avoid passing a null log record
            # to shouldRollover(), which would crash trying to format it.
            try:
                if (
                    self._handler.maxBytes > 0
                    and self._handler.stream.tell() >= self._handler.maxBytes
                ):
                    self._handler.doRollover()
                    # Re-apply permissions after rotation
                    os.chmod(self._handler.baseFilename, 0o600)
            except (OSError, IOError) as exc:
                logger.error("FileSinkDrainer: rotation error: %s", exc)
                # Continue — degrade to writing to pre-rotation file

            # Periodic fsync
            now = time.monotonic()
            if (
                write_count >= self._fsync_records
                or (now - last_fsync) >= self._fsync_secs
            ):
                try:
                    self._handler.stream.flush()
                    os.fsync(self._handler.stream.fileno())
                    write_count = 0
                    last_fsync = now
                except Exception as exc:
                    logger.error("FileSinkDrainer: fsync error: %s", exc)


class FileSink:
    """Bounded-durable JSONL file sink.

    put() is non-blocking: serializes to JSONL line, enqueues or drops-oldest
    with a gap_marker when the queue is full.

    Construction raises RuntimeError if the trace file cannot be opened —
    fail-fast at startup, never register a sink with a broken file handle.
    """

    def __init__(self, run_id: str, config: ObservabilityConfig) -> None:
        self._run_id = run_id
        self._config = config
        self._q: queue.Queue = queue.Queue(maxsize=config.file_queue_depth)

        trace_path = config.trace_dir / f"{run_id}.jsonl"

        try:
            handler = logging.handlers.RotatingFileHandler(
                filename=str(trace_path),
                mode="a",
                maxBytes=config.file_max_size_mb * 1024 * 1024,
                backupCount=config.file_max_count,
                encoding="utf-8",
                delay=False,
            )
            # Set 0o600 permissions immediately after open
            os.chmod(str(trace_path), 0o600)
        except (OSError, IOError) as exc:
            raise RuntimeError(
                f"FileSink: cannot open trace file {trace_path}: {exc}"
            ) from exc

        self._handler = handler
        self._drainer = FileSinkDrainer(
            q=self._q,
            handler=self._handler,
            fsync_records=config.file_fsync_records,
            fsync_secs=config.file_fsync_secs,
        )
        self._drainer.start()

    def put(self, record: dict) -> None:
        """Serialize record to JSONL and enqueue. Non-blocking.

        On full queue: drop oldest, append gap_marker, then enqueue record.
        Producer is never blocked.
        """
        try:
            line = json.dumps(record, default=str)
        except Exception as exc:
            logger.error("FileSink: JSON serialization error: %s", exc)
            return

        try:
            self._q.put_nowait(line)
        except queue.Full:
            # Drop oldest
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            # Emit gap_marker
            gap = make_gap_marker(
                run_id=self._run_id,
                sink_id="file",
                drop_count=1,
            )
            try:
                gap_line = json.dumps(gap, default=str)
                self._q.put_nowait(gap_line)
            except queue.Full:
                pass  # even gap_marker doesn't fit — silently skip
            # Re-enqueue the actual record
            try:
                self._q.put_nowait(line)
            except queue.Full:
                pass  # still full — record lost (bounded-durable contract)

    def shutdown(self) -> None:
        """Enqueue sentinel, wait for drainer to flush, close handler."""
        self._q.put(_SENTINEL)
        self._drainer.join(timeout=5.0)
        if self._drainer.is_alive():
            logger.error("FileSink: drainer thread did not finish within 5s timeout")
        try:
            self._handler.close()
        except Exception as exc:
            logger.error("FileSink: handler close error: %s", exc)
