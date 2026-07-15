# M2 · Observability — Task Checklist

**Spec:** `004-m2-observability`
**Milestone:** M2 — "Watch it think"
**Status:** COMPLETE

---

## 1. Foundation — Schema and Config

- [x] 1.1 `schema.py` — `ObservabilityConfig` author writes `SCHEMA_VERSION`, `OTEL_SCHEMA_URL`, `serialize_span_start()`, `serialize_span_end()`, `make_gap_marker()` in `src/axiom/observability/schema.py` _OBS-03, OBS-04_
- [x] 1.2 `config.py` — `ObservabilityConfig` dataclass author writes all configurable parameters (trace_dir, file_max_size_mb, file_max_age_days, file_max_count, file_queue_depth, file_fsync_records, file_fsync_secs, ws_token, ws_port, tui_buffer) in `src/axiom/observability/config.py` _OBS-08_

## 2. Sink Protocol

- [x] 2.1 `sinks/base.py` — `Sink` Protocol author writes `put(record: dict) -> None` and `shutdown() -> None` in `src/axiom/observability/sinks/base.py` _OBS-04, OBS-05_
- [x] 2.2 `sinks/__init__.py` — `sinks` package author creates empty `src/axiom/observability/sinks/__init__.py` _OBS-10_

## 3. In-Process Fan-Out

- [x] 3.1 `registry.py` — `SinkRegistry` author writes `register(subject, sink)`, `publish(subject, record)` fan-out (per-subject list, catch-and-log per-sink errors) in `src/axiom/observability/registry.py` _OBS-04, OBS-09_

## 4. SpanProcessor Pipeline

- [x] 4.1 `processors.py` — `LiveNotificationProcessor` author writes `on_start` -> `serialize_span_start` -> `registry.publish("trace", record)` in `src/axiom/observability/processors.py` _OBS-10, INV-3_
- [x] 4.2 `processors.py` — `JsonlExportProcessor` author writes `on_end` -> `serialize_span_end` -> `registry.publish("trace", record)` in `src/axiom/observability/processors.py` _OBS-10_

## 5. Sinks

- [x] 5.1 `sinks/file_sink.py` — `FileSink` + `FileSinkDrainer` author writes bounded queue, `RotatingFileHandler` backend, poison-pill shutdown, gap-marker on full, `0o600` permissions, periodic fsync in `src/axiom/observability/sinks/file_sink.py` _OBS-06_
- [x] 5.2 `sinks/tui_sink.py` — `TuiSink` author writes `deque(maxlen=200)` with `_deque_lock`, drain thread, gap-marker on full, optional startup in `src/axiom/observability/sinks/tui_sink.py` _OBS-07_
- [x] 5.3 `sinks/ws_sink.py` — `WsBridgeSink` author writes dedicated asyncio event loop thread, `run_coroutine_threadsafe` shutdown bridge, per-client deque, localhost-only bind, token auth in `src/axiom/observability/sinks/ws_sink.py` _OBS-08_

## 6. Record Call-Point

- [x] 6.1 `record.py` — `record_phase()` context manager author writes OTel `start_as_current_span` wrapping each PRAO phase, `StatusCode.OK/ERROR` on exit in `src/axiom/observability/record.py` _OBS-01, OBS-02_

## 7. ObservabilityFaculty

- [x] 7.1 `faculty.py` — `ObservabilityFaculty` author writes `TracerProvider` init, processor registration (`LiveNotificationProcessor` first, `JsonlExportProcessor` second), sink construction + registration (FileSink -> TuiSink -> WsBridgeSink), atexit + SIGTERM handlers, idempotent shutdown, `run_id` generation in `src/axiom/observability/faculty.py` _OBS-01, OBS-10_

## 8. Loop Wiring

- [x] 8.1 `loop.py` — `PraoLoop` author wraps `run()` with `record_phase()` context managers for run-root span and each PRAO phase boundary in `src/axiom/loop.py` _OBS-01, OBS-02_

## 9. Public API Export

- [x] 9.1 `observability/__init__.py` — package author exports `ObservabilityFaculty`, `record_phase` in `src/axiom/observability/__init__.py` _OBS-10_

## 10. Unit Tests

- [x] 10.1 `tests/test_observability_schema.py` — test author writes record schema shape tests and JSONL round-trip tests _OBS-03_
- [x] 10.2 `tests/test_observability_registry.py` — test author writes fan-out, per-consumer FIFO ordering, per-sink error isolation tests _OBS-04, OBS-09_
- [x] 10.3 `tests/test_observability_file_sink.py` — test author writes gap-marker on bounded-drop, durability drain, permissions, shutdown tests _OBS-06_
- [x] 10.4 `tests/test_observability_processor.py` — test author writes span parent/child linkage, KIND-B-under-Act rule, on_start vs on_end processor tests _OBS-10, INV-1, INV-3_
- [x] 10.5 `tests/test_observability_faculty.py` — test author writes integration: faculty assembles, sinks registered, shuts down cleanly _OBS-01, OBS-10_

---

## Implementation Notes

- `FileSinkDrainer.shouldRollover()` replaced with `stream.tell() >= maxBytes` to avoid
  passing `None` as a log record (which crashes `RotatingFileHandler.shouldRollover`).
- `serialize_span_end()` maps `StatusCode.UNSET` → `"OK"` (only `ERROR` is a failure).
- `record_phase()` in `loop.py` is injected via `_maybe_record()` helper — no-op when
  `run_id=None`, preserving backward compat with direct callers that don't wire faculty.
- OTel global TracerProvider is a process-level singleton; faculty tests use
  `faculty._tracer_provider.get_tracer()` directly for test isolation.

---

## Requirement Traceability

| Code | Meaning |
|------|---------|
| OBS-01 | US-01 -- Step-level PRAO trace at every phase boundary |
| OBS-02 | US-02 -- Provider-general span tree (KIND A + KIND B) |
| OBS-03 | US-03 -- Normalized span schema: common core + extensions bag |
| OBS-04 | US-04 -- JSONL wire format with single-producer fan-out |
| OBS-05 | US-05 -- Async non-blocking emit with per-consumer buffering |
| OBS-06 | US-06 -- File sink: bounded-durable, drains on its own thread |
| OBS-07 | US-07 -- TUI sink: live terminal view, lossy |
| OBS-08 | US-08 -- WebSocket bridge sink: localhost-only, token-authenticated |
| OBS-09 | US-09 -- In-process pub/sub seam |
| OBS-10 | US-10 -- OTel SDK in-process |
| INV-1  | Invariant 1 -- Asyncio Task Timing Contract |
| INV-2  | Invariant 2 -- Thread Boundary Rule |
| INV-3  | Invariant 3 -- Live Sinks Subscribe to on_start |
