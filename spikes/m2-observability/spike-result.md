# M2 Observability Spike — Result

**Spike:** `spikes/m2-observability/contextvars_spike.py`
**Run date:** 2026-07-13
**Gate question:** Does OTel context propagation correctly mint parent/child span
relationships across asyncio task / thread boundaries (the KIND-B pattern)?
**Research doc:** `.claude/research/005-m2-observability-architecture-2026-07-13.md` §3 + §6

---

## Packages installed

| Package | Version | How installed |
|---------|---------|---------------|
| `opentelemetry-api` | 1.43.0 | `uv add --dev "opentelemetry-sdk>=1.20"` |
| `opentelemetry-sdk` | 1.43.0 | (pulled by sdk) |
| `opentelemetry-semantic-conventions` | 0.64b0 | (pulled by sdk) |

Added to `pyproject.toml` under `[dependency-groups] dev`.

---

## Full stdout

```
======================================================================
M2 Observability Spike — OTel context propagation across boundaries
======================================================================
opentelemetry-api version : 1.43.0
opentelemetry-sdk version : 1.43.0
opentelemetry-semantic-conventions: 0.64b0

======================================================================
E1 — Baseline: parent + child in same coroutine
======================================================================
  [parent] name='e1.parent'           span_id=2a751887  parent_id=None
  [child ] name='e1.child'            span_id=e82cf7e5  parent_id=2a751887
  [E1] child.parent_id=2a751887  expected=2a751887  → PASS

======================================================================
E2 — asyncio.create_task (no manual context): KIND-B pattern
======================================================================
  [parent] name='e2.parent'           span_id=b0f484aa  parent_id=None
  [child ] name='e2.child'            span_id=c2c2d15f  parent_id=b0f484aa
  [E2] child.parent_id=b0f484aa  expected=b0f484aa  → PASS

======================================================================
E3 — Task created BEFORE vs AFTER parent span activation
======================================================================
  [parent-before] name='e3.parent.before'    span_id=02b217e7  parent_id=None
  [child-before ] name='e3.child.before'     span_id=7c1b56da  parent_id=None
  [E3-before] child.parent_id=None  expected=02b217e7  → FAIL
  [parent-after ] name='e3.parent.after'     span_id=793a4022  parent_id=None
  [child-after  ] name='e3.child.after'      span_id=5abb5610  parent_id=793a4022
  [E3-after] child.parent_id=793a4022  expected=793a4022  → PASS

======================================================================
E4 — run_in_executor (thread pool), no manual context
======================================================================
  [parent] name='e4.parent'           span_id=3e1b61dc  parent_id=None
  [child ] name='e4.child.thread'     span_id=5dadee1a  parent_id=None
  [E4] child.parent_id=None  expected=3e1b61dc  → FAIL

======================================================================
E5 — Manual context capture + attach (the FIX)
======================================================================

  E5a — asyncio.create_task WITH manual context capture:
  [parent] name='e5a.parent'          span_id=b5e805a0  parent_id=None
  [child ] name='e5a.child.task'      span_id=22457b7d  parent_id=b5e805a0
  [E5a] child.parent_id=b5e805a0  expected=b5e805a0  → PASS

  E5b — run_in_executor WITH manual otel_context capture (closure fix):
  [parent] name='e5b.parent'          span_id=0f1a95e8  parent_id=None
  [child ] name='e5b.child.thread'    span_id=70501d30  parent_id=0f1a95e8
  [E5b] child.parent_id=0f1a95e8  expected=0f1a95e8  → PASS

======================================================================
E6 — SpanProcessor lifecycle: on_start vs on_end
======================================================================
  Opening e6.parent span...
  (inside parent span — parent span_id=bfe327db)
  Opening e6.child span...
  (inside child span — child span_id=ecffb8ca)
  e6.child span closed.
  e6.parent span closed.

  Lifecycle events captured:
  on_start  fired → span='e6.parent'  span_id=bfe327db
  on_start  fired → span='e6.child'  span_id=ecffb8ca
  on_end    fired → span='e6.child'  span_id=ecffb8ca
  on_end    fired → span='e6.parent'  span_id=bfe327db

  on_start events: 2  |  on_end events: 2
  on_start fires BEFORE span closes (live visibility available): YES
  on_end fires when span closes:                                 YES
  [E6] PASS — on_start IS available for live sink notification.

======================================================================
SPIKE COMPLETE
======================================================================
```

---

## Per-experiment analysis

### E1 — Baseline (same coroutine) — PASS

Sanity confirmed. `e1.child` parent_id `e82cf7e5` matches `e1.parent` span_id `2a751887`.
No surprises.

---

### E2 — `asyncio.create_task` (no manual context) — PASS

**This is the key KIND-B gate result.**

`e2.child` opened inside a spawned task (no manual context handling) correctly
carries parent_id `b0f484aa` = the Act-equivalent parent span `e2.parent`.

**Mechanism:** Python's `asyncio.create_task` copies the current `contextvars.Context`
at the moment of task creation. OTel stores its active span in a `contextvars.ContextVar`,
so the snapshot automatically includes the active span. The child task inherits it
and `start_as_current_span` correctly sees the parent.

