# M10 · Interactive CLI — Design

**Spec:** `012-m10-interactive-cli`
**Author:** Nira — 2026-07-27, revised 2026-07-28 (dryrun-design-1 fixes)
**Status:** DRAFT

---

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Backend integration goes through the **low-level `ag-ui-protocol` package**, hand-emitting AG-UI events from a new `src/axiom/interface/web/` module — **not** the official `copilotkit` PyPI package's `CopilotKitRemoteEndpoint`/`Action` abstractions. | Resolves **OQ-06**. `copilotkit`'s own abstractions are still LangGraph/LangChain-framed (research doc), and axiom's own architecture principle is "we own every decision point" (roadmap: controllability-by-construction) — the same reasoning that put OTel behind a hand-wired `SpanProcessor` in M2 rather than adopting an off-the-shelf tracing framework wholesale. `ag-ui-protocol` is pure Pydantic types + SSE encoding with zero orchestration-framework coupling, matching that precedent exactly. |
| D2 | Frontend is a plain **Vite + React + TypeScript** app (`web/`), using `@copilotkit/react-core`/`@copilotkit/react-ui` directly — **not** Next.js. | CopilotKit's React packages are framework-agnostic; Next.js's SSR/routing/server-actions machinery solves problems (multi-page routing, server-rendered pages, deployment to an edge network) axiom doesn't have — it's a single-page, single-user, locally-served assistant. Vite is the lighter, more honest fit. Don't over-design (CLAUDE.md coding principle). |
| D3 | `Agent.run()` (existing, one-shot, closes memory in `finally`) is **left unchanged in its public contract** (`-> str`). A new `Agent.run_turn()` + `Agent.end_session()` pair is added for multi-turn use. | Resolves the persistent-session blocker found while reading `agent.py`: `run()`'s `finally` block calls `self._memory_adapter.close()` on *every* call — calling `run()` twice on one `Agent` instance today would fail on the second call. US-01 needs many turns per `Agent` instance without tearing memory down between them. Splitting the method (rather than mutating `run()`'s contract) satisfies Constraint #4 (no breaking change to `axiom-cli`) while giving the web session manager the multi-turn lifecycle it needs. |
| D4 | Runtime provider switching (US-05) is implemented via a new `Router.set_forced_provider()` method plus a new `ConductorProxy` class — **`loop.py`/`PraoLoop` are not modified.** | Resolves **OQ-02**. `select_worker()`/`select_committee()` already re-read `self._forced_provider` fresh on every call — so Worker-side switching is nearly free (just needs a setter). The Conductor (bound to `perceive`/`reason`/`observe` in `PraoLoop`) is the harder case: it's resolved once at `Agent.__init__` time and handed to `PraoLoop` as a fixed object. Rather than touching `PraoLoop`'s constructor contract, a `ConductorProxy` — duck-typing the same `control_level`/`act`/`reason`/`perceive`/`observe` surface `RoutableAdapter` already defines — is handed to `PraoLoop` instead of a raw adapter. The proxy delegates to whichever adapter `Router` currently resolves as Conductor; `Agent.set_provider()` just calls `router.set_forced_provider()` + re-resolves. `PraoLoop` never knows switching happened. |
| D5 | `GuardrailsGate` (`axiom/tools/guardrails.py`) is **not modified at all**. The UI approval path is a new `approval_fn` implementation, passed into the existing `GuardrailsGate(approval_fn=...)` constructor parameter. | `GuardrailsGate` was already built (M4, D2) with `approval_fn: Callable[[str, dict], bool] = _cli_prompt_approval` as an injectable seam — exactly the extension point US-03 needs. |
| D6 | The UI-side approval function is **synchronous and blocking**, bridged to the async web server via a `concurrent.futures.Future` keyed by a generated `approval_id`, delivered to the frontend over the per-session event queue (D14) — mirroring the existing `anyio.to_thread.run_sync` bridge M4 already uses for the CLI's blocking `input()` call from KIND-B's async hook context. | `GuardrailsGate.request_approval()`'s signature is synchronous. The UI approval function only needs to block the calling thread until a frontend HTTP callback resolves a `Future` — no change to the bridging pattern already proven by M4. |
| D7 | **True token-level model streaming is out of scope for M10.** US-02 ships **chunked delivery of the already-complete response** (D15's `TurnResult.text`, split into word/sentence chunks and emitted as a sequence of AG-UI `TEXT_MESSAGE_CONTENT` delta events with a small inter-chunk delay) — not real per-token streaming from the provider. | AC-02.1 requires "streaming carried over AG-UI's protocol," not real-time model token emission. Real streaming needs adapter-level changes (Ollama's streaming API for KIND-A, the Claude Agent SDK's own streaming surface for KIND-B) that touch M6/M7's adapter contracts — genuinely new scope. Chunked-delivery gives the UI-responsiveness benefit US-02 asks for today; real streaming is Future Work. **REVISED post-M10 (2026-07-29):** the chunked delivery described here was REMOVED. Because the text is already complete when `stream_turn()` reaches it, splitting it into per-word deltas separated by `_CHUNK_DELAY_SECS` added pure latency and no information — measured at **10.5s on a 364-word answer** (36% of that turn's wall clock), growing linearly with length; Windows' ~15.6ms timer granularity inflated each 0.02s sleep to ~0.029s. `stream_turn()` now emits the whole response as a SINGLE `TEXT_MESSAGE_CONTENT` delta. The standing rule is **stream only when the backend genuinely streams** — when the adapters gain real token streaming (still Future Work, below), deltas must be yielded FROM that stream as tokens arrive, never synthesized from a finished string. |
| D8 | Canvas routing (US-06/OQ-04) uses a concrete, code-level predicate: `write_file`/`run_shell` tool output (D13, KIND-A only) and any fenced code block ≥ 15 lines in the assistant's response route to the canvas pane; everything else stays in chat. | Resolves OQ-04 with a testable rule instead of a vague "structured content" criterion. The 15-line threshold is a starting default — see Future Work. **REMOVED post-M10 (2026-07-29):** the canvas pane was removed at the user's request (#17), together with `canvas_routing.py`, `split_for_canvas()`, `CanvasBlock`, and the `CANVAS_BLOCK` events. All response text now renders inline in chat; #16's markdown rendering landed first precisely because the canvas had been the ONLY path that displayed long fenced blocks correctly. `write_file`/`run_shell` output is consequently no longer surfaced anywhere in the UI -- accepted knowingly. `TurnResult.tool_outputs` is retained as core data with no current consumer. |
| D9 | Canvas is **read-only for M10** (display only, no live editing). | Resolves OQ-05. Research confirmed CopilotKit's canvas pane exists but did not confirm live-editing capability. Editable canvas is Future Work, gated on a confirming spike. **REMOVED post-M10 (2026-07-29):** the canvas pane was removed at the user's request (#17), together with `canvas_routing.py`, `split_for_canvas()`, `CanvasBlock`, and the `CANVAS_BLOCK` events. All response text now renders inline in chat; #16's markdown rendering landed first precisely because the canvas had been the ONLY path that displayed long fenced blocks correctly. `write_file`/`run_shell` output is consequently no longer surfaced anywhere in the UI -- accepted knowingly. `TurnResult.tool_outputs` is retained as core data with no current consumer. |
| D10 | UI-side chat scrollback (US-01/OQ-01): the frontend keeps an **in-memory buffer for the current browser tab/connection only** (cleared on reload/close); on a fresh connection, the assistant's opening context comes from M3's `recall()` (same mechanism M8's INJECT already uses), not a replayed transcript. | Resolves OQ-01. Keeps the "memory-driven, not thread-log-driven" principle (AC-01.3) honest even within a single session's UI. |
| D11 | `axiom-cli` (existing) and the new web server are **two separate entry points**, both wired through `Agent`, sharing all core logic. `axiom-cli`'s `main()` is untouched; a new `axiom-web` script entry point is added. | Satisfies Constraint #4 directly. OQ-03 (whether the CLI is eventually retired) is explicitly left open. |
| D12 | The frontend connects **directly** to M2's existing WebSocket trace bridge (`ws://127.0.0.1:{ws_port}/?token=...`) for US-04, rather than the new FastAPI backend proxying trace records. The FastAPI backend exposes one small `GET /api/trace-endpoint` route returning `{ws_url, ws_token}`. | M2's `WsBridgeSink` (`004-m2-observability` US-08) is already a complete, secured, standalone transport — proxying it would duplicate a working mechanism for no benefit. **REVISED post-M10 (2026-07-29):** the transport is unchanged, but the faculty behind it is now built ONCE per process in `create_app`'s `_lifespan` and injected into every `Agent` (`Agent(faculty=...)`), not constructed per session. Everything a faculty owns is process-global -- the `WsBridgeSink` TCP port, and OTel's `TracerProvider` global slot, which silently ignores a second `set_tracer_provider()`. Per-session construction meant only the FIRST session bound `ws_port`; later sessions failed to bind, yet `/api/trace-endpoint` still returned their own dead token, which the live server rejected with `4001 Unauthorized`. The trace pane and PRAO phase indicator therefore worked in the first browser tab only and failed silently everywhere else (a page refresh re-rolls `threadId`, so it counted as a new tab). |
| D13 | Tool-output canvas routing (`write_file`/`run_shell`) is **KIND-A (local provider) only** for M10. | *(dryrun-design-1 C2 fix.)* Axiom's own `ToolRegistry.execute()` (KIND-A) is a single, addressable dispatch point that can report results via a callback. Claude's native `Write`/`Bash` tool results (KIND-B) flow through the Claude Agent SDK's own message stream, not axiom's `ToolsPort` contract — capturing them for canvas would require a deeper `ClaudeAdapter` change genuinely out of this milestone's scope. Honest, explicit descope rather than a silent gap: KIND-B users still get the fenced-code-block canvas path (D8's second rule), just not the tool-output path. |
| D14 | Mid-turn events (currently: tool-approval requests) travel over a **per-`WebSession` `asyncio.Queue`**, populated thread-safely via `loop.call_soon_threadsafe()` from `emit_event()` (invoked synchronously from the worker thread running `handle_turn()`), and drained **concurrently** by `stream_turn()`'s generator while `handle_turn()` runs as a separate `asyncio.Task` on a thread. | *(dryrun-design-1 C1 fix.)* The original design had `stream_turn()` `await`ing the entire turn before yielding anything — an approval request raised mid-turn, from inside that blocked call, had no path to reach the frontend. A queue drained concurrently with the turn task is the standard fix for "an async generator needs to yield things a blocking background operation produces partway through." |
| D15 | `Agent.run_turn()` returns a new `TurnResult(text: str, tool_outputs: list[tuple[str, ToolResult]])` dataclass — **not** a plain `str`, and **not** carrying `CanvasBlock`s directly. `Agent.run()`'s public contract stays `-> str` (`return self._execute_turn(user_input).text`). | *(dryrun-design-1 C2 fix, data-flow half; revised in dryrun-design-3 C1 to fix a layering violation.)* `canvas_routing.py`'s tool-output rule (D13) needs `ToolResult`s that are gathered *during* the turn but only need to be visible *after* it completes — richer than a raw string, but still a synchronous return value, not a second mid-turn channel (unlike approval, D14). `TurnResult` carries only raw core types (`ToolResult`, from `axiom/tools/port.py` — already part of `agent.py`'s existing import graph); it does **not** import `CanvasBlock` (an interface-layer type, `axiom/interface/web/canvas_routing.py`), since a core module importing from the interface layer would invert this project's core/interface dependency direction. The `write_file`/`run_shell` filter and `CanvasBlock` conversion happen in `agui_bridge.stream_turn()` (§4, interface-side), not in `Agent._execute_turn()`. Keeping `run()`'s signature unchanged preserves Constraint #4 exactly. |
| D16 | `Agent.__init__`'s new `approval_fn: Callable[[str, dict], bool] \| None = None` parameter is forwarded to `GuardrailsGate` **only when non-`None`** (`GuardrailsGate(auto_approve=..., **({"approval_fn": approval_fn} if approval_fn is not None else {}))`). | *(dryrun-design-1 C3 fix.)* An unconditional forward of a `None` default would override `GuardrailsGate`'s own default parameter value (`_cli_prompt_approval`), crashing the **existing, unmodified CLI path** on its first `DESTRUCTIVE` tool call. This one-line rule is the entire fix. |
| D17 | Provider-selector visibility (AC-05.3) is satisfied by **the selector's own local state**, set on user selection and confirmed by `/api/provider`'s response body — **not** a trace-derived AG-UI state event. | *(dryrun-design-1 C4 fix.)* The original design cited reusing `axiom.router.provider` (an M2 observability trace attribute) as an AG-UI-visible value, but nothing in the design actually emits an AG-UI state event carrying it. Rather than inventing a new event type and a new emission point for a value the UI itself already knows (it's the thing the user just clicked), the selector is simply the source of truth for what it displays, and the backend response confirms the change took effect (or the request failing surfaces as an error instead of a silent revert). **REMOVED post-M10 (2026-07-29):** the provider selector was removed at the user's request (#19), along with `POST /api/provider` and `WebSession.set_provider()`. Provider is the Router's policy decision (M6 RT-4/5/6). `Agent.set_provider()` / `Router.set_forced_provider()` deliberately remain — they still back the `--provider` flag on both entry points. Per-message targeting is being considered separately via `@agent` syntax (#20); note `set_provider()` is session-sticky and so does NOT serve that use case. |
| D18 | The frontend connects to the FastAPI backend via **`@ag-ui/client`'s `HttpAgent`, passed directly into CopilotKit's `selfManagedAgents` provider prop** — **no Node.js `CopilotRuntime` intermediary process.** `App.tsx` constructs `new HttpAgent({ url: "/api/agent/run", threadId })` and passes `selfManagedAgents={{ axiom: httpAgent }}` to `<CopilotKitProvider>`; `runtimeUrl` is omitted entirely. | *(Implementation-time discovery, not in the original design or research doc.)* CopilotKit's docs describe a Node `CopilotRuntime` (`copilotRuntimeNodeHttpEndpoint` + `@ag-ui/client`'s own `HttpAgent`) as the standard integration path, which would have added a second Node.js process beyond D2's Vite-only frontend. Inspecting the installed `@copilotkit/react-core@1.63.2` type definitions directly (`CopilotKitProviderProps`) found `selfManagedAgents?: Record<string, AbstractAgent>` — an officially-typed direct-agent mode requiring neither `runtimeUrl` nor a runtime process; `HttpAgent` (from `@ag-ui/client`) is itself just a thin `AbstractAgent` subclass that POSTs `RunAgentInput` and parses the SSE response, with no dependency on `CopilotRuntime`. It logs one `console.warn` about `selfManagedAgents` being an Enterprise Intelligence Platform feature when no `publicLicenseKey` is set — cosmetic only for this project's local/self-hosted, non-commercial deployment (§2's existing single-process scope), not a functional block. `agents__unsafe_dev_only` (the other direct-agent prop) was rejected — its name signals it is not meant for even self-hosted production use. |
| D19 | `POST /api/agent/run`'s request body is **`ag_ui.core.RunAgentInput` directly** (imported from the same `ag-ui-protocol` package D1 already depends on) — **not** the ad-hoc `TurnRequest{threadId, message}` schema originally planned. `server.py` extracts `thread_id = body.thread_id` and the latest message where `role == "user"` for `stream_turn()`'s `user_input` argument. | *(D18 follow-on.)* `HttpAgent.requestInit()` POSTs `JSON.stringify(prepareRunAgentInput(...))` — camelCase keys (`threadId`, `runId`, `forwardedProps`, ...) — and expects `Accept: text/event-stream` back. Verified directly via `ag_ui.core.RunAgentInput.model_config`: `alias_generator=to_camel, populate_by_name=True, validate_by_alias=True` — FastAPI parses `HttpAgent`'s exact wire body with zero custom aliasing code when the route parameter is typed as `RunAgentInput`. This is the same pattern already proven for the *outgoing* AG-UI events (`agui_bridge.py` already constructs `RunStartedEvent(threadId=..., ...)` using these models' camelCase Python field names, per D1) — now applied to the *incoming* side too, so both directions speak AG-UI's real wire contract instead of a hand-rolled one. |
| D20 | Browser-facing CORS is avoided by **Vite dev server proxying**: `web/vite.config.ts`'s `server.proxy` forwards `/api/*` to `http://127.0.0.1:8420` (the FastAPI backend), so the page's origin is always the Vite dev origin and neither server needs CORS middleware. | *(D18 follow-on — a gap the unit-test suite structurally cannot catch, since `TestClient` doesn't enforce CORS.)* Without this, the browser would see two origins (Vite's dev port and FastAPI's `8420`) and every direct `fetch()` call the frontend makes (`/api/approval/{id}`, `/api/provider`, `/api/trace-endpoint` — everything except the AG-UI turn call, which goes through `HttpAgent`) would fail CORS preflight in a real browser even though it passes in `TestClient`. Production static-file serving (FastAPI serving `web/dist/` directly, collapsing to one origin with no proxy needed) is Future Work — out of scope for M10's dev-server-based Playwright verification. |
| D21 | `GET /api/trace-endpoint` takes a **required `threadId` query parameter** and lazily creates/reuses that session via the same `_get_or_create_session()` helper the other routes already use, instead of scanning `_sessions.values()` for any live session. | *(D18 follow-on.)* The original design's route had no way to succeed on `TracePane.tsx`'s "fetch once on mount" (§6) — on a fresh page load, `_sessions` is empty until the *first chat turn* completes, so the route always returned `503` in the exact flow Playwright verification exercises. The frontend already has a `threadId` (generated once in `App.tsx` and reused for the `HttpAgent`, D18) before it mounts `TracePane`, so passing it through makes trace availability match `Agent` construction, not turn completion. |
| D22 | `ApprovalPrompt.tsx` and `CanvasPane.tsx` subscribe **directly to the `HttpAgent` instance's raw AG-UI event stream** (`useAgent({agentId: "default"})` from `@copilotkit/react-core/v2`, then `agent.subscribe({ onCustomEvent })`, matching on `event.name`) — **not** CopilotKit's `useFrontendTool`/tool-call rendering machinery. | *(D18 follow-on.)* `useFrontendTool` (and CopilotKit's activity-message renderers) are built for LLM-invoked tool calls (`TOOL_CALL_START`/`ARGS`/`END` AG-UI events) — the backend's approval and canvas signals are out-of-band `CustomEvent`s (`agui_bridge.py` already emits `CustomEvent(name="TOOL_APPROVAL_REQUEST", ...)`/`CustomEvent(name="CANVAS_BLOCK", ...)`, unchanged from the original design), which is a different event family. `AgentSubscriber.onCustomEvent` (from `@ag-ui/client`'s `AbstractAgent`) is the framework-agnostic, purpose-built hook for exactly this — matches D1's "own every decision point" precedent instead of routing a protocol-level event through a UI abstraction designed for a different purpose. |
| D23 | `<CopilotKit>` is constructed with **`enableInspector={false}`** (plus `showDevConsole={false}` for error toasts/banners) — the provider component used is `<CopilotKit>` (main `@copilotkit/react-core` entry) rather than `<CopilotKitProvider>` (`/v2` subpath) directly. | *(Both discovered via Playwright browser verification — invisible to `tsc`/`curl`/unit tests, since both are runtime-only failures with no type-level signal.)* (1) `<CopilotKitProvider>` alone left `<CopilotChat>` throwing "wrap your app in a `<CopilotKit>`" at runtime — `CopilotChat`'s `useCopilotContext()` needs the legacy context `<CopilotKit>` sets up *around* `CopilotKitProvider` (confirmed by reading `<CopilotKit>`'s own source: it renders `CopilotKitProvider` internally, then a `CopilotKitInternal` legacy-context wrapper around `children`). `CopilotKitProps extends CopilotKitProviderProps`, so `selfManagedAgents` (D18) is still valid on `<CopilotKit>`. (2) CopilotKit's built-in AG-UI Inspector (`<cpk-web-inspector>`, a floating "Web Inspector" button, enabled by default) intercepted pointer-events on the chrome bar's `canvas`/`trace` toggle buttons underneath it — real clicks (via Playwright) timed out with "`<cpk-web-inspector></cpk-web-inspector>` intercepts pointer events." First attempted fix (`showDevConsole={false}` alone) did NOT remove it — reading `<CopilotKit>`'s own source showed `showDevConsole` only toggles `ToastProvider`'s `enabled` flag; the inspector is gated by a *separate* `enableInspector` prop (confirmed in `CopilotKitProviderProps`'s JSDoc: "`showDevConsole` only controls error toasts/banners, not the inspector button", "Defaults to enabled" for `enableInspector`). `enableInspector={false}` is the actual fix; also a better fit for AC-07.4's minimal-chrome requirement regardless. |

---

## 1. Module Layout

```
src/axiom/interface/
    cli.py                  # UNCHANGED (M1, one-shot CLI)
    web/
        __init__.py
        server.py            # FastAPI app + routes
        session_manager.py   # per-connection persistent Agent + event queue (D3, D14)
        agui_bridge.py        # axiom turn -> AG-UI event translation (D14, D15)
        approval_bridge.py    # UI-backed GuardrailsGate approval_fn (D5, D6)
        canvas_routing.py     # chat-vs-canvas content predicate (D8, D13)
    web_cli.py                # `axiom-web` entry point (uvicorn launcher)
    tray_launcher.py          # `axiom-ui` entry point (pystray background launcher)

src/axiom/agent.py            # +run_turn(), +end_session(), +set_provider(),
                               # +TurnResult, +approval_fn/on-tool-output wiring (D3,D4,D15,D16)
src/axiom/router/
    router.py                 # +set_forced_provider()                       (D4)
    conductor_proxy.py         # ConductorProxy                               (D4)
src/axiom/tools/
    registry.py                # +on_result callback param                    (D13, D15)
src/axiom/providers/
    local_adapter.py            # threads on_result through to ToolRegistry    (D13)

web/                            # new top-level frontend (Vite+React+TS)
    package.json
    vite.config.ts
    public/
        manifest.json           # PWA manifest
    src/
        main.tsx
        App.tsx                  # CopilotKit provider + Chat+Canvas layout
        theme.css                # dark theme, monospace, density tokens (AC-07.4)
        components/
            ApprovalPrompt.tsx    # direct agent.subscribe(onCustomEvent) for US-03 (D22)
            TracePane.tsx          # M2 WS trace consumer (US-04)
            CanvasPane.tsx          # custom read-only canvas renderer, direct subscribe (US-06, D22)
            ProviderSelector.tsx    # US-05, local-state display (D17)
```

---

## 2. Configuration

New module-level constants (not exposed as CLI flags in M10 — revisit if real usage demands it):

| Constant | Location | Default | Purpose |
|---|---|---|---|
| `_APPROVAL_TIMEOUT_SECS` | `approval_bridge.py` | `300` | How long a pending tool-approval `Future` waits before denying-by-timeout (§4). |
| ~~`_CHUNK_DELAY_SECS`~~ | ~~`agui_bridge.py`~~ | ~~`0.02`~~ | **REMOVED** post-M10 — see D7. Response text is now emitted as a single delta. |
| ~~`_CANVAS_LINE_THRESHOLD`~~ | ~~`canvas_routing.py`~~ | ~~`15`~~ | **REMOVED** post-M10 with the canvas pane — see D8. |

**Deployment constraint** (dryrun-design-1 O1): `axiom-web` MUST run single-process (`uvicorn` default, no `--workers > 1`). `approval_bridge.py`'s pending-approval registry is an in-process dict — a second worker process would have a disjoint registry, and an approval POST routed to the wrong worker would 404. Documented here so this isn't "optimized" later without realizing the dependency. Consistent with this project's single-user, local-first scope — not a real limitation for the target deployment.

---

## 3. Persistent Session & Multi-Turn Agent Lifecycle (US-01)

**What**: `Agent.run()`'s current body:

```python
def run(self, user_input: str) -> str:
    try:
        ...  # loop.run(), timing
        return response_text
    except ...:
        return "[Error: ...]"
    finally:
        if self._faculty is not None:
            self._faculty.shutdown()
        asyncio.run(self._memory_adapter.consolidate())
        self._memory_adapter.close()
```

is split into a shared private helper and separate public entry points. The helper now returns the richer `TurnResult` (D15), not a plain string:

```python
@dataclass
class TurnResult:
    """Core-only types (D15, dryrun-design-3 C1) -- ToolResult lives in
    axiom/tools/port.py, already part of agent.py's import graph. No
    CanvasBlock (interface-layer) reference here; that conversion happens
    in agui_bridge.stream_turn() (S4), not in Agent."""
    text: str
    tool_outputs: list[tuple[str, ToolResult]]   # raw KIND-A tool results, empty for KIND-B

def _execute_turn(self, user_input: str) -> TurnResult:
    """The existing try/except body of run(), unchanged in content --
    no memory/faculty teardown here. self._tool_outputs (populated by the
    on_result callback threaded to ToolRegistry, D13) is snapshotted and
    cleared here so each turn's tool outputs don't leak into the next.
    Filtering to write_file/run_shell and canvas-worthiness is the
    interface layer's job (S4), not Agent's."""
    try:
        ...  # existing loop.run()/timing logic, producing response_text
        return TurnResult(text=response_text, tool_outputs=list(self._tool_outputs))
    except MaxCyclesExceededError as e:
        return TurnResult(text=f"[Error: max cycles exceeded -- {e}]", tool_outputs=[])
    except (AdapterError, RouterError) as e:
        return TurnResult(text=f"[Error: {e}]", tool_outputs=[])
    finally:
        self._tool_outputs.clear()

def run(self, user_input: str) -> str:
    """UNCHANGED public contract -- one-shot, tears down at the end.
    Used by axiom-cli (D11)."""
    try:
        return self._execute_turn(user_input).text
    finally:
        self._teardown()

def run_turn(self, user_input: str) -> TurnResult:
    """NEW -- multi-turn safe, richer return value. No teardown between calls."""
    return self._execute_turn(user_input)

def end_session(self) -> None:
    """NEW -- explicit teardown, called once when a web session ends
    (WebSocket/SSE disconnect). Idempotent, same as faculty.shutdown()
    already is."""
    self._teardown()

def _teardown(self) -> None:
    """Extracted from run()'s existing finally block, verbatim."""
    if self._faculty is not None:
        self._faculty.shutdown()
    asyncio.run(self._memory_adapter.consolidate())
    self._memory_adapter.close()
```

`Agent.__init__` gains `self._tool_outputs: list[tuple[str, ToolResult]] = []` and, when constructing a local adapter, passes `on_result=lambda name, result: self._tool_outputs.append((name, result))` through to `_make_local_adapter()` → `LocalAdapter(on_result=...)` → `ToolRegistry(on_result=...)` (D13). (Note: `on_result`'s declared signature is `Callable[[str, ToolResult], None]`, called as `on_result(name, result)` — `self._tool_outputs.append` alone is not a valid implementation of that signature, since `list.append` takes exactly one positional argument; the lambda wraps the two arguments into the tuple `append()` actually expects.) For the Claude (KIND-B) adapter, no `on_result` wiring is added — `tool_outputs` is always `[]` for KIND-B turns, per D13's explicit descope. `Agent`/`agent.py` has no dependency on `axiom.interface` anywhere in this wiring (dryrun-design-3 C1) — it only ever produces/collects `ToolResult`s, a type it already has access to.

**Why**: US-01 (AC-01.1–AC-01.3), US-06 (tool-output data collection, not routing policy), D3, D13, D15.

**How — session lifecycle in `session_manager.py`**:

```python
_SENTINEL = object()

class WebSession:
    """One per browser connection. Owns exactly one long-lived Agent AND
    the per-session event queue mid-turn signals (approvals) travel over."""

    def __init__(self, **agent_kwargs) -> None:
        self._loop = asyncio.get_running_loop()   # constructed from an async context
        self.event_queue: asyncio.Queue = asyncio.Queue()
        agent_kwargs["approval_fn"] = make_ui_approval_fn(self.emit_event)
        self._agent = Agent(**agent_kwargs)

    def emit_event(self, event: dict) -> None:
        """Thread-safe -- may be called from the worker thread running a
        turn (D14). Never called from the main event-loop thread directly."""
        self._loop.call_soon_threadsafe(self.event_queue.put_nowait, event)

    def handle_turn(self, user_input: str) -> TurnResult:
        return self._agent.run_turn(user_input)

    def close(self) -> None:
        self._agent.end_session()

    def set_provider(self, provider: str | None) -> None:
        self._agent.set_provider(provider)
```

`server.py` creates one `WebSession` per AG-UI connection and calls `.close()` on disconnect.

---

## 4. AG-UI Event Bridge (US-02, US-03 delivery, US-06 delivery)

**What**: `agui_bridge.py::stream_turn()` runs the turn as a background `asyncio.Task` and **concurrently drains** `session.event_queue`, so mid-turn events (currently: approval requests) reach the frontend while the turn is still in progress — fixing dryrun-design-1's C1.

```python
from ag_ui.core import (
    RunStartedEvent, RunFinishedEvent, CustomEvent,
    TextMessageStartEvent, TextMessageContentEvent, TextMessageEndEvent,
)
from ag_ui.encoder import EventEncoder

async def stream_turn(session: WebSession, user_input: str, thread_id: str):
    encoder = EventEncoder()
    run_id = new_run_id()
    yield encoder.encode(RunStartedEvent(thread_id=thread_id, run_id=run_id))

    # D14: run the turn on a worker thread as a Task, so this generator can
    # keep awaiting session.event_queue concurrently instead of blocking on
    # the whole turn before yielding anything.
    turn_task = asyncio.create_task(asyncio.to_thread(session.handle_turn, user_input))
    turn_task.add_done_callback(
        lambda _: session.loop.call_soon_threadsafe(session.event_queue.put_nowait, _SENTINEL)
    )

    while True:
        item = await session.event_queue.get()
        if item is _SENTINEL:
            break
        # item shape: {"type": "TOOL_APPROVAL_REQUEST", "approval_id": ..., ...} (S4)
        yield encoder.encode(CustomEvent(name=item["type"], value=item))

    turn_result: TurnResult = turn_task.result()  # re-raises any exception from handle_turn

    # US-06 -- canvas, both halves, only now that the turn has actually completed.
    # dryrun-design-3 C1: the write_file/run_shell filter + CanvasBlock conversion
    # live HERE (interface layer), not in Agent -- TurnResult only carries raw
    # ToolResults (D15), keeping agent.py free of any axiom.interface import.
    tool_canvas_blocks = [
        CanvasBlock.from_tool_result(name, result)
        for name, result in turn_result.tool_outputs
        if name in {"write_file", "run_shell"} and not result.denied
    ]
    chat_text, text_canvas_blocks = split_for_canvas(turn_result.text)   # D8, response-text rule
    for block in tool_canvas_blocks + text_canvas_blocks:                 # D13, tool-output rule
        yield encoder.encode(CustomEvent(name="CANVAS_BLOCK", value=block.to_dict()))

    message_id = new_message_id()
    yield encoder.encode(TextMessageStartEvent(message_id=message_id, role="assistant"))
    if chat_text:                                     # D7 (revised) -- ONE delta, no fake typing
        yield encoder.encode(TextMessageContentEvent(message_id=message_id, delta=chat_text))
    yield encoder.encode(TextMessageEndEvent(message_id=message_id))

    yield encoder.encode(RunFinishedEvent(thread_id=thread_id, run_id=run_id))
```

`server.py`'s turn-handling route validates non-empty input **before** calling `stream_turn()` — mirroring `cli.py`'s existing `if not user_input: ...` guard (dryrun-design-1 W1) — and returns `400` for empty/whitespace-only input instead of dispatching a turn.

**Why**: US-02 (AC-02.1–AC-02.3), US-03 delivery, US-06 delivery, D1, D7, D14, D15.

---

## 5. Tool-Approval UI Bridge (US-03)

**What**: `approval_bridge.py` provides a UI-backed `approval_fn` for `GuardrailsGate`, matching the exact signature `_cli_prompt_approval` already has:

```python
import uuid
from concurrent.futures import Future

_pending: dict[str, Future[bool]] = {}   # approval_id -> Future, per-process (see §2 constraint)

def make_ui_approval_fn(emit_event: Callable[[dict], None]) -> Callable[[str, dict], bool]:
    """emit_event is WebSession.emit_event (§3) -- thread-safe, pushes onto
    this session's event_queue, drained by stream_turn() (§4, D14)."""

    def _ui_prompt_approval(tool_name: str, arguments: dict) -> bool:
        approval_id = str(uuid.uuid4())
        future: Future[bool] = Future()
        _pending[approval_id] = future

        emit_event({
            "type": "TOOL_APPROVAL_REQUEST",
            "approval_id": approval_id,
            "tool_name": tool_name,
            "arguments": arguments,
        })

        try:
            return future.result(timeout=_APPROVAL_TIMEOUT_SECS)   # default 300s, §2
        except TimeoutError:
            return False   # denial-by-timeout -- never hangs the loop forever
        finally:
            _pending.pop(approval_id, None)

    return _ui_prompt_approval
```

`server.py` exposes `POST /api/approval/{approval_id}` (body: `{"approved": bool}`) — called by the frontend's `ApprovalPrompt.tsx` when the user clicks Approve/Deny. The route resolves the matching `Future`:

```python
@app.post("/api/approval/{approval_id}")
async def resolve_approval(approval_id: str, body: ApprovalDecision):
    future = _pending.get(approval_id)
    if future is None:
        raise HTTPException(404, "no such pending approval (already resolved or expired)")
    if future.done():
        # dryrun-design-2 W1: a double-click, retried request, or Approve+Deny
        # race would otherwise raise concurrent.futures.InvalidStateError
        # (set_result() on an already-resolved Future) as an unhandled 500.
        raise HTTPException(409, "approval already resolved")
    future.set_result(body.approved)
    return {"ok": True}
```

`WebSession.__init__` (§3) already wires `approval_fn=make_ui_approval_fn(self.emit_event)` into `agent_kwargs` before constructing `Agent`. `Agent.__init__` forwards it to `GuardrailsGate` per D16 (never overriding the default with an unconditional `None`).

**Why**: US-03 (AC-03.1–AC-03.4), D5, D6, D14, D16.

**Frontend** (`ApprovalPrompt.tsx`): subscribes directly to the agent's raw event stream (`agent.subscribe({ onCustomEvent })`, D22) for `event.name === "TOOL_APPROVAL_REQUEST"`, renders the tool name + arguments, and on click `POST`s to `/api/approval/{approval_id}`.

---

## 6. Reasoning Trace View (US-04)

Unchanged from the original design — no dryrun findings against this section.

**What**: no new backend transport. `server.py` adds one route, taking `threadId` so the session (and its `observability_config`) exists at mount time rather than only after the first turn (D21):

```python
@app.get("/api/trace-endpoint")
async def trace_endpoint(threadId: str):
    session = _get_or_create_session(threadId)
    config = session._agent.observability_config
    if config is None or config.ws_port is None:
        raise HTTPException(503, "observability not enabled")
    return {
        "ws_url": f"ws://{config.ws_host}:{config.ws_port}",
        "ws_token": config.ws_token,
    }
```

`TracePane.tsx` fetches this once on mount (passing the same `threadId` `App.tsx` generated for the `HttpAgent`, D18), then opens its own `WebSocket` directly to M2's `WsBridgeSink` (unchanged, D12) and renders incoming JSONL records, keyed by `span_id`/`parent_span_id` into a tree (AC-04.2), showing gap-marker records as a visible indicator (AC-04.3). The trace pane is a collapsible panel (AC-04.4), off by default, toggled from the UI chrome.

**Why**: US-04 (AC-04.1–AC-04.4), D12. This is exactly the "future rendering layer" M2's own US-08/AC-08.7 named and deferred.

**Precondition**: the web server must be launched with observability enabled and a WS port configured — `web_cli.py` defaults this on (unlike `axiom-cli`, where `--observe` defaults off), since a UI with an always-available-but-empty trace toggle is a worse experience than always running the (already async, non-blocking per M2's own invariants) trace sink.

---

## 7. Provider Selection (US-05)

**What — `router.py`**:

```python
def set_forced_provider(self, provider: str | None) -> None:
    """NEW. Same validation as Agent.__init__'s existing provider check --
    caller (agent.py) validates before calling this."""
    self._forced_provider = provider
```

**What — `conductor_proxy.py`** (new file):

```python
@dataclass
class ConductorProxy:
    """Duck-types RoutableAdapter's control_level/act/reason/perceive/observe
    surface by always delegating to Router's CURRENT conductor. Constructed
    once at Agent.__init__ time and handed to PraoLoop instead of a raw
    adapter -- PraoLoop never knows the target can change (D4)."""

    _router: Router

    @property
    def control_level(self) -> str:
        return _PROVIDER_KIND.get(self._router.conductor_provider, "KIND_A")

    def act(self, instruction: str) -> str:
        return self._router.select_conductor().act(instruction)

    def reason(self, context: str) -> object:
        return self._router.select_conductor().reason(context)

    def perceive(self, run_state: object) -> str:
        return self._router.select_conductor().perceive(run_state)

    def observe(self, result: str, run_state: object) -> object:
        return self._router.select_conductor().observe(result, run_state)
```

**What — `agent.py`**:

```python
def set_provider(self, provider: str | None) -> None:
    """NEW. AC-05.2 -- takes effect for the NEXT dispatch, no restart."""
    if provider is not None and provider not in ("claude", "local", "committee"):
        raise ValueError(f"unknown provider: {provider!r}")
    self._router.set_forced_provider(provider)
    self._router.select_conductor()   # cheap re-resolution -- _get() caches per provider name
```

`server.py` exposes `POST /api/provider {"provider": "claude" | "local" | "committee" | null}` calling `session.set_provider(...)` and responding `{"provider": provider}` on success or `400` on `ValueError` (Error Handling table). `ProviderSelector.tsx` treats its own last-set value as the source of truth for what it displays (D17) — it does **not** read provider state from any trace/AG-UI-state mechanism; the four selectable options are `claude` / `local` / `committee` / "Auto (Router default)" i.e. `null` (AC-05.1).

**Why**: US-05 (AC-05.1–AC-05.3), D4, D17.

---

## 8. Canvas (US-06)

**What — `canvas_routing.py`**:

```python
_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

@dataclass
class CanvasBlock:
    language: str
    content: str
    source: str   # "response_text" | "tool_output"

    def to_dict(self) -> dict: ...

    @classmethod
    def from_tool_result(cls, tool_name: str, result: ToolResult) -> CanvasBlock:
        # D13 -- write_file/run_shell only, called from agui_bridge.stream_turn() (S4)
        language = "diff" if tool_name == "write_file" else "shell-output"
        return cls(language=language, content=result.output, source="tool_output")

def split_for_canvas(response: str) -> tuple[str, list[CanvasBlock]]:
    """Returns (remaining_chat_text, canvas_blocks). D8's response-text rule."""
    canvas_blocks = []
    def _extract(match):
        code = match.group(2)
        if code.count("\n") >= _CANVAS_LINE_THRESHOLD:   # default 15, §2
            canvas_blocks.append(CanvasBlock(language=match.group(1) or "text",
                                              content=code, source="response_text"))
            return f"[see canvas: {match.group(1) or 'code'} block]"
        return match.group(0)   # short blocks stay inline
    chat_text = _FENCE_RE.sub(_extract, response)
    return chat_text, canvas_blocks
```

Both call sites are now real (dryrun-design-1 C2 fix) and both live in the interface layer, not core (dryrun-design-3 C1): `agui_bridge.stream_turn()` (§4) filters `turn_result.tool_outputs` to `write_file`/`run_shell` and calls `from_tool_result()` for each qualifying `ToolResult`, and separately calls `split_for_canvas()` on the assistant's response text before chunking it — emitting every resulting `CanvasBlock`, from either source, as a `CustomEvent(name="CANVAS_BLOCK", ...)`.

**Why**: US-06 (AC-06.1–AC-06.3), D8, D9, D13.

**Frontend** (`CanvasPane.tsx`): a custom React panel — not CopilotKit's Generative UI "Chat+" system — that subscribes directly to `CANVAS_BLOCK` `CustomEvent`s (D22) and accumulates them across the session. **Read-only** (D9): a monospace, non-editable `<pre>` view (no syntax highlighting — not required by any AC, and pulling in a highlighter library was judged over-scope for M10), tagged by `source` so tool-output blocks (e.g. shell output) are visually distinct from response-text code blocks. No save/edit affordance is built in M10.

---

## 9. Deployment & Visual Style (US-07)

**What — `web_cli.py`** (new `axiom-web` entry point):

```python
def main() -> None:
    parser = argparse.ArgumentParser(prog="axiom-web", description="Axiom -- web UI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8420)
    ...
    uvicorn.run(app, host=args.host, port=args.port)   # single-process, no --workers (§2)
```

Binds `127.0.0.1` by default (LAN exposure is an explicit `--host 0.0.0.0`-style opt-in).

**PWA**: `web/public/manifest.json` (name, icons, `display: "standalone"`) + `vite-plugin-pwa` generating the service worker — gives the installable, own-window behavior AC-07.2 asks for.

**Tray launcher** (`scripts/tray_launcher.py`, `pystray`): starts `axiom-web` as a subprocess, opens the default browser to it, and offers Start/Stop/Open/Quit from a system-tray icon.

**Visual style — `web/src/theme.css`** (AC-07.4, all four sub-criteria made concrete):

```css
:root {
  color-scheme: dark;
  --bg: #0d1117;
  --fg: #c9d1d9;
  --font-mono: "JetBrains Mono", "Fira Code", ui-monospace, monospace;
  --font-ui: var(--font-mono);   /* AC-07.4: monospace on ALL technical surfaces */
  --space-unit: 4px;              /* dense spacing scale, not an 8pt airy grid */
  --chrome-height: 40px;          /* minimal header/toolbar height */
}
```

- Dark default: `color-scheme: dark`, no light-theme toggle shipped in M10.
- Monospace on technical surfaces: `--font-mono` applied to `TracePane`, `CanvasPane`, and all chat code blocks; `--font-ui` (also monospace) applied to the chat pane's own UI chrome.
- Density: `--space-unit: 4px` base spacing scale, tight line-height on the trace tree.
- Minimal chrome: a single `--chrome-height: 40px` top bar (provider selector, trace toggle, canvas toggle) — no sidebar, no branding splash.

**Why**: US-07 (AC-07.1–AC-07.4), D2.

---

## Error Handling

| Failure | Handling |
|---|---|
| Empty/whitespace-only user input | `server.py`'s turn route rejects with `400` before calling `stream_turn()` — mirrors `cli.py`'s existing guard (§4). |
| Approval request times out (`_APPROVAL_TIMEOUT_SECS`, default 300s) | `approval_fn` returns `False` (deny-by-timeout) — never hangs the PRAO loop indefinitely. |
| Frontend disconnects mid-approval | The pending `Future` is left unresolved until timeout; `WebSession.close()` does not force-resolve it. |
| Approval decision submitted twice (double-click, retry, race) | `resolve_approval` checks `future.done()` and returns `409` instead of letting a second `set_result()` raise `InvalidStateError` as an unhandled `500` (dryrun-design-2 W1). |
| WS trace bridge unreachable (observability disabled or port closed) | `TracePane.tsx`'s `/api/trace-endpoint` fetch or the subsequent WS connection fails; the pane shows a "trace unavailable" state instead of a broken/silent panel. |
| `set_provider()` called with an invalid value | Raises `ValueError` — `server.py`'s `/api/provider` route catches this and returns `400`, not a `500`. |
| `RouterError`/`AdapterError`/`MaxCyclesExceededError` during `run_turn()` | Caught inside `_execute_turn()` (§3), returned as `TurnResult(text="[Error: ...]", tool_outputs=[])` — streamed to chat as the assistant's message, not a broken connection. |
| `axiom-web` run with multiple workers | Not handled defensively — documented as an unsupported deployment shape (§2) rather than guarded against at runtime, consistent with this project's "don't add validation for scenarios that can't happen [in the supported deployment]" principle. |

---

## Files Changed

| File | Change | AC Trace |
|------|--------|----------|
| `src/axiom/agent.py` | Add `TurnResult`, `_execute_turn()`, `run_turn()`, `end_session()`, `_teardown()`, `set_provider()`; construct `ConductorProxy` instead of a raw conductor adapter for `PraoLoop`; add `approval_fn`/tool-output-collector wiring (D16, D13). | US-01, US-05, US-06 (D3, D4, D13, D15, D16) |
| `src/axiom/router/router.py` | Add `set_forced_provider()`. | US-05 (D4) |
| `src/axiom/router/conductor_proxy.py` | New — `ConductorProxy` class. | US-05 (D4) |
| `src/axiom/tools/registry.py` | Add optional `on_result: Callable[[str, ToolResult], None] \| None` param to `__init__`; `execute()` invokes it for `write_file`/`run_shell` results. | US-06 (D13) |
| `src/axiom/providers/local_adapter.py` | Thread `on_result` through `LocalAdapter.__init__` to its `ToolRegistry` construction. | US-06 (D13) |
| `src/axiom/interface/web/__init__.py` | New — package init. | US-07 |
| `src/axiom/interface/web/server.py` | New — FastAPI app: AG-UI turn endpoint accepting `ag_ui.core.RunAgentInput` directly (D19, with empty-input validation), `/api/approval/{id}`, `/api/provider`, `/api/trace-endpoint?threadId=` (D21). | US-02, US-03, US-04, US-05 |
| `src/axiom/interface/web/session_manager.py` | New — `WebSession` (D3 multi-turn Agent wrapper + D14 event queue). | US-01, US-03 |
| `src/axiom/interface/web/agui_bridge.py` | New — `stream_turn()`: concurrent turn-task + event-queue drain (D14), canvas emission (D8/D13), single-delta response emission (D7 as revised). | US-02, US-03, US-06 |
| `src/axiom/interface/web/approval_bridge.py` | New — UI-backed `approval_fn` + pending-`Future` registry (D5, D6). | US-03 |
| ~~`src/axiom/interface/web/canvas_routing.py`~~ | **DELETED** post-M10 with the canvas pane — see D8. | ~~US-06~~ |
| `src/axiom/interface/web_cli.py` | New — `axiom-web` entry point (single-process uvicorn launcher). | US-07 (D11) |
| `pyproject.toml` | Add `axiom-web`/`axiom-ui` script entries; add `fastapi`, `uvicorn`, `ag-ui-protocol`, `pystray` dependencies. | US-07 |
| `src/axiom/interface/tray_launcher.py` | New — `pystray` background launcher, `axiom-ui` entry point. | US-07 |
| `web/package.json` | New — Vite + React + TS + `@copilotkit/react-core`/`@copilotkit/react-ui` project. | US-07 (D2) |
| `web/vite.config.ts` | New — Vite config + `vite-plugin-pwa` + dev-server `/api` proxy to `http://127.0.0.1:8420` (D20, no CORS middleware needed). | US-07 |
| `web/public/manifest.json` | New — PWA manifest. | US-07 (AC-07.2) |
| `web/src/App.tsx` | New — `<CopilotKit selfManagedAgents={{ default: httpAgent }} enableInspector={false} showDevConsole={false}>` (D18, D23; no `runtimeUrl`/Node runtime), chat+canvas layout, top chrome bar. | US-01, US-06, US-07 |
| `web/src/theme.css` | New — dark/monospace/density design tokens. | US-07 (AC-07.4) |
| `web/src/components/ApprovalPrompt.tsx` | New — direct `agent.subscribe(onCustomEvent)` HITL rendering for US-03 (D22, not `useFrontendTool`). | US-03 |
| `web/src/components/TracePane.tsx` | New — direct WS consumer of M2's trace bridge. | US-04 |
| `web/src/components/CanvasPane.tsx` | New — custom read-only canvas renderer (direct `agent.subscribe`, D22, not CopilotKit's Generative UI system), tagged by block source. | US-06 |
| `web/src/components/ProviderSelector.tsx` | New — provider dropdown, local-state display (D17), calls `/api/provider`. | US-05 |

---

## Future Work (Out of Scope)

- **Real token-level model streaming** (D7) — adapter-level streaming for KIND-A (Ollama) and KIND-B (Claude Agent SDK). Natural M10.1 follow-up.
- **KIND-B (Claude) tool-output canvas routing** (D13) — would need a `ClaudeAdapter`-level hook into the Agent SDK's own message stream to capture `Write`/`Bash` results; deferred as a distinct, deeper piece of work.
- **Editable canvas** (D9) — live-editing support, gated on confirming CopilotKit actually supports it.
- **Voice** — explicitly descoped by Kaushik for this milestone.
- **Tauri desktop packaging** — noted as a plausible later upgrade; not attempted here.
- **`axiom-cli` retirement decision** — OQ-03 remains open.
- **Canvas line-count threshold tuning** (`_CANVAS_LINE_THRESHOLD = 15`) — a starting default; revisit once real usage shows whether it's routing the right content.
- **Multi-worker `axiom-web` deployment** — would require moving `approval_bridge.py`'s pending-approval registry out of in-process memory (e.g. a shared store) — not needed at this project's current single-user, single-process scope (§2).
