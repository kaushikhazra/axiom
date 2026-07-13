"""
SpanProcessor pipeline — two processors registered on the TracerProvider.

LiveNotificationProcessor  — on_start -> span_start record -> SinkRegistry.publish()
JsonlExportProcessor       — on_end   -> span_end record   -> SinkRegistry.publish()

Both receive the SinkRegistry via constructor injection (no singleton / service locator).
Processor errors go to stdlib logging only — never the fan-out bus (AC-11.4).

Invariant 3 (spike E6): live sinks subscribe to on_start, not on_end.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

from axiom.observability.schema import serialize_span_end, serialize_span_start

if TYPE_CHECKING:
    from axiom.observability.registry import SinkRegistry

logger = logging.getLogger(__name__)


class LiveNotificationProcessor(SpanProcessor):
    """Fires on span OPEN — publishes span_start record to all registered sinks.

    Implements Invariant 3: live sinks (TUI, WS) get immediate notification
    when a span opens, not when it closes. For a 30s Act span, on_start fires
    at the start, giving "Act in progress" visibility.
    """

    def __init__(self, registry: SinkRegistry) -> None:
        self._registry = registry

    def on_start(
        self, span: ReadableSpan, parent_context: Context | None = None
    ) -> None:
        """Serialize span header and publish span_start to all trace sinks."""
        try:
            record = serialize_span_start(span)
            self._registry.publish("trace", record)
        except Exception as exc:
            logger.error("LiveNotificationProcessor.on_start error: %s", exc)

    def on_end(self, span: ReadableSpan) -> None:
        pass  # handled by JsonlExportProcessor

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


class JsonlExportProcessor(SpanProcessor):
    """Fires on span CLOSE — publishes span_end record (fully populated) to all sinks.

    This is the durable record: complete with timing, status, gen_ai.* attributes.
    """

    def __init__(self, registry: SinkRegistry) -> None:
        self._registry = registry

    def on_start(
        self, span: ReadableSpan, parent_context: Context | None = None
    ) -> None:
        pass  # handled by LiveNotificationProcessor

    def on_end(self, span: ReadableSpan) -> None:
        """Serialize completed span and publish span_end to all trace sinks."""
        try:
            record = serialize_span_end(span)
            self._registry.publish("trace", record)
        except Exception as exc:
            logger.error("JsonlExportProcessor.on_end error: %s", exc)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True
