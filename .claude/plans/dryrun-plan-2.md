# Plan Dry-Run Report #2

**Plan**: `.claude/plans/001-agent-core-roadmap.md`
**Reviewed**: 2026-07-27
**Trigger**: M10 — Interactive CLI milestone added (this session); Stop-hook context-eval gate required re-evaluation.

---

## Critical Gaps (plan cannot be executed as-is)

### [C1] M1 Router claim still conflicts with M1 spec decision — carried forward from Report #1, unresolved
- **Pass**: Pass 4 — Consistency Check
- **What**: The M1 bullet still reads "a *minimal* Router (subscription-Claude first)". `002-m1-prao-proof/requirement.md:20` explicitly overrides this: "The Router (from the roadmap) is **not in M1** — there is one adapter, wired in code." Confirmed still true today: `requirement.md:137` — "Router / multi-provider — one adapter, wired in code; no routing policy."
- **Impact**: Unchanged from Report #1 — a reader scoping M6 from this plan will assume an M1 Router stub exists to grow from. It doesn't.
- **Fix**: Replace "a *minimal* Router (subscription-Claude first)" with "one Claude adapter, wired in code (no Router in M1 — Router seam deferred to M6)."
- **Status**: 20 days since Report #1 flagged this (2026-07-07 → 2026-07-27). Not fixed.

### [C2] Phase naming "think" still diverges from code and every downstream document — carried forward from Report #1, unresolved
- **Pass**: Pass 4 — Consistency Check
- **What**: The plan still says "perceive → **think** → act → observe" (tech stack section, line 19) and "loop.py (the perceive → **think** → act → observe loop)" (code structure section, line 69). Confirmed against current code: `src/axiom/loop.py` implements `perceive` → `reason` → `act` → `observe` (`ReasonPort`, `self._reason.reason(context)`, `_maybe_record("reason", ...)`) — "think" appears nowhere in the codebase.
- **Impact**: Unchanged from Report #1 — this is the plan every future milestone (including the new M10) is read against; the naming fork persists.
- **Fix**: Replace all "think" occurrences with "reason".
- **Status**: Not fixed.

---

## Warnings (plan can be executed but may lead to rework)

### [W1] Plan status header still stale — carried forward from Report #1, unresolved
- **Pass**: Pass 1 — Structure Check
- **What**: Header still reads "milestone order is a proposal for Kaushik to reshape," contradicting the Decisions section's "LOCKED as proposed." Now additionally stale: the Decisions line itself was edited today to note M10's addition, but the top-of-file Status line (line 3) was not touched.
- **Suggestion**: Update per Report #1's suggested text; while there, note that M10 extends the locked M1–M9 order rather than reopening it.

### [W2] M10's placement after M9 asserts a dependency the plan doesn't substantiate — new
- **Pass**: Pass 3 — Decision Completeness / Pass 4 — Consistency Check
- **What**: The plan's own stated method is "**Ordering rule:** by *dependency*, not list-number" (line 12). M10 (Interactive CLI) is placed after M9 (Connectors) with the rationale "deferred until the components it fronts existed" — but M9 is currently **blocked** on an unresolved open question (`011-m9-connectors/requirement.md` OQ-1, MCP-wrapped vs. direct-API), not yet started. M10 (replacing the M1 CLI with a persistent-session interface) has no evident functional dependency on Connectors specifically — it depends on M1–M8 existing to have something to front, which is already true today.
- **Impact**: As written, a reader would infer M10 waits on M9's resolution, potentially blocking a shippable-interface milestone behind a stalled, externally-gated one for no real technical reason.
- **Suggestion**: Either state explicitly that M10 can proceed in parallel with / independent of M9 (most likely true), or state the actual dependency if one exists (e.g., "the interface should account for connector-sourced content once M9 lands"). One sentence resolves the ambiguity.

### [W3] "Rebuild CM" — scope still undefined — carried forward from Report #1, unresolved
- **Pass**: Pass 3 — Decision Completeness
- **What**: Unchanged since Report #1 (line 24). Not a blocker for M10 specifically, noted for completeness since this report re-reviews the whole document.
- **Suggestion**: As Report #1.

### [W4] "Velhari-pattern" at M7 still assumes insider context — carried forward, unresolved
- **Pass**: Pass 3 — Decision Completeness
- **What**: Unchanged since Report #1 (line 44).
- **Suggestion**: As Report #1.

