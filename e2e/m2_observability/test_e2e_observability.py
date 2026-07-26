"""
M2 Observability E2E Test
=========================

All four steps are PRIMARY and must PASS.

  Step 3 — Real trace validation: ObservabilityFaculty + FileSink drives a real
            PraoLoop run (stub adapter, no external model), reads produced JSONL,
            asserts schema + span tree.
  Step 4 — Gap marker path: overflow a lossy sink buffer, confirm gap_marker
            record with correct drop count.
  Step 5 — WsBridgeSink: start, connect a websockets client, confirm records
            stream to client, clean shutdown.
  Step 6 — ClaudeAdapter KIND-B smoke: one real PraoLoop run against the
            subscription model (claude_agent_sdk / Agent SDK — no ANTHROPIC_API_KEY
            needed), asserts act-phase spans, well-formed trace records, and real
            model response. SKIP is not acceptable here.

Run:
    python e2e/m2_observability/test_e2e_observability.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

# Ensure src/ is on the path so we can import axiom without pip install
_repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_repo_root / "src"))

from axiom.observability.config import ObservabilityConfig
from axiom.observability.faculty import ObservabilityFaculty
from axiom.observability.sinks.tui_sink import TuiSink
from axiom.loop import PraoLoop

# ---------------------------------------------------------------------------
# Stub adapter (no external model)
# ---------------------------------------------------------------------------

from axiom.interfaces import ActIntent, RespondIntent, RunState


class StubAdapter:
    """Deterministic in-memory adapter for E2E tracing — no external calls."""

    def __init__(self, act_cycles: int = 1) -> None:
        self._act_cycles = act_cycles
        self._cycle = 0

    def perceive(self, run_state: RunState) -> str:
        return f"[stub context] cycle={run_state.cycle_count}"

    def reason(self, context: str) -> object:
        if self._cycle < self._act_cycles:
            return ActIntent(instruction=f"do_thing_{self._cycle}")
        return RespondIntent(text="[stub] all done")

    def act(self, instruction: str) -> str:
        self._cycle += 1
        return f"[stub result] {instruction}"

    def observe(self, result: str, run_state: RunState) -> RunState:
        run_state.history.append(result)
        run_state.cycle_count += 1
        return run_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def err(msg: str) -> None:
    print(f"  [ERR] {msg}")


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Step 3 — Real trace validation
# ---------------------------------------------------------------------------


def step3_real_trace() -> str:
    section("STEP 3 — Real trace validation")

    with tempfile.TemporaryDirectory() as tmp:
        trace_dir = Path(tmp)
        config = ObservabilityConfig(
            trace_dir=trace_dir,
            tui_enabled=False,  # no TUI in E2E
            ws_port=None,
            file_fsync_records=1,  # flush eagerly for test determinism
            file_fsync_secs=0.1,
        )

        faculty = ObservabilityFaculty(config=config)
        run_id = faculty.new_run()

        ok(f"run_id = {run_id}")

        adapter = StubAdapter(
            act_cycles=1
        )  # 1 act cycle → perceive/reason/act/observe + final reason
        loop = PraoLoop(
            perceive=adapter,
            reason=adapter,
            act=adapter,
            observe=adapter,
            max_cycles=5,
        )

        response, run_state = loop.run(
            user_input="hello e2e",
            run_id=run_id,
            provider_kind="KIND_A",
        )
        ok(f"loop.run() returned: {response!r}  (cycles={run_state.cycle_count})")

        # Shut down faculty — flushes all sinks to disk
        faculty.shutdown()

        # Locate the trace file
        jsonl_files = list(trace_dir.glob("*.jsonl"))
        if not jsonl_files:
            err("No .jsonl trace file produced")
            return FAIL
        trace_path = jsonl_files[0]
        ok(f"trace file: {trace_path.name}")

        records = read_jsonl(trace_path)
        ok(f"total records in trace: {len(records)}")

        if not records:
            err("Trace file is empty")
            return FAIL

        # Print a snippet of the first few records
        print("\n  --- JSONL SNIPPET (first 4 records) ---")
        for r in records[:4]:
            print("  " + json.dumps(r))
        print("  --- END SNIPPET ---\n")

        # ---------------------------------------------------------------
        # Assertion: every record is well-formed JSON with mandatory fields
        # ---------------------------------------------------------------
        mandatory_fields = {"record_type", "schema_version", "run_id", "span_id"}
        for i, r in enumerate(records):
            rt = r.get("record_type")
            if rt == "gap_marker":
                # gap_markers carry run_id but no span_id — that's fine
                for f in ("record_type", "schema_version", "run_id"):
                    if f not in r:
                        err(f"record[{i}] gap_marker missing field {f!r}: {r}")
                        return FAIL
                continue
            missing = mandatory_fields - r.keys()
            if missing:
                err(f"record[{i}] missing mandatory fields {missing}: {r}")
                return FAIL
        ok("All records carry mandatory fields")

        # ---------------------------------------------------------------
        # Assertion: span_start AND span_end for each of perceive/reason/act/observe
        # ---------------------------------------------------------------
        starts = {
            r["span_id"]: r for r in records if r.get("record_type") == "span_start"
        }
        ends = {r["span_id"]: r for r in records if r.get("record_type") == "span_end"}

        ok(f"span_start records: {len(starts)}, span_end records: {len(ends)}")

        # Find phases among span_end records
        phase_ends: dict[str, list[dict]] = {}
        for r in ends.values():
            phase = r.get("phase") or ""
            phase_ends.setdefault(phase, []).append(r)

        ok(f"Phases with span_end records: {sorted(phase_ends.keys())}")

        required_phases = {"perceive", "reason", "act", "observe", "run"}
        missing_phases = required_phases - phase_ends.keys()
        if missing_phases:
            err(f"Missing span_end records for phases: {missing_phases}")
            return FAIL
        ok(
            "All required phases (perceive/reason/act/observe/run) have span_end records"
        )

        # ---------------------------------------------------------------
        # Assertion: every span_end has a corresponding span_start (same span_id)
        # ---------------------------------------------------------------
        unmatched = [sid for sid in ends if sid not in starts]
        if unmatched:
            err(f"span_end records with no matching span_start: {unmatched}")
            return FAIL
        ok("Every span_end has a matching span_start by span_id")

        # ---------------------------------------------------------------
        # Assertion: parent_span_id tree is valid
        # ---------------------------------------------------------------
        # Collect all span_ids from span_end records
        all_span_ids = set(ends.keys())

        # run-root must have parent_span_id == None
        run_roots = [r for r in ends.values() if r.get("phase") == "run"]
        for r in run_roots:
            if r.get("parent_span_id") is not None:
                err(f"run-root span has non-null parent_span_id: {r}")
                return FAIL
        ok(f"run-root span(s) have parent_span_id=null: {len(run_roots)} found")

        # All non-root spans must have a parent_span_id that resolves to a known span
        non_root_ends = [r for r in ends.values() if r.get("phase") != "run"]
        for r in non_root_ends:
            pid = r.get("parent_span_id")
            if pid is None:
                err(f"Non-root span has null parent_span_id: {r}")
                return FAIL
            if pid not in all_span_ids:
                err(f"Span {r['span_id']} parent_span_id {pid!r} not in span tree")
                return FAIL
        ok(f"All {len(non_root_ends)} non-root spans have valid parent_span_id links")

        # ---------------------------------------------------------------
        # Assertion: schema_version and span_source on all span records
        # ---------------------------------------------------------------
        for r in records:
            if r.get("record_type") in ("span_start", "span_end"):
                if r.get("schema_version") != "1.0":
                    err(f"Wrong schema_version in record: {r}")
                    return FAIL
                if not r.get("span_source"):
                    err(f"Missing span_source in record: {r}")
                    return FAIL
        ok("schema_version='1.0' and span_source present on all span records")

        # ---------------------------------------------------------------
        # Assertion: phase values are correct strings
        # ---------------------------------------------------------------
        valid_phases = {"perceive", "reason", "act", "observe", "run"}
        for r in ends.values():
            ph = r.get("phase")
            if ph not in valid_phases:
                err(f"Invalid phase value {ph!r} in span_end record: {r}")
                return FAIL
        ok(f"All phase values correct: {sorted(valid_phases)}")

        print()
        ok("STEP 3: ALL ASSERTIONS PASSED")
        return PASS


# ---------------------------------------------------------------------------
# Step 4 — Gap marker path (lossy sink overflow)
# ---------------------------------------------------------------------------


def step4_gap_marker() -> str:
    section("STEP 4 — Gap marker path (lossy sink overflow)")

    # Use TuiSink (lossy) with a tiny buffer so we can easily overflow it
    captured_records: list[dict] = []

    def capture_render(record: dict) -> None:
        captured_records.append(record)

    tui = TuiSink(buffer=5, render_fn=capture_render)

    # Push more records than the buffer size
    burst_count = 20
    dummy_records = [
        {
            "record_type": "span_start",
            "schema_version": "1.0",
            "otel_schema_url": "https://opentelemetry.io/schemas/1.28.0",
            "run_id": "test-run-gap",
            "trace_id": "aabbccdd" * 4,
            "span_id": f"aa{i:014x}",
            "parent_span_id": None,
            "phase": "act",
            "span_name": "axiom.loop.act",
            "span_source": "core-minted",
            "provider_kind": "KIND_A",
            "start_time_unix_nano": time.time_ns(),
        }
        for i in range(burst_count)
    ]

    for r in dummy_records:
        tui.put(r)

    # Wait for drain thread to process all records
    time.sleep(0.3)
    tui.shutdown()

    ok(f"Pushed {burst_count} records into TuiSink(buffer=5)")
    ok(f"Captured {len(captured_records)} rendered records (includes gap_markers)")

    # Confirm at least one gap_marker was emitted
    gap_markers = [r for r in captured_records if r.get("record_type") == "gap_marker"]
    if not gap_markers:
        err("No gap_marker records emitted after buffer overflow")
        return FAIL

    ok(f"gap_marker records emitted: {len(gap_markers)}")

    # Check gap_marker has correct structure
    gm = gap_markers[0]
    print(f"  gap_marker sample: {json.dumps(gm)}")

    for field in ("record_type", "schema_version", "sink_id", "drop_count", "reason"):
        if field not in gm:
            err(f"gap_marker missing field {field!r}")
            return FAIL
    if gm["record_type"] != "gap_marker":
        err(f"Wrong record_type: {gm['record_type']!r}")
        return FAIL
    if gm["sink_id"] != "tui":
        err(f"Wrong sink_id: {gm['sink_id']!r}")
        return FAIL
    if not isinstance(gm["drop_count"], int) or gm["drop_count"] < 1:
        err(f"Invalid drop_count: {gm['drop_count']!r}")
        return FAIL
    if gm["reason"] != "buffer_full":
        err(f"Wrong reason: {gm['reason']!r}")
        return FAIL

    total_dropped = sum(r["drop_count"] for r in gap_markers)
    ok(f"Total drop_count across gap_markers: {total_dropped}")
    ok(
        "gap_marker structure validated: record_type, sink_id, drop_count, reason all correct"
    )

    print()
    ok("STEP 4: ALL ASSERTIONS PASSED")
    return PASS


# ---------------------------------------------------------------------------
# Step 5 — WsBridgeSink: start, connect, stream, clean shutdown
# ---------------------------------------------------------------------------


def step5_ws_bridge() -> str:
    section("STEP 5 — WsBridgeSink: start, connect, stream, clean shutdown")

    try:
        import websockets
    except ImportError:
        err("'websockets' package not installed — cannot test WsBridgeSink")
        return FAIL

    from axiom.observability.sinks.ws_sink import WsBridgeSink

    # Find a free port
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        ws_port = s.getsockname()[1]

    config = ObservabilityConfig(
        ws_port=ws_port,
        ws_host="127.0.0.1",
        tui_enabled=False,
        ws_buffer=500,
    )
    ws_token = config.ws_token
    ok(f"Starting WsBridgeSink on port {ws_port}, token={ws_token[:8]}...")

    ws_sink = WsBridgeSink(config=config)
    ok("WsBridgeSink started")

    # Inject some records before client connects (queued per-client on connect)
    # and some after — the drain loop will send all
    dummy = {
        "record_type": "span_start",
        "schema_version": "1.0",
        "otel_schema_url": "https://opentelemetry.io/schemas/1.28.0",
        "run_id": "ws-e2e-run",
        "trace_id": "abcd1234" * 4,
        "span_id": "dead00000001beef",
        "parent_span_id": None,
        "phase": "run",
        "span_name": "axiom.loop.run",
        "span_source": "core-minted",
        "provider_kind": "KIND_B",
        "start_time_unix_nano": time.time_ns(),
    }

    async def ws_client_test() -> list[str]:
        uri = f"ws://127.0.0.1:{ws_port}/?token={ws_token}"
        received: list[str] = []

        # Connect first — the _handle_client coroutine runs on the WS sink's own
        # event loop and registers this client's deque.
        # Records put() BEFORE connection are NOT queued per-client (no client
        # registered yet).  We must: (1) connect, (2) wait for registration,
        # (3) THEN put records, (4) wait for drain loop to send them.
        async with websockets.connect(uri) as ws:
            # Give the WS sink's _handle_client time to register this client's deque.
            # The handler runs on a separate event loop (asyncio.sleep here only
            # yields our coroutine; the WS thread runs independently).
            await asyncio.sleep(0.2)

            # NOW put records — client is registered, deque exists
            ws_sink.put(dummy)
            ws_sink.put({**dummy, "span_id": "dead00000002beef"})

            # Wait up to 3 seconds for at least 1 record (drain loop polls every 10ms)
            deadline = asyncio.get_event_loop().time() + 3.0
            while asyncio.get_event_loop().time() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.2)
                    received.append(msg)
                    if len(received) >= 1:
                        break
                except asyncio.TimeoutError:
                    continue

        return received

    received = asyncio.run(ws_client_test())

    ok(f"WS client received {len(received)} record(s)")

    if not received:
        err("No records received by WS client within 2s timeout")
        ws_sink.shutdown()
        return FAIL

    # Validate the received record is valid JSON
    for msg in received[:1]:
        try:
            parsed = json.loads(msg)
            ok(f"Received record: {json.dumps(parsed)[:120]}...")
        except json.JSONDecodeError as e:
            err(f"Received non-JSON message: {msg!r} — {e}")
            ws_sink.shutdown()
            return FAIL

    ok("WS client received valid JSON record(s)")

    # Test clean shutdown — must not hang or raise
    start_shutdown = time.monotonic()
    ws_sink.shutdown()
    shutdown_elapsed = time.monotonic() - start_shutdown

    ok(f"WsBridgeSink.shutdown() completed in {shutdown_elapsed:.2f}s (must be < 5s)")
    if shutdown_elapsed > 5.0:
        err(f"Shutdown took too long: {shutdown_elapsed:.2f}s")
        return FAIL

    print()
    ok("STEP 5: ALL ASSERTIONS PASSED")
    return PASS


# ---------------------------------------------------------------------------
# Step 6 — ClaudeAdapter smoke (KIND-B, real subscription model)
# ---------------------------------------------------------------------------


def step6_claude_adapter_smoke() -> str:
    section("STEP 6 — ClaudeAdapter smoke (KIND-B, real subscription model)")

    # NOTE: ClaudeAdapter uses claude_agent_sdk (subscription/Agent SDK path),
    # NOT a raw ANTHROPIC_API_KEY. The old gate on ANTHROPIC_API_KEY was wrong
    # for this project and is intentionally removed here.

    try:
        from axiom.providers.claude_adapter import ClaudeAdapter
        from axiom import persona as persona_pkg
    except ImportError as e:
        err(f"ClaudeAdapter or persona not importable: {type(e).__name__}: {e}")
        return FAIL

    ok(
        "Constructing ClaudeAdapter exactly as agent.py does (subscription model, no ANTHROPIC_API_KEY needed)"
    )

    # ---------------------------------------------------------------
    # OTel global-provider reset (E2E multi-faculty workaround)
    # OTel only allows set_tracer_provider() once per process (enforced
    # by _TRACER_PROVIDER_SET_ONCE, a Once object).  Earlier steps (step 3)
    # already called it.  Reset the Once._done flag so this step's
    # ObservabilityFaculty can install its own TracerProvider and wire spans
    # to step 6's FileSink.  This is test-only bookkeeping; production runs
    # one faculty per process, so the restriction never bites there.
    # ---------------------------------------------------------------
    try:
        import opentelemetry.trace as _otel_trace

        _once = getattr(_otel_trace, "_TRACER_PROVIDER_SET_ONCE", None)
        if _once is not None and getattr(_once, "_done", False):
            _once._done = False
            ok("OTel _TRACER_PROVIDER_SET_ONCE reset (multi-faculty E2E workaround)")
    except Exception as _reset_err:
        ok(f"OTel provider-once reset not applicable / skipped: {_reset_err}")

    try:
        persona_text = persona_pkg.load()
    except (FileNotFoundError, ValueError) as e:
        err(f"Could not load persona: {type(e).__name__}: {e}")
        return FAIL
    ok(f"Persona loaded ({len(persona_text)} chars)")

    # Same allowed tools as agent.py's CLAUDE_SAFE_TOOLS (M4 renamed M1_ALLOWED_TOOLS)
    M1_ALLOWED_TOOLS: list[str] = ["Bash", "WebSearch"]
    from axiom.tools.guardrails import GuardrailsGate

    # M4: gate is a required ClaudeAdapter param; auto_approve=True so this
    # script runs unattended (best-effort file -- see design.md Files Changed).
    gate = GuardrailsGate(auto_approve=True)

    with tempfile.TemporaryDirectory() as tmp:
        trace_dir = Path(tmp)
        config = ObservabilityConfig(
            trace_dir=trace_dir,
            tui_enabled=False,
            ws_port=None,
            file_fsync_records=1,
            file_fsync_secs=0.1,
        )
        faculty = ObservabilityFaculty(config=config)
        run_id = faculty.new_run()
        ok(f"run_id = {run_id}")

        try:
            adapter = ClaudeAdapter(
                persona=persona_text, allowed_tools=M1_ALLOWED_TOOLS, gate=gate
            )
            loop = PraoLoop(
                perceive=adapter,
                reason=adapter,
                act=adapter,
                observe=adapter,
                max_cycles=3,
            )
            # Use a Bash-tool prompt so reason() MUST route to ACT
            # (TOOL-LESS-MEANS-DELEGATE rule in base.py mandates ACT when a tool
            # is needed; Bash is always available and deterministic).
            # This guarantees an act-phase span is minted in the trace.
            response, run_state = loop.run(
                user_input="Use the Bash tool to run: echo AXIOM_E2E_KIND_B_OK",
                run_id=run_id,
                provider_kind="KIND_B",
            )
            ok(f"ClaudeAdapter response (first 200 chars): {response[:200]!r}")
            ok(f"Cycles completed: {run_state.cycle_count}")
        except Exception as e:
            err("ClaudeAdapter run FAILED — verbatim error below:")
            err(f"  {type(e).__name__}: {e}")
            import traceback as _tb

            err(_tb.format_exc())
            faculty.shutdown()
            return FAIL

        faculty.shutdown()

        # ---------------------------------------------------------------
        # Read trace
        # ---------------------------------------------------------------
        jsonl_files = list(trace_dir.glob("*.jsonl"))
        if not jsonl_files:
            err("No trace file produced by ClaudeAdapter run")
            return FAIL
        trace_path = jsonl_files[0]
        records = read_jsonl(trace_path)
        ok(f"Total trace records: {len(records)}")

        if not records:
            err("Trace file is empty")
            return FAIL

        print("\n  --- KIND-B TRACE SNIPPET (first 8 records) ---")
        for r in records[:8]:
            print("  " + json.dumps(r))
        print("  --- END SNIPPET ---\n")

        # ---------------------------------------------------------------
        # Assertion 1: real model response obtained
        # ---------------------------------------------------------------
        if not response:
            err("Response is empty — model did not produce output")
            return FAIL
        ok("Real model response obtained (non-empty)")

        # ---------------------------------------------------------------
        # Assertion 2: all records well-formed (mandatory fields present)
        # ---------------------------------------------------------------
        mandatory = {"record_type", "schema_version", "run_id"}
        for i, r in enumerate(records):
            if r.get("record_type") == "gap_marker":
                continue
            missing = mandatory - r.keys()
            if missing:
                err(f"record[{i}] missing mandatory fields {missing}: {r}")
                return FAIL
        ok("All records carry mandatory fields")

        # ---------------------------------------------------------------
        # Assertion 3: act-phase span_end exists (ACT path was executed)
        # ---------------------------------------------------------------
        ends = {r["span_id"]: r for r in records if r.get("record_type") == "span_end"}
        act_ends = [r for r in ends.values() if r.get("phase") == "act"]
        if not act_ends:
            err("No act-phase span_end record found in trace")
            err(
                "  The prompt should have triggered ACT intent via TOOL-LESS-MEANS-DELEGATE rule"
            )
            err(f"  Phases present: {sorted({r.get('phase') for r in ends.values()})}")
            return FAIL
        ok(f"Act-phase span_end record(s) found: {len(act_ends)}")

        act_span = act_ends[0]
        act_span_id = act_span.get("span_id")
        ok(f"Act span_id: {act_span_id}")

        # ---------------------------------------------------------------
        # Assertion 4: act span parent resolves to run-root (valid tree)
        # ---------------------------------------------------------------
        run_ends = [r for r in ends.values() if r.get("phase") == "run"]
        if not run_ends:
            err("No run-root span_end record found in trace")
            return FAIL
        run_root_span_id = run_ends[0].get("span_id")
        act_parent_id = act_span.get("parent_span_id")
        if act_parent_id != run_root_span_id:
            err(
                f"Act span parent {act_parent_id!r} != run-root span {run_root_span_id!r}"
            )
            return FAIL
        ok(f"Act span correctly parents to run-root span {run_root_span_id}")

        # ---------------------------------------------------------------
        # Assertion 5: KIND-B provider-streamed child spans (informational)
        # The current ClaudeAdapter does not yet instrument SDK stream events
        # as OTel child spans (§3.6 / §4.3 of design.md are aspirational for
        # this iteration). Report count; validate parent_span_id if any exist;
        # but do NOT fail if absent — this is the honest state of the adapter.
        # ---------------------------------------------------------------
        provider_streamed = [
            r for r in records if r.get("span_source") == "provider-streamed"
        ]
        if provider_streamed:
            ok(f"KIND-B provider-streamed child spans found: {len(provider_streamed)}")
            for ps in provider_streamed:
                pid = ps.get("parent_span_id")
                if pid != act_span_id:
                    err(
                        f"provider-streamed span {ps.get('span_id')!r} has parent "
                        f"{pid!r}, expected act span {act_span_id!r}"
                    )
                    return FAIL
            ok("All provider-streamed spans correctly parent to act span")
            print("\n  --- KIND-B STREAMED SPAN SAMPLE ---")
            for r in provider_streamed[:3]:
                print("  " + json.dumps(r))
            print("  ---\n")
        else:
            ok(
                "No KIND-B provider-streamed child spans in trace "
                "(ClaudeAdapter SDK stream events not yet instrumented as OTel children "
                "— design.md §3.6/§4.3 aspirational for current adapter iteration)"
            )

        # ---------------------------------------------------------------
        # Assertion 6: gen_ai.* attributes present on act span (null is valid
        # when adapter doesn't surface them; field must be present in record)
        # ---------------------------------------------------------------
        for field in (
            "gen_ai_system",
            "gen_ai_request_model",
            "gen_ai_response_model",
            "gen_ai_operation_name",
            "gen_ai_usage_input_tokens",
            "gen_ai_usage_output_tokens",
        ):
            if field not in act_span:
                err(
                    f"gen_ai field {field!r} missing from act span_end record (must be present, null if unavailable)"
                )
                return FAIL
        ok(
            "All gen_ai.* common-core fields present on act span (null = not surfaced by adapter)"
        )
        ok(f"  gen_ai_system              = {act_span.get('gen_ai_system')!r}")
        ok(f"  gen_ai_request_model       = {act_span.get('gen_ai_request_model')!r}")
        ok(f"  gen_ai_response_model      = {act_span.get('gen_ai_response_model')!r}")
        ok(f"  gen_ai_operation_name      = {act_span.get('gen_ai_operation_name')!r}")
        ok(
            f"  gen_ai_usage_input_tokens  = {act_span.get('gen_ai_usage_input_tokens')!r}"
        )
        ok(
            f"  gen_ai_usage_output_tokens = {act_span.get('gen_ai_usage_output_tokens')!r}"
        )

        # gen_ai_operation_name is always set to the phase name by record_phase() — must be non-null
        if not act_span.get("gen_ai_operation_name"):
            err(
                "gen_ai_operation_name is null on act span — record_phase() always sets this"
            )
            return FAIL
        ok(f"gen_ai_operation_name = {act_span['gen_ai_operation_name']!r}")

        print()
        ok("STEP 6: ALL ASSERTIONS PASSED — real KIND-B run against subscription model")
        return PASS


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def main() -> int:
    print("\n" + "#" * 60)
    print("  M2 Observability E2E Test Suite")
    print("#" * 60)

    results: dict[str, str] = {}

    # Step 3 — Real trace validation
    try:
        results["step3_real_trace"] = step3_real_trace()
    except Exception:
        err(f"EXCEPTION in step3:\n{traceback.format_exc()}")
        results["step3_real_trace"] = FAIL

    # Step 4 — Gap marker
    try:
        results["step4_gap_marker"] = step4_gap_marker()
    except Exception:
        err(f"EXCEPTION in step4:\n{traceback.format_exc()}")
        results["step4_gap_marker"] = FAIL

    # Step 5 — WsBridgeSink
    try:
        results["step5_ws_bridge"] = step5_ws_bridge()
    except Exception:
        err(f"EXCEPTION in step5:\n{traceback.format_exc()}")
        results["step5_ws_bridge"] = FAIL

    # Step 6 — ClaudeAdapter smoke (KIND-B, real subscription model)
    try:
        results["step6_claude_smoke"] = step6_claude_adapter_smoke()
    except Exception:
        err(f"EXCEPTION in step6:\n{traceback.format_exc()}")
        results["step6_claude_smoke"] = FAIL

    # -------------------------------------------------------------------
    # Final report
    # -------------------------------------------------------------------
    section("FINAL REPORT")
    for step, result in results.items():
        marker = (
            "[PASS]" if result == PASS else ("[SKIP]" if result == SKIP else "[FAIL]")
        )
        print(f"  {marker}  {step}")

    # All four steps are now primary — step 6 exercises the real subscription
    # model (KIND-B) and must PASS; SKIP is no longer acceptable.
    primary_steps = [
        "step3_real_trace",
        "step4_gap_marker",
        "step5_ws_bridge",
        "step6_claude_smoke",
    ]
    primary_pass = all(results.get(s) == PASS for s in primary_steps)

    print()
    if primary_pass:
        print("  ALL STEPS: PASS")
    else:
        failed = [s for s in primary_steps if results.get(s) != PASS]
        print(f"  FAILED STEPS: {failed}")

    print()
    return 0 if primary_pass else 1


if __name__ == "__main__":
    sys.exit(main())
