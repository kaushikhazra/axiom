"""
SinkRegistry — in-process fan-out for trace records.

publish(subject, record) broadcasts to all sinks registered for that subject.
Per-sink errors are caught and logged to stdlib — never cross-contaminate other sinks.

M2 uses subject="trace" only. Subject taxonomy deferred to M7.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axiom.observability.sinks.base import Sink

logger = logging.getLogger(__name__)


class SinkRegistry:
    """In-process fan-out: register sinks per subject; publish records to all.

    Registration order within a subject determines delivery order.
    Durability-priority order (FileSink first) is enforced by the caller
    (ObservabilityFaculty) at registration time.
    """

    def __init__(self) -> None:
        # subject -> ordered list of sinks
        self._sinks: dict[str, list[Sink]] = defaultdict(list)

    def register(self, subject: str, sink: Sink) -> None:
        """Register sink for subject. Duplicate registrations are allowed
        (same sink registered twice will receive each record twice)."""
        self._sinks[subject].append(sink)

    def unregister(self, subject: str, sink: Sink) -> None:
        """Remove the first occurrence of sink from the subject list."""
        try:
            self._sinks[subject].remove(sink)
        except ValueError:
            pass  # not registered — silently ignore

    def publish(self, subject: str, record: dict) -> None:
        """Broadcast record to all sinks registered for subject.

        If a sink's put() raises, the exception is logged and the next sink
        still receives the record (no cross-contamination, AC-11.3).
        """
        for sink in self._sinks.get(subject, []):
            try:
                sink.put(record)
            except Exception as exc:
                logger.error(
                    "SinkRegistry: sink %r put() error for subject %r: %s",
                    sink,
                    subject,
                    exc,
                )

    def sinks_for(self, subject: str) -> list[Sink]:
        """Return a snapshot of sinks registered for subject (for inspection/testing)."""
        return list(self._sinks.get(subject, []))