### [W5] LiteLLM stack entry vs. M1 actual implementation — carried forward, unresolved
- **Pass**: Pass 4 — Consistency Check
- **What**: Unchanged since Report #1 (line 21).
- **Suggestion**: As Report #1.

### [W6] No actor named per milestone, including the new M10 — carried forward, unresolved
- **Pass**: Pass 2 — Actionability Check
- **What**: Unchanged pattern since Report #1 (line 53-56) — M10 follows the same no-actor convention as every other milestone bullet. Consistent with O1 below (intentional, low risk for a solo-plus-Velasari project), but still un-stated in the document itself.
- **Suggestion**: As Report #1.

---

## Observations

### [O1] Plan's role vs. spec's role is correctly scoped — reaffirmed
Unchanged from Report #1. M10's bullet follows the same pattern (direction only, no task-level detail) — correct for a roadmap.

### [O2] M1 spec supersedes the plan on M1 scope — reaffirmed
Unchanged from Report #1. Directly relevant to C1: `002-m1-prao-proof/requirement.md` is the actual authority on M1 scope; the plan text is simply out of date, not in dispute.

### [O3] Router milestone split needs re-anchoring once C1 is fixed — reaffirmed
Unchanged from Report #1, still pending C1's fix.

### [O4] No timeline — still appropriate
Unchanged from Report #1.

### [O5] Report #1's [W2] ("`interfaces.py` drifted to `ports.py`") is now moot — resolved
Current codebase has `src/axiom/interfaces.py` (not `ports.py`) defining the port Protocols (`PerceivePort`, `ReasonPort`, etc. — confirmed via `loop.py` imports). The plan's original text ("interfaces.py — the contracts components implement") matches current reality. No action needed; dropped from this report's warning list.

### [O6] M10 addition itself is well-scoped and introduces no new contradiction
M10's text is consistent with the locked "M1 interface — CLI only (no web surface at M1)" decision (line 56) — a persistent-session TUI is still a terminal interface, not a web surface, so no conflict with that lock. Style and level of detail match the other nine milestone bullets. The only issue found is W2 above (dependency-on-M9 ambiguity), which is a one-line fix, not a structural problem.

---

## Task Audit

| Milestone / Item | Actor? | Action? | Target? | Actionable? |
|---|---|---|---|---|
| M1 — Walking skeleton | No (implicit) | Implied "build" | Loop, CLI, Router (conflicts — C1) | Partial — Router conflict blocks |
| M2 — Observability | No | Implied "build" | Reasoning trace | Yes (high-level) |
| M3 — Memory | No | "CM-kind persistence" | CM store | Yes (high-level) |
| M4 — Tools | No | Implied "build" | Tools + code escape-hatch | Yes |
| M5 — Skills | No | "progressive disclosure; self-authoring" | agentskills.io | Yes (high-level) |
| M6 — Router (full) | No | Implied "build" | Intent→provider policy | Partial — M1 stub assumption breaks (C1) |
| M7 — Orchestrator | No | Implied "build" | Multi-provider consortium | Partial — "Velhari-pattern" undefined (W4) |
| M8 — Self-correction | No | "Capture lessons + deliver at decision point" | Loop hooks | Yes (high-level) |
| M9 — Connectors | No | Implied "build" | Email/Slack/Drive intake | Yes (high-level; separately blocked on its own OQ-1, not a plan-level gap) |
| M10 — Interactive CLI | No | "Replace the M1 one-shot test CLI" | CLI interface / TUI | Partial — dependency on M9 unclear (W2) |
| Tech stack decisions | N/A | N/A | N/A | ✅ Locked, rationale present |
| Code structure decisions | N/A | N/A | N/A | ✅ Consistent with code (O5) |
| Router decision | N/A | N/A | N/A | ✅ Rationale present |
| M4 sandboxing decision | N/A | N/A | N/A | ✅ Rationale present |
| M10 addition to Decisions log | N/A | N/A | N/A | ✅ Dated, rationale present |

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 2        | 6        | 6            |

**Verdict**: FAIL — needs revision

The two critical gaps from Report #1 (C1: M1 Router claim, C2: "think" vs. "reason" naming) remain unresolved 20 days later and are unrelated to today's M10 addition — they should be fixed regardless of M10. The M10 addition itself is clean (O6) with one new, low-effort warning (W2: state whether it truly depends on M9 or can proceed independently). None of today's findings block starting M10's own `requirement.md` — they block treating the roadmap document itself as fully consistent.
