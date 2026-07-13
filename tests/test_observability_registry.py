"""
Unit tests — SinkRegistry (task 10.2).

Tests:
  - Fan-out: all registered sinks receive the record
  - Per-consumer FIFO ordering
  - Per-sink error isolation: one sink failing does not stop others
  - register/unregister contract
  - Multiple subjects are independent
"""

from __future__ import annotations

import logging


from axiom.observability.registry import SinkRegistry


# ---------------------------------------------------------------------------
# Minimal in-memory sink for testing
# ---------------------------------------------------------------------------


class CaptureSink:
    """Records every put() call for assertion."""

    def __init__(self, name: str = "capture") -> None:
        self.name = name
        self.received: list[dict] = []
        self.shutdown_called = False

    def put(self, record: dict) -> None:
        self.received.append(record)

    def shutdown(self) -> None:
        self.shutdown_called = True

    def __repr__(self) -> str:
        return f"CaptureSink({self.name!r})"


class BrokenSink:
    """Always raises on put() — used to test error isolation."""

    def put(self, record: dict) -> None:
        raise RuntimeError("BrokenSink.put() always fails")

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fan-out
# ---------------------------------------------------------------------------


class TestFanOut:
    def test_single_sink_receives_record(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        reg.register("trace", sink)
        record = {"record_type": "span_end", "run_id": "r1"}
        reg.publish("trace", record)
        assert sink.received == [record]

    def test_two_sinks_both_receive_record(self):
        reg = SinkRegistry()
        s1, s2 = CaptureSink("a"), CaptureSink("b")
        reg.register("trace", s1)
        reg.register("trace", s2)
        record = {"record_type": "span_start"}
        reg.publish("trace", record)
        assert s1.received == [record]
        assert s2.received == [record]

    def test_three_sinks_all_receive_record(self):
        reg = SinkRegistry()
        sinks = [CaptureSink(str(i)) for i in range(3)]
        for s in sinks:
            reg.register("trace", s)
        rec = {"k": "v"}
        reg.publish("trace", rec)
        for s in sinks:
            assert s.received == [rec]

    def test_no_sinks_publish_is_noop(self):
        reg = SinkRegistry()
        # Must not raise
        reg.publish("trace", {"record_type": "span_end"})

    def test_publish_to_unknown_subject_is_noop(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        reg.register("trace", sink)
        reg.publish("other_subject", {"x": 1})
        assert sink.received == []


# ---------------------------------------------------------------------------
# FIFO ordering
# ---------------------------------------------------------------------------


class TestFifoOrdering:
    def test_records_arrive_in_emit_order(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        reg.register("trace", sink)
        records = [{"seq": i} for i in range(5)]
        for r in records:
            reg.publish("trace", r)
        assert sink.received == records

    def test_two_sinks_maintain_independent_fifo(self):
        reg = SinkRegistry()
        s1, s2 = CaptureSink("a"), CaptureSink("b")
        reg.register("trace", s1)
        reg.register("trace", s2)
        records = [{"i": i} for i in range(4)]
        for r in records:
            reg.publish("trace", r)
        assert s1.received == records
        assert s2.received == records


# ---------------------------------------------------------------------------
# Per-sink error isolation
# ---------------------------------------------------------------------------


class TestErrorIsolation:
    def test_broken_sink_does_not_stop_later_sink(self):
        reg = SinkRegistry()
        broken = BrokenSink()
        good = CaptureSink()
        reg.register("trace", broken)
        reg.register("trace", good)
        reg.publish("trace", {"x": 1})
        # good sink must still receive despite broken raising
        assert good.received == [{"x": 1}]

    def test_broken_sink_does_not_stop_earlier_sink(self):
        reg = SinkRegistry()
        good = CaptureSink()
        broken = BrokenSink()
        reg.register("trace", good)
        reg.register("trace", broken)
        reg.publish("trace", {"y": 2})
        assert good.received == [{"y": 2}]

    def test_broken_sink_error_logged_not_raised(self, caplog):
        reg = SinkRegistry()
        reg.register("trace", BrokenSink())
        with caplog.at_level(logging.ERROR, logger="axiom.observability.registry"):
            reg.publish("trace", {"z": 3})
        # Must log an error rather than propagating
        assert any("put() error" in m for m in caplog.messages)

    def test_multiple_broken_sinks_all_logged(self, caplog):
        reg = SinkRegistry()
        reg.register("trace", BrokenSink())
        reg.register("trace", BrokenSink())
        good = CaptureSink()
        reg.register("trace", good)
        with caplog.at_level(logging.ERROR, logger="axiom.observability.registry"):
            reg.publish("trace", {"a": 1})
        assert good.received == [{"a": 1}]
        error_count = sum(1 for m in caplog.messages if "put() error" in m)
        assert error_count == 2


# ---------------------------------------------------------------------------
# register / unregister
# ---------------------------------------------------------------------------


class TestRegisterUnregister:
    def test_register_same_sink_twice_delivers_twice(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        reg.register("trace", sink)
        reg.register("trace", sink)
        reg.publish("trace", {"k": "v"})
        assert len(sink.received) == 2

    def test_unregister_removes_sink(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        reg.register("trace", sink)
        reg.unregister("trace", sink)
        reg.publish("trace", {"k": "v"})
        assert sink.received == []

    def test_unregister_unknown_sink_noop(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        # Never registered — must not raise
        reg.unregister("trace", sink)

    def test_sinks_for_returns_snapshot(self):
        reg = SinkRegistry()
        s1 = CaptureSink("a")
        s2 = CaptureSink("b")
        reg.register("trace", s1)
        reg.register("trace", s2)
        snap = reg.sinks_for("trace")
        assert snap == [s1, s2]

    def test_sinks_for_snapshot_does_not_mutate_registry(self):
        reg = SinkRegistry()
        s = CaptureSink()
        reg.register("trace", s)
        snap = reg.sinks_for("trace")
        snap.clear()
        # Original registry still has the sink
        assert reg.sinks_for("trace") == [s]


# ---------------------------------------------------------------------------
# Multiple subjects are independent
# ---------------------------------------------------------------------------


class TestMultipleSubjects:
    def test_subjects_are_independent(self):
        reg = SinkRegistry()
        s_trace = CaptureSink("trace")
        s_agent = CaptureSink("agent")
        reg.register("trace", s_trace)
        reg.register("agent", s_agent)
        reg.publish("trace", {"t": 1})
        assert s_trace.received == [{"t": 1}]
        assert s_agent.received == []

    def test_same_sink_can_subscribe_to_multiple_subjects(self):
        reg = SinkRegistry()
        sink = CaptureSink()
        reg.register("trace", sink)
        reg.register("agent", sink)
        reg.publish("trace", {"t": 1})
        reg.publish("agent", {"a": 2})
        assert {"t": 1} in sink.received
        assert {"a": 2} in sink.received
