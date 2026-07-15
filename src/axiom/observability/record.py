"""
record_phase() — the RECORD call-point API.

This is the ONLY observability import that loop.py touches.
All OTel imports live here — never in loop.py or interfaces.py.

Usage (in loop.py):
    with record_phase("perceive", run_id="abc", provider_kind="KIND_B"):
        context = self._perceive.perceive(run_state)

The four PRAO phase spans nest under a run-root span:
    axiom.loop.run
      axiom.loop.perceive
      axiom.loop.reason
      axiom.loop.act
        [adapter children — KIND A: full-depth; KIND B: event-derived under Act]
      axiom.loop.observe

Error invariant (AC-01.4): span is emitted even on error — the except branch
sets StatusCode.ERROR and re-raises, so on_end fires with error status captured.

Startup ordering constraint (design.md §2.2 / O1):
ObservabilityFaculty MUST be fully initialized before any call to record_phase().
Calling record_phase() before initialization uses the no-op default OTel tracer
and silently loses all trace data. The composition root (agent.py) is responsible
for enforcing this ordering.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.trace import StatusCode, Span

_TRACER_NAME = "axiom.loop"


def _get_tracer() -> trace.Tracer:
    """Acquire a tracer from the global TracerProvider (set by ObservabilityFaculty)."""
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def record_phase(
    phase: str,
    run_id: str,
    provider_kind: str,
    span_source: str = "core-minted",
    extra_attributes: dict | None = None,
) -> Generator[Span, None, None]:
    """Context manager that wraps a PRAO phase in an OTel span.

    Args:
        phase: PRAO phase name — "run", "perceive", "reason", "act", "observe".
        run_id: UUID4 run identifier (from ObservabilityFaculty.new_run()).
        provider_kind: "KIND_A" or "KIND_B".
        span_source: "core-minted" (default) or "provider-streamed" for adapter children.
        extra_attributes: additional span attributes merged in.

    Yields:
        The active OTel Span for further attribute setting inside the phase.

    On exit:
        Sets StatusCode.OK on clean exit, StatusCode.ERROR (with description) on exception.
        Re-raises any exception after setting status — spans are always emitted (AC-01.4).
    """
    attributes: dict = {
        "axiom.run_id": run_id,
        "axiom.phase": phase,
        "axiom.provider_kind": provider_kind,
        "axiom.span_source": span_source,
        "gen_ai.operation.name": phase,
    }
    if extra_attributes:
        attributes.update(extra_attributes)

    tracer = _get_tracer()
    with tracer.start_as_current_span(
        name=f"axiom.loop.{phase}",
        attributes=attributes,
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            raise
        else:
            span.set_status(StatusCode.OK)
