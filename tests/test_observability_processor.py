"""
Unit tests — SpanProcessor pipeline (task 10.4).

Tests:
  - LiveNotificationProcessor fires on_start → publishes span_start record
  - JsonlExportProcessor fires on_end → publishes span_end record
  - on_start record delivered before on_end (Invariant 3)
  - span parent/child linkage preserved through serialization
  - KIND-B-under-Act: child span carries Act span_id as parent_span_id
  - Processor errors go to logging only — never cross-contaminate other sinks
"""

from __future__ import annotations

import logging

from opentelemetry.sdk.trace import TracerProvider

from axiom.observability.processors import (
    JsonlExportProcessor,
    LiveNotificationProcessor,
)
from axiom.observability.registry import SinkRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CaptureSink:
    def __init__(self) -> None:
        self.received: list[dict] = []

    def put(self, record: dict) -> None:
        self.received.append(record)

    def shutdown(self) -> None:
        pass


class BrokenSink:
    def put(self, record: dict) -> None:
        raise RuntimeError("broken")

    def shutdown(self) -> None:
        pass


def _make_provider_with_capture() -> tuple[TracerProvider, CaptureSink]:
    registry = SinkRegistry()
    sink = CaptureSink()
    registry.register("trace", sink)
    tp = TracerProvider()
    tp.add_span_processor(LiveNotificationProcessor(registry=registry))
    tp.add_span_processor(JsonlExportProcessor(registry=registry))
    return tp, sink


# ---------------------------------------------------------------------------
# LiveNotificationProcessor — on_start fires span_start
# ---------------------------------------------------------------------------


class TestLiveNotificationProcessor:
    def test_on_start_publishes_span_start_record(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.act", attributes={}):
            pass
        starts = [r for r in sink.received if r["record_type"] == "span_start"]
        assert len(starts) >= 1

    def test_span_start_record_has_span_name(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.perceive", attributes={}):
            pass
        starts = [r for r in sink.received if r["record_type"] == "span_start"]
        assert any(r["span_name"] == "axiom.loop.perceive" for r in starts)

    def test_on_start_fires_before_on_end(self):
        """span_start must appear in the record list before span_end (Invariant 3)."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.act", attributes={}):
            pass
        types = [r["record_type"] for r in sink.received]
        start_idx = types.index("span_start")
        end_idx = types.index("span_end")
        assert start_idx < end_idx

    def test_span_start_contains_no_duration_ms(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            pass
        starts = [r for r in sink.received if r["record_type"] == "span_start"]
        for r in starts:
            assert "duration_ms" not in r
            assert "end_time_unix_nano" not in r

    def test_live_proc_on_end_is_noop(self):
        """LiveNotificationProcessor.on_end must not publish any record."""
        registry = SinkRegistry()
        sink = CaptureSink()
        registry.register("trace", sink)
        tp = TracerProvider()
        # Only register LiveNotificationProcessor — no JsonlExportProcessor
        tp.add_span_processor(LiveNotificationProcessor(registry=registry))
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.act", attributes={}):
            pass
        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        assert ends == []


# ---------------------------------------------------------------------------
# JsonlExportProcessor — on_end fires span_end
# ---------------------------------------------------------------------------


class TestJsonlExportProcessor:
    def test_on_end_publishes_span_end_record(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.observe", attributes={}):
            pass
        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        assert len(ends) >= 1

    def test_span_end_has_duration_ms(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.act", attributes={}):
            pass
        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        assert all("duration_ms" in r for r in ends)

    def test_jsonl_proc_on_start_is_noop(self):
        """JsonlExportProcessor.on_start must not publish any record."""
        registry = SinkRegistry()
        sink = CaptureSink()
        registry.register("trace", sink)
        tp = TracerProvider()
        # Only register JsonlExportProcessor — no LiveNotificationProcessor
        tp.add_span_processor(JsonlExportProcessor(registry=registry))
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            pass
        starts = [r for r in sink.received if r["record_type"] == "span_start"]
        assert starts == []


# ---------------------------------------------------------------------------
# Parent/child span linkage
# ---------------------------------------------------------------------------


class TestParentChildLinkage:
    def test_child_span_carries_parent_span_id(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.run", attributes={}) as parent:
            with tracer.start_as_current_span("axiom.loop.act", attributes={}) as child:
                pass

        # Find the child span_end record
        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        child_end = next((r for r in ends if r["span_name"] == "axiom.loop.act"), None)
        assert child_end is not None
        assert child_end["parent_span_id"] is not None

        # The parent_span_id of the child must match the parent's span_id
        parent_end = next((r for r in ends if r["span_name"] == "axiom.loop.run"), None)
        assert parent_end is not None
        assert child_end["parent_span_id"] == parent_end["span_id"]

    def test_run_root_has_null_parent_span_id(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.run", attributes={}):
            pass
        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        run_end = next((r for r in ends if r["span_name"] == "axiom.loop.run"), None)
        assert run_end is not None
        assert run_end["parent_span_id"] is None

    def test_kind_b_child_under_act_carries_act_span_id(self):
        """KIND-B invariant: provider-streamed child spans nest under Act."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span(
            "axiom.loop.act",
            attributes={"axiom.phase": "act", "axiom.provider_kind": "KIND_B"},
        ) as act_span:
            # Simulate a KIND-B child span (tool_call) created inside the Act context
            with tracer.start_as_current_span(
                "gen_ai.tool_call",
                attributes={"axiom.span_source": "provider-streamed"},
            ) as child:
                pass

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        act_end = next((r for r in ends if r["span_name"] == "axiom.loop.act"), None)
        child_end = next(
            (r for r in ends if r["span_name"] == "gen_ai.tool_call"), None
        )
        assert act_end is not None
        assert child_end is not None
        assert child_end["parent_span_id"] == act_end["span_id"]

    def test_trace_id_consistent_across_spans_in_one_trace(self):
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        with tracer.start_as_current_span("axiom.loop.run", attributes={}):
            with tracer.start_as_current_span("axiom.loop.act", attributes={}):
                pass
        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        trace_ids = {r["trace_id"] for r in ends}
        # All spans in one trace share the same trace_id
        assert len(trace_ids) == 1


# ---------------------------------------------------------------------------
# Processor error handling
# ---------------------------------------------------------------------------


class TestProcessorErrorHandling:
    def test_broken_sink_does_not_raise_in_on_start(self, caplog):
        registry = SinkRegistry()
        registry.register("trace", BrokenSink())
        tp = TracerProvider()
        tp.add_span_processor(LiveNotificationProcessor(registry=registry))
        tracer = tp.get_tracer("test")
        with caplog.at_level(logging.ERROR):
            # Must not propagate exception
            with tracer.start_as_current_span("axiom.loop.act", attributes={}):
                pass

    def test_broken_sink_does_not_raise_in_on_end(self, caplog):
        registry = SinkRegistry()
        registry.register("trace", BrokenSink())
        tp = TracerProvider()
        tp.add_span_processor(JsonlExportProcessor(registry=registry))
        tracer = tp.get_tracer("test")
        with caplog.at_level(logging.ERROR):
            with tracer.start_as_current_span("axiom.loop.act", attributes={}):
                pass  # on_end fires here; must not raise
