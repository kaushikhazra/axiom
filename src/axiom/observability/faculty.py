"""
ObservabilityFaculty — composition root for the M2 observability system.

Owns:
  - TracerProvider init (OTel in-process setup)
  - SpanProcessor registration (LiveNotificationProcessor first, JsonlExportProcessor second)
  - Sink construction + registration (FileSink -> TuiSink -> WsBridgeSink)
  - atexit + SIGTERM handlers (with previous-handler chaining)
  - Idempotent shutdown via threading.Event
  - run_id generation via new_run()
  - Trace directory creation + age-based purge at new_run()

Design ref: design.md §2.1
"""

from __future__ import annotations

import atexit
import logging
import signal
import threading
import time
import uuid
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from axiom.observability.config import ObservabilityConfig
from axiom.observability.processors import (
    JsonlExportProcessor,
    LiveNotificationProcessor,
)
from axiom.observability.registry import SinkRegistry
from axiom.observability.sinks.file_sink import FileSink
from axiom.observability.sinks.tui_sink import TuiSink


logger = logging.getLogger(__name__)


class ObservabilityFaculty:
    """Composition root for the M2 observability system.

    Wires the OTel TracerProvider, two-processor pipeline, SinkRegistry,
    and all registered sinks into a single cohesive unit.

    Lifecycle:
        faculty = ObservabilityFaculty(config)
        run_id = faculty.new_run()
        # ... run PraoLoop with run_id ...
        faculty.shutdown()          # called automatically via atexit/SIGTERM

    Startup ordering constraint (O1 / design.md §2.2):
    This object MUST be fully constructed before any call to record_phase().
    The composition root (agent.py) is responsible for this ordering.
    """

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self._config = config or ObservabilityConfig()
        self._shutdown_called = threading.Event()
        self._registry = SinkRegistry()
        self._sinks: list = []  # ordered list of registered sinks (for reverse shutdown)

        # --- OTel TracerProvider setup ---
        self._tracer_provider = TracerProvider()

        # Register processors: Live first (on_start), Jsonl second (on_end)
        live_proc = LiveNotificationProcessor(registry=self._registry)
        jsonl_proc = JsonlExportProcessor(registry=self._registry)
        self._tracer_provider.add_span_processor(live_proc)
        self._tracer_provider.add_span_processor(jsonl_proc)

        # Set as global OTel provider — record_phase() picks this up via get_tracer()
        trace.set_tracer_provider(self._tracer_provider)

        # --- atexit registration ---
        atexit.register(self.shutdown)

        # --- SIGTERM handler with previous-handler chaining (design.md §2.1 O2) ---
        try:
            old_sigterm = signal.signal(
                signal.SIGTERM,
                lambda sig, frame: self.shutdown(),  # placeholder; replaced below
            )

            def _sigterm_handler(sig: int, frame) -> None:
                self.shutdown()
                if callable(old_sigterm):
                    old_sigterm(sig, frame)

            signal.signal(signal.SIGTERM, _sigterm_handler)
        except (OSError, ValueError):
            # SIGTERM cannot be set in some environments (e.g. Windows threads, test runners)
            logger.debug(
                "ObservabilityFaculty: SIGTERM handler not installed (not supported in this context)"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_run(self) -> str:
        """Generate a run_id, create trace directory, purge stale files.

        Returns:
            run_id: UUID4 string uniquely identifying this PraoLoop.run() call.

        Note: Multiple calls to new_run() are supported. Each call unregisters the
        previous run's sinks from the registry (so they no longer receive new-run
        records) before registering fresh ones. The previous sinks remain in
        self._sinks for orderly shutdown — they are still drained and closed when
        ObservabilityFaculty.shutdown() is called.
        """
        run_id = str(uuid.uuid4())

        # Ensure trace directory exists (O3 — design.md §2.1)
        trace_dir: Path = self._config.trace_dir
        trace_dir.mkdir(parents=True, exist_ok=True)

        # Age-based purge: delete .jsonl files older than file_max_age_days
        self._purge_old_traces(trace_dir)

        # Unregister any sinks left over from a previous run so they don't receive
        # records for this new run. They remain in self._sinks for shutdown ordering.
        for sink in self._registry.sinks_for("trace"):
            self._registry.unregister("trace", sink)

        # Construct and register FileSink for this run
        try:
            file_sink = FileSink(run_id=run_id, config=self._config)
            self._registry.register("trace", file_sink)
            self._sinks.append(file_sink)
        except RuntimeError as exc:
            logger.error("ObservabilityFaculty: FileSink construction failed: %s", exc)
            # Fail fast — design.md §2.5 FileSink Construction and run_id Injection
            raise

        # Optionally register TuiSink
        if self._config.tui_enabled:
            tui_sink = TuiSink(buffer=self._config.tui_buffer)
            self._registry.register("trace", tui_sink)
            self._sinks.append(tui_sink)

        # Optionally register WsBridgeSink
        if self._config.ws_port is not None:
            from axiom.observability.sinks.ws_sink import WsBridgeSink

            try:
                ws_sink = WsBridgeSink(config=self._config)
                self._registry.register("trace", ws_sink)
                self._sinks.append(ws_sink)
            except Exception as exc:
                logger.error(
                    "ObservabilityFaculty: WsBridgeSink construction failed: %s", exc
                )
                # Non-fatal — WS is optional; continue without it

        return run_id

    def shutdown(self) -> None:
        """Idempotent shutdown — safe to call multiple times (atexit + SIGTERM may both fire).

        Shutdown sequence (design.md §2.1):
        1. Force-flush and shut down the TracerProvider (flushes processor callbacks).
        2. Shut down sinks in REVERSE registration order (WsBridgeSink -> TuiSink -> FileSink).
        """
        if self._shutdown_called.is_set():
            return
        self._shutdown_called.set()

        # Step 1: flush OTel processor pipeline
        try:
            self._tracer_provider.force_flush(timeout_millis=5_000)
        except Exception as exc:
            logger.error(
                "ObservabilityFaculty: tracer_provider.force_flush error: %s", exc
            )
        try:
            self._tracer_provider.shutdown()
        except Exception as exc:
            logger.error(
                "ObservabilityFaculty: tracer_provider.shutdown error: %s", exc
            )

        # Step 2: shut down sinks in reverse registration order
        for sink in reversed(self._sinks):
            try:
                sink.shutdown()
            except Exception as exc:
                logger.error(
                    "ObservabilityFaculty: sink %r shutdown error: %s", sink, exc
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _purge_old_traces(self, trace_dir: Path) -> None:
        """Delete .jsonl files in trace_dir older than config.file_max_age_days."""
        cutoff = time.time() - (self._config.file_max_age_days * 86_400)
        try:
            for path in trace_dir.glob("*.jsonl"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        logger.debug(
                            "ObservabilityFaculty: purged stale trace %s", path
                        )
                except OSError as exc:
                    logger.error(
                        "ObservabilityFaculty: error purging %s: %s", path, exc
                    )
        except OSError as exc:
            logger.error(
                "ObservabilityFaculty: error scanning trace dir %s: %s", trace_dir, exc
            )
