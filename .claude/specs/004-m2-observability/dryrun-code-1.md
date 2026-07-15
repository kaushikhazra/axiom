# Code Dry-Run Report #1

**Scope**: `src/axiom/observability/` (record.py, schema.py, config.py, faculty.py, processors.py, registry.py, sinks/base.py, sinks/file_sink.py, sinks/tui_sink.py, sinks/ws_sink.py, __init__.py) + `src/axiom/loop.py` (`_maybe_record` integration)
**Design**: `.claude/specs/004-m2-observability/design.md`
**Spike ref**: `spikes/m2-observability/spike-result.md`
**Reviewed**: 2026-07-13

---

## Bugs (will cause incorrect behavior)

### [B1] TuiSink: `deque(maxlen=buffer)` causes silent double-drop — violates AC-05.3

- **File**: `src/axiom/observability/sinks/tui_sink.py:49` (deque construction), `63-76` (put logic)
- **Pass**: Pass 2 (Execution Path Trace) + Pass 4 (Input Validation)
- **What**: `self._deque` is constructed with `maxlen=buffer` (200). In `put()`, when the deque is full, the code does: `popleft()` (→ buffer-1 items), `append(gap_marker)` (→ buffer items, full again), `append(record)` (→ deque auto-pops leftmost via `maxlen`, stays at buffer items). The `deque.append()` to a full deque silently evicts the leftmost element. After `append(gap_marker)` the deque is again full at `maxlen`. The subsequent `append(record)` causes the deque to auto-drop `items[1]` (the second-oldest) without any gap_marker signal.
- **Impact**: Every overflow event drops **two** records — the explicitly `popleft()`'d oldest and the implicitly auto-dropped second-oldest — but emits only one `gap_marker(drop_count=1)`. AC-05.3 requires "the oldest record is dropped… A gap-marker record is immediately appended." The implementation silently drops a second record per overflow with no signal. `drop_count` is understated by 1 for every overflow event.
- **Fix**: Remove `maxlen=buffer` from the deque constructor (use `deque()` instead). When `len(deque) >= buffer`, do **two** `popleft()` calls (making room for both the gap_marker and the record), emit `gap_marker(drop_count=2)`, then `append(gap_marker)` and `append(record)`. This preserves the exact buffer size and accurately accounts for all drops.

```python
# Before (line 49):
self._deque: deque[dict] = deque(maxlen=buffer)

# After:
self._deque: deque[dict] = deque()  # no maxlen — managed manually in put()

# Before (put(), lines 65-76):
if len(self._deque) == self._buffer:
    self._deque.popleft()
    gap = make_gap_marker(run_id=record.get("run_id"), sink_id="tui", drop_count=1)
    self._deque.append(gap)
self._deque.append(record)

# After:
if len(self._deque) >= self._buffer:
    self._deque.popleft()   # drop oldest
    self._deque.popleft()   # drop second-oldest (needed for gap_marker + record)
    gap = make_gap_marker(run_id=record.get("run_id"), sink_id="tui", drop_count=2)
    self._deque.append(gap)
self._deque.append(record)
```

---

### [B2] WsBridgeSink: same `deque(maxlen)` double-drop in per-client buffers

- **File**: `src/axiom/observability/sinks/ws_sink.py:165` (client deque construction in `_handle_client`), `97-105` (put logic)
- **Pass**: Pass 2
- **What**: Identical root cause to B1. Per-client deques are created with `deque(maxlen=self._ws_buffer)` in `_handle_client`. In `put()`, the same popleft → append(gap) → append(record) sequence on a full deque auto-drops the second-oldest item silently via `maxlen`.
- **Impact**: Same as B1 — `drop_count` understated by 1 per overflow; one record silently dropped per overflow event without a gap_marker.
- **Fix**: Create client deques without maxlen (`deque()`) and apply the same 2x popleft pattern as B1 fix.

---

## Gaps (missing implementation)

### [G1] `websockets` not declared as a project dependency

- **File**: `pyproject.toml` (missing from `[project.dependencies]`)
- **Pass**: Pass 7 (Contract Violations)
- **What**: `ws_sink.py` imports `websockets` with an `ImportError` fallback. The design (IQ-2) states: "websockets (already in dep scope); confirm at impl." The `pyproject.toml` has no `websockets` entry in `[project.dependencies]` or any optional group. The WsBridgeSink will always log "websockets package not installed; WS sink disabled" in any fresh install.
- **Design ref**: design.md §2.7, IQ-2 (websockets in dep scope)
- **Fix**: Add `websockets>=10.0` to `[project.dependencies]` in `pyproject.toml`. The ImportError fallback may be retained as a defensive guard.

---

## Warnings (potential issues)

### [W1] WsBridgeSink `_handle_client` signature incompatible with `websockets >= 12.0`

- **File**: `src/axiom/observability/sinks/ws_sink.py:148`
- **Pass**: Pass 7
- **What**: `websockets >= 12.0` (released 2023) changed the server handler API: handlers receive only `websocket`; the request path is accessible via `websocket.request.path`. The current signature `_handle_client(self, websocket, path: str = "/")` with `path` defaulting to `"/"` means that with websockets ≥ 12, `path` is never passed and stays `"/"`. `urllib.parse.urlparse("/").query` is empty, so `params.get("token", [])` returns `[]`, causing ALL connections to fail authentication and be rejected with code 4001. WsBridgeSink silently becomes non-functional for all clients.
- **Risk**: Any installation that picks websockets ≥ 12.0 (including after adding websockets to deps per G1 fix) produces WsBridgeSink that rejects every client silently.
- **Fix**: Update `_handle_client` to read path from `websocket.request.path` (websockets ≥ 12 API) with a fallback for older versions, and remove the `path` positional parameter:

