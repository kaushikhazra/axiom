# M10 · Interactive CLI — Requirements

**Spec:** `012-m10-interactive-cli`
**Milestone:** M10 — "Interactive CLI. Replace the M1 one-shot test CLI with a real, shippable interface." (`001-agent-core-roadmap.md`)
**Author:** Nira — 2026-07-27
**Status:** DRAFT

---

## Purpose

Axiom's interface today is `axiom-cli` (`src/axiom/interface/cli.py`): a one-shot argparse command — parse a single instruction, run one turn, print, exit. It was always scoped this way deliberately (`001-agent-core-roadmap.md`: "M1 interface — LOCKED CLI only (no web surface at M1)"), but it was never meant to be the shipped product. M10 replaces it with a persistent, genuinely polished interface — Kaushik's own framing: "folks are building quite good solutions, very lucrative, we need to build nice UI," explicitly rejecting a terminal TUI upgrade as "not impressive."

**Frontend/backend decision is already locked**, via `.claude/research/007-m10-ui-landscape-2026-07-27.md` (revised 2026-07-27 after a deep-dive prompted by Kaushik's own questions on customization depth, the no-session/voice-assistant paradigm, and canvas support): **CopilotKit + the AG-UI protocol**, not Chainlit, not a TUI, not Electron. The deciding factors, in brief (full rationale and citations in the research doc):
- CopilotKit ships composable React hooks/components, not a pre-built app shell — so a "no browsable session list, one persistent assistant" experience is native to how it's built, not a workaround against a default chat-app UI.
- CopilotKit's Generative UI ships a first-party "Chat+" canvas pane — the Claude-Artifacts/ChatGPT-Canvas pattern the leading reuse alternative (Chainlit) explicitly closed as "not planned."
- Python integration is real and documented at two levels: the official `copilotkit` PyPI package (`CopilotKitRemoteEndpoint`/`Action`/`add_fastapi_endpoint`, confirmed LangGraph-optional via a working code sample) and the framework-agnostic `ag-ui-protocol` PyPI package (pure Pydantic event/protocol types, no orchestration framework dependency at all) — the latter is the natural integration point for axiom's own bespoke PRAO loop, the same way M2's trace is hand-emitted today.
- Tool-approval human-in-the-loop has a real, documented precedent for a custom (non-LangGraph) Python agent loop — CopilotKit's Pydantic AI integration — via name-matched frontend/backend tool registration.

**Form factor is also locked**: a self-hosted web app (FastAPI backend + the CopilotKit-based frontend), installable as a PWA, with a `pystray` tray launcher for background presence — not a desktop-app wrapper (Electron/Tauri) and not a TUI. Tauri is noted in the research as a plausible later upgrade, not part of this milestone.

**Voice was explicitly descoped** for this milestone by Kaushik ("skip the voice conversation for now") — deferred to a later pass, not part of M10's scope.

---

## User Stories

---

### US-01 — Persistent assistant session, no browsable session list

**As** a user of axiom,
**I want** a single continuous assistant view with no thread/session switcher or "new chat" list,
**so that** the interface matches what axiom actually is — one persistent assistant whose memory (M3) carries continuity, not a multi-thread chatbot I have to manage.

#### Acceptance criteria

- AC-01.1: The UI never renders a thread list, session switcher, or "start new chat" as a primary UI element — per the research doc's structural finding, this is achieved by never building one (CopilotKit has no default app shell to suppress), not by hiding/disabling a built-in one.
- AC-01.2: On app load or reconnect, the UI resumes the same single, continuous conversation view.
- AC-01.3: Cross-session continuity is sourced from M3's `recall()` (memory), consistent with M8's INJECT mechanism — the UI does not maintain its own independent, UI-side persisted chat transcript as the source of "history."
- AC-01.4: The exact scrollback behavior within a single connected session (whether the UI keeps a local in-memory buffer for the live session, versus re-querying memory on every reconnect) is a design-time decision — see OQ-01.

---

### US-02 — Streaming responses

**As** a user,
**I want** the Reasoner's output to appear token-by-token as it's produced,
**so that** interacting with axiom feels responsive, not a long silent wait followed by a wall of text.

#### Acceptance criteria

- AC-02.1: Streaming is carried over AG-UI's own event protocol (`ag_ui.core`/`ag_ui.encoder`, SSE-based per research) — no separate, axiom-specific streaming transport is built.
- AC-02.2: Streaming behavior is uniform across all three `--provider` values (`claude`/`local`/`committee`, M6/M7) from the UI's perspective — provider-specific KIND-A/KIND-B differences (per `architecture.md`) do not leak into the UI-facing event contract.
- AC-02.3: Whether the backend integration goes through the `copilotkit` package's abstractions or hand-emits `ag-ui-protocol` events directly from the PRAO loop is a design-time decision — see OQ-06.

---

### US-03 — Live tool-approval rendering (Guardrails GATE)

**As** a user,
**I want** a `DESTRUCTIVE` tool-call approval prompt (M4's Guardrails GATE) rendered in the UI itself,
**so that** I review and approve/deny consequential actions from the same interface I'm talking to axiom in, not a separate terminal.

#### Acceptance criteria

- AC-03.1: `GuardrailsGate.request_approval()` (`006-m4-tools`, the single approval seam per that spec's US-03/AC-03.1) gains a UI-capable implementation. The seam itself — and the KIND-A/KIND-B contracts that call through it — is reused unchanged; M10 plugs a new approval backend into the existing seam, it does not modify `GuardrailsGate`'s classify/approve contract.
- AC-03.2: The UI-side approval flow uses AG-UI's human-in-the-loop pattern: a frontend tool/action registered with a name matching the backend's pending approval request (the name-matched convention documented in the research doc's Pydantic AI precedent), rendering the tool name and its arguments, and capturing an approve/deny decision.
- AC-03.3: Approval and denial continue to round-trip through M4's existing contract unchanged: `ToolResult(denied=True, ...)` for KIND-A, a `PreToolUse` hook `deny` decision for KIND-B (`006-m4-tools` AC-03.3, AC-06.2). M10 changes where the human decision originates, not what happens with it afterward.
- AC-03.4: `axiom-cli`'s existing stdin-based approval prompt (`006-m4-tools` US-03) continues to function unchanged for CLI/headless use — the UI is an additional approval channel plugged into the same seam, not a replacement that breaks the existing CLI. (Whether the CLI itself remains a supported entry point long-term, or is eventually retired in favor of the UI, is out of this milestone's scope — see OQ-03.)

---

### US-04 — Reasoning trace view

**As** a user,
**I want** to see axiom's phase-span reasoning trace (perceive → reason → act → observe) live in the UI,
**so that** I can watch it think, the same visibility a developer gets today from the JSONL trace file or the M2 TUI sink.

#### Acceptance criteria

- AC-04.1: The trace view is a consumer of M2's **existing** WebSocket bridge sink (`004-m2-observability` US-08: localhost-only, token-authenticated, streams JSONL trace records) — M10 does not build a new trace transport; it builds a UI renderer for the transport that already exists. This is the exact scope M2's own US-08 (AC-08.7) deferred: "There is no web dashboard served from this port... A future rendering layer (browser UI) is out of scope for M2" — M10 is that future rendering layer.
- AC-04.2: Spans are rendered nested by `parent_span_id` (M2 AC-02.5), so the perceive/reason/act/observe hierarchy is visible as a tree, not a flat scrolling log.
- AC-04.3: Gap-marker records (M2 AC-05.4, emitted when the lossy WS sink drops records under load) are rendered as a visible "trace gap" indicator, not silently dropped from the UI or allowed to render a misleadingly-complete tree.
- AC-04.4: The trace view is optional/collapsible — it does not have to be visible at all times to use the assistant (consistent with M2's own sinks being optional at runtime, AC-08.6).

---

### US-05 — Provider selection from the UI

**As** a user,
**I want** to switch between `claude` / `local` / `committee` providers from the UI,
**so that** I don't need to stop and restart the backend with a different `--provider` flag to change providers mid-use.

#### Acceptance criteria

- AC-05.1: A provider selector in the UI offers the same three forced-provider values the CLI's `--provider` flag already supports (`claude`, `local`, `committee` — M6/M7), plus the Router's own default policy-driven mode (no forced provider — M6 requirement.md's documented default when `--provider` is omitted).
- AC-05.2: Selecting a provider from the UI takes effect for the next dispatch without restarting the backend process. **The exact mechanism is a design-time decision, not fixed here** — today, `forced_provider` is fixed at `Agent.__init__` time (M6 requirement.md, RT-8); M10 needs either a new runtime-mutable Router entry point or an equivalent, and this needs to be resolved in `design.md` — see OQ-02.
- AC-05.3: The currently-active provider (and, for a fallback event, the provider actually used — M6's existing `axiom.router.provider` trace attribute) is visible in the UI, not just selectable.

---

### US-06 — Canvas for structured output

**As** a user,
**I want** structured output axiom produces (code, documents, or other non-conversational content) to appear in a dedicated canvas pane,
**so that** it isn't squeezed into chat message text the way a plain chatbot would render it.

#### Acceptance criteria

- AC-06.1: The canvas pane uses CopilotKit's Generative UI "Chat+" surface (research doc) — a side-by-side/multi-pane layout with chat in one pane and the canvas in another.
- AC-06.2: The exact criteria for what routes to the canvas vs. plain chat text (e.g. file-write tool results, code blocks over some length, any `write_file`/`run_shell` output) is a design-time decision — see OQ-04.
- AC-06.3: Whether the canvas content is read-only display or supports live editing was **not** confirmed as a native CopilotKit capability during research (unlike the HITL approval primitive, which was confirmed to code-sample depth) — `design.md` must either confirm editability with a targeted spike or scope US-06 to read-only display for M10, deferring editable canvas to a later pass. Do not assume editability without verifying it.

---

### US-07 — Self-hosted deployment, dev-tool visual style

**As** a user,
**I want** axiom's UI to run as a local/LAN web app, installable as a PWA with a background tray launcher, styled as a dark, dense, developer-tool interface,
**so that** it fits how axiom is actually used — an engineering tool I built and operate — rather than looking like a generic consumer chat product.

#### Acceptance criteria

- AC-07.1: The backend serves the web app locally via FastAPI, reachable at `localhost` or the LAN/DGX-Spark IP — no internet-hosted/cloud dependency required to use axiom.
- AC-07.2: The frontend is installable as a PWA (web app manifest + service worker), giving it its own window, taskbar/Start-menu presence — not merely a bookmarked browser tab.
- AC-07.3: A `pystray`-based tray launcher can start/stop the backend and open the UI window, giving persistent background presence without adopting a full desktop-app framework. Electron and Tauri are explicitly out of scope for this milestone (research doc form-factor decision).
- **AC-07.4 — UI styling (explicit and testable, per Kaushik's direct request that this not be left implicit):**
  - Default theme is dark. There is no light-theme-first default; a light theme, if offered at all, is a secondary/opt-in toggle, not the default experience.
  - Monospace font is used for all technical/code-adjacent surfaces: chat code blocks, the US-04 trace view, and the US-06 canvas when displaying code or structured data — this is a consistent typographic rule, not a one-off accent.
  - Layout favors information density over whitespace: comparable visual density to Claude Code's or Cursor's own interface, not a wide-margin, whitespace-heavy consumer chat layout.
  - Chrome — toolbars, headers, decorative/branding elements — is minimal; available screen space favors content (chat, trace, canvas) over navigation or branding chrome.
  - These four sub-criteria are individually checkable at `dryrun-design`/`dryrun-code` time — "looks professional" alone is not an acceptable substitute for any of them.

---

## Non-Goals (M10 scope fence)

| Non-Goal | Notes |
|----------|-------|
| Voice conversation | Explicitly descoped by Kaushik for this milestone ("skip the voice conversation for now"). Deferred to a later pass — not yet assigned to a numbered future milestone. |
| Desktop app (Electron/Tauri) | Research doc's form-factor decision: self-hosted web app first. Tauri is a plausible later upgrade, not part of M10. |
| Terminal TUI | Explicitly rejected by Kaushik ("not impressive") before this spec was opened. |
| Adapting Chainlit, Open WebUI, AnythingLLM, LibreChat, or Lobe Chat | Evaluated and superseded by the CopilotKit/AG-UI decision — see research doc. |
| M9 Connectors integration | Separate, currently-blocked milestone (`011-m9-connectors`, paused on OQ-1). Not part of M10's scope. |
| Multi-user accounts / auth beyond the existing local-token model | Axiom remains single-user, persona-driven — no user/org/permissions system introduced here. |
| Editable canvas (live document editing, Claude-Artifacts-style) | Not confirmed as a native CopilotKit capability during research — see US-06/OQ-04. M10 may ship read-only canvas display and defer editability. |
| Retiring `axiom-cli` | The existing CLI entry point continues to function (US-03/AC-03.4); whether it is eventually deprecated in favor of the UI is a future decision, not part of M10. |

---

## Open Questions

These MUST be resolved at design time (before `design.md` is marked complete).

| ID | Question | Why it's load-bearing |
|----|----------|------------------------|
| **OQ-01** | Exact scrollback behavior within a single connected session — local in-memory buffer for the live session vs. re-querying M3 memory on every reconnect. | Affects US-01's implementation and whether "history" ever behaves inconsistently between a live session and a reconnect. |
| **OQ-02** | Mechanism for runtime-mutable provider selection (US-05) — `forced_provider` is currently fixed at `Agent.__init__` time (M6). A new Router entry point, a re-constructed `Agent`, or an equivalent must be designed. | Without resolving this, US-05 cannot be implemented against the current Router/Agent construction contract. |
| **OQ-03** | Whether `axiom-cli` remains a permanently-supported parallel entry point, or is expected to be retired once the UI ships. | Affects whether M4's CLI-based approval path (US-03/AC-03.4) needs indefinite maintenance or is a transitional bridge. |
| **OQ-04** | Exact criteria for what content routes to the US-06 canvas vs. plain chat text. | Without this, US-06's acceptance criteria are not independently testable — "structured content" is not yet a concrete predicate. |
| **OQ-05** | Whether CopilotKit's Generative UI canvas pane supports live editing, and if not, whether a targeted spike or read-only-for-M10 scoping is the right call. | US-06/AC-06.3 explicitly defers this rather than assuming an unconfirmed capability. |
| **OQ-06** | Backend integration path: the official `copilotkit` PyPI package's `CopilotKitRemoteEndpoint`/FastAPI abstractions, vs. hand-emitting `ag-ui-protocol` events directly from the PRAO loop. | Determines the shape of the new interface-layer code (`src/axiom/interface/`) and how much of CopilotKit's own Python package is actually depended on vs. bypassed. |

---

## Constraints and Invariants

Carried forward from already-built milestones; M10 must not violate these.

1. **`loop.py`/`interfaces.py` stay framework-free.** Per this project's package-per-component rule (already enforced for Tools/M4, Observability/M2, etc.), CopilotKit/AG-UI integration lives in `src/axiom/interface/`, not in the core PRAO loop.
2. **`GuardrailsGate`'s classify/approve contract is not modified.** M10 plugs a new approval backend into the existing seam (US-03); it does not change `GuardrailsGate.classify()`/`request_approval()`'s signature or the KIND-A/KIND-B call contracts established in M4.
3. **M2's WS bridge sink stays localhost-only, token-authenticated.** US-04 consumes it as-is; M10 does not weaken that sink's existing security posture (`004-m2-observability` AC-08.1/AC-08.2) to make UI integration easier.
4. **No breaking change to `axiom-cli`.** Per US-03/AC-03.4 and the Non-Goals table, the existing CLI entry point keeps working.
