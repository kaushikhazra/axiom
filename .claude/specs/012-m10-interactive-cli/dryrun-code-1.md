# Code Dry-Run Report #1

**Scope**: `012-m10-interactive-cli` — backend (`src/axiom/agent.py`, `src/axiom/router/{router,conductor_proxy}.py`, `src/axiom/tools/registry.py`, `src/axiom/providers/local_adapter.py`, `src/axiom/interface/web/*.py`, `src/axiom/interface/web_cli.py`, `scripts/tray_launcher.py`) and frontend (`web/`), plus end-to-end browser verification of the running app via the Playwright MCP server
**Design**: `.claude/specs/012-m10-interactive-cli/design.md`
**Reviewed**: 2026-07-28

All findings below were found and fixed in this same pass (verified via `npx tsc -b --noEmit`, `npm run lint`, `npm run build`, and the full backend suite — 635 passed, 5 skipped — after each fix). Nothing is outstanding.

---

## Bugs (will cause incorrect behavior)

### [B1] CopilotChat's input box rendered light-themed against a dark page
- **File**: `web/src/theme.css`
- **Pass**: Pass 1 (Design Conformance) / Pass 4 (Boundaries — visual)
- **What**: `.axiom-chat` overrode `--copilot-kit-background-color`/`--copilot-kit-secondary-color`/`--copilot-kit-primary-color`/`--copilot-kit-contrast-color`, but `@copilotkit/react-ui`'s own `styles.css` defines its light-theme defaults for `--copilot-kit-input-background-color` (`#fbfbfb`), `--copilot-kit-separator-color`, and `--copilot-kit-muted-color` separately — none of which were overridden.
- **Impact**: AC-07.4 requires a dark theme "on all technical surfaces"; the chat input box would render near-white against the dark chrome/background, a visible, testable violation.
- **Fix**: Added the three missing overrides (`--copilot-kit-input-background-color: var(--bg-inset)`, `--copilot-kit-separator-color: var(--border)`, `--copilot-kit-muted-color: var(--fg-muted)`) plus `--copilot-kit-secondary-contrast-color`, verified against the real variable names in `node_modules/@copilotkit/react-ui/dist/index.css`.

### [B2] CanvasPane silently lost all content on toggle-close/reopen
- **File**: `web/src/App.tsx`, `web/src/components/CanvasPane.tsx`
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: `App.tsx` conditionally rendered `{canvasOpen && <CanvasPane />}`. `CanvasPane` accumulates `CANVAS_BLOCK` events in local `useState`, with no external store to rehydrate from. Toggling the canvas closed unmounted the component (discarding state); toggling it back open remounted a fresh, empty instance — any blocks emitted before the close are gone, not just hidden.
- **Impact**: A real US-06 UX regression a user (or Playwright) would hit on the very first close/reopen of the canvas panel.
- **Fix**: `CanvasPane` now takes a `hidden: boolean` prop and returns `null` from its own render when hidden, but is unconditionally present in `App.tsx`'s tree — the component instance (and its `blocks` state) never unmounts across toggles. `TracePane` was deliberately left on conditional mount/unmount: closing it correctly tears down its WebSocket connection (no equivalent resource to leak), so unmounting is the right behavior there.

---

## Gaps (missing implementation)

### [G1] design.md/task.md drifted from the actual frontend implementation
- **File**: `.claude/specs/012-m10-interactive-cli/design.md` (Module Layout, §5, §8, Files Changed), `task.md` (item 20)
- **Pass**: Pass 1 (Design Conformance)
- **What**: The original design specified `useFrontendTool`/CopilotKit's Generative UI "Chat+" pane for `ApprovalPrompt.tsx`/`CanvasPane.tsx`. The actual implementation (D18's direct-agent discovery) subscribes directly to the `HttpAgent`'s raw AG-UI event stream (`agent.subscribe({ onCustomEvent })`) instead — a deliberate, better-fitting choice (those CopilotKit abstractions are built for LLM-invoked tool calls, not out-of-band `CustomEvent`s), but the design docs still described the old approach.
- **Design ref**: §5 (Tool-Approval UI Bridge), §8 (Canvas)
- **Fix**: Added D22 to the Decisions Log documenting the direct-subscribe approach and its rationale; updated the Module Layout comments, §5/§8 prose, and both Files Changed rows to match; updated `task.md` item 20's description.

---

## Warnings (potential issues)

None outstanding.

---

## Style (code quality, conventions)

### [S1] Stale comment in `agui_bridge.py` referencing `useFrontendTool`
- **File**: `src/axiom/interface/web/agui_bridge.py:100-102`
- **What**: A comment on the `TOOL_APPROVAL_REQUEST` emission described frontend consumption via "the frontend's useFrontendTool registration" — inaccurate after D18/D22 (direct `agent.subscribe`, not a CopilotKit frontend-tool). Fixed to describe the actual consumer.

