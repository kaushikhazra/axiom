"""
Unit tests — observability schema (task 10.1).

Tests:
  - span_start record shape (all required fields present)
  - span_end record shape (all common-core fields present, extensions bag)
  - gap_marker record shape
  - JSONL round-trip (serialize → JSON → deserialize → values preserved)
  - Hex ID formatting (trace_id 32 chars, span_id 16 chars)
  - Null parent_span_id for run-root (no parent context)
  - duration_ms derivation
"""

from __future__ import annotations

import json
import time

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider

from axiom.observability.schema import (
    OTEL_SCHEMA_URL,
    SCHEMA_VERSION,
    make_gap_marker,
    serialize_span_end,
    serialize_span_start,
)


# ---------------------------------------------------------------------------
# Helpers — build minimal ReadableSpan instances via a real TracerProvider
# ---------------------------------------------------------------------------


def _make_tracer_provider() -> TracerProvider:
    return TracerProvider()


def _make_span(
    name: str = "axiom.loop.act",
    attributes: dict | None = None,
    with_parent: bool = False,
    provider: TracerProvider | None = None,
) -> ReadableSpan:
    """Start (and end) a real OTel span via TracerProvider so all fields are set."""
    tp = provider or _make_tracer_provider()
    tracer = tp.get_tracer("test")
    with tracer.start_as_current_span(
        name=name,
        attributes=attributes or {},
    ) as span:
        pass  # span ends on context-manager exit
    # ReadableSpan is accessible after context-manager exit via the span object
    return span  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# span_start shape
# ---------------------------------------------------------------------------


class TestSerializeSpanStart:
    def _make_span_and_serialize(self, attributes: dict | None = None) -> dict:
        tp = _make_tracer_provider()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span(
            "axiom.loop.act",
            attributes=attributes
            or {
                "axiom.run_id": "run-123",
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            },
        ) as span:
            record = serialize_span_start(span)
        return record

    def test_record_type_is_span_start(self):
        r = self._make_span_and_serialize()
        assert r["record_type"] == "span_start"

    def test_schema_version_present(self):
        r = self._make_span_and_serialize()
        assert r["schema_version"] == SCHEMA_VERSION

    def test_otel_schema_url_present(self):
        r = self._make_span_and_serialize()
        assert r["otel_schema_url"] == OTEL_SCHEMA_URL

    def test_run_id_from_attributes(self):
        r = self._make_span_and_serialize(
            {
                "axiom.run_id": "abc-123",
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            }
        )
        assert r["run_id"] == "abc-123"

    def test_trace_id_is_32_char_hex(self):
        r = self._make_span_and_serialize()
        assert isinstance(r["trace_id"], str)
        assert len(r["trace_id"]) == 32
        int(r["trace_id"], 16)  # must be valid hex

    def test_span_id_is_16_char_hex(self):
        r = self._make_span_and_serialize()
        assert isinstance(r["span_id"], str)
        assert len(r["span_id"]) == 16
        int(r["span_id"], 16)  # must be valid hex

    def test_parent_span_id_none_for_root(self):
        # root span — no parent context
        r = self._make_span_and_serialize()
        assert r["parent_span_id"] is None

    def test_phase_from_attributes(self):
        r = self._make_span_and_serialize(
            {
                "axiom.run_id": "x",
                "axiom.phase": "perceive",
                "axiom.provider_kind": "KIND_B",
            }
        )
        assert r["phase"] == "perceive"

    def test_span_name_matches(self):
        tp = _make_tracer_provider()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.perceive", attributes={}) as span:
            record = serialize_span_start(span)
        assert record["span_name"] == "axiom.loop.perceive"

    def test_span_source_defaults_to_core_minted(self):
        r = self._make_span_and_serialize()
        assert r["span_source"] == "core-minted"

    def test_start_time_unix_nano_present(self):
        r = self._make_span_and_serialize()
        assert isinstance(r["start_time_unix_nano"], int)
        assert r["start_time_unix_nano"] > 0

    def test_no_gen_ai_fields_in_span_start(self):
        r = self._make_span_and_serialize()
        # span_start must NOT contain gen_ai_* or duration_ms — not available at open time
        for key in ("gen_ai_system", "duration_ms", "end_time_unix_nano", "status"):
            assert key not in r, f"span_start should not contain {key!r}"


# ---------------------------------------------------------------------------
# span_end shape
# ---------------------------------------------------------------------------


