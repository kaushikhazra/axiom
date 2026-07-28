# Design Dry-Run Report #1

**Document**: `.claude/specs/012-m10-interactive-cli/design.md`
**Reviewed**: 2026-07-28

---

## Critical Gaps (must fix before implementation)

### [C1] `stream_turn()` cannot deliver a mid-turn tool-approval event — the whole US-03 mechanism is unreachable as designed

- **Pass**: Pass 2 (Data Flow Trace) / Pass 6 (Concurrency & Ordering)
- **What**: §3's `stream_turn()` is an async generator that does `response = await asyncio.to_thread(session.handle_turn, user_input)` — it blocks on the **entire** turn completing before yielding a single event. §4's `make_ui_approval_fn(emit_event)` is invoked synchronously, *from inside* that blocked call (on the worker thread `asyncio.to_thread` runs on), whenever `GuardrailsGate` hits a `DESTRUCTIVE` tool mid-turn. The design states `emit_event` "pushes an AG-UI CUSTOM event onto the active session's outgoing stream — the same stream `stream_turn()` is yielding into" — but `stream_turn()`'s generator is *suspended awaiting the very call `emit_event` is nested inside*, so it has not reached (and cannot reach) a `yield` statement to emit anything until `handle_turn()` returns in full. There is no described mechanism (queue, threadsafe callback, second concurrent task) by which a synchronous call on a worker thread can inject an event into a generator that is parked on `await`ing that same thread.
- **Risk**: As designed, a `TOOL_APPROVAL_REQUEST` event is either never sent to the frontend (the user never sees the approval prompt, and `future.result(timeout=300)` in `approval_bridge.py` times out every single time, silently denying every destructive tool call) or the implementer discovers this is impossible during coding and has to redesign the streaming architecture mid-implementation — exactly the kind of design-time gap this review exists to catch before that happens. US-03 (the whole point of this milestone's Guardrails GATE integration) is not implementable against §3/§4 as written.
- **Fix**: Replace the linear `await asyncio.to_thread(...)` structure with a producer/consumer pattern: an `asyncio.Queue` (or equivalent) owned per-turn (or per-session), `emit_event` pushes onto it via `loop.call_soon_threadsafe`/`asyncio.run_coroutine_threadsafe` (since it's called from the worker thread), and `stream_turn()` runs `handle_turn()` and the queue-drain loop **concurrently** (e.g. `asyncio.gather` of a task running `handle_turn` and a task that `yield`s everything the queue produces until a sentinel signals the turn is done). Update §3's code sample and §4's `emit_event` description to reflect the actual mechanism — the current code sample is presented as "copy-paste-close to implementation" per this project's own design.md convention, so leaving it as-is will get built exactly as shown.

---

### [C2] Canvas routing (US-06) has no real data path — neither for tool output nor for the response text it's shown operating on

- **Pass**: Pass 2 (Data Flow Trace) / Pass 3 (Interface Contract Validation)
- **What**: Two distinct breaks in the same story:
  1. §7 states "`write_file`/`run_shell` tool results... are routed to canvas unconditionally" — but `WebSession.handle_turn()` → `Agent.run_turn()` returns only a single flattened response `str` (confirmed by reading `agent.py`'s existing `run()` contract, which `run_turn()` reuses unchanged per D3). Individual `ToolResult.output` values (from `ToolsPort`/`GuardrailsGate`-gated calls deep inside the PRAO loop) are never surfaced to the interface layer as a separate, addressable value — `canvas_routing.py` has nothing to apply its `write_file`/`run_shell` rule to.
  2. Even for the response-text half of D8 (fenced code blocks ≥15 lines), §3's `stream_turn()` code sample chunks and streams the **raw** `response` string directly — it never calls `canvas_routing.split_for_canvas()`. The prose immediately below the code block asserts the split happens "before emitting `TextMessageContentEvent`s," but the code shown does not do this. One of the two is wrong; as written, a reader implementing the code sample literally ships US-06 as dead code with an unreachable canvas pane.
- **Risk**: US-06 (canvas for structured output) does not function — neither its tool-output path (no data available) nor its response-text path (function never called). `CanvasPane.tsx` would have nothing to render.
- **Fix**: (a) Decide and specify how tool-level output reaches the interface layer — e.g., have the PRAO loop's `Observe` phase or the adapter's tool-dispatch path surface completed `ToolResult`s to a per-turn collector the interface layer can read after `handle_turn()` returns (or stream them as they occur, given C1's fix already requires a mid-turn event channel — the same queue could carry `ToolResult` events). (b) Correct §3's code sample to actually call `split_for_canvas()` on `response` before the chunking loop, and route extracted `CanvasBlock`s through the same event channel as C1's fix, as a `CUSTOM` AG-UI event carrying canvas payloads — consistent with the "Canvas-routing hook" paragraph's stated intent.

---

### [C3] `Agent`'s new `approval_fn` parameter has no specified default — a naive implementation breaks the CLI (regresses AC-03.4 / Constraint #4)

- **Pass**: Pass 3 (Interface Contract Validation) / Pass 5 (Failure Path Analysis)
- **What**: The Files Changed row for `agent.py` says "add `approval_fn` passthrough parameter," and §4 says the web session's `Agent` is "constructed with `GuardrailsGate(approval_fn=make_ui_approval_fn(...))` passed through." `GuardrailsGate.__init__` already defaults `approval_fn` to `_cli_prompt_approval` (confirmed by reading `guardrails.py`) — but the design never specifies what `Agent.__init__`'s new parameter defaults to, or how `Agent` forwards it to `GuardrailsGate` when the caller (i.e. `axiom-cli`, unchanged per D11) doesn't pass one. If implemented as `approval_fn: Callable | None = None` followed by `GuardrailsGate(auto_approve=..., approval_fn=approval_fn)` unconditionally, an explicit `None` overrides `GuardrailsGate`'s own default parameter value, sets `self._approval_fn = None`, and the very next `DESTRUCTIVE` tool call crashes with `TypeError: 'NoneType' object is not callable` inside `request_approval()` — for the **existing, unchanged CLI path**, since `cli.py` never passes `approval_fn` at all.
- **Risk**: Direct regression of `axiom-cli`'s M4 Guardrails GATE (Constraint #4: "No breaking change to `axiom-cli`"; AC-03.4: CLI approval "continues to function unchanged"). This is a one-line omission in the design that has an outsized, silent blast radius — it would pass any test that doesn't specifically exercise a `DESTRUCTIVE` tool call via plain `Agent()` construction with no `approval_fn`.
- **Fix**: Add one sentence to §4 or the Files Changed row: `Agent.__init__`'s new `approval_fn: Callable[[str, dict], bool] | None = None` parameter is forwarded to `GuardrailsGate` only when non-`None` — i.e. `GuardrailsGate(auto_approve=auto_approve_tools, **({"approval_fn": approval_fn} if approval_fn is not None else {}))`, so `GuardrailsGate`'s own default (`_cli_prompt_approval`) is preserved for every caller that doesn't explicitly override it.

---

### [C4] `ProviderSelector.tsx`'s "currently-active provider" display (AC-05.3) depends on an AG-UI `STATE` event that is never actually emitted anywhere in the design

- **Pass**: Pass 2 (Data Flow Trace)
- **What**: §6 says `ProviderSelector.tsx` "reads the currently-active provider from the AG-UI `STATE` event stream (`axiom.router.provider`, already emitted into traces per M6 — reused as a UI-facing state field here)." `axiom.router.provider` is an **observability trace attribute** (M2/M6) — it is written into M2's JSONL/OTel span records, not into any AG-UI protocol event. §3's `agui_bridge.py` code sample only constructs `RunStartedEvent`/`TextMessageStart/Content/EndEvent`/`RunFinishedEvent` — no `STATE` (or AG-UI's actual state-snapshot/state-delta event type) is ever constructed or emitted anywhere in the design. This is data the frontend is designed to consume that nothing in the design produces.
- **Risk**: AC-05.3 ("The currently-active provider... is visible in the UI, not just selectable") is not satisfiable as designed — `ProviderSelector.tsx` has no data source for it. If an implementer notices the gap, they'll have to invent a mechanism unreviewed by this dry-run; if they don't notice, the UI silently ships without this AC met.
- **Fix**: Either (a) have `stream_turn()` emit an AG-UI state event (its actual name per the `ag-ui-protocol` package's `ag_ui.core` types — confirm the exact event class, e.g. `StateSnapshotEvent`/`StateDeltaEvent`, rather than assuming a generic `STATE` type name) carrying `{"active_provider": router.conductor_provider}` at the start/end of each turn and after every `/api/provider` call, or (b) simplify: since `/api/provider`'s own response can just echo back the provider it set, and `ProviderSelector.tsx` already owns the selector's local state from the user's own selection — drop the "trace-derived visibility" framing and have the selector display whatever it last set (with the response payload as confirmation), removing the dependency on a trace attribute that was never designed to leave the observability subsystem.

---

## Warnings (should fix, may cause issues)

### [W1] Empty/whitespace-only user input isn't validated on the web turn-handling path

- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: `cli.py` explicitly checks `if not user_input: print(...); sys.exit(1)` before ever constructing an `Agent`. The design's `server.py` turn-handling route (§3) has no equivalent check described — an empty or whitespace-only message would flow straight into `session.handle_turn("")`.
- **Risk**: Undefined behavior for an empty turn — likely a wasted PRAO cycle, possibly a confusing empty-response UI state. Low severity (not a crash risk based on what's known about `PraoLoop`), but inconsistent with the existing CLI's explicit guard.
- **Suggestion**: Add the same empty-input check to the AG-UI turn endpoint in `server.py`, returning a `400` (consistent with how `/api/provider`'s validation error is already handled per the Error Handling table) rather than dispatching an empty turn.

### [W2] `_APPROVAL_TIMEOUT_SECS` and `_CHUNK_DELAY_SECS` are referenced but never given a concrete default in a config/constants section

- **Pass**: Pass 1 (Completeness Check) / Pass 7 (Edge Cases)
- **What**: §4's prose mentions "default 300s" once for the approval timeout; §3's `_CHUNK_DELAY_SECS` has no value mentioned anywhere, "configurable" is asserted but not via what mechanism (env var? `ObservabilityConfig`-style dataclass? hardcoded module constant?).
- **Risk**: Minor — an implementer has to invent both values and their configuration mechanism from scratch, which the M2 design (referenced as a style precedent throughout this design) was careful to pin down explicitly (e.g. `PER_QUERY_TIMEOUT_SECS`-style module constants named in M4's own requirement.md).
- **Suggestion**: Add a short "Configuration" subsection naming both constants, their default values, and whether they're module-level constants or exposed as `web_cli.py` CLI flags.

---

## Observations (worth discussing)

### [O1] The pending-approval registry is a single-process, in-memory global — fine for this milestone's scope, but worth a one-line constraint

`approval_bridge.py`'s `_pending: dict[str, Future[bool]]` is a module-level dict. This is consistent with axiom's single-user, locally-run scope (Constraint set implied throughout this spec and `007-m10-ui-landscape`'s form-factor recommendation), and is not a bug — but it does mean `axiom-web` cannot be run with `uvicorn --workers > 1` (a second worker process would have its own, disjoint `_pending` dict, so an approval POST routed to the wrong worker would 404). Worth a one-sentence note in §8 or the Error Handling table stating `axiom-web` must run single-process/single-worker, so nobody "optimizes" this later without realizing the approval mechanism depends on it.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 4        | 2        | 1             |

**Verdict**: FAIL — needs revision

All four Critical Gaps are concentrated in the same underlying issue: the design's streaming/event model (§3) is linear (await the full turn, then chunk-emit the result) but three separate stories — US-03's mid-turn approval event, US-06's canvas content (both the tool-output and response-text paths), and US-05's active-provider visibility — all need out-of-band events to reach the frontend *during or independent of* that linear flow, and no such channel is designed. Fixing C1 (the producer/consumer event channel) is the load-bearing fix; C2 and C4 are largely "route this data through the same channel C1's fix builds" once that channel exists. C3 is independent and small — a one-line default-forwarding fix to avoid a silent CLI regression.
