# Design Dry-Run Report #4

**Document**: `.claude/specs/004-m2-observability/design.md`
**Reviewed**: 2026-07-13

---

## Critical Gaps (must fix before implementation)

*None.*

---

## Warnings (should fix, may cause issues)

### [W1] WsBridgeSink.shutdown() async/sync caller-chain underspecified
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: `WsBridgeSink.shutdown()` uses `await _server_task` (an async operation), but its caller — `ObservabilityFaculty.shutdown()` — is a synchronous method registered as an `atexit` handler and a SIGTERM handler. By the time `atexit` fires, the asyncio event loop may already be stopped or in teardown. The design (§2.1, §2.7) does not specify how the synchronous `ObservabilityFaculty.shutdown()` drives the async `WsBridgeSink.shutdown()`. The three common resolution patterns (each with tradeoffs) are: (a) `asyncio.get_event_loop().run_until_complete(sink.shutdown())` if the loop is still running; (b) `loop.call_soon_threadsafe(...)` from a non-event-loop thread; (c) run the WS server on a separate thread with its own event loop, so shutdown is synchronous from the caller's perspective.
- **Risk**: At process exit, `WsBridgeSink.shutdown()` either silently no-ops (if `await` is called outside a running event loop, raising `RuntimeError: no running event loop`) or requires a running loop that may no longer exist. The WS server task may never be cleanly cancelled, leaving connected clients with dangling connections. This is an implementation trap — the implementer will discover it at integration time and have to make an ad hoc decision without design guidance.
- **Suggestion**: Add one sentence to §2.7 WsBridgeSink Shutdown specifying the bridging mechanism. Recommended: "Since `ObservabilityFaculty.shutdown()` is synchronous, `WsBridgeSink.shutdown()` MUST run the cancel/await in the WS sink's own event loop via `asyncio.run_coroutine_threadsafe(_do_shutdown(), self._loop).result(timeout=2.0)` — capturing `self._loop` at WS server startup." Alternatively, state that WsBridgeSink's asyncio server runs in its own dedicated thread (separate event loop), making `shutdown()` a synchronous cancel + `thread.join(timeout=2.0)`. Either choice resolves the ambiguity; the design just needs to pick one.

---

## Observations (worth discussing)

### [O1] FileSink.put() behavior after shutdown() is unspecified
Mild edge case: if `put()` is called on `FileSink` after `shutdown()` has enqueued the sentinel (e.g., a racing processor callback fires between `tracer_provider.shutdown()` and `sink.shutdown()`), records enter the queue but the drainer thread has already exited on the sentinel. They will never be drained. The design does not specify a guard (e.g., check `_shutdown_called` in `put()` and discard or log). In the intended startup/shutdown ordering — where `tracer_provider.shutdown()` flushes all pending callbacks before `sink.shutdown()` is called — this cannot happen. The shutdown sequence in §2.1 enforces this: OTel processors are flushed first (`tracer_provider.force_flush()` + `tracer_provider.shutdown()`), then sinks are shut down. This ordering eliminates the race. Worth a comment in the implementation, but not a design gap given the documented sequence.

### [O2] Age-based rotation concurrency not addressed
§2.5 specifies startup-time age-based rotation: `ObservabilityFaculty` deletes `.jsonl` files older than `config.file_max_age_days` on `new_run()`. No mention of what happens if two Axiom agent processes share the same `~/.axiom/traces/` directory and both run `new_run()` concurrently. In M2's single-agent-process scope this is not an issue. Worth noting as a M3+ constraint if multi-agent local scenarios arrive.

### [O3] All previous dryrun-3 warnings and observations confirmed resolved
- W1 (FileSinkDrainer conflicting shutdown mechanisms): §2.5 "FileSinkDrainer Loop Design" now describes pure poison-pill / sentinel-only exit with explicit rationale for removing `_stop_event` + timeout. Resolved.
- W2 (asyncio.shield() misuse): §2.7 "WsBridgeSink Shutdown" now shows correct `cancel() / await / except CancelledError` pattern with explicit "MUST NOT use asyncio.shield()" warning. Resolved.
- W3 (shutdown() not idempotent): §2.1 now specifies `threading.Event _shutdown_called` guard with set-before-proceed semantics. Resolved.
- O1 (startup ordering constraint): §2.2 now carries an explicit "Startup ordering constraint" paragraph. Resolved.
- O2 (SIGTERM handler chaining): §2.1 now shows the correct `_old_sigterm` capture and chain pattern. Resolved.
- O3 (shutdown() not on Sink Protocol): §2.4 now defines the `Sink` Protocol with both `put()` and `shutdown()` methods; §10 module layout updated for `base.py`. Resolved.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 0        | 1        | 3            |

**Verdict**: PASS WITH WARNINGS — one warning remains (WsBridgeSink async/sync caller-chain underspecified, W1 above). All previous iteration-3 findings resolved cleanly. The design is implementation-ready; the remaining warning is low-risk given M2's single-process scope but should be addressed before implementation begins to prevent an integration-time surprise.