class TestSerializeSpanEnd:
    _ATTRS = {
        "axiom.run_id": "run-xyz",
        "axiom.phase": "reason",
        "axiom.provider_kind": "KIND_A",
        "gen_ai.system": "anthropic",
        "gen_ai.request.model": "claude-3-opus",
        "gen_ai.usage.input_tokens": 100,
        "gen_ai.usage.output_tokens": 50,
    }

    def _serialize(self, attrs: dict | None = None) -> dict:
        tp = _make_tracer_provider()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span(
            "axiom.loop.reason",
            attributes=attrs or self._ATTRS,
        ) as span:
            pass
        return serialize_span_end(span)  # type: ignore[arg-type]

    def test_record_type_is_span_end(self):
        assert self._serialize()["record_type"] == "span_end"

    def test_schema_version_present(self):
        assert self._serialize()["schema_version"] == SCHEMA_VERSION

    def test_otel_schema_url_present(self):
        assert self._serialize()["otel_schema_url"] == OTEL_SCHEMA_URL

    def test_run_id(self):
        assert self._serialize()["run_id"] == "run-xyz"

    def test_trace_id_32_chars(self):
        r = self._serialize()
        assert len(r["trace_id"]) == 32

    def test_span_id_16_chars(self):
        r = self._serialize()
        assert len(r["span_id"]) == 16

    def test_duration_ms_positive(self):
        r = self._serialize()
        assert isinstance(r["duration_ms"], float)
        assert r["duration_ms"] >= 0.0

    def test_status_ok_on_clean_exit(self):
        assert self._serialize()["status"] == "OK"

    def test_error_message_none_on_ok(self):
        assert self._serialize()["error_message"] is None

    def test_gen_ai_system(self):
        assert self._serialize()["gen_ai_system"] == "anthropic"

    def test_gen_ai_request_model(self):
        assert self._serialize()["gen_ai_request_model"] == "claude-3-opus"

    def test_gen_ai_usage_tokens(self):
        r = self._serialize()
        assert r["gen_ai_usage_input_tokens"] == 100
        assert r["gen_ai_usage_output_tokens"] == 50

    def test_extensions_bag_present_and_dict(self):
        r = self._serialize()
        assert isinstance(r["extensions"], dict)

    def test_extensions_empty_when_no_extra_attrs(self):
        # Only common-core attrs supplied — extensions must be {}
        r = self._serialize()
        assert r["extensions"] == {}

    def test_extensions_contains_extra_attrs(self):
        attrs = dict(self._ATTRS)
        attrs["axiom.adapter"] = "ClaudeAdapter"
        r = self._serialize(attrs)
        assert "axiom.adapter" in r["extensions"]
        assert r["extensions"]["axiom.adapter"] == "ClaudeAdapter"

    def test_start_and_end_time_unix_nano(self):
        r = self._serialize()
        assert r["start_time_unix_nano"] > 0
        assert r["end_time_unix_nano"] >= r["start_time_unix_nano"]

    def test_common_core_fields_never_missing(self):
        r = self._serialize()
        required = [
            "record_type",
            "schema_version",
            "otel_schema_url",
            "run_id",
            "trace_id",
            "span_id",
            "parent_span_id",
            "phase",
            "span_name",
            "span_source",
            "provider_kind",
            "start_time_unix_nano",
            "end_time_unix_nano",
            "duration_ms",
            "status",
            "error_message",
            "gen_ai_system",
            "gen_ai_request_model",
            "gen_ai_response_model",
            "gen_ai_operation_name",
            "gen_ai_usage_input_tokens",
            "gen_ai_usage_output_tokens",
            "cost_usd",
            "extensions",
        ]
        for field in required:
            assert field in r, f"common-core field {field!r} missing from span_end"


# ---------------------------------------------------------------------------
# gap_marker shape
# ---------------------------------------------------------------------------


class TestMakeGapMarker:
    def test_record_type(self):
        g = make_gap_marker("run-1", "file", 3)
        assert g["record_type"] == "gap_marker"

    def test_schema_version(self):
        g = make_gap_marker("run-1", "file", 3)
        assert g["schema_version"] == SCHEMA_VERSION

    def test_otel_schema_url(self):
        g = make_gap_marker("run-1", "file", 3)
        assert g["otel_schema_url"] == OTEL_SCHEMA_URL

    def test_run_id(self):
        g = make_gap_marker("run-1", "file", 3)
        assert g["run_id"] == "run-1"

    def test_sink_id(self):
        assert make_gap_marker("r", "tui", 1)["sink_id"] == "tui"

    def test_drop_count(self):
        assert make_gap_marker("r", "ws", 7)["drop_count"] == 7

    def test_drop_start_time_auto_set(self):
        before = time.time_ns()
        g = make_gap_marker("r", "file", 1)
        after = time.time_ns()
        assert before <= g["drop_start_time_unix_nano"] <= after

    def test_explicit_drop_start_time(self):
        ts = 12345678900
        g = make_gap_marker("r", "file", 1, drop_start_time_unix_nano=ts)
        assert g["drop_start_time_unix_nano"] == ts

    def test_reason_is_buffer_full(self):
        assert make_gap_marker("r", "file", 1)["reason"] == "buffer_full"


# ---------------------------------------------------------------------------
# JSONL round-trip
# ---------------------------------------------------------------------------


class TestJsonlRoundTrip:
    def test_span_end_json_roundtrip(self):
        tp = _make_tracer_provider()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span(
            "axiom.loop.act",
            attributes={
                "axiom.run_id": "trip-1",
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            },
        ) as span:
            pass
        record = serialize_span_end(span)  # type: ignore[arg-type]
        line = json.dumps(record, default=str)
        recovered = json.loads(line)
        assert recovered["record_type"] == "span_end"
        assert recovered["run_id"] == "trip-1"
        assert recovered["schema_version"] == SCHEMA_VERSION

    def test_gap_marker_json_roundtrip(self):
        g = make_gap_marker("run-trip", "file", 5)
        line = json.dumps(g, default=str)
        recovered = json.loads(line)
        assert recovered["record_type"] == "gap_marker"
        assert recovered["drop_count"] == 5

    def test_no_embedded_newlines_in_jsonl_line(self):
        tp = _make_tracer_provider()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.run", attributes={}) as span:
            pass
        record = serialize_span_end(span)  # type: ignore[arg-type]
        line = json.dumps(record, default=str)
        assert "\n" not in line
