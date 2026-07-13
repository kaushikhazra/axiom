"""
Unit tests — ObservabilityFaculty integration (task 10.5).

Tests:
  - Faculty assembles without error (TracerProvider, processors, sinks)
  - new_run() returns a unique UUID4 run_id
  - new_run() creates trace directory
  - FileSink is registered and receives records after new_run()
  - TUI sink is optional (tui_enabled=False skips registration)
  - WS sink is optional (ws_port=None skips instantiation)
  - Shutdown is idempotent (safe to call twice)
  - Shutdown flushes and closes FileSink (file written to disk)
  - Spans emitted via the faculty's TracerProvider reach sinks

Note on OTel global provider isolation:
  OTel's global TracerProvider is a process-level singleton — once set it cannot
  be overridden (subsequent set_tracer_provider calls log a warning and are ignored).
  End-to-end tests that verify span delivery use faculty._tracer_provider.get_tracer()
  directly rather than the global getter, which gives full test isolation.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from axiom.observability.config import ObservabilityConfig
from axiom.observability.faculty import ObservabilityFaculty


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    tmp_path: Path, tui_enabled: bool = False, ws_port=None
) -> ObservabilityConfig:
    return ObservabilityConfig(
        trace_dir=tmp_path,
        tui_enabled=tui_enabled,
        ws_port=ws_port,
        file_fsync_records=1_000_000,
        file_fsync_secs=9999.0,
    )


def _read_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _emit_span(faculty: ObservabilityFaculty, name: str, attributes: dict) -> None:
    """Emit a span via the faculty's own TracerProvider (process-isolation-safe)."""
    tracer = faculty._tracer_provider.get_tracer("test")
    with tracer.start_as_current_span(name, attributes=attributes):
        pass


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestFacultyConstruction:
    def test_constructs_without_error(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.shutdown()

    def test_default_config_used_when_none_passed(self, tmp_path):
        # Verify construction works; skip new_run() to avoid touching default trace dir
        faculty = ObservabilityFaculty()
        faculty.shutdown()

    def test_has_tracer_provider(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        from opentelemetry.sdk.trace import TracerProvider

        assert isinstance(faculty._tracer_provider, TracerProvider)
        faculty.shutdown()

    def test_has_sink_registry(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        from axiom.observability.registry import SinkRegistry

        assert isinstance(faculty._registry, SinkRegistry)
        faculty.shutdown()


# ---------------------------------------------------------------------------
# new_run()
# ---------------------------------------------------------------------------


class TestFacultyNewRun:
    def test_new_run_returns_string(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()
        faculty.shutdown()
        assert isinstance(run_id, str)

    def test_new_run_returns_uuid4(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()
        faculty.shutdown()
        parsed = uuid.UUID(run_id, version=4)
        assert str(parsed) == run_id

    def test_new_run_returns_unique_ids(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        ids = {faculty.new_run() for _ in range(3)}
        faculty.shutdown()
        assert len(ids) == 3

    def test_new_run_creates_trace_directory(self, tmp_path):
        trace_dir = tmp_path / "nested" / "traces"
        cfg = _make_config(trace_dir)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        faculty.shutdown()
        assert trace_dir.exists()

    def test_new_run_creates_jsonl_file(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()
        faculty.shutdown()
        assert (tmp_path / f"{run_id}.jsonl").exists()


# ---------------------------------------------------------------------------
# Sink registration
# ---------------------------------------------------------------------------


class TestFacultySinkRegistration:
    def test_file_sink_registered_on_trace_subject(self, tmp_path):
        cfg = _make_config(tmp_path, tui_enabled=False, ws_port=None)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        sinks = faculty._registry.sinks_for("trace")
        faculty.shutdown()
        from axiom.observability.sinks.file_sink import FileSink

        assert any(isinstance(s, FileSink) for s in sinks)

    def test_tui_sink_not_registered_when_disabled(self, tmp_path):
        cfg = _make_config(tmp_path, tui_enabled=False)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        sinks = faculty._registry.sinks_for("trace")
        faculty.shutdown()
        from axiom.observability.sinks.tui_sink import TuiSink

        assert not any(isinstance(s, TuiSink) for s in sinks)

    def test_tui_sink_registered_when_enabled(self, tmp_path):
        cfg = _make_config(tmp_path, tui_enabled=True)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        sinks = faculty._registry.sinks_for("trace")
        faculty.shutdown()
        from axiom.observability.sinks.tui_sink import TuiSink

        assert any(isinstance(s, TuiSink) for s in sinks)

    def test_ws_sink_not_registered_when_port_none(self, tmp_path):
        cfg = _make_config(tmp_path, ws_port=None)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        sinks = faculty._registry.sinks_for("trace")
        faculty.shutdown()
        from axiom.observability.sinks.ws_sink import WsBridgeSink

        assert not any(isinstance(s, WsBridgeSink) for s in sinks)

    def test_file_sink_registered_first(self, tmp_path):
        """FileSink must be first (most durable) in registration order."""
        cfg = _make_config(tmp_path, tui_enabled=True)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        sinks = faculty._registry.sinks_for("trace")
        faculty.shutdown()
        from axiom.observability.sinks.file_sink import FileSink

        assert isinstance(sinks[0], FileSink)


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestFacultyShutdown:
    def test_shutdown_is_idempotent(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        faculty.shutdown()
        try:
            faculty.shutdown()
        except Exception as exc:
            pytest.fail(f"second shutdown raised: {exc}")

    def test_shutdown_called_flag_set_after_first_shutdown(self, tmp_path):
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        faculty.new_run()
        faculty.shutdown()
        assert faculty._shutdown_called.is_set()

    def test_records_written_to_disk_after_shutdown(self, tmp_path):
        """Spans emitted via faculty._tracer_provider reach the file sink on disk."""
        cfg = _make_config(tmp_path)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()

        _emit_span(
            faculty,
            "axiom.loop.act",
            {
                "axiom.run_id": run_id,
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            },
        )

        faculty.shutdown()

        path = tmp_path / f"{run_id}.jsonl"
        records = _read_jsonl(path)
        types = {r["record_type"] for r in records}
        assert "span_end" in types


# ---------------------------------------------------------------------------
# End-to-end: faculty TracerProvider emits spans that reach the file sink
# ---------------------------------------------------------------------------


class TestFacultyEndToEnd:
    def test_spans_reach_file_sink(self, tmp_path):
        cfg = _make_config(tmp_path, tui_enabled=False)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()

        attrs = {
            "axiom.run_id": run_id,
            "axiom.phase": "perceive",
            "axiom.provider_kind": "KIND_A",
        }
        _emit_span(faculty, "axiom.loop.perceive", attrs)

        attrs2 = {
            "axiom.run_id": run_id,
            "axiom.phase": "reason",
            "axiom.provider_kind": "KIND_A",
        }
        _emit_span(faculty, "axiom.loop.reason", attrs2)

        faculty.shutdown()

        records = _read_jsonl(tmp_path / f"{run_id}.jsonl")
        phases = [r.get("phase") for r in records if r.get("record_type") == "span_end"]
        assert "perceive" in phases
        assert "reason" in phases

    def test_run_id_propagated_to_records(self, tmp_path):
        cfg = _make_config(tmp_path, tui_enabled=False)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()

        _emit_span(
            faculty,
            "axiom.loop.act",
            {
                "axiom.run_id": run_id,
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            },
        )

        faculty.shutdown()

        records = _read_jsonl(tmp_path / f"{run_id}.jsonl")
        for r in records:
            if r["record_type"] in ("span_start", "span_end"):
                assert r.get("run_id") == run_id

    def test_error_span_has_status_error(self, tmp_path):
        """A span set to ERROR status is serialized with status='ERROR'."""
        from opentelemetry.trace import StatusCode

        cfg = _make_config(tmp_path, tui_enabled=False)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()

        tracer = faculty._tracer_provider.get_tracer("test")
        with tracer.start_as_current_span(
            "axiom.loop.act",
            attributes={
                "axiom.run_id": run_id,
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            },
        ) as span:
            span.set_status(StatusCode.ERROR, "something went wrong")

        faculty.shutdown()

        records = _read_jsonl(tmp_path / f"{run_id}.jsonl")
        ends = [r for r in records if r["record_type"] == "span_end"]
        act_end = next((r for r in ends if r.get("phase") == "act"), None)
        assert act_end is not None
        assert act_end["status"] == "ERROR"
        assert "something went wrong" in (act_end["error_message"] or "")

    def test_span_start_emitted_before_span_end(self, tmp_path):
        """LiveNotificationProcessor fires span_start before JsonlExportProcessor fires span_end."""
        cfg = _make_config(tmp_path, tui_enabled=False)
        faculty = ObservabilityFaculty(config=cfg)
        run_id = faculty.new_run()

        _emit_span(
            faculty,
            "axiom.loop.act",
            {
                "axiom.run_id": run_id,
                "axiom.phase": "act",
                "axiom.provider_kind": "KIND_A",
            },
        )

        faculty.shutdown()

        records = _read_jsonl(tmp_path / f"{run_id}.jsonl")
        types = [r["record_type"] for r in records]
        assert "span_start" in types
        assert "span_end" in types
        start_idx = types.index("span_start")
        end_idx = types.index("span_end")
        assert start_idx < end_idx
