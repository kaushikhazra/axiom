# Code Dry-Run Report #2

**Scope**: `src/axiom/observability/` (record.py, schema.py, config.py, faculty.py, processors.py, registry.py, sinks/base.py, sinks/file_sink.py, sinks/tui_sink.py, sinks/ws_sink.py, __init__.py) + `src/axiom/loop.py` (`_maybe_record` integration) + `tests/test_observability_*.py`
**Design**: `.claude/specs/004-m2-observability/design.md`
**Spike ref**: `spikes/m2-observability/spike-result.md`
**Reviewed**: 2026-07-13

---

## Bugs (will cause incorrect behavior)

_None._

---

## Gaps (missing implementation)

_None._

---

## Warnings (potential issues)

### [W1] TuiSink `put()`: second `popleft()` raises `IndexError` when `buffer < 2`

- **File**: `src/axiom/observability/sinks/tui_sink.py:78-79`
- **Pass**: Pass 4 (Input Validation & Boundaries)
- **What**: After the B1 fix, `put()` does two consecutive `popleft()` calls when `len(self._deque) >= self._buffer`. When `self._buffer == 1` and the deque contains exactly 1 item, the condition fires (1 >= 1), the first `popleft()` empties the deque, and the second `popleft()` raises `IndexError` on an empty deque.
- **Risk**: `ObservabilityConfig` defaults `tui_buffer=200`, so this cannot occur in production. However, tests that construct `TuiSink(buffer=1)` or any edge-case buffer value below 2 will crash the drain thread silently (the thread catches `Exception` and logs but continues). The drain thread exits without further recovery, leaving `put()` calls successfully enqueuing but nothing draining — a silent resource state divergence.
- **Fix**: Guard the second `popleft()` with a non-empty check:
  ```python
  if len(self._deque) >= self._buffer:
      self._deque.popleft()
      if self._deque:  # guard: buffer=1 edge case
          self._deque.popleft()
      gap = make_gap_marker(...)
      self._deque.append(gap)
  self._deque.append(record)
  ```

---

### [W2] WsBridgeSink `put()`: same `IndexError` on second `dq.popleft()` when `ws_buffer < 2`

- **File**: `src/axiom/observability/sinks/ws_sink.py:121-122`
- **Pass**: Pass 4 (Input Validation & Boundaries)
- **What**: Identical root cause to W1. Per-client deque `dq` has 1 item when `ws_buffer == 1`, condition `len(dq) >= 1` fires, first `dq.popleft()` empties it, second `dq.popleft()` raises `IndexError`. This propagates up through `put()` (no try/except around the per-client loop body), crashes the calling thread (a span processor callback), and leaves the per-client deque in a partially-modified state.
- **Risk**: Same as W1 — `ws_buffer` defaults to `512`, so production is safe. Tests or misconfiguration with `ws_buffer=1` will crash `put()` (not just drain thread).
- **Fix**: Same guard pattern:
  ```python
  with lock:
      if len(dq) >= self._ws_buffer:
          dq.popleft()
          if dq:  # guard: ws_buffer=1 edge case
              dq.popleft()
          gap = make_gap_marker(...)
          ...
  ```

---

## Style (code quality, conventions)

### [S1] TuiSink module docstring: stale reference to `deque(maxlen=TUI_BUFFER)`

- **File**: `src/axiom/observability/sinks/tui_sink.py:5`
- **What**: Module docstring line 5 says "Uses a collections.deque(maxlen=TUI_BUFFER) guarded by threading.Lock." The B1 fix removed `maxlen` — the deque is now unbounded (size enforced manually in `put()`). The docstring is now inaccurate and misleading.

---

### [S2] TuiSink `put()` docstring: doesn't reflect 2-popleft / `drop_count=2` behaviour

- **File**: `src/axiom/observability/sinks/tui_sink.py:64-72`
- **What**: The method docstring for `put()` (lines 64–72) correctly describes the 2-popleft/gap_marker(drop_count=2) logic after B1. However, the class docstring (lines 31–34) still reads "drop-oldest and append gap_marker" without mentioning that two records are dropped and `drop_count=2` is emitted. Minor inconsistency but creates confusion for the next reader.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 2 | 2 |

**Verdict**: PASS WITH WARNINGS — 2 edge-case warnings (buffer < 2 IndexError), 2 stale docstrings. No correctness impact in production configuration.
