# Design Dry-Run Report #2

**Document**: `.claude/specs/012-m10-interactive-cli/design.md`
**Reviewed**: 2026-07-28

---

## Critical Gaps (must fix before implementation)

None. All four Critical Gaps from Report #1 are resolved:

- **C1** (mid-turn approval events unreachable) — fixed by D14: `stream_turn()` now runs the turn as a concurrent `asyncio.Task` and drains `session.event_queue` (populated thread-safely via `emit_event()`/`call_soon_threadsafe`) while the turn is in flight. Traced through end-to-end (worker-thread block on `future.result()` → queue put → generator yield → SSE → frontend POST → `future.set_result()` → worker thread unblocks) — the full round trip is now coherent.
- **C2** (canvas had no real data path) — fixed by D13/D15: tool-output routing now flows through a new `Agent._tool_outputs` collector (populated via `on_result` threaded to `ToolRegistry`, KIND-A only, explicitly descoped for KIND-B) and the returned `TurnResult.tool_canvas_blocks`; response-text routing is fixed by `stream_turn()` actually calling `split_for_canvas()` before chunking (§4), which Report #1 found was described in prose but never called in code.
- **C3** (silent CLI regression risk from `approval_fn`'s unspecified default) — fixed by D16: forwarded to `GuardrailsGate` only when non-`None`, preserving its own default for the unmodified CLI path.
- **C4** (`ProviderSelector.tsx` depended on a never-emitted AG-UI STATE event) — fixed by D17: the selector is now its own source of truth for what it displays, confirmed by `/api/provider`'s response rather than a phantom trace-derived event.

One thing worth naming: while re-verifying the C2 fix's wiring (`self._tool_outputs.append` as `on_result`), I caught that a bare `list.append` bound method doesn't match `on_result`'s two-argument call signature (`on_result(name, result)` vs. `append`'s one positional argument) — `self._tool_outputs.append` alone would raise `TypeError` on the very first tool call. This was caught and fixed in the design (now `lambda name, result: self._tool_outputs.append((name, result))`) before this report was written, so it is not listed as a fresh Critical here — noted for the record since it was a real bug, not a hypothetical one.

---

## Warnings (should fix, may cause issues)

### [W1] Double-submitting an approval decision isn't guarded — second `future.set_result()` call raises unhandled `InvalidStateError`

- **Pass**: Pass 2 (Data Flow Trace) / Pass 5 (Failure Path Analysis)
- **What**: `POST /api/approval/{approval_id}` (§5) calls `future.set_result(body.approved)` directly. `concurrent.futures.Future.set_result()` raises `InvalidStateError` if the future's result has already been set. A double-click on Approve/Deny in the frontend, a retried request (e.g. a flaky network causing the browser to resend the POST), or a user clicking both Approve and Deny in quick succession would all trigger a second `set_result()` call on the same `Future`.
- **Risk**: An unhandled `InvalidStateError` inside an `async def` route surfaces as a `500 Internal Server Error` to whichever request loses the race — a confusing failure for what's really a harmless duplicate click, and inconsistent with the design's own care elsewhere (e.g. the `404` for an already-resolved/expired approval_id) about giving approval-flow errors clean, specific status codes rather than raw exceptions.
- **Suggestion**: In `resolve_approval`, catch the case explicitly — e.g. check `future.done()` before calling `set_result()`, and return a clean `409 Conflict` ("approval already resolved") instead of letting the second call raise. Small, same-file fix, no architectural change needed.

---

## Observations (worth discussing)

None.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 0        | 1        | 0             |

**Verdict**: PASS WITH WARNINGS

All Report #1 findings are resolved and re-verified end-to-end (approval round trip, canvas dual-path wiring, CLI-default preservation, provider-display data source). One small new finding surfaced during re-verification of the approval flow: an unguarded double-submit on the approval-resolution endpoint. Fix is a few lines in `server.py`'s existing route, no design-level rework required.
