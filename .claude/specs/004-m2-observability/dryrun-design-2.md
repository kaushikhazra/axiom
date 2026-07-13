# Design Dry-Run Report #2

**Document**: `.claude/specs/004-m2-observability/design.md`
**Reviewed**: 2026-07-13

---

## Critical Gaps (must fix before implementation)

None.

---

## Warnings (should fix, may cause issues)

### [W1] `RotatingFileHandler.doRollover()` closes and reopens the underlying stream — `FileSinkDrainer` must reacquire `handler.stream` after rollover
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: §2.5 "File Rotation Mechanism" specifies that `FileSinkDrainer` writes via `handler.stream.write(line + "\n")` and calls `handler.shouldRollover()` + `handler.doRollover()` manually after each write batch. However, `RotatingFileHandler.doRollover()` closes the current stream and opens a new one — after `doRollover()` returns, `handler.stream` points to the **new** file. The design does not state that `FileSinkDrainer` must reacquire `handler.stream` after each rollover call. If the drainer holds a local reference to the old stream (e.g. `f = handler.stream` caching it before the loop), writes after rollover go to the closed/renamed file.
- **Risk**: Silent data loss after first rotation event — records written to a closed, rotated-away file handle. The old file is renamed by `doRollover()`, so the write may succeed (depending on OS file handle semantics) but write to the wrong file.
- **Suggestion**: Specify in design §2.5 that `FileSinkDrainer` MUST re-dereference `handler.stream` on every write iteration (never cache `handler.stream` in a local variable across iterations), and that after calling `doRollover()`, the drainer reads `handler.stream` from the handler object to obtain the new file handle. Additionally specify that `doRollover()` failure (e.g. rename failure) is caught, logged to stdlib, and the drainer continues writing to the current file.

---

### [W2] `TuiSink` and `WsBridgeSink` shutdown lifecycle not specified
- **Pass**: Pass 4 (State Machine & Transitions)
- **What**: §2.5 specifies a detailed shutdown contract for `FileSink` (poison-pill pattern, non-daemon thread, `shutdown()` method, join with timeout). No equivalent shutdown contract is defined for `TuiSink` or `WsBridgeSink`. The design mentions that TuiSink "drains on its own asyncio task (or daemon thread)" and WsBridgeSink "drains on an asyncio task" and runs a WS server — but how these are stopped at process exit is unspecified. `ObservabilityFaculty.shutdown()` is mentioned in §2.1 as "flushes processors" but does not enumerate what sink cleanup it performs.
- **Risk**: At process exit, the WS server asyncio task continues running until the event loop is destroyed; the TUI drain task is left uncancelled. Depending on task/daemon-thread configuration, this may hang interpreter exit or produce spurious errors after the main loop has finished.
- **Suggestion**: Add shutdown contracts for `TuiSink` and `WsBridgeSink` in their respective design sections (§2.6 and §2.7). Specify: `TuiSink.shutdown()` cancels the drain task and waits for it; `WsBridgeSink.shutdown()` closes the WS server, closes all connected clients, cancels the drain task. State that `ObservabilityFaculty.shutdown()` calls `.shutdown()` on all registered sinks in reverse registration order (WsBridgeSink → TuiSink → FileSink), so the durable sink is flushed last.

---

### [W3] `FileSinkDrainer` blocks forever on `queue.get()` if `FileSink.shutdown()` is not called
- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: `FileSinkDrainer` is specified as `daemon=False` (so the interpreter waits for it at exit) and loops on `queue.get()` (blocking indefinitely). The shutdown sentinel path requires `FileSink.shutdown()` to be called explicitly by `ObservabilityFaculty.shutdown()`. If `shutdown()` is not called (e.g. an unhandled exception exits the composition root before cleanup, or the agent is killed via SIGTERM without a registered handler), the drainer thread blocks `queue.get()` indefinitely, hanging interpreter exit permanently — the process never exits.
- **Risk**: Process hangs on exit in any code path that doesn't reach `ObservabilityFaculty.shutdown()`. This is an ops risk: users kill the process with SIGKILL instead of waiting, losing any records still in the queue.
- **Suggestion**: Specify in §2.5 that `FileSinkDrainer`'s `queue.get()` uses a **timeout** (e.g. `queue.get(timeout=1.0)`) in a loop, so the drainer can periodically check a `_stop_event` (threading.Event) alongside the sentinel path. This gives two clean-exit paths: (a) sentinel from `shutdown()` — deterministic drain; (b) `_stop_event.set()` + timeout expiry — emergency exit if shutdown is not called. Alternatively, document that `ObservabilityFaculty.shutdown()` MUST be registered as both an `atexit` handler AND a SIGTERM handler at composition-root startup, to ensure the sentinel is always delivered.

---

## Observations (worth discussing)

### [O1] `make_gap_marker()` import into sinks is implicit
The design states in §2.5, §2.6, §2.7 that sinks "append a `gap_marker` record" when dropping — but doesn't explicitly state that sinks import and call `make_gap_marker()` from `schema.py`. This is the only reasonable wiring, but it should be made explicit in the module layout (§10) or in each sink's description to prevent an implementer from hand-rolling gap_marker construction per sink. Recommendation: add one sentence to §10 noting that sinks import `make_gap_marker` from `schema.py` for gap record construction.

### [O2] Processor-to-registry dependency injection not specified
§2.3 shows `self._registry.publish(...)` in both processors but does not state how `_registry` is set. The implied wiring is that `ObservabilityFaculty` constructs both processors with a `registry` constructor argument. This should be explicit — either in §2.1 or §2.3 — to prevent an implementer from using a module-level singleton or a global.

### [O3] Trace directory creation on first run not specified
`FileSink.__init__()` opens `~/.axiom/traces/{run_id}.jsonl`. If `~/.axiom/traces/` does not exist on first run, this raises `FileNotFoundError` (wrapped in `RuntimeError`). The design doesn't specify whether `ObservabilityFaculty` creates the directory on startup (e.g. `mkdir -p ~/.axiom/traces/`), or whether this is the operator's responsibility. Recommendation: state explicitly in §2.5 or §2.1 that `ObservabilityFaculty.new_run()` calls `Path(config.trace_dir).mkdir(parents=True, exist_ok=True)` before constructing `FileSink`.

### [O4] task.md intentionally deferred
`task.md` is intentionally empty at design phase per the explicit note in design.md header. Pass 9 traceability check on the Task axis was waived per that note. AC axis for all body file prescriptions is fully covered by requirement.md user stories and acceptance criteria. No action needed.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 0        | 3        | 4            |

**Verdict**: PASS WITH WARNINGS — no critical gaps blocking implementation. Three warnings should be addressed in design.md before `/e-spec:implement` is run. Observations are low-risk and may be deferred to implementation-time decisions.