**Practical implication:** As long as the KIND-B adapter calls `asyncio.create_task`
for its streaming sub-tasks WHILE INSIDE the Act span's `with` block, OTel context
propagates automatically — no manual threading required for this path.

---

### E3 — Timing of task creation vs parent span — PASS / FAIL

- **E3-before (FAIL):** Task created BEFORE the parent span is active: child is
  orphaned (`parent_id=None`). The context snapshot at task-creation time had no
  active span, so the task starts with an empty context.
- **E3-after (PASS):** Task created AFTER entering the parent span: child is
  correctly parented. Same mechanism as E2.

**Critical constraint:** Context propagation across `create_task` is snapshot-at-creation.
The natural KIND-B adapter structure (open Act span, then delegate streaming to tasks)
meets the E3-after condition automatically — but this must be stated explicitly in
design.md as a contract, not left implicit.

---

### E4 — `run_in_executor` (thread pool), no manual context — FAIL

Thread-pool executor does NOT copy `contextvars.Context` automatically (this is
a known Python behavior: `ThreadPoolExecutor` does not call `copy_context().run()`
before dispatching to threads). `e4.child.thread` is orphaned (`parent_id=None`).

This is the **failure boundary**: threads, unlike asyncio tasks, lose OTel context
without manual intervention.

---

### E5 — Manual fix — both PASS

- **E5a (asyncio task + manual attach):** PASS. Capturing `otel_context.get_current()`
  while inside the parent span, then `otel_context.attach(captured)` inside the task,
  correctly parents the child. (Note: for the KIND-B asyncio path, E2 already works
  without this — E5a validates the recovery pattern for edge cases where natural
  propagation can't be relied upon, e.g. tasks spawned outside the Act span's with-block.)

- **E5b (executor + closure-captured context + manual attach):** PASS. The working
  pattern for threads:
  ```python
  # Inside the Act span:
  captured_ctx = otel_context.get_current()   # snapshot while parent active
  def thread_fn():
      token = otel_context.attach(captured_ctx)  # via closure, not parameter
      try:
          with tracer.start_as_current_span("...") as s: ...
      finally:
          otel_context.detach(token)
  await loop.run_in_executor(None, thread_fn)
  ```
  **Key pitfall avoided:** the context must reach the thread via closure (or passed
  before task dispatch), NOT evaluated as a function argument evaluated in the thread,
  which runs in the wrong context.

---

### E6 — SpanProcessor lifecycle (on_start vs on_end) — PASS

`SpanProcessor.on_start` fires immediately when a span opens — BEFORE it closes.
`SpanProcessor.on_end` fires when it closes.

Both events are available. For the "Act in progress" live TUI/WS case (a 30s Act
span that must be surfaced live, not only on close), a custom `SpanProcessor`
overriding `on_start` gives the live-open signal. This resolves spike item 2 from
§3: live sinks do NOT need to wait for `on_end`. The schema can include a
`span_open` record (from `on_start`) and a `span_close` record (from `on_end`),
or the live sink can register for `on_start` and track open spans itself.

---

## VERDICT

**(B) — OTel context does NOT auto-propagate across thread boundaries
(`run_in_executor`); manual context capture/attach IS required for any thread-based
adapter path. E5b shows it works with the closure-capture pattern.**

**For the asyncio task path specifically (the primary KIND-B pattern), E2 shows
auto-propagation works — the §6 guarantee holds mechanically — but there is an
implicit timing constraint that E3 makes explicit: tasks must be spawned INSIDE the
Act span's `with` block for the snapshot to include the parent.**

**Summary of what design.md must add:**

1. **Asyncio task timing contract (E3 finding):** The KIND-B adapter MUST create its
   streaming sub-tasks inside the Act span's `with` block (after `tracer.start_as_current_span`
   has been entered), not before. This is the condition that makes `asyncio.create_task`
   auto-propagation work. State this as an adapter implementation invariant, not an
   optional best practice.

2. **Thread boundary rule (E4/E5b finding):** Any adapter path that dispatches work
   via `run_in_executor` (or any `ThreadPoolExecutor`) MUST explicitly capture
   `otel_context.get_current()` while inside the parent span, then `otel_context.attach()`
   that captured context inside the thread function (via closure). Document the closure
   pattern; warn against evaluating `otel_context.get_current()` as a thread-function
   parameter (it evaluates in the thread's empty context, not the captured one).

3. **Live sink processor hook (E6 finding):** Live sinks (TUI, WS) should subscribe
   to `SpanProcessor.on_start` for span-open signals, not wait for `on_end`. This
   resolves the "Act in progress" visibility problem without schema changes.
   The processor pipeline must therefore include a live-notification processor (like
   the `LifecycleTrackingProcessor` in the spike) in addition to the JSONL exporter.

---

## What design.md does NOT need to change

- The §6 "loop owns the tree, parent_span_id always valid" guarantee holds for the
  asyncio.create_task-based KIND-B pattern.
- The OTel SDK-in-process decision is confirmed correct — no surprises from the library.
- The `SimpleSpanProcessor` choice is valid for synchronous/live paths (no batch delay).
