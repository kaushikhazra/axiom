# M10 UI — Accent Color Review (factory.ai reference, amber/gold proposal)

**Date**: 2026-07-28
**Context**: M10 web UI (`012-m10-interactive-cli`) ships with a blue accent (`--accent: #58a6ff` in `web/src/theme.css`). Kaushik asked to check factory.ai's style and preview an amber/gold accent swap before touching real code.
**Paired artifact**: `008-m10-accent-color-preview-2026-07-28.html` — open directly in a browser; a live toggle compares axiom's real chrome bar / chat / approval-card / canvas / trace-pane components under the current blue vs. a proposed amber accent, with no other changes.

---

## factory.ai style findings

Fetched `https://factory.ai/` (both a summarized read and raw HTML for exact colors).

**Palette** (from inline SVG/CSS in the page source):

| Hex | Role |
|---|---|
| `#0a0a0a` / `#0c0b0a` / `#060505` / `#020202` | Near-black backgrounds — dark-first, several shades layered |
| `#EE6018` | Primary accent — brand color, "live" status dot, glow effects (`filter: drop-shadow(0 0 7px #EE6018)`) |
| `#b3541d`, `#d15010`, `#ef6f2e` | Accent variants/gradient stops around the same orange family |
| `#b8b8b8`, `#848484`, `#9a9a9a`, `#6e6e6e` | Gray text/border hierarchy |
| `#fcfafa`, `#fdfcfb`, `#faf8f4` | Near-white, used for high-contrast text |
| `#a0ca92` (127 occurrences) | Green — appears to be a decorative gradient/illustration color, not core UI chrome |

**Typography**: `--font-geist-mono` (Vercel's Geist Mono) for technical/dashboard text — same category of choice axiom already made (`JetBrains Mono`/`Fira Code` stack).

**Layout/tone**: dense dashboard cards, generous whitespace between major sections, technical KPI displays in monospace, enterprise-professional tone.

**Takeaway**: factory.ai's system is structurally identical to what axiom's `theme.css` already does (dark ground, monospace on technical surfaces, dense spacing) — the one distinctive move is a **single warm accent color used everywhere, including a glowing live-status indicator**. That glow-on-accent technique is worth borrowing regardless of which hex axiom lands on.

---

## Proposed amber/gold values

| Token | Current (blue) | Proposed (amber) |
|---|---|---|
| `--accent` | `#58a6ff` | `#e3b341` |
| glow (new token, `--accent-glow`) | `rgba(88, 166, 255, 0.45)` | `rgba(227, 179, 65, 0.5)` |

`#e3b341` was chosen over factory.ai's `#EE6018` (orange) because Kaushik asked for amber/gold specifically — this hex sits closer to GitHub's own dark-mode "attention" gold token, tuned for legibility against `--bg: #0d1117` at the sizes axiom uses (12–13px UI text, 11px trace text).

Every current use of `--accent` in `theme.css` is driven by that one token (chrome-toggle active state, approval-prompt border, CopilotKit primary color, trace-phase color) — swapping it is a one-line change if the amber reads well. The paired HTML adds a `--accent-glow` token (not present in the current `theme.css`) to demo the factory.ai-style glow on the trace pane's live-span indicator; adopting the glow is a separate, optional decision from the accent hex itself.

---

## Status

Preview only — **no changes made to `web/src/theme.css` or any shipped code**. This is a design review artifact for Kaushik to react to before any real edit.
