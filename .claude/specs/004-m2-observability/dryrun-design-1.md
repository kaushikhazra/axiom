# Design Dry-Run Report #1

**Document**: `.claude/specs/004-m2-observability/design.md`
**Reviewed**: 2026-07-13

---

## Critical Gaps (must fix before implementation)

### [C1] task.md is empty — all file-level prescriptions are untraced on the task axis
- **Pass**: Pass 9 (Design-to-Task-to-AC Traceability)
- **What**: `task.md` exists but is empty (0 bytes). No task items exist. The design prescribes 13 files to create/modify across body sections (§2.1–2.7, §10): `faculty.py`, `record.py`, `processors.py`, `registry.py`, `schema.py`, `config.py`, `sinks/__init__.py`, `sinks/base.py`, `sinks/file_sink.py`, `sinks/tui_sink.py`, `sinks/ws_sink.py`, `__init__.py`, and `timing.py` (deprecation); plus `loop.py` import boundary and `agent.py` composition wiring. None of these have a scheduled task.
- **Risk**: All prescribed implementation work is invisible to the pipeline. Nothing gets built — every file prescription silently drops.
- **Fix**: Populate `task.md` with tasks covering every file prescription in the design. Each task must state actor, action, and target component. The `/design` skill is expected to produce `task.md` before `/dryrun-design` runs.

---

## Warnings (should fix, may cause issues)

### [W1] FileSink graceful shutdown path is underspecified
- **Pass**: Pass 3 (Interface Contract Validation) + Pass 5 (Failure Path Analysis)
- **What**: §2.1 says `ObservabilityFaculty.shutdown()` is "called at process exit (flushes processors)." §2.5 defines `FileSinkDrainer` as a **daemon thread**. Daemon threads in Python are killed immediately when the main thread exits — they do not drain their queue. If `ObservabilityFaculty.shutdown()` calls OTel `TracerProvider.force_flush()` + `shutdown()`, that flushes in-flight spans through the processors to the `SinkRegistry`, but records already in the `FileSink` queue are not drained before the daemon thread dies. The result: the last `N` records (up to `D=10,000`) in the queue at exit are silently lost with no gap-marker, contradicting the "bounded-durable" contract.
- **Risk**: Trace records from the final seconds of a run are lost at normal process exit. The bounded-durable guarantee is only meaningful mid-run, not at shutdown — a significant reliability gap for a "persistent trace on every run" system.
- **Suggestion**: Add a `FileSink.shutdown()` method that signals the drainer thread to stop accepting new records, drains the remaining queue to disk, performs a final `fsync`, and joins the thread. `ObservabilityFaculty.shutdown()` must call `FileSink.shutdown()` after `TracerProvider.shutdown()`. Alternatively, use a non-daemon thread and signal via a sentinel value (`queue.put(None)`). Document this in §2.5 and §2.1.

### [W2] TUI and WS sink deque drop-oldest is not thread-safe if drain runs on a daemon thread
- **Pass**: Pass 6 (Concurrency & Ordering)
- **What**: §2.6 says TUI sink drains "on its own asyncio task **or** daemon thread." §2.7 says WS bridge drains "on an asyncio task." `collections.deque(maxlen=...)` append/popleft are individually atomic in CPython (GIL), but the drop-oldest sequence in `put()` — `(1) check len == maxlen → (2) popleft (drop oldest) → (3) append gap_marker → (4) append record` — is NOT atomic. If the drain task runs on a **separate thread** and calls `popleft()` between steps (1) and (2), the deque may no longer be full, causing an unnecessary drop-oldest on a non-full deque, or the `gap_marker` and record may interleave unexpectedly.
- **Risk**: Corrupted drop-oldest accounting (gap_markers emitted for records not actually dropped; or records emitted without gap_markers when drops occurred). Data integrity of the loss-accounting mechanism is compromised.
- **Suggestion**: Either (a) mandate that all TUI and WS drain loops run as **asyncio tasks on the same event loop** as `put()` (single-threaded, no race); or (b) replace deque with `queue.Queue` (thread-safe, matching FileSink pattern); or (c) protect the drop-oldest sequence with a `threading.Lock`. Option (a) is simplest — state it explicitly: "TUI and WS sinks drain on asyncio tasks, not daemon threads, to ensure single-threaded access to the deque." Update §2.6 and §2.7 to remove the "or daemon thread" ambiguity.

