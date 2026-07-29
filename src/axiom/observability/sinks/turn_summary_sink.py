"""
TurnSummarySink — one human-readable line per completed turn.

Unlike FileSink/TuiSink/WsBridgeSink, this sink does no I/O beyond an
occasional stderr print (one line per completed "run" span, not one line
per span) — so put() runs synchronously on the OTel export thread with no
queue/drain thread of its own. That's safe precisely because it's rare:
one print per turn, not per span.

Existing sinks already carry every number this needs (schema.py's
span_end.duration_ms, derived from the OTel SDK's own span timestamps) --
this sink adds nothing to what's measured, only aggregates what's already
there into a total + per-PRAO-phase breakdown, keyed by the "run" span's
own span_id (not axiom.run_id, which is shared across every turn in a
multi-turn web session — see loop.py's _maybe_record("run", ...) wrapping
each PraoLoop.run() call in its own span).
"""

from __future__ import annotations

import sys
from typing import Callable

# Canonical PRAO order; anything else (future phases) is appended
# alphabetically after these, never dropped.
_PHASE_ORDER = ("perceive", "reason", "act", "observe", "use_skill")


def _fmt_ms(ms: float) -> str:
    """1.2s for >=1000ms, else N.Nms -- matches TuiSink's ms-first convention
    but switches to seconds for the totals/phases that are actually slow
    enough to matter (this feature exists because turns feel slow)."""
    if ms >= 1000:
        return f"{ms / 1000:.2f}s"
    return f"{ms:.1f}ms"


def _default_writer(line: str) -> None:
    print(line, file=sys.stderr)


class _TurnAccumulator:
    """Per-in-flight-turn duration/count totals, bucketed by phase name."""

    __slots__ = ("totals", "counts")

    def __init__(self) -> None:
        self.totals: dict[str, float] = {}
        self.counts: dict[str, int] = {}

    def add(self, phase: str, duration_ms: float) -> None:
        self.totals[phase] = self.totals.get(phase, 0.0) + duration_ms
        self.counts[phase] = self.counts.get(phase, 0) + 1


class TurnSummarySink:
    """Aggregates span_end records into one summary line per completed turn.

    Registered like any other sink (Sink Protocol: put()/shutdown()), but
    holds no queue -- state is a small in-memory dict of in-flight turns,
    keyed by the "run" span's own span_id, so multiple turns on the same
    Agent (run_turn(), which shares one axiom.run_id across the whole
    session) don't cross-contaminate each other's phase totals.
    """

    def __init__(self, writer: Callable[[str], None] | None = None) -> None:
        self._writer = writer or _default_writer
        self._active: dict[str, _TurnAccumulator] = {}

    # ------------------------------------------------------------------
    # Sink Protocol
    # ------------------------------------------------------------------

    def put(self, record: dict) -> None:
        record_type = record.get("record_type")

        if record_type == "span_start":
            if record.get("phase") == "run":
                span_id = record.get("span_id")
                if span_id is not None:
                    self._active[span_id] = _TurnAccumulator()
            return

        if record_type != "span_end":
            return  # gap_marker etc. -- nothing to aggregate

        phase = record.get("phase")
        span_id = record.get("span_id")
        duration_ms = record.get("duration_ms") or 0.0

        if phase == "run":
            acc = self._active.pop(span_id, None) if span_id is not None else None
            if acc is not None:
                self._emit(
                    total_ms=duration_ms,
                    acc=acc,
                    run_id=record.get("run_id"),
                    status=record.get("status"),
                )
            return

        parent_id = record.get("parent_span_id")
        acc = self._active.get(parent_id) if parent_id is not None else None
        if acc is not None and phase is not None:
            acc.add(phase, duration_ms)

    def shutdown(self) -> None:
        """No resources held (no queue, no thread) -- nothing to flush."""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit(
        self,
        total_ms: float,
        acc: _TurnAccumulator,
        run_id: str | None,
        status: str | None,
    ) -> None:
        ordered_phases = [p for p in _PHASE_ORDER if p in acc.totals]
        ordered_phases += sorted(p for p in acc.totals if p not in _PHASE_ORDER)

        parts = []
        for phase in ordered_phases:
            count = acc.counts.get(phase, 1)
            suffix = f"(x{count})" if count > 1 else ""
            parts.append(f"{phase} {_fmt_ms(acc.totals[phase])}{suffix}")

        run_tag = f" (run={run_id[:8]})" if run_id else ""
        error_tag = " [ERROR]" if status == "ERROR" else ""
        breakdown = " -- " + " ".join(parts) if parts else ""
        self._writer(f"[axiom] turn {_fmt_ms(total_ms)}{breakdown}{error_tag}{run_tag}")
