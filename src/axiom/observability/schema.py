"""
Trace record serialization — schema constants and serializers.

Defines:
  SCHEMA_VERSION  — local schema version string ("1.0")
  OTEL_SCHEMA_URL — OTel GenAI semantic conventions URL in effect
  serialize_span_start() — LiveNotificationProcessor on_start record
  serialize_span_end()   — JsonlExportProcessor on_end record
  make_gap_marker()      — gap-marker record emitted by consumer buffers

Import path for gap markers in sinks:
  from axiom.observability.schema import make_gap_marker
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

SCHEMA_VERSION: str = "1.0"
OTEL_SCHEMA_URL: str = "https://opentelemetry.io/schemas/1.28.0"  # matches opentelemetry-semantic-conventions 0.64b0


def _hex_span_id(span_id: int | None) -> str | None:
    """Convert OTel integer span ID to 16-char hex string, or None."""
    if span_id is None or span_id == 0:
        return None
    return format(span_id, "016x")


def _hex_trace_id(trace_id: int | None) -> str | None:
    """Convert OTel integer trace ID to 32-char hex string, or None."""
    if trace_id is None or trace_id == 0:
        return None
    return format(trace_id, "032x")


def _get_attr(span: ReadableSpan, key: str, default=None):
    """Safely retrieve a span attribute by key."""
    attrs = span.attributes or {}
    return attrs.get(key, default)


def serialize_span_start(span: ReadableSpan) -> dict:
    """Produce a span_start record from a just-opened span (on_start callback).

    Contains header fields only — gen_ai.* attributes and end timing are not
    available at open time. Consumers correlate span_start/span_end by span_id.
    """
    ctx = span.context
    parent_id = None
    if span.parent is not None:
        parent_id = _hex_span_id(span.parent.span_id)

    return {
        "record_type": "span_start",
        "schema_version": SCHEMA_VERSION,
        "otel_schema_url": OTEL_SCHEMA_URL,
        # Identity
        "run_id": _get_attr(span, "axiom.run_id"),
        "trace_id": _hex_trace_id(ctx.trace_id) if ctx else None,
        "span_id": _hex_span_id(ctx.span_id) if ctx else None,
        "parent_span_id": parent_id,
        # Phase metadata
        "phase": _get_attr(span, "axiom.phase"),
        "span_name": span.name,
        "span_source": _get_attr(span, "axiom.span_source", "core-minted"),
        "provider_kind": _get_attr(span, "axiom.provider_kind"),
        # Timing — only start is available
        "start_time_unix_nano": span.start_time,
    }


def serialize_span_end(span: ReadableSpan) -> dict:
    """Produce a span_end record from a completed span (on_end callback).

    All common-core fields present; provider-specific fields in extensions.
    Fields unavailable for a given provider carry null, never omitted.
    """
    from opentelemetry.trace import StatusCode  # local import — OTel confined here

    ctx = span.context
    parent_id = None
    if span.parent is not None:
        parent_id = _hex_span_id(span.parent.span_id)

    start_ns = span.start_time or 0
    end_ns = span.end_time or 0
    duration_ms = (end_ns - start_ns) / 1_000_000 if (start_ns and end_ns) else 0.0

    # UNSET (no explicit status set) is treated as OK — only StatusCode.ERROR
    # indicates a failed span. This matches the OTel SDK convention: status is
    # UNSET by default; ERROR must be set explicitly.
    status_ok = span.status.status_code != StatusCode.ERROR
    error_message = None
    if not status_ok and span.status.description:
        error_message = span.status.description

    # Pull gen_ai.* attrs from span attributes
    attrs = span.attributes or {}

    # Collect extension attributes — everything not in common-core
    _common_keys = {
        "axiom.run_id",
        "axiom.phase",
        "axiom.span_source",
        "axiom.provider_kind",
        "gen_ai.system",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "gen_ai.operation.name",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "axiom.cost_usd",
    }
    extensions = {k: v for k, v in attrs.items() if k not in _common_keys}

    return {
        "record_type": "span_end",
        "schema_version": SCHEMA_VERSION,
        "otel_schema_url": OTEL_SCHEMA_URL,
        # Identity
        "run_id": attrs.get("axiom.run_id"),
        "trace_id": _hex_trace_id(ctx.trace_id) if ctx else None,
        "span_id": _hex_span_id(ctx.span_id) if ctx else None,
        "parent_span_id": parent_id,
        # Phase metadata
        "phase": attrs.get("axiom.phase"),
        "span_name": span.name,
        "span_source": attrs.get("axiom.span_source", "core-minted"),
        "provider_kind": attrs.get("axiom.provider_kind"),
        # Timing
        "start_time_unix_nano": start_ns,
        "end_time_unix_nano": end_ns,
        "duration_ms": duration_ms,
        # Status
        "status": "OK" if status_ok else "ERROR",
        "error_message": error_message,
        # gen_ai.* common-core (null when unavailable — never omitted)
        "gen_ai_system": attrs.get("gen_ai.system"),
        "gen_ai_request_model": attrs.get("gen_ai.request.model"),
        "gen_ai_response_model": attrs.get("gen_ai.response.model"),
        "gen_ai_operation_name": attrs.get(
            "gen_ai.operation.name", attrs.get("axiom.phase")
        ),
        "gen_ai_usage_input_tokens": attrs.get("gen_ai.usage.input_tokens"),
        "gen_ai_usage_output_tokens": attrs.get("gen_ai.usage.output_tokens"),
        "cost_usd": attrs.get("axiom.cost_usd"),
        # Extensions bag — provider/adapter-specific; empty {} when nothing
        "extensions": extensions,
    }


def make_gap_marker(
    run_id: str | None,
    sink_id: str,
    drop_count: int,
    drop_start_time_unix_nano: int | None = None,
) -> dict:
    """Produce a gap_marker record for consumer buffer overflow.

    Emitted by each consumer (FileSink, TuiSink, WsBridgeSink) when a record
    is dropped from their bounded buffer. First-class JSONL record.
    """
    if drop_start_time_unix_nano is None:
        drop_start_time_unix_nano = time.time_ns()

    return {
        "record_type": "gap_marker",
        "schema_version": SCHEMA_VERSION,
        "otel_schema_url": OTEL_SCHEMA_URL,
        "run_id": run_id,
        "sink_id": sink_id,
        "drop_count": drop_count,
        "drop_start_time_unix_nano": drop_start_time_unix_nano,
        "reason": "buffer_full",
    }
