"""
M2 Observability Spike — contextvars_spike.py
==============================================
THROWAWAY SPIKE — lives under spikes/, not src/.

Question: Does OTel context propagation correctly mint parent/child span
relationships across asyncio task / thread boundaries (the KIND-B pattern)?

Exercises:
  E1 — Baseline: parent + child in same coroutine.
  E2 — asyncio.create_task: child span opened in a spawned task, no manual ctx.
  E3 — Task created BEFORE vs AFTER parent span is active (timing sensitivity).
  E4 — loop.run_in_executor (thread pool): child span opened in thread, no manual ctx.
  E5 — Fix: manual context capture + attach for E2 (task) and E4 (executor).
  E6 — SpanProcessor lifecycle: confirm on_start vs on_end firing, with SimpleSpanProcessor.
"""

import asyncio
from opentelemetry import trace, context as otel_context
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def short(span_id: int | None) -> str:
    """Return last 8 hex digits of a span/trace id, or 'None'."""
    if span_id is None:
        return "None"
    return format(span_id, "016x")[-8:]


def parent_id(span) -> str:
    ctx = span.parent
    if ctx is None:
        return "None"
    return short(ctx.span_id)


def describe(label: str, span) -> str:
    return (
        f"  [{label}] name={span.name!r:20s}  "
        f"span_id={short(span.context.span_id)}  "
        f"parent_id={parent_id(span)}"
    )


def check_parent(label: str, child_span, parent_span) -> str:
    """Return PASS/FAIL based on whether child's parent_id matches parent's span_id."""
    expected = short(parent_span.context.span_id)
    actual = parent_id(child_span)
    verdict = "PASS" if actual == expected else "FAIL"
    return f"  [{label}] child.parent_id={actual}  expected={expected}  → {verdict}"


# ─────────────────────────────────────────────────────────────────────────────
# E6 — Custom SpanProcessor to track on_start / on_end lifecycle
# ─────────────────────────────────────────────────────────────────────────────

lifecycle_log: list[str] = []


class LifecycleTrackingProcessor(SimpleSpanProcessor):
    """Wraps SimpleSpanProcessor; logs on_start and on_end events."""

    def __init__(self, exporter):
        super().__init__(exporter)
        self._exporter = exporter

    def on_start(self, span, parent_context=None):
        lifecycle_log.append(
            f"  on_start  fired → span={span.name!r}  span_id={short(span.context.span_id)}"
        )
        # Do NOT call super().on_start — SimpleSpanProcessor has no on_start work to delegate.

    def on_end(self, span: ReadableSpan):
        lifecycle_log.append(
            f"  on_end    fired → span={span.name!r}  span_id={short(span.context.span_id)}"
        )
        super().on_end(span)


# ─────────────────────────────────────────────────────────────────────────────
# Provider + Exporter setup
# ─────────────────────────────────────────────────────────────────────────────