### [S2] Stale comment in `conductor_proxy.py` referencing a removed `agent.py` constant
- **File**: `src/axiom/router/conductor_proxy.py:19-22`
- **What**: The `_PROVIDER_KIND` dict's comment claimed to "mirror agent.py's module-level `_PROVIDER_KIND` (kept in sync there)" — but `agent.py` no longer has that constant (it now reads `provider_kind` dynamically via `ConductorProxy.control_level`, per its own comment at agent.py:52-55). Fixed to describe the actual current relationship (this module is the single source).

### [S3] Frontend package name left as the Vite scaffold default
- **File**: `web/package.json:2`
- **What**: `"name": "web"` — the generic default from `npm create vite`. Renamed to `"axiom-web-ui"` for clarity; no functional effect (private package, not published).

---

## Browser Verification (Playwright, real Chrome instance)

Playwright's MCP tools weren't in this session's tool registry (server not connected at session start), so the harness's own Playwright MCP server (`http://localhost:8931/mcp`) was driven directly via the official `mcp` Python SDK client (Streamable HTTP) — same server, same browser, same tools, called via the wire protocol instead of the harness's tool-call abstraction.

Both `axiom-web` (`--provider local --ollama-host http://192.168.0.235:11434`) and `npm run dev` were running; the browser navigated to `http://localhost:5173/` (Vite dev server, D20's proxy).

### Bugs found and fixed via browser interaction (invisible to `tsc`/`curl`/unit tests)

### [B3] `<CopilotChat>` crashed at runtime: wrong CopilotKit provider
- **File**: `web/src/App.tsx`
- **What**: `<CopilotKitProvider>` (the `/v2` subpath component) does not set up the legacy context `CopilotChat`'s `useCopilotContext()` needs. First page load threw (visible only in `browser_console_messages`, not in `tsc` or a curl smoke test): `Error: Remember to wrap your app in a <CopilotKit> {...} </CopilotKit>`.
- **Impact**: The entire chat UI was non-functional — this is exactly the failure mode a `curl`-only smoke test structurally cannot detect, since it never renders React.
- **Fix**: Switched to `<CopilotKit>` (main `@copilotkit/react-core` entry), which composes `CopilotKitProvider` internally and additionally sets up the legacy context. `selfManagedAgents` (D18) is still valid — `CopilotKitProps extends CopilotKitProviderProps`. Documented as design.md D23.

### [B4] CopilotKit's built-in AG-UI Inspector intercepted clicks on the chrome bar
- **File**: `web/src/App.tsx`
- **What**: A floating "Web Inspector" overlay (`<cpk-web-inspector>`), enabled by default, sat over the `canvas`/`trace` toggle buttons and intercepted pointer events — real Playwright clicks timed out (`<cpk-web-inspector></cpk-web-inspector> intercepts pointer events`). A first attempted fix, `showDevConsole={false}`, did **not** resolve it (that prop only controls error toasts/banners per `<CopilotKit>`'s own JSDoc); `enableInspector={false}` is the prop that actually gates the inspector.
- **Impact**: The trace and canvas toggles were unusable in a real browser — again, undetectable without actually clicking them.
- **Fix**: Added `enableInspector={false}` (kept `showDevConsole={false}` too, for the toasts). Documented as design.md D23.

### Flows exercised end-to-end (all passed after the two fixes above)

| Flow | Result |
|------|--------|
| Page load / agent wiring | Full UI renders (chrome bar, provider selector, chat pane, canvas pane); 0 console errors |
| Chat + streaming (US-02) | Typed "Say hello in exactly three words." → assistant replied "Hi there.", rendered via real AG-UI SSE → `HttpAgent` → `CopilotChat` |
| Provider switch (US-05, D17) | Selected "local" in the dropdown; selection persisted (no revert) |
| Tool approval (US-03, D14) | Asked the agent to call `write_file`; approval card rendered with tool name + JSON args; clicked Approve; turn completed with the tool's result message — the full mid-turn event-queue path (D14) verified live |
| Canvas (US-06, D8/D13) | `write_file`'s output appeared as a `diff · tool_output` block with the correct content |
| Canvas persistence (B2 fix, this report) | Toggled canvas closed then reopened — the block was still there, confirming the earlier B2 fix holds under real interaction |
| Trace pane (US-04, D12/D21) | Toggled on; on a fresh single session, live spans rendered (`[run]`, `[perceive] (1.0ms)`, `[reason]`, ...) over the direct WebSocket connection. (A separate multi-session test run correctly showed the documented "trace unavailable" fallback — expected, since concurrent sessions collide on the single trace WS port per the accepted §2 limitation.) |

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 4 (fixed) | 1 (fixed) | 0 | 3 (fixed) |

**Verdict**: PASS — all findings fixed; re-verified via `tsc --noEmit`, `oxlint`, `vite build`, the full backend test suite, and end-to-end Playwright browser verification of all six DoD flows (chat/streaming, provider switch, tool approval, canvas, canvas persistence, trace) against a real running `axiom-web` + Vite dev server.
