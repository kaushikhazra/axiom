# Plan Dry-Run Report #1

**Plan**: `.claude/plans/001-agent-core-roadmap.md`
**Reviewed**: 2026-07-05

---

## Critical Gaps (plan cannot be executed as-is)

### [C1] Package name mismatch — plan says `axiom`, code says `agentcore`

- **Pass**: Consistency (Pass 4)
- **What**: The "Code structure" section locks the package name as `axiom` and specifies Python src-layout (`src/`). However, the existing codebase already has `src/agentcore/` with 11 sub-packages created. A builder starting M1 doesn't know which name is canonical.
- **Impact**: Builder either creates a second parallel tree (`src/axiom/`) leaving dead code, or continues in `agentcore/` contradicting the locked plan. Either way, confusion and rework.
- **Fix**: Resolve the name: either rename existing `src/agentcore/` → `src/axiom/` now (before M1 design), or update the plan to reflect `agentcore` as the true package name and retire the `axiom` decision.

### [C2] "Subscription-Claude" transport — undefined for M1 builder

- **Pass**: Actionability (Pass 2)
- **What**: M1 requires a "minimal Router (subscription-Claude first)." The tech-stack section mentions "CLI-wrappers → subscription Claude (Claude Code / Agent SDK on Claude Max)" but doesn't specify which mechanism M1 should wire: a subprocess calling `claude` CLI? The Agent SDK? A direct API key? The "Velhari pattern, rebuilt" phrase is opaque to anyone who hasn't seen Velhari's internals.
- **Impact**: The M1 design pass has no concrete transport to design against. The builder must reverse-engineer intent or ask, violating "executable without clarifying questions."
- **Fix**: Add a one-sentence decision: "M1 uses [specific mechanism] to reach Claude. The CLI-wrapper abstraction is designed at M6." Or mark this as an explicit open question to resolve in M1's design pass.

---

## Warnings (plan can be executed but may lead to rework)

### [W1] No testing strategy stated

- **Pass**: Structure (Pass 1)
- **What**: The plan describes "design → build → observe" loops but never mentions how correctness is verified — unit tests, integration tests, manual-only, TDD, test-after. For a green-field project with package-per-component isolation, the testing contract shapes the interfaces from day one.
- **Suggestion**: Add a locked decision: "Each component has unit tests against its interface contract; integration tests at milestone boundaries." Or defer explicitly: "Testing strategy decided per-milestone in design.md."

### [W2] "One basic action" in M1 is ambiguous

- **Pass**: Actionability (Pass 2)
- **What**: M1's scope is "something you can talk to that thinks and takes one basic action." What action? File write? Shell command? Echo response? A builder could interpret this as "just respond in chat" (trivial) or "execute a shell command" (requires tool infrastructure from M4).
- **Suggestion**: Pin the action: e.g., "M1's single action is *reply to the user* (no tool use). Tool actions arrive at M4." This distinguishes the walking skeleton from a tool-using agent.

### [W3] "Velhari pattern" referenced without accessible definition

- **Pass**: Decision Completeness (Pass 3)
- **What**: The orchestrator (M7) and provider transport reference the "Velhari pattern" — flat-sub cost, multi-provider consortium. This is institutional knowledge (K + V only). A builder reading only this plan + referenced docs cannot reconstruct it.
- **Suggestion**: Either link to a document describing the pattern, or inline a 2-3 sentence definition in the Decisions section. Enough for a design pass to work from.

### [W4] No explicit actor per milestone

- **Pass**: Actionability (Pass 2)
- **What**: Milestones don't state who designs/builds them. Per CLAUDE.md task rules, every task must state the actor. At roadmap altitude this is less critical, but M1 is imminent — is Velasari designing alone? Is Kaushik pairing? Are sub-agents building?
- **Suggestion**: At minimum, state the default actor for design passes and build passes (e.g., "Velasari designs; Kaushik reviews; sub-agents implement under Velasari direction").

### [W5] "Observe" phase undefined

- **Pass**: Actionability (Pass 2)
- **What**: Each milestone runs "design → build → observe" but "observe" is never defined. What constitutes observation? Manual testing? A demo session? Metrics from M2's observability? Without definition, the loop has no exit criterion.
- **Suggestion**: Define "observe" minimally: "Kaushik interacts with the agent at milestone end; findings feed the next milestone's design." Or defer to each milestone's task.md.

---

## Observations

### [O1] Dependency ordering is sound

The M1→M9 sequence correctly layers: skeleton → observability (so you can judge) → memory → tools → skills → full router → orchestrator → self-correction → connectors. Each milestone's inputs are available from prior milestones.

### [O2] "Build to learn" philosophy is well-calibrated

The explicit framing that survey choices are hypotheses, not conclusions, protects the plan from premature lock-in. The plan flexes as learnings accumulate — this is a strength.

### [O3] Code-structure section is a useful bridging artifact

Recording structural decisions *in the plan* before design docs exist prevents them from being lost between sessions. The "direction for the design" framing correctly scopes their authority.

### [O4] Router emergence is well-handled

The Router's lifecycle (thin seam at M1, full component at M6, consumed by orchestrator at M7) is cleanly separated and the rationale for standalone status is explicit.

### [O5] Existing code scaffolding aligns with component list

The `src/agentcore/` tree already has one package per component (persona, memory, orchestrator, router, etc.) — structurally aligned with the plan's "package-per-component" decision, modulo the naming conflict (C1).

---

## Task Audit

_Note: This plan is a milestone-level roadmap, not a granular task list. Task.md comes per-milestone. The audit below evaluates milestones as high-level action items._

| Milestone | Actor? | Action? | Target? | Actionable? |
|-----------|--------|---------|---------|-------------|
| M1 — Walking skeleton | No | Partial ("talk to, thinks, takes one basic action") | Yes (persona + loop + CLI + Router) | No — "basic action" and transport undefined |
| M2 — Observability | No | Yes (surface reasoning trace) | Yes (observability component) | Partial — what "surfaced" means at CLI level unclear |
| M3 — Memory | No | Yes (CM-kind persistence) | Yes (memory component) | Yes — "rebuild CM" is sufficient direction for design |
| M4 — Tools | No | Yes (structured tools + escape-hatch) | Yes (tools component) | Yes — scope and safety model stated |
| M5 — Skills | No | Yes (progressive disclosure, self-authoring) | Yes (skills component) | Partial — agentskills.io dependency unclear |
| M6 — Router (full) | No | Yes (intent→provider policy) | Yes (router component) | Yes — policy dimensions enumerated |
| M7 — Orchestrator | No | Yes (multi-provider consortium) | Yes (orchestrator component) | Partial — "Velhari pattern" opaque |
| M8 — Self-correction | No | Yes (capture + deliver lessons) | Yes (self-correction component) | Yes — distinct from memory, purpose clear |
| M9 — Connectors | No | Yes (email/Slack/Drive intake) | Yes (connectors component) | Yes — scope clear |

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 2        | 5        | 5            |

**Verdict**: **PASS WITH WARNINGS**

The plan is sound at roadmap altitude — dependency ordering is correct, the "build to learn" philosophy protects against premature commitment, and structural decisions are well-scoped. However, two critical gaps block M1 execution: the package-name contradiction (C1) must be resolved before any code is written, and the subscription-Claude transport (C2) must be pinned before M1's design pass can proceed. The warnings are addressable during M1's design phase but represent ambiguities a builder would trip on.