```python
async def _handle_client(self, websocket) -> None:
    import urllib.parse
    # websockets >= 12.0: path via websocket.request.path
    # websockets < 12.0: path was a second positional arg (no longer supported here)
    try:
        raw_path = websocket.request.path
    except AttributeError:
        raw_path = getattr(websocket, "path", "/")
    query = urllib.parse.urlparse(raw_path).query
    ...
```

---

### [W2] Multiple `new_run()` calls accumulate FileSinks — cross-run record contamination

- **File**: `src/axiom/observability/faculty.py:122-128`
- **Pass**: Pass 6 (Concurrency)
- **What**: Each call to `new_run()` creates a new `FileSink` and appends it to `self._registry` under `"trace"` without unregistering the previous run's sinks. After three `new_run()` calls, three FileSinks are registered. All subsequent spans are written to all three files simultaneously. Run 2's spans appear in run 1's `.jsonl` file and vice versa.
- **Risk**: Any scenario where a single `ObservabilityFaculty` instance is reused across multiple `PraoLoop.run()` calls (a natural pattern for a long-lived agent server) produces cross-contaminated trace files. The test `test_new_run_returns_unique_ids` calls `new_run()` three times without detecting this contamination.
- **Fix**: At the start of `new_run()`, unregister previously registered sinks from the `"trace"` subject before creating new ones. Keep them in `self._sinks` for orderly shutdown:

```python
def new_run(self) -> str:
    run_id = str(uuid.uuid4())
    trace_dir = self._config.trace_dir
    trace_dir.mkdir(parents=True, exist_ok=True)
    self._purge_old_traces(trace_dir)

    # Unregister any sinks from previous run so they don't receive new-run records
    for sink in self._registry.sinks_for("trace"):
        self._registry.unregister("trace", sink)

    # ... rest unchanged ...
```

---

### [W3] WsBridgeSink `_do_shutdown` cancels `wait_closed()` task, not the server — no graceful WS close

- **File**: `src/axiom/observability/sinks/ws_sink.py:146, 203-210`
- **Pass**: Pass 5 (Resource Management)
- **What**: `_start_server` stores `asyncio.ensure_future(server.wait_closed())` as `self._server_task`, but the `server` object itself is a local variable and not stored on `self`. `_do_shutdown` calls `self._server_task.cancel()` which cancels `wait_closed()`, but this does NOT close the server or send WebSocket close frames to connected clients. The design comment "all client connections are now closed" in the `_do_shutdown` pseudocode is incorrect. Connections are only terminated when `self._loop.stop()` kills the event loop (abrupt TCP drop, no WS close frame).
- **Risk**: Connected WS clients receive abrupt TCP disconnections rather than graceful WebSocket close frames (1001 Going Away) on agent shutdown. For a localhost dev tool this is acceptable but misleading; clients may log spurious errors.
- **Fix**: Store the server object as `self._ws_server` and call `server.close()` + `await server.wait_closed()` in `_do_shutdown`:

```python
# In _start_server:
self._ws_server = await websockets.serve(self._handle_client, self._host, self._port)
self._server_task = asyncio.ensure_future(self._ws_server.wait_closed())

# In _do_shutdown:
async def _do_shutdown(self) -> None:
    if getattr(self, '_ws_server', None) is not None:
        self._ws_server.close()
        try:
            await asyncio.wait_for(self._ws_server.wait_closed(), timeout=1.0)
        except Exception:
            pass
    if self._server_task is not None:
        self._server_task.cancel()
        try:
            await self._server_task
        except (asyncio.CancelledError, Exception):
            pass
```

---

## Style (code quality, conventions)

### [S1] WsBridgeSink: inconsistent item wrapping in per-client deques

- **File**: `src/axiom/observability/sinks/ws_sink.py:99-105`
- **What**: Regular records are stored as `{"_line": serialized_line, "_raw": record}` wrappers; gap_markers are stored as raw dicts without `_line`. The drain loop handles both via `isinstance(item, dict) and "_line" in item`. The inconsistency makes the deque's content type ambiguous and the drain loop's fallback branch (`else: json.dumps(item)`) surprising. Fix: store gap_markers with the same wrapper format for consistency.

### [S2] Unused `if TYPE_CHECKING: pass` block in `faculty.py`

- **File**: `src/axiom/observability/faculty.py:39-40`
- **What**: `if TYPE_CHECKING: pass` is a no-op. The TYPE_CHECKING guard was likely left over from a refactor. Remove it.

### [S3] OTel deps use `>=1.20` in `pyproject.toml`, not pinned as design specifies

- **File**: `pyproject.toml:32`
- **What**: design.md §2.1 states: "OTel dep pinned: `opentelemetry-sdk==1.43.0`, `opentelemetry-api==1.43.0`, `opentelemetry-semantic-conventions==0.64b0`." The actual constraint is `opentelemetry-sdk>=1.20`. While `>=` is better for maintenance, it deviates from the design's pinning contract and could admit a future OTel version with breaking `gen_ai.*` attribute changes. Update to `>=1.43.0` (not exact pin but close to design intent while allowing patch updates).

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 2 | 1 | 3 | 3 |

**Verdict**: FAIL — 2 bugs (AC-05.3 violation in lossy sinks), 1 gap (missing websockets dep), 3 warnings.