### [W3] File rotation mechanism is not designed — only policy is stated
- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: §2.5 states "Rotation: max 100 MB per file, max 7 days age, max 10 files retained" and §8 lists these as configurable parameters. But the design nowhere describes HOW rotation is implemented: Does `FileSinkDrainer` check file size after each write? Does it use Python's `RotatingFileHandler` or `TimedRotatingFileHandler`? Does it open a new file mid-run (and if so, what `run_id` does the new file get)? What happens to the current open file handle during rotation? The gap is the mechanism, not the policy.
- **Risk**: Implementer invents rotation ad hoc — either picking a heavy library approach (coupling `FileSink` to `logging.handlers`) or writing a fragile custom rotation that doesn't handle concurrent writes, missing the size threshold, or producing files with inconsistent naming.
- **Suggestion**: Specify the rotation mechanism. Recommended: use Python's `logging.handlers.RotatingFileHandler` internally as the write backend (it handles size + count rotation atomically and is battle-tested), with `TimedRotatingFileHandler` for age-based. Or specify that one file is written per run (no mid-run rotation) and old files are pruned at startup based on max-count + max-age. Whichever is chosen, state it in §2.5 and §8.

---

## Observations (worth discussing)

### [O1] FileSink needs `run_id` at construction but the injection is not stated
`§2.5` says the file path is `~/.axiom/traces/{run_id}.jsonl`. The `FileSink` must know the `run_id` to open the file. `IQ-4` (§14) says `run_id` is "generated in `ObservabilityFaculty.new_run()`, injected into `record_phase()` calls" — but doesn't mention it also being injected into `FileSink` at construction. This is implied but not stated. A future implementer might look at `IQ-4` and only inject `run_id` into `record_phase()`, leaving `FileSink` to derive the filename from the first record's `run_id` field — which means the file isn't opened until the first record arrives, and the timing/error behavior differs. Recommend adding to §2.5: "`FileSink` receives `run_id` at construction from `ObservabilityFaculty.new_run()` and opens the trace file immediately."

### [O2] Sink registration ordering relative to first `publish()` not explicitly stated
§2.4 (`SinkRegistry`) doesn't say when sinks must be registered relative to the first `publish()` call. In practice, the composition root (`agent.py`) registers all sinks at startup before starting the loop. Adding a sentence to §2.4 or §10 stating "all sinks are registered during composition (agent.py startup) before `PraoLoop.run()` is called" would eliminate ambiguity for implementers.

### [O3] FileSink file-open failure handling not specified
§2.5 says "IOError → `logging.getLogger(__name__).error(...)`" for write errors, but doesn't address failure to open the file at sink startup (e.g., permission denied on `~/.axiom/traces/`, directory doesn't exist). If `FileSink.__init__` fails to open the file, subsequent `put()` calls would fail with `AttributeError` (writing to `None` file handle) rather than gracefully dropping records. The design should state whether `FileSink` (a) creates the directory if absent, (b) raises at construction time (failing fast), or (c) transitions to a degraded "drop-all" state.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 1        | 3        | 3            |

**Verdict**: FAIL — needs revision

The single Critical Gap (C1) is that `task.md` is empty. All file-level prescriptions in the design have no scheduled tasks, making the entire implementation pipeline invisible. Additionally, three Warnings cover non-trivial design gaps: `FileSink` graceful shutdown, deque thread-safety for TUI/WS sinks, and the missing file rotation mechanism. These should be resolved in the design before implementation begins.
