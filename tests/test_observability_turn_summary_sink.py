"""
Unit tests — TurnSummarySink.

Tests:
  - one summary line printed per completed "run" span
  - per-phase totals/counts aggregated correctly across multiple cycles
  - phases printed in canonical PRAO order, unknown phases appended after
  - phase span_end arriving with an unrecognized parent is ignored, not raised
  - gap_marker / other record types are no-ops
  - multiple concurrent turns (distinct run spans) don't cross-contaminate
  - ERROR status on the run span is surfaced in the summary line
  - shutdown() never raises (no resources held)
"""

from __future__ import annotations

from axiom.observability.sinks.turn_summary_sink import TurnSummarySink


def _span_start(span_id: str, phase: str) -> dict:
    return {"record_type": "span_start", "span_id": span_id, "phase": phase}


def _span_end(
    span_id: str,
    parent_span_id: str | None,
    phase: str,
    duration_ms: float,
    run_id: str | None = "run-abc12345",
    status: str = "OK",
) -> dict:
    return {
        "record_type": "span_end",
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "phase": phase,
        "duration_ms": duration_ms,
        "run_id": run_id,
        "status": status,
    }


class TestTurnSummarySink:
    def test_emits_one_line_per_completed_turn(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("run-1", None, "run", 4820.0))

        assert len(lines) == 1
        sink.shutdown()

    def test_summary_includes_total_and_phase_breakdown(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("p1", "run-1", "perceive", 2.5))
        sink.put(_span_end("r1", "run-1", "reason", 1800.0))
        sink.put(_span_end("a1", "run-1", "act", 900.0))
        sink.put(_span_end("o1", "run-1", "observe", 5.0))
        sink.put(_span_end("run-1", None, "run", 2707.5))

        line = lines[0]
        assert "2.71s" in line
        assert "perceive 2.5ms" in line
        assert "reason 1.80s" in line
        assert "act 900.0ms" in line
        assert "observe 5.0ms" in line

    def test_phases_appear_in_canonical_prao_order(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        # Emit end-of-span records out of PRAO order.
        sink.put(_span_end("o1", "run-1", "observe", 1.0))
        sink.put(_span_end("a1", "run-1", "act", 1.0))
        sink.put(_span_end("r1", "run-1", "reason", 1.0))
        sink.put(_span_end("p1", "run-1", "perceive", 1.0))
        sink.put(_span_end("run-1", None, "run", 4.0))

        line = lines[0]
        assert (
            line.index("perceive")
            < line.index("reason")
            < line.index("act")
            < line.index("observe")
        )

    def test_unknown_phase_appended_after_canonical_ones(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("x1", "run-1", "zzz_custom", 1.0))
        sink.put(_span_end("p1", "run-1", "perceive", 1.0))
        sink.put(_span_end("run-1", None, "run", 2.0))

        line = lines[0]
        assert line.index("perceive") < line.index("zzz_custom")

    def test_multiple_cycles_of_same_phase_are_summed_and_counted(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("r1", "run-1", "reason", 500.0))
        sink.put(_span_end("r2", "run-1", "reason", 300.0))
        sink.put(_span_end("run-1", None, "run", 800.0))

        line = lines[0]
        assert "reason 800.0ms(x2)" in line

    def test_single_occurrence_has_no_count_suffix(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("r1", "run-1", "reason", 500.0))
        sink.put(_span_end("run-1", None, "run", 500.0))

        assert "reason 500.0ms(x1)" not in lines[0]
        assert "reason 500.0ms" in lines[0]

    def test_span_end_with_unrecognized_parent_is_ignored(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        # No matching span_start for this parent -- must not raise or emit.
        sink.put(_span_end("p1", "no-such-run-span", "perceive", 1.0))

        assert lines == []

    def test_gap_marker_and_other_record_types_are_noops(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put({"record_type": "gap_marker", "drop_count": 2})
        sink.put({"record_type": "something_else"})

        assert lines == []
        sink.shutdown()

    def test_concurrent_turns_do_not_cross_contaminate(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_start("run-2", "run"))
        sink.put(_span_end("p1", "run-1", "perceive", 10.0))
        sink.put(_span_end("p2", "run-2", "perceive", 20.0))
        sink.put(_span_end("run-1", None, "run", 100.0, run_id="run-first00"))
        sink.put(_span_end("run-2", None, "run", 200.0, run_id="run-second0"))

        assert len(lines) == 2
        assert "10.0ms" in lines[0] and "100.0ms" in lines[0]
        assert "20.0ms" in lines[1] and "200.0ms" in lines[1]

    def test_error_status_on_run_span_is_flagged(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("run-1", None, "run", 50.0, status="ERROR"))

        assert "[ERROR]" in lines[0]

    def test_ok_status_has_no_error_flag(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("run-1", None, "run", 50.0, status="OK"))

        assert "[ERROR]" not in lines[0]

    def test_run_id_prefix_included_in_summary(self):
        lines: list[str] = []
        sink = TurnSummarySink(writer=lines.append)

        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("run-1", None, "run", 50.0, run_id="abcdefgh-1234"))

        assert "run=abcdefgh" in lines[0]

    def test_shutdown_never_raises(self):
        sink = TurnSummarySink(writer=lambda _line: None)
        sink.shutdown()
        sink.shutdown()  # idempotent, matches Sink Protocol contract

    def test_default_writer_prints_to_stderr(self, capsys):
        sink = TurnSummarySink()  # no writer override -- exercise the default
        sink.put(_span_start("run-1", "run"))
        sink.put(_span_end("run-1", None, "run", 12.0))
        captured = capsys.readouterr()
        assert "[axiom] turn" in captured.err
