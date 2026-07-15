# Design Dry-Run Report #3

**Document**: `.claude/specs/004-m2-observability/design.md`
**Reviewed**: 2026-07-13

---

## Critical Gaps (must fix before implementation)

None.

---

## Warnings (should fix, may cause issues)

### [W1] FileSinkDrainer has two conflicting shutdown mechanisms described in two separate sub-sections

- **Pass**: Pass 4 (State Machine & Transitions)
- **What**: The design describes the drain-loop shutdown in two places with different mechanisms. §2.5 "FileSink Graceful Shutdown" describes a **poison-pill sentinel** pattern: `shutdown()` enqueues `_SENTINEL` onto the queue; the drainer loops until it sees the sentinel, then flushes and exits. §2.5 "FileSinkDrainer Loop Design" describes a `while not _stop_event.is_set()` loop with `queue.get(timeout=0.1)`. These are two different exit conditions: one exits on sentinel arrival; the other exits on `_stop_event`. Both are described as authoritative. An implementor reading both sections could produce a drainer that checks `_stop_event` and exits before the sentinel arrives, skipping the final `flush()` + `fsync()` in the sentinel branch — or a drainer that waits for the sentinel forever if `_stop_event` never triggers the loop exit.
- **Risk**: Inconsistent implementation. If `_stop_event` causes loop exit before the sentinel is dequeued, the final fsync may not fire. If the sentinel is dequeued first (the FIFO guarantee), `_stop_event` is redundant but harmless. But the current design leaves this undefined and the two sections don't reference each other.
- **Suggestion**: Reconcile into one canonical mechanism. The recommended resolution: use the **sentinel-only** pattern for FileSinkDrainer (the sentinel is the authoritative drain-complete signal; `_stop_event` is not needed for FileSink since the sentinel carries the flush guarantee). The `_stop_event` / `queue.get(timeout=0.1)` loop is appropriate for TuiSink where there is no sentinel, but is redundant and confusing for FileSink. Revise §2.5 to remove `_stop_event` from FileSinkDrainer and clarify that the sentinel is the sole exit signal. Alternatively, if both are retained, specify explicitly that `_stop_event` is set only *after* the sentinel is enqueued, and the loop exits on sentinel arrival before `_stop_event` can take effect.

---

### [W2] `WsBridgeSink.shutdown()` uses `asyncio.shield()` incorrectly