memory_exporter = InMemorySpanExporter()
lifecycle_exporter = InMemorySpanExporter()

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
provider.add_span_processor(LifecycleTrackingProcessor(lifecycle_exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("axiom.spike")


# ─────────────────────────────────────────────────────────────────────────────
# E1 — Baseline: same coroutine, no task boundary
# ─────────────────────────────────────────────────────────────────────────────


async def e1_baseline():
    print("\n" + "=" * 70)
    print("E1 — Baseline: parent + child in same coroutine")
    print("=" * 70)
    with tracer.start_as_current_span("e1.parent") as parent:
        with tracer.start_as_current_span("e1.child") as child:
            child_snap = child  # snapshot while alive
        print(describe("parent", parent))
        print(describe("child ", child_snap))
        print(check_parent("E1", child_snap, parent))


# ─────────────────────────────────────────────────────────────────────────────
# E2 — asyncio.create_task: child opened in spawned task, NO manual ctx
# ─────────────────────────────────────────────────────────────────────────────

e2_child_span = None
e2_parent_span = None


async def e2_child_task():
    global e2_child_span
    with tracer.start_as_current_span("e2.child") as s:
        e2_child_span = s


async def e2_no_manual_ctx():
    global e2_parent_span
    print("\n" + "=" * 70)
    print("E2 — asyncio.create_task (no manual context): KIND-B pattern")
    print("=" * 70)
    with tracer.start_as_current_span("e2.parent") as parent:
        e2_parent_span = parent
        task = asyncio.create_task(e2_child_task())
        await task
    print(describe("parent", e2_parent_span))
    print(describe("child ", e2_child_span))
    print(check_parent("E2", e2_child_span, e2_parent_span))
    return e2_parent_span, e2_child_span


# ─────────────────────────────────────────────────────────────────────────────
# E3 — Task created BEFORE vs AFTER parent span activation (timing)
# ─────────────────────────────────────────────────────────────────────────────

e3_before_child = None
e3_after_child = None


async def e3_child_task(label_ref: list):
    with tracer.start_as_current_span(f"e3.child.{label_ref[0]}") as s:
        label_ref.append(s)


async def e3_timing():
    global e3_before_child, e3_after_child
    print("\n" + "=" * 70)
    print("E3 — Task created BEFORE vs AFTER parent span activation")
    print("=" * 70)

    # BEFORE: task created before the parent span is entered
    before_ref: list = ["before"]
    task_before = asyncio.create_task(e3_child_task(before_ref))
    with tracer.start_as_current_span("e3.parent.before") as parent_before:
        await task_before
    e3_before_child = before_ref[1] if len(before_ref) > 1 else None

    print(describe("parent-before", parent_before))
    if e3_before_child:
        print(describe("child-before ", e3_before_child))
        print(check_parent("E3-before", e3_before_child, parent_before))
    else:
        print("  [E3-before] child task did not complete before check — unexpected")

    # AFTER: task created after the parent span is entered (same as E2)
    after_ref: list = ["after"]
    with tracer.start_as_current_span("e3.parent.after") as parent_after:
        task_after = asyncio.create_task(e3_child_task(after_ref))
        await task_after
    e3_after_child = after_ref[1] if len(after_ref) > 1 else None

    print(describe("parent-after ", parent_after))
    if e3_after_child:
        print(describe("child-after  ", e3_after_child))
        print(check_parent("E3-after", e3_after_child, parent_after))
    else:
        print("  [E3-after] child task did not complete before check — unexpected")


# ─────────────────────────────────────────────────────────────────────────────
# E4 — run_in_executor (thread pool): child in thread, NO manual ctx
# ─────────────────────────────────────────────────────────────────────────────

e4_child_span = None
e4_parent_span = None


def e4_thread_work():
    global e4_child_span
    with tracer.start_as_current_span("e4.child.thread") as s:
        e4_child_span = s


async def e4_executor_no_manual():
    global e4_parent_span
    print("\n" + "=" * 70)
    print("E4 — run_in_executor (thread pool), no manual context")
    print("=" * 70)
    loop = asyncio.get_event_loop()
    with tracer.start_as_current_span("e4.parent") as parent:
        e4_parent_span = parent
        await loop.run_in_executor(None, e4_thread_work)
    print(describe("parent", e4_parent_span))
    print(describe("child ", e4_child_span))
    print(check_parent("E4", e4_child_span, e4_parent_span))


# ─────────────────────────────────────────────────────────────────────────────
# E5 — Fix: manual context capture + attach
#    E5a: asyncio.create_task with explicit context
#    E5b: run_in_executor with copy_context()
# ─────────────────────────────────────────────────────────────────────────────

e5a_child_span = None
e5a_parent_span = None
e5b_child_span = None
e5b_parent_span = None


async def e5a_child_task_with_ctx(captured_ctx):
    """Child task that manually attaches the parent OTel context."""
    global e5a_child_span
    token = otel_context.attach(captured_ctx)
    try:
        with tracer.start_as_current_span("e5a.child.task") as s:
            e5a_child_span = s
    finally:
        otel_context.detach(token)


def make_e5b_thread_fn(captured_otel_ctx):
    """
    Return a thread-callable that closes over a pre-captured OTel context.
    The context is captured while the parent span is active (in the coroutine),
    then attached inside the thread so start_as_current_span sees the parent.
    This avoids the arg-evaluation-before-context-swap bug.
    """

    def _thread():
        global e5b_child_span

        token = otel_context.attach(captured_otel_ctx)  # from closure, not a param
        try:
            with tracer.start_as_current_span("e5b.child.thread") as s:
                e5b_child_span = s
        finally:
            otel_context.detach(token)

    return _thread


async def e5_manual_fix():
    global e5a_parent_span, e5b_parent_span
    print("\n" + "=" * 70)
    print("E5 — Manual context capture + attach (the FIX)")
    print("=" * 70)

    # E5a: asyncio.create_task with captured OTel context
    print("\n  E5a — asyncio.create_task WITH manual context capture:")
    with tracer.start_as_current_span("e5a.parent") as parent_a:
        e5a_parent_span = parent_a
        # Capture current OTel context while inside the parent span
        captured = otel_context.get_current()
        task = asyncio.create_task(e5a_child_task_with_ctx(captured))
        await task
    print(describe("parent", e5a_parent_span))
    print(describe("child ", e5a_child_span))
    print(check_parent("E5a", e5a_child_span, e5a_parent_span))

    # E5b: run_in_executor with explicit OTel context capture via closure.
    # Key: capture otel_context.get_current() while inside the parent span,
    # then pass it to make_e5b_thread_fn so the thread can attach it.
    print("\n  E5b — run_in_executor WITH manual otel_context capture (closure fix):")
    loop = asyncio.get_event_loop()

    with tracer.start_as_current_span("e5b.parent") as parent_b:
        e5b_parent_span = parent_b
        # Capture OTel context HERE — while the parent span is active
        captured_otel = otel_context.get_current()
        thread_fn = make_e5b_thread_fn(captured_otel)
        await loop.run_in_executor(None, thread_fn)
    print(describe("parent", e5b_parent_span))
    print(describe("child ", e5b_child_span))
    print(check_parent("E5b", e5b_child_span, e5b_parent_span))


# ─────────────────────────────────────────────────────────────────────────────
# E6 — SpanProcessor lifecycle: on_start vs on_end
# ─────────────────────────────────────────────────────────────────────────────


async def e6_lifecycle():
    print("\n" + "=" * 70)
    print("E6 — SpanProcessor lifecycle: on_start vs on_end")
    print("=" * 70)
    lifecycle_log.clear()

    print("  Opening e6.parent span...")
    with tracer.start_as_current_span("e6.parent") as parent:
        print(
            f"  (inside parent span — parent span_id={short(parent.context.span_id)})"
        )
        print("  Opening e6.child span...")
        with tracer.start_as_current_span("e6.child") as child:
            print(
                f"  (inside child span — child span_id={short(child.context.span_id)})"
            )
        print("  e6.child span closed.")
    print("  e6.parent span closed.")

    print("\n  Lifecycle events captured:")
    for entry in lifecycle_log:
        print(entry)

    on_start_count = sum(1 for e in lifecycle_log if "on_start" in e)
    on_end_count = sum(1 for e in lifecycle_log if "on_end" in e)
    print(f"\n  on_start events: {on_start_count}  |  on_end events: {on_end_count}")

    # Check ordering: for each span, does on_start precede on_end?
    spans_seen = {}
    ordered_ok = True
    for entry in lifecycle_log:
        if "on_start" in entry:
            sid = entry.split("span_id=")[1].strip()
            spans_seen[sid] = "started"
        elif "on_end" in entry:
            sid = entry.split("span_id=")[1].strip()
            if spans_seen.get(sid) != "started":
                ordered_ok = False
            else:
                spans_seen[sid] = "ended"
    # But NOTE: SimpleSpanProcessor has NO on_start hook by design.
    # We only override on_start in LifecycleTrackingProcessor.
    print(
        f"  on_start fires BEFORE span closes (live visibility available): {'YES' if on_start_count > 0 else 'NO — on_start NOT fired'}"
    )
    print(
        f"  on_end fires when span closes:                                 {'YES' if on_end_count > 0 else 'NO'}"
    )
    if on_start_count > 0:
        print("  [E6] PASS — on_start IS available for live sink notification.")
    else:
        print(
            "  [E6] NOTE — on_start was not observed; live sinks need on_end or alternative."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


async def main():

    print("=" * 70)
    print("M2 Observability Spike — OTel context propagation across boundaries")
    print("=" * 70)
    from importlib.metadata import version as pkg_version

    print(f"opentelemetry-api version : {pkg_version('opentelemetry-api')}")
    print(f"opentelemetry-sdk version : {pkg_version('opentelemetry-sdk')}")
    print(
        f"opentelemetry-semantic-conventions: {pkg_version('opentelemetry-semantic-conventions')}"
    )

    await e1_baseline()
    await e2_no_manual_ctx()
    await e3_timing()
    await e4_executor_no_manual()
    await e5_manual_fix()
    await e6_lifecycle()

    print("\n" + "=" * 70)
    print("SPIKE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
