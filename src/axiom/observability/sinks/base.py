"""
Sink Protocol — interface every registered sink must satisfy.

Both methods are required. Any class registered via SinkRegistry.register()
that does not implement shutdown() will raise AttributeError when
ObservabilityFaculty.shutdown() iterates sinks in reverse order.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Sink(Protocol):
    """Protocol for all observability sinks (file, TUI, WebSocket bridge).

    put(record) must be non-blocking — enqueue immediately or drop-oldest.
    shutdown() must be idempotent and safe to call from any thread.
    """

    def put(self, record: dict) -> None:
        """Enqueue record for async drain. Must return immediately (non-blocking)."""
        ...

    def shutdown(self) -> None:
        """Flush pending records and release resources. Idempotent."""
        ...
