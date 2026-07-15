# M2 · Observability — Design

**Spec:** `004-m2-observability`
**Milestone:** M2 — "Watch it think"
**Author:** Velasari — 2026-07-13
**Status:** DRAFT
**Inputs:** Research Rev-3 (`005-m2-observability-architecture-2026-07-13.md`), requirement.md, spike-result.md (Verdict B), architecture.md

> **Note — task.md:** `task.md` is intentionally empty at design phase. It is populated by `/e-spec:implement` when implementation begins. The dryrun reviewer should not flag an empty `task.md` as a gap; its absence here is by convention, not an oversight.

---

## 1. Overview

M2 replaces the M1 timing stub (`observability/timing.py`) with a structured, provider-general, multi-sink tracing system. The design has four axes:

1. **Generalize** — observation is defined at the Agent-port level; works for KIND A and KIND B.
2. **Standardize** — one normalized JSONL schema; depth-asymmetry explicit via `span_source` and the extensions bag.
3. **Emit** — file, TUI, WebSocket bridge; single-producer / multi-consumer fan-out.
4. **Async** — non-blocking; no sink taxes the producer.

OTel SDK is adopted in-process for span creation, context propagation, and `gen_ai.*` attribute modeling. OTel is confined to the Observability faculty; the core loop imports nothing from `opentelemetry`. The three open design-phase gates (DG-10.A: asyncio context propagation; DG-10.B: span lifecycle for live sinks; dep pinning) are **resolved by the spike** (Verdict B) and encoded as invariants in §5.

---

## 2. Component Map

