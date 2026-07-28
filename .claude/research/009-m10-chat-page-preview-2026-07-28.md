# M10 UI — Chat Page Preview (custom component vs. stock CopilotChat)

**Date**: 2026-07-28
**Context**: Follow-on to `008-m10-accent-color-preview-2026-07-28.md` — amber (`#e3b341`) was approved. Kaushik then flagged that the chat pane itself still "looks like a POC" and asked what a properly-built chat page would look like, as a preview only (no code changed yet).
**Paired artifact**: `009-m10-chat-page-preview-2026-07-28.html` — open directly in a browser. No chrome bar, canvas pane, trace pane, or approval card. Message list (user + assistant turns) in a centered readable column, filling the viewport, with the composer/input bar fixed at the bottom. The composer is a real, typeable `<textarea>` (auto-grows up to 200px, Enter sends/Shift+Enter newline) — appends what you type as a new user message row, so the input's font/sizing/feel can actually be typing-tested, not just eyeballed. Sending also triggers a mock processing indicator: the live-dot cycles through the PRAO loop's own phase names (`[perceive]` → `[reason]` → `[act]` → `[observe]`, ~550ms each) before resolving into a canned reply — same phase-vocabulary idea as the earlier static example, now actually playable.

**Fixed (positioning)**: the message area's scrollbar was floating in the middle of a wide window instead of hugging the right edge — `max-width: 760px` had been applied directly to the `overflow-y: auto` element (`.msg-list`), so the scrollbar rendered at that 760px box's edge, not the viewport's. Split into `.msg-scroll` (full-width, owns the scrollbar) wrapping `.msg-list` (the 760px-capped, centered content) — same pattern already used correctly for the composer (`.composer` full-width strip, `.composer-inner` centered).

**Fixed (appearance)**: once correctly positioned at the right edge, the scrollbar still rendered as the OS's light, classic, arrow-buttoned widget (visible in Kaushik's screenshot) — `color-scheme: dark` on `:root` doesn't reliably override that on Windows. Added explicit dark/thin scrollbar styling for both engines (`scrollbar-width`/`scrollbar-color` for Firefox, `::-webkit-scrollbar-*` for Chromium) and hid the up/down spinner buttons, applied globally so it also covers the composer `<textarea>`'s own scrollbar.

---

## What's actually shipped today

`App.tsx` renders CopilotKit's stock `<CopilotChat>`, restyled only via `--copilot-kit-*` CSS variable overrides in `theme.css`. That gets the color palette right but keeps every one of CopilotKit's own interaction/layout decisions: symmetric rounded bubbles on both sides, a generic three-dot "..." typing indicator, a pill-shaped input field. It reads as a themed third-party widget, not a first-party product surface — which matches Kaushik's "POC, not a product" read.

## Proposed: a first-party chat component

Same underlying data (still driven by the real `HttpAgent`/AG-UI event stream — this is a rendering change, not a protocol change). The preview iterated in three steps: (1) stock-CopilotChat vs. custom side-by-side toggle, (2) settled on the custom design, dropped the comparison, went full-bleed with chrome/canvas/trace still present, (3) at Kaushik's request, stripped everything but the messages themselves — chrome bar, canvas pane, trace pane, and approval card are all still real, planned parts of the product; they're just not what's being reviewed in *this* preview, so they're out of the file entirely rather than hidden. Concrete differences from what's shipped today, still true of the stripped-down version:

1. **Asymmetric message grammar** — assistant replies render as an accent-striped log entry (`border-left: 2px solid var(--accent)`, no right border), your own messages stay boxed (`border: 1px solid var(--border)`). The shapes mean something: your input is contained; the assistant's output flows.
2. **PRAO-vocabulary streaming indicator** — instead of generic "..." dots, an in-progress assistant turn shows a pulsing live-dot (same glow technique as the trace pane) next to the actual PRAO phase name (`[reason]`, `[act]`) the loop is in, plus a blinking `▍` cursor at the end of streamed-so-far text. This is a detail unique to axiom's own architecture, not a generic chat-app convention.
3. **Code block treatment** — fenced code inside a message gets the same header-bar treatment as the canvas pane's own blocks (language label + copy affordance), instead of default markdown styling.

Dropped from this iteration (not rejected — just not part of what's being reviewed right now): the chrome bar, canvas pane, trace pane, and approval card. The composer/input bar came back at Kaushik's request — fixed at the bottom, same centered column width as the messages, with the keyboard-shortcut hint and connection-status dot.

## Status

Preview only — **no changes to `web/src/App.tsx`, `theme.css`, or any shipped component.** Next step, if this direction is approved, is scoping the actual component build (new `ChatPane.tsx` subscribing to the same `HttpAgent` event stream `ApprovalPrompt.tsx`/`CanvasPane.tsx` already use, replacing the `<CopilotChat>` usage in `App.tsx`).
