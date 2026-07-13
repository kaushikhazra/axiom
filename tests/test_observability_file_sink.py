"""
Unit tests — FileSink (task 10.3).

Tests:
  - gap_marker emitted on bounded-drop (queue full)
  - durability drain: records written to disk before shutdown returns
  - file permissions 0o600
  - clean shutdown (sentinel drains all records)
  - drainer thread is non-daemon
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from axiom.observability.config import ObservabilityConfig
from axiom.observability.sinks.file_sink import FileSink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path, queue_depth: int = 10_000) -> ObservabilityConfig:
    return ObservabilityConfig(
        trace_dir=tmp_path,
        file_queue_depth=queue_depth,
        file_max_size_mb=100,
        file_fsync_records=1_000_000,  # high — avoid fsync during tests
        file_fsync_secs=9999.0,
        tui_enabled=False,
        ws_port=None,
    )


def _read_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# File creation and permissions
# ---------------------------------------------------------------------------


class TestFileSinkPermissions:
    def test_trace_file_created(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-perm", config=cfg)
        sink.shutdown()
        assert (tmp_path / "run-perm.jsonl").exists()

    @pytest.mark.skipif(
        os.name == "nt",
        reason="Windows does not enforce Unix file permissions via stat()",
    )
    def test_trace_file_permissions_0o600(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-perm", config=cfg)
        sink.shutdown()
        path = tmp_path / "run-perm.jsonl"
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600

    def test_bad_trace_dir_raises_runtime_error(self, tmp_path):
        cfg = _make_config(tmp_path / "nonexistent_dir")
        with pytest.raises(RuntimeError, match="cannot open trace file"):
            FileSink(run_id="run-bad", config=cfg)


# ---------------------------------------------------------------------------
# Durability drain
# ---------------------------------------------------------------------------


class TestFileSinkDurabilityDrain:
    def test_records_written_before_shutdown_returns(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-drain", config=cfg)
        records = [{"record_type": "span_end", "seq": i} for i in range(10)]
        for r in records:
            sink.put(r)
        sink.shutdown()
        path = tmp_path / "run-drain.jsonl"
        written = _read_jsonl(path)
        assert len(written) == 10
        for i, rec in enumerate(written):
            assert rec["seq"] == i

    def test_empty_sink_shutdown_clean(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-empty", config=cfg)
        sink.shutdown()  # must not raise
        path = tmp_path / "run-empty.jsonl"
        assert path.exists()

    def test_single_record_round_trip(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-single", config=cfg)
        record = {"record_type": "gap_marker", "sink_id": "file", "drop_count": 1}
        sink.put(record)
        sink.shutdown()
        written = _read_jsonl(tmp_path / "run-single.jsonl")
        assert len(written) == 1
        assert written[0]["record_type"] == "gap_marker"

    def test_many_records_all_drained(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-many", config=cfg)
        n = 100
        for i in range(n):
            sink.put({"seq": i})
        sink.shutdown()
        written = _read_jsonl(tmp_path / "run-many.jsonl")
        assert len(written) == n


# ---------------------------------------------------------------------------
# Bounded-drop + gap_marker
# ---------------------------------------------------------------------------


class TestFileSinkBoundedDrop:
    """
    Test the gap_marker path by simulating queue.Full in FileSink.put().

    We monkey-patch put_nowait on the sink's queue BEFORE the drainer thread
    has a chance to consume anything. The drainer blocks on queue.get() on the
    real queue (which still works); we intercept put_nowait to inject Full on
    the first call, triggering the drop-oldest + gap_marker code path in put().
    After the test we restore put_nowait and drain cleanly via shutdown().
    """

    def test_gap_marker_emitted_when_put_nowait_raises_full(self, tmp_path):
        """patch put_nowait to raise Full on first call → gap_marker path executes."""
        import queue as qmod

        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-gap", config=cfg)

        original_put_nowait = sink._q.put_nowait
        call_count = [0]

        def _patched(item):
            call_count[0] += 1
            if call_count[0] == 1:
                raise qmod.Full()
            original_put_nowait(item)

        sink._q.put_nowait = _patched
        # This put() will see Full on the first put_nowait, trigger drop+gap_marker,
        # then call put_nowait again for the gap_marker and the original record.
        sink.put({"record_type": "span_end", "seq": 0})
        sink._q.put_nowait = original_put_nowait

        sink.shutdown()

        written = _read_jsonl(tmp_path / "run-gap.jsonl")
        record_types = [r["record_type"] for r in written]
        assert "gap_marker" in record_types

    def test_gap_marker_has_correct_sink_id(self, tmp_path):
        """gap_marker.sink_id must be 'file'."""
        import queue as qmod

        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-gap-id", config=cfg)

        original_put_nowait = sink._q.put_nowait
        call_count = [0]

        def _patched(item):
            call_count[0] += 1
            if call_count[0] == 1:
                raise qmod.Full()
            original_put_nowait(item)

        sink._q.put_nowait = _patched
        sink.put({"record_type": "span_end", "seq": 0})
        sink._q.put_nowait = original_put_nowait

        sink.shutdown()

        written = _read_jsonl(tmp_path / "run-gap-id.jsonl")
        gap = next((r for r in written if r["record_type"] == "gap_marker"), None)
        assert gap is not None
        assert gap["sink_id"] == "file"


# ---------------------------------------------------------------------------
# Shutdown / thread properties
# ---------------------------------------------------------------------------


class TestFileSinkShutdown:
    def test_shutdown_does_not_raise_on_second_call(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-shut", config=cfg)
        sink.shutdown()
        # Second shutdown sends another sentinel to an already-exited drainer.
        # The queue.put() will still work (queue is unbounded after drainer exits),
        # but the drainer thread is done. This must not propagate any exception.
        try:
            sink.shutdown()
        except Exception as exc:
            pytest.fail(f"second shutdown raised: {exc}")

    def test_drainer_thread_is_non_daemon(self, tmp_path):
        cfg = _make_config(tmp_path)
        sink = FileSink(run_id="run-daemon", config=cfg)
        assert sink._drainer.daemon is False
        sink.shutdown()