```
╔══════════════════════════════════════════════════════════════════╗
║  AGENT LOOP (PraoLoop)                single producer            ║
║  perceive → reason → act → observe                               ║
║                                                                  ║
║  loop mints four PRAO spans via OTel context                     ║
║  adapters add children (KIND A: full-depth; KIND B: Act-only)   ║
╚══════════════════════╤═══════════════════════════════════════════╝
                       │  Observability RECORD call-point
                       │  (fires at every phase boundary)
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY FACULTY  (src/axiom/observability/)               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  OTel Tracer (TracerProvider + in-process setup)         │   │
│  │  - GlobalTracerProvider configured once at startup       │   │
│  │  - No OTel collector; no OTel backend                    │   │
│  │  - SpanProcessor pipeline registered on TracerProvider   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                            │  spans flow through processors      │
│  ┌─────────────────────────▼──────────────────────────────────┐  │
│  │  SpanProcessor Pipeline (two processors, SimpleSpan-style) │  │
│  │                                                            │  │
│  │  [1] LiveNotificationProcessor                             │  │
│  │      on_start → serialize span_start record → publish()   │  │
│  │                                                            │  │
│  │  [2] JsonlExportProcessor                                  │  │
│  │      on_end → serialize span_end record → publish()       │  │
│  └─────────────────────────┬──────────────────────────────────┘  │
│                             │  publish(subject="trace", record)   │
│  ┌──────────────────────────▼──────────────────────────────────┐  │
│  │  SinkRegistry (in-process fan-out)                          │  │
│  │  publish(subject, record) → broadcast to all registered     │  │
│  │  sinks for that subject; M2 uses "trace" subject only       │  │
│  └──────┬──────────────────────┬───────────────────────────────┘  │
│         │                      │                │                  │
│   ┌─────▼──────┐   ┌───────────▼───┐   ┌───────▼──────────┐     │
│   │ FileSink   │   │  TuiSink      │   │  WsBridgeSink    │     │
│   │ own thread │   │  own task     │   │  own task        │     │
│   │ deep queue │   │  drop-oldest  │   │  drop-oldest     │     │
│   │ periodic   │   │  gap-marker   │   │  gap-marker      │     │
│   │ fsync      │   │               │   │  localhost+token │     │
│   └────────────┘   └───────────────┘   └──────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 OTel Tracer Setup

**File:** `src/axiom/observability/faculty.py`

- `ObservabilityFaculty` class owns tracer initialization and teardown.
- On startup: creates a `TracerProvider`; registers the `LiveNotificationProcessor` and `JsonlExportProcessor` via `add_span_processor()`.
- The `LiveNotificationProcessor` runs first in the pipeline (catches `on_start`); `JsonlExportProcessor` runs second (catches `on_end`).
- Both processors are `SimpleSpanProcessor`-equivalent (synchronous callbacks, no batching delay) — correct for the live-sink latency requirement (AC-10.7).
- The `TracerProvider` is set as the global OTel provider; the loop's Observability RECORD call-point acquires a tracer via `opentelemetry.trace.get_tracer("axiom.loop")`.
- **OTel dep pinned:** `opentelemetry-sdk==1.43.0`, `opentelemetry-api==1.43.0`, `opentelemetry-semantic-conventions==0.64b0` (installed as dev deps in `pyproject.toml`; spike confirmed these versions).
- `ObservabilityFaculty.shutdown()` called at process exit (flushes processors). Shutdown sequence: (1) call `tracer_provider.force_flush()` + `tracer_provider.shutdown()` to flush and close OTel processors; (2) call `sink.shutdown()` on each registered sink in **reverse registration order** (WsBridgeSink → TuiSink → FileSink). Reverse order ensures live sinks stop accepting new records before the file sink flushes its queue, preventing any live-sink write from arriving after the file sink is closed.
- `ObservabilityFaculty.__init__` registers `self.shutdown` as an `atexit` handler (`atexit.register(self.shutdown)`) and as a `SIGTERM` handler (see SIGTERM note below), guaranteeing shutdown() runs on all exit paths.
- **Idempotency guard (W3):** `ObservabilityFaculty` holds a `threading.Event _shutdown_called` initialized to unset. `shutdown()` begins by checking `_shutdown_called.is_set()`; if already set, it returns immediately. Otherwise it sets `_shutdown_called` before proceeding. This prevents double-sentinel injection into `FileSink`'s queue when both `atexit` and `SIGTERM` fire on the same exit path.
- **SIGTERM handler with previous-handler chaining (O2):** The SIGTERM handler stores and chains the previous handler:
  ```python
  _old_sigterm = signal.signal(signal.SIGTERM, lambda sig, frame: self.shutdown())
  # Correct form that chains:
  def _sigterm_handler(sig, frame):
      self.shutdown()
      if callable(_old_sigterm):
          _old_sigterm(sig, frame)
  _old_sigterm = signal.signal(signal.SIGTERM, _sigterm_handler)
  ```
  This ensures that any previously installed SIGTERM handler (e.g. from a test framework, container runtime, or parent process) is called after `ObservabilityFaculty.shutdown()` completes.
- `ObservabilityFaculty.__init__` calls `trace_dir.mkdir(parents=True, exist_ok=True)` before constructing `FileSink`, ensuring the trace directory exists on first run (O3 resolved).

### 2.2 Observability RECORD Call-Point Wiring

**File:** `src/axiom/observability/record.py`

The RECORD call-point fires at every `perceive → reason → act → observe` phase boundary. It is the **sole injection point** for trace emission — it does not live in loop control flow (`loop.py`) or in adapter code.

**Startup ordering constraint (O1):** `ObservabilityFaculty` MUST be fully initialized — all sinks registered and the `TracerProvider` configured as the global OTel provider — before any call to `record_phase()`. Calling `record_phase()` before `ObservabilityFaculty.__init__()` completes will use the no-op default OTel tracer and emit no spans; no error is raised, but all trace data is silently lost. The composition root (`agent.py`) is responsible for enforcing this ordering: `ObservabilityFaculty` is constructed and wired completely before `PraoLoop` is started.

**Wiring pattern (context-manager API):**

```python
# Pseudocode — the actual API is defined in record.py
@contextmanager
def record_phase(phase: PraoPhase, run_id: str, provider_kind: ProviderKind):
    with tracer.start_as_current_span(
        name=f"axiom.loop.{phase.value}",
        attributes={
            "axiom.phase": phase.value,
            "axiom.run_id": run_id,
            "axiom.provider_kind": provider_kind.value,
            "axiom.span_source": "core-minted",
        }
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            raise
        else:
            span.set_status(StatusCode.OK)
```

`PraoLoop.run()` wraps each phase call with `record_phase(...)`. The four phase context managers **nest** to form the span tree: the run-root span wraps the whole turn; each PRAO phase span is a child of the run-root.

**Loop integration (conceptual — actual wiring at implementation time):**

```
run_root_span (axiom.loop.run)
  ├── axiom.loop.perceive
  ├── axiom.loop.reason
  ├── axiom.loop.act
  │   └── [KIND A: nested child spans; KIND B: streamed event children]
  └── axiom.loop.observe
```

The `record_phase` API in `record.py` imports only `opentelemetry` — never `loop.py` or adapters. `loop.py` imports `record.py` from the observability faculty (the only OTel-touching import in the loop package, and only the call-point module, not the sinks or registry).

**Error invariant (AC-01.4):** A span is emitted even on error — the `except` branch sets `StatusCode.ERROR` and re-raises, so `on_end` fires with the error status captured.

### 2.3 SpanProcessor Pipeline

**File:** `src/axiom/observability/processors.py`

Two processors registered on the `TracerProvider`:

#### LiveNotificationProcessor

```python
class LiveNotificationProcessor(SpanProcessor):
    def on_start(self, span: ReadableSpan, parent_context: Context) -> None:
        record = serialize_span_start(span)
        try:
            self._registry.publish("trace", record)
        except Exception as exc:
            logging.getLogger(__name__).error(
                "LiveNotificationProcessor.on_start error: %s", exc
            )

    def on_end(self, span: ReadableSpan) -> None:
        pass  # handled by JsonlExportProcessor
```

Fires on span open. Serializes a `span_start` record (§3.3) and hands it to the `SinkRegistry`. Sink errors go to stdlib logging only (AC-11.1–11.4).

#### JsonlExportProcessor

```python
class JsonlExportProcessor(SpanProcessor):
    def on_start(self, span: ReadableSpan, parent_context: Context) -> None:
        pass  # handled by LiveNotificationProcessor

    def on_end(self, span: ReadableSpan) -> None:
        record = serialize_span_end(span)
        try:
            self._registry.publish("trace", record)
        except Exception as exc:
            logging.getLogger(__name__).error(
                "JsonlExportProcessor.on_end error: %s", exc
            )
```

Fires on span close. Serializes a complete `span_end` record (§3.2) including timing, attributes, status, and `gen_ai.*` fields.

**Serialization errors** (JSON serialization failure, attribute type mismatch): caught within the processor, logged to stdlib — never published to the bus (AC-11.4).

### 2.4 In-Process Fan-Out (SinkRegistry)

**File:** `src/axiom/observability/registry.py`

```python
class SinkRegistry:
    def register(self, subject: str, sink: Sink) -> None: ...
    def publish(self, subject: str, record: dict) -> None: ...
```

#### Sink Protocol (O3 resolved)

The `Sink` Protocol (defined in `sinks/base.py`) declares the full interface that all sinks must satisfy:

```python
from typing import Protocol

class Sink(Protocol):
    def put(self, record: dict) -> None: ...
    def shutdown(self) -> None: ...
```

**Both methods are required.** `shutdown() -> None` is part of the protocol — not an optional convenience. Any class registered as a sink that does not implement `shutdown()` will fail the duck-typing contract and cause `ObservabilityFaculty.shutdown()` to raise `AttributeError` when iterating sinks in reverse-registration order. Implementers MUST define both methods.

- `publish(subject, record)` iterates all sinks registered for `subject` and calls `sink.put(record)` on each.
- `sink.put(record)` is a non-blocking enqueue; returns immediately (AC-05.1).
- All three sinks registered against `"trace"` in M2 (file, TUI, WS).
- Subject taxonomy deferred to M7 (§7).
- If one sink's `put()` raises: log to stdlib, continue to next sink — no cross-contamination (AC-11.3).

#### Processor-to-Registry Injection (O2 resolved)

`LiveNotificationProcessor` and `JsonlExportProcessor` each receive their `SinkRegistry` instance via **constructor injection**:

```python
registry = SinkRegistry()
live_proc = LiveNotificationProcessor(registry=registry)
jsonl_proc = JsonlExportProcessor(registry=registry)
```

Both processors store `self._registry = registry` and call `self._registry.publish(...)` in their callbacks. The `ObservabilityFaculty` composition root constructs the `SinkRegistry` first, then passes it into both processors. There is no global registry singleton and no service-locator lookup.

#### Sink Registration Ordering (O2 resolved)

Sinks MUST be registered in the following order in `ObservabilityFaculty` (composition root):

1. `FileSink` — registered first. Most durable; must be guaranteed to receive every record before optional live sinks.
2. `ConsoleSink` (if present in a future milestone) — registered second.
3. `TuiSink` — registered third (only if `--no-tui` is not set and running interactively).
4. `WsBridgeSink` — registered last (only if WS port is configured).

**Rationale:** `SinkRegistry.publish()` iterates sinks in registration order. If an earlier sink's `put()` raises (caught and logged), later sinks still receive the record. Registering `FileSink` first ensures the file sink is never starved by a live-sink error. The order is also the order of durability priority: durable-first, lossy-last.

In M2, only `FileSink`, `TuiSink`, and `WsBridgeSink` exist. The ordering is: `FileSink` → `TuiSink` → `WsBridgeSink`.

### 2.5 File Sink

**File:** `src/axiom/observability/sinks/file_sink.py`

- Owns a `queue.Queue(maxsize=D)` where `D=10_000` (default, configurable).
- Drains on a **dedicated daemon thread** (`FileSinkDrainer`) — never the asyncio event loop or producer thread.
- `put(record)` serializes `record` to a JSONL line and attempts `queue.put_nowait(line)`. On `queue.Full`: drops oldest record (by `queue.get_nowait()` + discard), appends a `gap_marker` record (§3.4).
- `FileSinkDrainer` loop: `line = queue.get()` → `file.write(line + "\n")` → every `FSYNC_INTERVAL_RECORDS=100` writes OR `FSYNC_INTERVAL_SECS=1.0` seconds (whichever comes first): `file.flush()` + `os.fsync(file.fileno())`.
- File opened with `O_WRONLY | O_CREAT | O_APPEND`; permissions set to `0o600` immediately after open (AC-06.5).
- Storage path: `~/.axiom/traces/{run_id}.jsonl` (default; configurable via `ObservabilityConfig`).
- Rotation: max 100 MB per file, max 7 days age, max 10 files retained (defaults; configurable).
- IOError → `logging.getLogger(__name__).error(...)` — never the bus (AC-06.7).

#### FileSink Construction and run_id Injection (O1 resolved)

`FileSink.__init__(run_id: str, config: ObservabilityConfig)` receives `run_id` as an explicit constructor parameter. `run_id` is used to derive the output file path (`~/.axiom/traces/{run_id}.jsonl`). The `ObservabilityFaculty` generates the `run_id` (see IQ-4, §14) and passes it into `FileSink` at construction time — `FileSink` does not generate its own `run_id`.

#### FileSink File-Open Failure Handling (O3 resolved)

The file is opened (and permissions set to `0o600`) in `FileSink.__init__()` **before** the sink is registered. If the file cannot be opened (e.g., path does not exist, permissions denied, disk full at open), `FileSink.__init__()` raises `RuntimeError` immediately. This causes the composition root (`agent.py`) to fail fast at startup — no events are silently lost because the sink was registered without a working file handle. There is no retry or fallback; the agent must not start in a state where file durability is promised but unavailable.

#### FileSink Graceful Shutdown (W1 resolved)

`FileSinkDrainer` MUST be started as a **non-daemon thread** (i.e., `daemon=False`). This ensures that when the main thread exits, Python's shutdown sequence waits for `FileSinkDrainer` to finish before the interpreter terminates.

**Shutdown sequence (poison-pill pattern):**

1. `FileSink.shutdown()` is called by `ObservabilityFaculty.shutdown()` at process exit.
2. `shutdown()` enqueues a sentinel value (`_SENTINEL = object()`) onto the queue via `queue.put(_SENTINEL)`.
3. The drainer loop, upon receiving `_SENTINEL`, performs a final `file.flush()` + `os.fsync()` and exits cleanly.
4. `shutdown()` then calls `drainer_thread.join(timeout=5.0)` to wait for the drain to complete. If the join times out, an error is logged to stdlib and the thread is abandoned (non-blocking guarantee to the caller is preserved).

This design guarantees that all records enqueued before `shutdown()` is called are flushed to disk — the sentinel arrives after all preceding records in FIFO order.

**`daemon=False` rationale:** A daemon thread is killed at interpreter exit without draining the queue. Making the thread non-daemon, combined with the poison-pill flush, gives deterministic flush-on-exit without relying on atexit ordering. `FileSink.shutdown()` MUST be called explicitly (by `ObservabilityFaculty.shutdown()`) before the process exits to drive the sentinel path; the non-daemon thread is a fallback guard, not the primary drain trigger.

#### FileSinkDrainer Loop Design (W1 resolved)

`FileSinkDrainer` runs a blocking-get loop: each iteration calls `queue.get()` (no timeout) and blocks until a record or the sentinel arrives. There is no `_stop_event`, no polling timeout, and no periodic wakeup. The loop exits **only** when it dequeues the sentinel value (`_SENTINEL`). This is a pure poison-pill design — the sentinel is the sole exit mechanism.

**Why no timeout/stop-event:** A `queue.get(timeout=0.1)` + `_stop_event` approach creates two competing shutdown mechanisms and risks missing records that arrive between the timeout check and the stop-event check. The sentinel arrives in FIFO order after all preceding records, guaranteeing nothing is skipped.

**Stream re-dereference on every iteration:** The drainer MUST dereference `self._handler.stream` fresh on each write iteration — it MUST NOT cache the stream reference in a local variable across iterations. This is because `RotatingFileHandler.doRollover()` replaces `handler.stream` with a new file object; a cached reference would write to the old (now-closed) file after rotation.

**doRollover() failure handling:** After each write batch, the drainer calls `handler.shouldRollover(record=None)` + `handler.doRollover()` when size threshold is exceeded. If `doRollover()` raises `IOError` or `OSError`, the drainer logs the exception to `stderr` via `logging.getLogger(__name__).error(...)` and **continues** — it does not abort the drain loop or re-raise. This ensures that a rotation failure (e.g. disk full during rename) degrades to "writes continue to the pre-rotation file" rather than a silent drainer crash.

**Shutdown guarantee:** `ObservabilityFaculty.__init__` registers `self.shutdown` as:
1. An `atexit` handler: `atexit.register(self.shutdown)` — fires on normal interpreter exit.
2. A `SIGTERM` handler (with previous-handler chaining — see §2.1 SIGTERM note) — fires on OS-level process termination.

This guarantees `shutdown()` is called on all exit paths (normal exit, SIGTERM), ensuring the sentinel is enqueued and the drain thread flushes before the process terminates. The non-daemon thread is a secondary guard; `atexit`/`SIGTERM` is the primary shutdown trigger.

**Post-shutdown `put()` — no guard by design:** `FileSink.put()` does NOT check a `_shutdown_called` flag before enqueuing. This is intentional: the shutdown sequence in §2.1 — `tracer_provider.force_flush()` + `tracer_provider.shutdown()` (which flushes all processor callbacks) BEFORE any `sink.shutdown()` — makes it structurally impossible for a processor to call `put()` after the sentinel is enqueued under correct composition. Adding a silent discard guard in `put()` would mask incorrect composition (a caller bypassing the ordering invariant) rather than surfacing the bug. The sequence invariant IS the guard; `put()` after `shutdown()` is an API contract violation, not a handled case.

#### File Rotation Mechanism

File rotation is implemented using Python's `logging.handlers.RotatingFileHandler` **as the file-management backend only** — the handler is used for its rotation logic (size-based cutover, backup count enforcement), not for its logging API. `FileSinkDrainer` writes raw JSONL lines via the handler's underlying stream (`handler.stream`). The handler is configured with:

```python
import logging.handlers

handler = logging.handlers.RotatingFileHandler(
    filename=trace_path,          # ~/.axiom/traces/{run_id}.jsonl
    mode="a",
    maxBytes=config.file_max_size_mb * 1024 * 1024,   # default: 100 MB
    backupCount=config.file_max_count,                  # default: 10
    encoding="utf-8",
    delay=False,
)
```

On each write: `handler.stream.write(line + "\n")`. When the file exceeds `maxBytes`, `RotatingFileHandler.doRollover()` is called explicitly (or triggered automatically on the next `emit()` — but since we bypass `emit()`, we call `handler.shouldRollover()` + `handler.doRollover()` manually after each write batch).

**Age-based rotation** (max 7 days per file) is enforced at startup: `ObservabilityFaculty` scans `~/.axiom/traces/` on `new_run()` and deletes any `.jsonl` files older than `config.file_max_age_days`. This is a startup-time purge, not a continuous background task — simple and safe.

**Single-process constraint (M2 scope):** Age-based purge (and file sink writes generally) assume exactly one Axiom agent process accesses `~/.axiom/traces/` at a time. Concurrent `new_run()` calls from multiple processes sharing the same trace directory are explicitly NOT supported in M2 — file locking, TOCTOU races on deletion, and duplicate `run_id` collisions are all unaddressed. Multi-process / multi-agent local scenarios are an explicit M3+ constraint; M2 callers MUST NOT share the trace directory across processes.

**Gap marker import path (O1 resolved):** Sinks that emit gap markers import the factory function as:
`from axiom.observability.schema import make_gap_marker`
This is the explicit import path for all three sinks (`FileSink`, `TuiSink`, `WsBridgeSink`). The `make_gap_marker` function lives in `schema.py` alongside `serialize_span_start` and `serialize_span_end`.

**File permissions after rotation:** After `doRollover()`, the new file handle is `chmod`'d to `0o600` immediately (`os.chmod(handler.baseFilename, 0o600)`) — the same post-open permission enforcement as at construction.

### 2.6 TUI Sink

**File:** `src/axiom/observability/sinks/tui_sink.py`

- Owns a `collections.deque(maxlen=TUI_BUFFER=200)` (configurable) guarded by a `threading.Lock` (`_deque_lock`).
- `put(record)` acquires `_deque_lock` before inspecting or mutating the deque. Under the lock: if `len(deque) == maxlen`, `popleft()` (drop-oldest), create and `append()` a `gap_marker` entry, then `append(record)`. The lock is released immediately after the append — no I/O under the lock.
- The drain task also acquires `_deque_lock` before `popleft()` to drain. This ensures the check-and-mutate sequence in `put()` is atomic with respect to the drain task.
- **Rationale:** `collections.deque` is thread-safe for individual operations (CPython GIL), but the compound check-then-mutate sequence (`if full → popleft + gap + append`) is NOT atomic without a lock. The lock makes the drop-and-gap-marker sequence a single atomic unit, preventing a race where two threads both see `full=True` and both inject a gap_marker.
- Drains on its own asyncio task (or daemon thread if the TUI library requires a dedicated thread).
- Renders `span_start` records as "phase in progress" indicators; `span_end` records as completed phase summaries; `gap_marker` records as a visible `[N records dropped]` line.
- Optional at runtime (AC-07.5): `TuiSink` is not registered if `--no-tui` flag is passed or if running non-interactively.
- Render errors → `logging.getLogger(__name__).error(...)` (AC-07.4).

#### TuiSink Shutdown (W2 resolved)

`TuiSink.shutdown()` sets an internal `_stop_event` (threading.Event) and joins the drain thread (or awaits the asyncio drain task) with a **2-second timeout**. If the join/await does not complete within the timeout, the shutdown returns without blocking the caller further — the drain is best-effort for the TUI. Render errors during shutdown are logged to stdlib and suppressed.

### 2.7 WebSocket Bridge Sink

**File:** `src/axiom/observability/sinks/ws_sink.py`

- Binds **`127.0.0.1` only** (AC-08.1); MUST NOT bind `0.0.0.0`.
- Requires token authentication on every client connection (AC-08.2); token is generated at startup (UUID4) or supplied via `ObservabilityConfig.ws_token`; unauthenticated connections receive HTTP 401 and are closed before any trace data is sent.
- Owns a `collections.deque(maxlen=WS_BUFFER=500)` per connected client, each guarded by its own `threading.Lock` (`_client_lock[client_id]`).
- `put(record)`: for each connected client, acquires the client's lock; if deque is full, `popleft()` (drop-oldest) + `append(gap_marker)`, then `append(record)`. Lock released immediately after append — no I/O under the lock. Same compound-atomicity rationale as TUI sink above.
- The drain asyncio task acquires the per-client lock before `popleft()`.
- Drains on an asyncio task; serialized JSONL lines are sent as WebSocket text messages (AC-08.3).
- Client disconnect, send error, handshake failure → `logging.getLogger(__name__).error(...)` — never the bus (AC-08.5).
- Optional at runtime (AC-08.6): not started if no WS port configured.
- No HTTP server, no web dashboard — raw authenticated WS stream only (AC-08.7).

#### WsBridgeSink — Dedicated Event Loop Thread (W1 + W2 resolved)

`WsBridgeSink` runs its asyncio WebSocket server on a **dedicated background thread with its own event loop** — it does NOT share the main asyncio event loop or any application event loop. This isolation is the load-bearing architectural decision that makes synchronous shutdown possible.

**Why a dedicated loop thread is mandatory:** `ObservabilityFaculty.shutdown()` is a **synchronous** method registered as an `atexit` handler and a SIGTERM handler. At process exit the main event loop (if any) may already be stopped or in teardown. `WsBridgeSink` must be shut down without depending on any external event loop being alive.

**Startup:** `WsBridgeSink.__init__()` creates a new event loop (`asyncio.new_event_loop()`), stores it as `self._loop`, and starts a non-daemon background thread (`self._ws_thread`) whose sole job is `self._loop.run_forever()`. The asyncio WebSocket server coroutine is scheduled onto `self._loop` via `asyncio.run_coroutine_threadsafe(self._start_server(), self._loop)`. `self._loop` remains running and accessible until `shutdown()` explicitly stops it.

**Shutdown (synchronous bridging — the concrete mechanism):**

`WsBridgeSink.shutdown()` is a **SYNC method**. It submits the async cancellation coroutine to the WS sink's own loop via `asyncio.run_coroutine_threadsafe`, then blocks on the result:

```python
def shutdown(self) -> None:
    if self._loop is None or self._loop.is_closed():
        return
    try:
        future = asyncio.run_coroutine_threadsafe(self._do_shutdown(), self._loop)
        future.result(timeout=2.0)   # blocks calling thread; drives async shutdown
    except TimeoutError:
        logging.getLogger(__name__).error(
            "WsBridgeSink: shutdown timed out after 2s"
        )
    except Exception as exc:
        logging.getLogger(__name__).error(
            "WsBridgeSink: shutdown error: %s", exc
        )
    finally:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._ws_thread.join(timeout=2.0)

async def _do_shutdown(self) -> None:
    """Runs on the WsBridgeSink's own event loop."""
    if self._server_task is not None:
        self._server_task.cancel()
        try:
            await self._server_task
        except asyncio.CancelledError:
            pass  # expected; all client connections are now closed
```

**Why this is correct and unambiguous:**
- `self._loop` is always the WsBridgeSink's own event loop — started in `__init__()`, running on `self._ws_thread`, never closed until `shutdown()` explicitly stops it.
- `asyncio.run_coroutine_threadsafe` is explicitly designed for the sync-caller-to-async-event-loop bridge pattern. It returns a `concurrent.futures.Future`; `.result(timeout=2.0)` blocks the sync caller until the coroutine completes or times out.
- No `RuntimeError: no running event loop` can occur: `self._loop` is always running (on its dedicated thread) at the point `shutdown()` is called.
- The sync caller (`ObservabilityFaculty.shutdown()`) does NOT need a running asyncio event loop of its own.
- After `future.result()` returns, `self._loop.stop()` is scheduled (via `call_soon_threadsafe` to respect thread safety) and `self._ws_thread` is joined with a 2-second timeout.
- `asyncio.shield()` MUST NOT be used inside `_do_shutdown()` — it prevents cancellation from reaching the server task, the opposite of the intended behavior.

---

## 3. Trace Record Schema

All records are JSON objects (one per JSONL line, no embedded newlines, terminated by `\n`). Three record types exist, distinguished by the mandatory `record_type` field.

### 3.1 Record Types

| `record_type` | Emitted by | When |
|--------------|-----------|------|
| `span_start` | `LiveNotificationProcessor.on_start` | Immediately when a span opens |
| `span_end` | `JsonlExportProcessor.on_end` | When a span closes (fully populated) |
| `gap_marker` | Consumer buffer logic (per-sink) | When a record is dropped from the buffer |

### 3.2 `span_end` Record — Full Span

All fields present on every `span_end` record. Fields that are semantically unavailable for a given provider carry `null`, not a missing key (AC-03.3).

```
Field                           Type              Notes
────────────────────────────────────────────────────────────────────────
record_type                     str               Always "span_end"
schema_version                  str               "1.0" — local version (§11)
otel_schema_url                 str               OTel GenAI conventions URL in effect

run_id                          str               UUID4 — unique per PraoLoop.run() call
trace_id                        str               OTel trace ID (hex, 32 chars)
span_id                         str               OTel span ID (hex, 16 chars)
parent_span_id                  str | null        OTel parent span ID; null ONLY for run-root

phase                           str               "perceive"|"reason"|"act"|"observe"|"run"
span_name                       str               OTel span name (e.g. "axiom.loop.act")
span_source                     str               "core-minted" | "provider-streamed"
provider_kind                   str               "KIND_A" | "KIND_B"

start_time_unix_nano            int               Span open timestamp (ns since epoch)
end_time_unix_nano              int               Span close timestamp (ns since epoch)
duration_ms                     float             Derived: (end − start) / 1_000_000

status                          str               "OK" | "ERROR"
error_message                   str | null        Present when status == "ERROR"; null otherwise

# gen_ai.* common-core attributes (always present; null when not available for provider)
gen_ai_system                   str | null        Provider system name ("anthropic", "openai")
gen_ai_request_model            str | null        Requested model name
gen_ai_response_model           str | null        Actual model used (may differ from request)
gen_ai_operation_name           str               Phase name or operation ("act", "reason", ...)
gen_ai_usage_input_tokens       int | null        Prompt tokens consumed
gen_ai_usage_output_tokens      int | null        Completion tokens generated
cost_usd                        float | null      Estimated cost in USD; null if not computable

# Extensions bag — provider/adapter-specific; freeform; never absent (empty {} if nothing)
extensions                      object            See §3.5 for examples
```

### 3.3 `span_start` Record — Live Notification

Emitted on `on_start` for live TUI/WS "in progress" visibility. Contains span header fields only — `gen_ai.*` attributes and timing end are not available at open time.

```
Field                           Type              Notes
────────────────────────────────────────────────────────────────────────
record_type                     str               Always "span_start"
schema_version                  str               "1.0"
otel_schema_url                 str               OTel GenAI conventions URL

run_id                          str               UUID4
trace_id                        str               OTel trace ID (hex)
span_id                         str               OTel span ID (hex)
parent_span_id                  str | null        OTel parent span ID; null for run-root

phase                           str               "perceive"|"reason"|"act"|"observe"|"run"
span_name                       str               OTel span name
span_source                     str               "core-minted" | "provider-streamed"
provider_kind                   str               "KIND_A" | "KIND_B"

start_time_unix_nano            int               Span open timestamp (ns since epoch)
```

`span_start` records carry no `gen_ai.*` attributes (not available at open time). Consumers correlate `span_start` / `span_end` by `span_id`.

### 3.4 `gap_marker` Record — Drop Signal

Emitted by each consumer's buffer logic when a record is dropped. First-class JSONL record; must carry `schema_version` for parser compatibility (AC-12.3).

```
Field                           Type              Notes
────────────────────────────────────────────────────────────────────────
record_type                     str               Always "gap_marker"
schema_version                  str               "1.0"
otel_schema_url                 str               OTel GenAI conventions URL (for parsers)

run_id                          str               Run ID active when drops occurred
sink_id                         str               "file" | "tui" | "ws"
drop_count                      int               Number of records dropped in this gap
drop_start_time_unix_nano       int               Approximate wall-clock time of first drop
reason                          str               "buffer_full" (only value in M2)
```

**Consumer obligation (AC-05.5):** A consumer that receives a `gap_marker` knows child spans may be missing from the tree. It MAY choose to tolerate orphaned spans or drop the whole subtree — but the signal MUST be present so the consumer can make that choice.

### 3.5 Common-Core vs Extensions Boundary (OQ-01 resolved)

**Common-core** — present on every `span_end` record, `null` when not available, never omitted:

| Field | Always non-null? |
|-------|-----------------|
| `run_id`, `trace_id`, `span_id` | Yes |
| `parent_span_id` | Yes (null only for run-root — the sole legal exception) |
| `schema_version`, `otel_schema_url` | Yes |
| `phase`, `span_name`, `span_source`, `provider_kind` | Yes |
| `start_time_unix_nano`, `end_time_unix_nano`, `duration_ms` | Yes |
| `status` | Yes; `error_message` null when status=OK |
| `gen_ai_system` | null when provider doesn't report |
| `gen_ai_request_model` | null when not known |
| `gen_ai_response_model` | null when provider doesn't report |
| `gen_ai_operation_name` | Yes (always a phase name) |
| `gen_ai_usage_input_tokens` | null for non-LLM phases or unavailable |
| `gen_ai_usage_output_tokens` | null for non-LLM phases or unavailable |
| `cost_usd` | null when not computable |
| `extensions` | Yes — empty `{}` when no extensions, never absent |

**Extensions bag** — provider/adapter-specific; absence of a key within `extensions` is legal:

```json
{
  "extensions": {
    "gen_ai.usage.cache_read_input_tokens": 1024,
    "gen_ai.usage.cache_creation_input_tokens": 512,
    "gen_ai.response.finish_reason": "end_turn",
    "gen_ai.request.max_tokens": 8192,
    "gen_ai.request.temperature": 1.0,
    "axiom.adapter": "ClaudeAdapter",
    "axiom.spawn_count": 3
  }
}
```

Additional extension keys (not exhaustive): `gen_ai.request.top_p`, KIND B tool call name/arguments/result, subagent event metadata, any future adapter-specific telemetry.

### 3.6 KIND-B Stream-to-Span Mapping (OQ-04 resolved)

For KIND B adapters (`ClaudeAdapter`), `act()` receives a stream of provider events. The adapter maps events to child spans under the Act span:

| Stream event | Adapter action |
|-------------|---------------|
| `tool_use_start` | Open child span `gen_ai.tool_call`; `span_source="provider-streamed"` |
| `tool_use_end` | Close matching `gen_ai.tool_call` span; attach tool name + input summary to attrs |
| `message_start` | Open child span `gen_ai.message`; `span_source="provider-streamed"` |
| `message_end` | Close matching `gen_ai.message` span; attach finish reason + token counts if available |
| Other events | Captured as attributes on parent Act span or in `extensions` bag; no new span opened |

**Concurrency rule (AC-02.4):** Concurrent provider stream events (e.g. parallel tool calls) are represented as **sequential siblings** under the Act span. The adapter MUST NOT attempt to reconstruct provider concurrency or open overlapping child spans for concurrent events — doing so would revive the provider-internal-depth fidelity claim that §4.3 disclaims. Sequential ordering is the contract; `start_time_unix_nano` preserves best-effort time ordering within siblings.

**Parent pointer guarantee:** All KIND B child spans carry the Act span's `span_id` as `parent_span_id`. Guaranteed by Invariant 1 (§5.1) — tasks spawned inside the Act span's `with` block.

---

## 4. Span-Tree Construction Rules

### 4.1 Loop-Owned Phase Spans (all KINDs)

`PraoLoop.run()` owns the span tree root. For each user turn:

```
axiom.loop.run            ← run-root span (parent_span_id = null)
  axiom.loop.perceive     ← phase span, child of run-root
  axiom.loop.reason       ← phase span, child of run-root
  axiom.loop.act          ← phase span, child of run-root
    [adapter children]    ← KIND A: full-depth; KIND B: event-derived under Act
  axiom.loop.observe      ← phase span, child of run-root
  [... repeats per cycle]
```

Each PRAO phase span opens at phase start and closes at phase end. The run-root span wraps the entire `PraoLoop.run()` call (opened before the first perceive, closed after RESPOND/FINISH exit).

**`parent_span_id` is always valid** for every span except the run-root. This guarantee rests on Invariant 1 (§5.1) for asyncio paths and Invariant 2 (§5.2) for thread paths.

### 4.2 KIND A — Full-Depth Child Spans

KIND A adapters (local vLLM via LiteLLM, direct API) own the completion step internally. They can produce nested child spans at full depth:

```
axiom.loop.reason
  gen_ai.completion.request    ← KIND A: LiteLLM/API call start; span_source="core-minted"
    gen_ai.completion.chunk    ← streaming chunks (optional; may omit for brevity)
  gen_ai.completion.response   ← KIND A: response received; span_source="core-minted"
```

KIND A adapters call `tracer.start_as_current_span(...)` while the phase span is active; OTel context propagation automatically makes the active phase span the parent.

### 4.3 KIND B — Best-Effort Children Under Act

KIND B adapters (`ClaudeAdapter`) delegate to the provider's internal loop. Child spans are derived from the streamed event trace — best-effort depth only, not a claim to reproduce the provider's internal tree.

```
axiom.loop.act
  gen_ai.tool_call   ← span_source="provider-streamed"; sequential sibling
  gen_ai.tool_call   ← span_source="provider-streamed"; sequential sibling
  gen_ai.message     ← span_source="provider-streamed"; sequential sibling
```

`parent_span_id` of all children = Act span's `span_id`. No deeper nesting. Concurrent events are sequential siblings.

**Consumer contract (AC-02.7, stated in design for implementers):**

- Consumers MAY rely on `parent_span_id` being valid for all providers, all spans.
- Consumers MUST NOT assume provider-internal depth for KIND B (`span_source="provider-streamed"`).
- `span_source` is the fidelity signal: `core-minted` = Axiom-authored span; `provider-streamed` = derived from provider event stream.

---

## 5. Spike-Derived Invariants

These three invariants are **load-bearing design decisions** derived from the spike (Verdict B). They MUST be encoded as adapter implementation contracts — not optional best practices. They resolve OQ-05 (DG-10.A) and OQ-06 (DG-10.B) from the requirement.

### 5.1 Invariant 1 — Asyncio Task Timing Contract (Spike E3 finding)

**Rule:** The KIND-B adapter MUST create its streaming sub-tasks (via `asyncio.create_task`) INSIDE the Act span's `with` block — i.e., AFTER `tracer.start_as_current_span(...)` has been entered — never before.

**Mechanism:** `asyncio.create_task` snapshots the current `contextvars.Context` at task-creation time. OTel stores its active span in a `ContextVar`; the snapshot includes the active span. If the task is created before the Act span is open, the snapshot contains no active span and the child span spawned inside that task is orphaned (`parent_span_id=None`).

**Evidence:** Spike E3: task created BEFORE parent span → `parent_id=None` (FAIL). Task created AFTER entering parent span → correct `parent_id` (PASS).

**Required adapter structure:**

```python
async def _act_async(self, instruction: str) -> str:
    with tracer.start_as_current_span("axiom.loop.act", ...) as act_span:
        # Tasks MUST be created here (inside the with block, after span open)
        streaming_task = asyncio.create_task(self._stream_events(instruction))
        result = await streaming_task
    return result

# WRONG — task created before span is open:
# streaming_task = asyncio.create_task(self._stream_events(instruction))
# with tracer.start_as_current_span("axiom.loop.act", ...) as act_span:
#     result = await streaming_task
```

### 5.2 Invariant 2 — Thread Boundary Rule (Spike E4/E5b finding)

**Rule:** Any adapter path that dispatches work via `loop.run_in_executor()` (or any `ThreadPoolExecutor`) MUST explicitly:
1. Capture `otel_context.get_current()` while INSIDE the parent span (before dispatching).
2. Attach that captured context INSIDE the thread function via **closure** (not as a function argument evaluated at dispatch time).

**Mechanism:** `ThreadPoolExecutor` does NOT copy `contextvars.Context` automatically (unlike `asyncio.create_task`). A thread dispatched without context capture inherits an empty context; spans opened inside the thread are orphaned.

**Evidence:** Spike E4: `run_in_executor` without context → `parent_id=None` (FAIL). Spike E5b: closure-captured context + `attach()` inside thread → correct `parent_id` (PASS).

**Required pattern (mandatory for all `run_in_executor` paths):**

```python
# Inside the parent span:
captured_ctx = otel_context.get_current()   # snapshot WHILE parent is active

def thread_fn():
    token = otel_context.attach(captured_ctx)   # via closure, NOT as parameter
    try:
        with tracer.start_as_current_span("child.span") as span:
            # ... do work ...
            pass
    finally:
        otel_context.detach(token)

await asyncio.get_event_loop().run_in_executor(None, thread_fn)
```

**Critical pitfall (flag in code review):** Do NOT pass `otel_context.get_current()` as a function argument evaluated at dispatch time:

```python
# WRONG — get_current() evaluates in the thread's empty context:
executor.submit(thread_fn, otel_context.get_current())
```

The expression `otel_context.get_current()` must be evaluated **before** `executor.submit` / `run_in_executor`, captured in a closure variable, and attached inside the thread.

### 5.3 Invariant 3 — Live Sinks Subscribe to on_start (Spike E6 finding)

**Rule:** Live sinks (TUI, WS bridge) obtain "span in progress" signals from `SpanProcessor.on_start`, NOT from `on_end`. A separate `LiveNotificationProcessor` in the pipeline publishes `span_start` records on `on_start`. The `JsonlExportProcessor` publishes `span_end` records on `on_end`.

**Mechanism:** `SpanProcessor.on_start` fires immediately when a span opens — before it closes. For a long-running Act span (e.g. 30 seconds), `on_end` fires when "Act in progress" is no longer useful to live consumers. `on_start` fires at the moment the phase begins.

**Evidence:** Spike E6: `on_start` fires before span closes; live visibility confirmed (PASS).

**Design consequence:** Two processors in the pipeline; both must be registered on the `TracerProvider`. The schema includes `span_start` records (§3.3) for live signaling alongside `span_end` records (§3.2). All sinks receive both record types from the fan-out; TUI/WS use `span_start` for "in progress" display and `span_end` for completion. Consumers correlate by `span_id`.

---

## 6. Transport and Fan-Out

### 6.1 Producer

The single producer is the two-processor OTel pipeline:
- `LiveNotificationProcessor` — publishes `span_start` records on `on_start`.
- `JsonlExportProcessor` — publishes `span_end` records on `on_end`.

Both call `SinkRegistry.publish("trace", record)`. This is the **only code path** that publishes to the fan-out (AC-04.3).

### 6.2 Fan-Out (SinkRegistry)

`SinkRegistry.publish(subject, record)`:
1. Look up all sinks registered for `subject`.
2. For each sink: call `sink.put(record)` — non-blocking enqueue.
3. If `sink.put()` raises: log to stdlib, continue to next sink (no cross-contamination, AC-11.3).

No filtering, no routing in M2. All sinks get all records. Subject taxonomy deferred to M7.

### 6.3 Backpressure Invariant (hard — AC-05.1)

`sink.put(record)` MUST be non-blocking. Each sink owns its own buffer queue; `put()` either enqueues immediately or drops-oldest with a `gap_marker` — it NEVER blocks waiting for the drain thread/task. The producer (OTel processor callbacks) returns immediately after all `put()` calls complete. No sink — file, TUI, or WS — can cause the producer to block under any condition (disk-full, terminal hang, WS client disconnect).

### 6.4 Per-Consumer Buffer Contracts

| Sink | Buffer type | Default depth | Drop policy | Loss class |
|------|------------|--------------|-------------|------------|
| File | `queue.Queue` (FIFO) | D = 10,000 | Drop-oldest + `gap_marker` when full | **bounded-durable** |
| TUI | `collections.deque(maxlen=...)` | 200 | Drop-oldest + `gap_marker` | loss-tolerant |
| WS bridge | `collections.deque(maxlen=...)` per client | 500 | Drop-oldest + `gap_marker` | loss-tolerant |

File sink is the most durable: deep queue, dedicated drain thread, periodic fsync. But it is **bounded-durable** — not absolutely durable. Records in the un-drained queue at process crash are lost. A synchronous "forensic durable" mode is explicitly **not M2** (would violate the non-blocking emit invariant).

### 6.5 FIFO Ordering

Single producer + per-consumer FIFO queue → **per-consumer record order preserved** (AC-05.6). Within a consumer's queue, records arrive in producer emit order. Live-tree consumers can rely on parent-before-child span arrival (the loop opens parent spans before adapters open child spans).

---

## 7. Broker Seam

**`SinkRegistry.publish(subject: str, record: dict)`** is the broker seam.

**M2 semantics:** subject = `"trace"` only; broadcast-all (every registered sink gets every record, no filtering).

**M7 seam guarantee (AC-09.4):**
- Publisher call-sites (`processors.py` calling `registry.publish("trace", record)`) are **protected from rework** when M7 adds new subjects — new subjects require only new `register("agent.*", sink)` calls.
- The fan-out **internals** will need rework at M7: broadcast-all becomes subject-addressed delivery (routing). This is a known, recorded M7 constraint — not hidden.
- **A2A contention (M7 note):** When A2A lands, control-plane messages (e.g. mid-run ABORT) must not queue behind a trace burst. That is an M7 design constraint; M2 does not solve it.

**Rejected transport alternatives:** external NATS (install/attack surface), MQTT/amqtt (overkill, alpha-versioned), OTel collector/backend (external infra). In-process only.

---

## 8. File Sink Configuration (OQ-03 resolved)

| Parameter | Default | Configurable via |
|-----------|---------|-----------------|
| Storage directory | `~/.axiom/traces/` | `ObservabilityConfig.trace_dir` |
| File naming | `{run_id}.jsonl` | (derived; not separately configurable) |
| Max file size | 100 MB | `ObservabilityConfig.file_max_size_mb` |
| Max file age | 7 days | `ObservabilityConfig.file_max_age_days` |
| Max file count | 10 | `ObservabilityConfig.file_max_count` |
| Queue depth D | 10,000 records | `ObservabilityConfig.file_queue_depth` |
| fsync cadence (records) | Every 100 records | `ObservabilityConfig.file_fsync_records` |
| fsync cadence (time) | Every 1.0 seconds | `ObservabilityConfig.file_fsync_secs` |

File permissions: always `0o600` — not configurable (AC-06.5).

---

## 9. Security

- **WS bridge:** binds `127.0.0.1` only; MUST NOT bind `0.0.0.0` or any external interface. Token authentication required on every connection. Token: UUID4 generated at startup or supplied via `ObservabilityConfig.ws_token`. Unauthenticated connections receive HTTP 401 and are closed before any data is transmitted.
- **File sink:** permissions `0o600`. Traces contain full prompts, tool arguments, and potentially sensitive data.
- **Redaction policy:** No redaction in M2. Traces are trusted-local. A redaction hook is deferred to M9 (Connectors / Guardrails), where untrusted external input first arrives. This is an explicit decision, not an oversight.
- **Schema versioning:** `schema_version` on every record (including `gap_marker`) guards against silent schema churn. `otel_schema_url` tracks OTel GenAI convention version independently. Both present on every record (AC-12.1).
- **Self-observation recursion guard:** All sink error handlers and processor error handlers use stdlib `logging` only — never `registry.publish()`. This closes the trace-of-trace loop (US-11, AC-11.2).

---

## 10. Module Layout

```
src/axiom/observability/
├── __init__.py              # Re-exports ObservabilityFaculty, record_phase
├── faculty.py               # ObservabilityFaculty: TracerProvider init/shutdown,
│                            #   processor registration, sink wiring
├── record.py                # record_phase() context manager — the RECORD call-point API
│                            #   The only observability import that loop.py touches
├── processors.py            # LiveNotificationProcessor, JsonlExportProcessor
├── registry.py              # SinkRegistry: publish(), register(); Sink Protocol
├── schema.py                # Serialization: serialize_span_start(), serialize_span_end(),
│                            #   make_gap_marker(); SCHEMA_VERSION="1.0"; OTEL_SCHEMA_URL
├── config.py                # ObservabilityConfig dataclass (all configurable parameters)
├── sinks/
│   ├── __init__.py
│   ├── base.py              # Sink Protocol: put(record: dict) -> None; shutdown() -> None
│   ├── file_sink.py         # FileSink + FileSinkDrainer thread
│   ├── tui_sink.py          # TuiSink + render loop (asyncio task or daemon thread)
│   └── ws_sink.py           # WsBridgeSink + asyncio server + per-client buffer queues
└── timing.py                # M1 stub (deprecated in M2; retained for backward compat)
```

**Import boundary rule:** `loop.py` imports ONLY `axiom.observability.record` (the `record_phase` context manager). It does not import `faculty.py`, `registry.py`, `processors.py`, or any sink. `interfaces.py` imports nothing from observability. `faculty.py`, `processors.py`, `registry.py`, `schema.py`, and all sinks are wired together in the composition root (`agent.py`), the same layer that wires M1's `timed_run`.

---

## 11. Schema Versioning

- `SCHEMA_VERSION = "1.0"` at M2 launch (defined in `schema.py`).
- Increment on every **backward-incompatible** change: field removed, field type changed, mandatory field added.
- Additive changes (new optional `extensions` keys, new optional common-core fields defaulting to `null`) do NOT require a bump.
- `schema_version` appears on every record type: `span_start`, `span_end`, `gap_marker` (AC-12.3).
- `otel_schema_url` is independent — set to the OTel GenAI semantic conventions schema URL matching the installed `opentelemetry-semantic-conventions==0.64b0` package. Both fields always present together.

---

## 12. Non-Goals (M2 scope fence)

| Non-Goal | Notes |
|----------|-------|
| External message broker | No NATS, no MQTT, no Redis — in-process fan-out only |
| OTel collector or backend | OTel SDK in-process yes; OTel infra no |
| Subject taxonomy / addressing | Deferred to M7 (Orchestrator); M2 uses `trace` only |
| Redaction / PII scrubbing | Deferred to M9 (Connectors / Guardrails) |
| Web dashboard | Raw authenticated WS stream only; no HTTP server, no browser UI |
| Consumer storage decisions | Sinks receive JSONL; internal storage is sink-local concern |
| Self-correction | M8 |
| Synchronous "forensic durable" file mode | Future opt-in; not M2 (violates non-blocking emit invariant) |
| A2A / inter-agent message routing | M7; M2 fan-out is broadcast-all |
| Multi-user / permissions | Later phase |

---

## 13. Resolved Open Questions

| OQ | Question | Resolution |
|----|----------|-----------|
| OQ-01 | Core vs extensions attribute boundary | Resolved §3.5. Common-core field list defined with null policy; `extensions` is freeform `{}` object, never absent. |
| OQ-02 | Gap-marker schema | Resolved §3.4. Fields: `record_type`, `schema_version`, `otel_schema_url`, `run_id`, `sink_id`, `drop_count`, `drop_start_time_unix_nano`, `reason`. |
| OQ-03 | File sink config (path, rotation, D, fsync) | Resolved §8. All defaults specified; all configurable via `ObservabilityConfig`. |
| OQ-04 | KIND-B stream-to-span mapping | Resolved §3.6. `tool_use_start/end` and `message_start/end` open/close child spans; concurrent events → sequential siblings. |
| OQ-05 (DG-10.A) | OTel `contextvars` across asyncio (gate) | **Resolved by spike Verdict B.** E2: `asyncio.create_task` auto-propagates when task created inside parent span (PASS). E3: timing constraint — task MUST be created after span open (Invariant 1, §5.1). Parent-id-always-valid guarantee holds for asyncio path. |
| OQ-06 (DG-10.B) | Span-lifecycle events for live sinks (gate) | **Resolved by spike.** E6: `on_start` fires before span closes, giving live visibility (PASS). Two-processor pipeline: `LiveNotificationProcessor` (`on_start` → `span_start` record) + `JsonlExportProcessor` (`on_end` → `span_end` record). Resolves "Act in progress" problem without schema divergence (Invariant 3, §5.3). |

---

## 14. Remaining Implementation-Phase Questions

None of the requirement's OQ-01 through OQ-06 remain open — all resolved above. The following are **deferred to implementation-time decisions** (not design-phase blockers):

| # | Question | Recommendation |
|---|----------|---------------|
| IQ-1 | TUI rendering library (Rich, Textual, or custom) | Defer to implementation; Rich is the natural fit |
| IQ-2 | WS bridge library choice | `websockets` (already in dep scope); confirm at impl |
| IQ-3 | `ObservabilityFaculty` lifecycle wiring in `agent.py` | Composition root pattern; same layer as M1's `timed_run` |
| IQ-4 | `run_id` generation — loop vs faculty | Recommendation: generated in `ObservabilityFaculty.new_run()`; injected into `record_phase()` calls |
| IQ-5 | `timing.py` deprecation vs removal in M2 | Recommendation: retain as deprecated in M2; remove in M3 cleanup |

---

## 15. Architecture Invariants (hard — may not be relaxed without updating this document and requirement.md)

1. **Non-blocking emit.** No sink may back-pressure the producer under any condition.
2. **Loop sovereignty over span tree.** The loop mints PRAO phase spans. Adapters add children. No adapter reparents or replaces loop-level spans.
3. **OTel confined to Observability.** `loop.py` and `interfaces.py` import nothing from `opentelemetry` except via `record.py`.
4. **In-process only.** No external queue, no external infra, no OTel collector.
5. **Single producer.** Only `processors.py` calls `registry.publish()`. No other code path publishes to the fan-out.
6. **`parent_span_id` always valid** (except run-root). Guaranteed by Invariants 1 and 2 (§5.1, §5.2).
7. **WS localhost-only + token auth.** Non-negotiable.
8. **File sink `0o600` permissions.** Non-negotiable.
9. **Sink errors → stdlib logging only.** Never the bus.
