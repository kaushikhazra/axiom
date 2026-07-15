"""
Observability package public API.

Exports:
    ObservabilityFaculty — composition root; initialize before any record_phase() call.
    record_phase          — context manager wrapping each PRAO phase in an OTel span.
"""

from axiom.observability.faculty import ObservabilityFaculty
from axiom.observability.record import record_phase

__all__ = ["ObservabilityFaculty", "record_phase"]