- **Pass**: Pass 5 (Failure Path Analysis)
- **What**: §2.7 "WsBridgeSink Shutdown" specifies the pattern `_server_task.cancel(); await asyncio.shield(_server_task)`. `asyncio.shield()` is used to *protect* a coroutine from external cancellation — it does not help await a task that has already been cancelled. The correct idiom for awaiting a cancelled task and suppressing `CancelledError` is `_server_task.cancel(); try: await _server_task; except asyncio.CancelledError: pass`.
- **Risk**: `asyncio.shield(_server_task)` after cancel will itself raise `CancelledError` immediately (since the outer task's cancel propagates through shield), potentially leaving the server task un-awaited and producing a "Task was destroyed but it is pending!" warning, or silently not completing cleanup of active client connections.
- **Suggestion**: Replace the shutdown pattern in §2.7 with: `_server_task.cancel(); try: await _server_task; except asyncio.CancelledError: pass`. This is the canonical pattern for cancelling and cleanly awaiting an asyncio task.

---

### [W3] `ObservabilityFaculty.shutdown()` is not specified as idempotent, but may be called twice

- **Pass**: Pass 6 (Concurrency & Ordering)
- **What**: §2.1 registers `self.shutdown` as both an `atexit` handler and a `SIGTERM` handler. On an orderly exit that also receives SIGTERM (e.g. Docker/Kubernetes sends SIGTERM and the process also exits naturally), both handlers may fire, calling `shutdown()` twice. The design does not specify that `shutdown()` is idempotent. Double-call consequences: `tracer_provider.shutdown()` called twice (OTel SDK behavior on double-shutdown is unspecified), `FileSink.shutdown()` enqueues a second sentinel (drainer has already exited — second `queue.put()` blocks indefinitely on a non-blocking queue, or the already-joined thread receives it). `TuiSink.shutdown()` re-sets `_stop_event` (harmless) and re-joins the already-exited thread (harmless). `WsBridgeSink.shutdown()` calls `cancel()` on an already-done task (harmless).
- **Risk**: The FileSink double-shutdown case is the most dangerous: if the drainer thread has already exited (processed the first sentinel), a second `queue.put(_SENTINEL)` on a full queue could block. The `shutdown()` call from the second handler could hang.
- **Suggestion**: Specify that `ObservabilityFaculty.shutdown()` is **idempotent**: use a `threading.Event` (`_shutdown_called`) and guard: `if self._shutdown_called.is_set(): return; self._shutdown_called.set()`. This eliminates all double-call races.

---

## Observations (worth discussing)

### [O1] `record_phase()` acquires the global OTel TracerProvider via get_tracer() — implicit dependency on startup ordering

The design (§2.2) shows `record_phase()` calling `tracer.start_as_current_span(...)`. The tracer is acquired via `opentelemetry.trace.get_tracer("axiom.loop")`, which retrieves the globally-set TracerProvider. This means `ObservabilityFaculty.__init__()` must run (setting the global TracerProvider) before `record_phase()` is first called. The design states this in §2.1 ("set as the global OTel provider") but does not make the startup ordering constraint explicit as a hard requirement. Composition root (`agent.py`) must construct `ObservabilityFaculty` before constructing `PraoLoop`. This is worth an explicit note in §2.2 or §14 (IQ-3).

---

### [O2] SIGTERM handler replaces any previously-installed SIGTERM handler — no chaining

§2.1 installs `signal.signal(signal.SIGTERM, lambda sig, frame: self.shutdown())`. This replaces any previously-installed SIGTERM handler (e.g., from the Python runtime, or from libraries that install their own SIGTERM handling). The design does not mention handler chaining. For an agentic system that may eventually host multiple components, this is worth a note: "The SIGTERM handler does not chain; if another library installs a SIGTERM handler before `ObservabilityFaculty.__init__`, it will be silently replaced." This is an architectural note for IQ-3 or a future lifecycle-management spec.

---

### [O3] Sink Protocol (`base.py`) does not declare `shutdown()` — `ObservabilityFaculty` calls it duck-type

§2.1 states `ObservabilityFaculty.shutdown()` calls `sink.shutdown()` on each registered sink in reverse registration order. But `sinks/base.py` defines the `Sink` Protocol as `put(record: dict) -> None` only. `shutdown()` is a method on the concrete sink classes (`FileSink`, `TuiSink`, `WsBridgeSink`) but not declared on the Protocol. This means `ObservabilityFaculty` iterates the `SinkRegistry` (which holds `Sink`-typed objects) and calls `.shutdown()` via duck-typing — a type-checker would flag this. Consider adding `shutdown() -> None` to the `Sink` Protocol (with a default no-op), so the call is type-safe and any future third-party sink that forgets to implement `shutdown()` gets a clear contract violation rather than an `AttributeError` at runtime.

---

### [O4] task.md is intentionally empty at design phase — no action needed

Per the design document's explicit note (line 9): "task.md is intentionally empty at design phase. It is populated by `/e-spec:implement` when implementation begins." Pass 9 (Design-to-Task-to-AC Traceability) skips the task axis check accordingly. No traceability gap exists here — this is the established convention.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 0        | 3        | 4            |

**Verdict**: PASS WITH WARNINGS

The three warnings are all fixable with small targeted edits to design.md:
- **W1**: reconcile the two FileSinkDrainer shutdown descriptions into one canonical mechanism
- **W2**: fix the `asyncio.shield()` misuse in WsBridgeSink shutdown (one line change)
- **W3**: add idempotency specification to `ObservabilityFaculty.shutdown()`

No critical gaps remain. All six findings from dryrun-design-2 (W1–W3, O1–O3) have been resolved. The design is implementation-ready once the three warnings above are addressed.
