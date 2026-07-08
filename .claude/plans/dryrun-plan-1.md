# Plan Dry-Run Report #1

**Plan**: `.claude/plans/001-agent-core-roadmap.md`
**Reviewed**: 2026-07-07

---

## Critical Gaps (plan cannot be executed as-is)

### [C1] M1 Router claim conflicts with M1 spec decision
- **Pass**: Pass 4 — Consistency Check
- **What**: The plan states M1 includes "a *minimal* Router (subscription-Claude first)". The M1 requirement (`002-m1-prao-proof/requirement.md`) explicitly overrides this: "The Router (from the roadmap) is **not in M1** — there is one adapter, wired in code." The plan and its first executed milestone directly contradict each other.
- **Impact**: Any reader using this plan to scope M1 work will budget for and expect a Router component that was deliberately dropped. If the plan is used for M6 scoping ("Router full, built on the M1 minimal stub"), the M1 stub won't exist — M6 planning starts from a wrong premise.
- **Fix**: Update M1 bullet: replace "a *minimal* Router (subscription-Claude first)" with "one Claude adapter, wired in code (no Router in M1 — Router seam deferred to M6)." Also clarify in the M6 bullet that the Router is built from scratch at M6, not grown from an M1 stub.

---

### [C2] Phase naming diverges from all downstream documents
- **Pass**: Pass 4 — Consistency Check
- **What**: The plan uses "perceive → **think** → act → observe" throughout (tech stack section, code structure section). Every downstream document — `architecture.md` (loop decomposition), `002-m1-prao-proof/requirement.md`, `002-m1-prao-proof/design.md` — uses "perceive → **reason** → act → observe" (PRAO). The loop phase is called `reason()` in all code-level references; `think` appears nowhere in the codebase design.
- **Impact**: The plan is the entry point for new milestones. Anyone reading the plan will write milestone specs using "think", which will be inconsistent with the architecture document, existing specs, and eventually the code. Creates a persistent naming fork.
- **Fix**: Replace all occurrences of "think" with "reason" in the plan. Update code structure section: `loop.py (perceive → reason → act → observe)`.

---

## Warnings (plan can be executed but may lead to rework)

### [W1] Plan status header is stale
- **Pass**: Pass 1 — Structure Check
- **What**: The header reads "Status: DRAFT proposal … The **milestone order is a proposal** for Kaushik to reshape." The Decisions section (same document) says "Milestone order — LOCKED." The status header was never updated after the evening lock session.
- **Suggestion**: Update header to: `**Status:** LOCKED (2026-07-04 evening). Milestone order, tech stack, and code structure decisions are final. Each milestone's design→build→observe pass may refine within these bounds.`

### [W2] `interfaces.py` name drifted to `ports.py` in actual design
- **Pass**: Pass 4 — Consistency Check
- **What**: Code structure section names "interfaces.py (the contracts components implement)" as the seam file. The M1 design settled on `ports.py` (PerceivePort, ReasonPort, ActPort, ObservePort as Protocols) and `intent.py` as separate files. The plan and the design have diverged on this naming.
- **Suggestion**: Update code structure section to name `ports.py` (port Protocol definitions) and note that each milestone's `design.md` owns the final file-level decisions — the plan sets direction, not file names.

### [W3] "Rebuild CM" — scope undefined
- **Pass**: Pass 3 — Decision Completeness
- **What**: M3 and the decisions section reference "rebuild CM" as the memory approach without defining CM's scope or linking to any reference. A reader unfamiliar with the project history (Velasari, Cognitive Memory) cannot act on this.
- **Suggestion**: Add a parenthetical: "rebuild CM (Cognitive Memory: episodic/semantic/procedural store with decay and multi-strategy recall — see Velasari CM for reference implementation)" or create a research note at `.claude/research/` that defines the CM model.

### [W4] "Velhari-pattern" at M7 assumes insider context
- **Pass**: Pass 3 — Decision Completeness
- **What**: M7 says "Velhari-pattern" without defining it. The architecture doc briefly mentions it ("consortium of providers, fan-out") but the plan itself doesn't.
- **Suggestion**: Add a brief inline definition: "Velhari-pattern (fan-out to multiple providers, aggregate results, the model committee approach)."

### [W5] LiteLLM stack entry vs M1 actual implementation
- **Pass**: Pass 4 — Consistency Check
- **What**: The tech stack lists "LiteLLM → local vLLM model + any true-API provider" as a stack component. M1 uses `claude_agent_sdk` directly (no LiteLLM involved). LiteLLM applies only to the local/true-API path. A reader may expect LiteLLM to appear in M1 work.
- **Suggestion**: Clarify in the tech stack that LiteLLM applies to the local/API path only, and that the CLI-wrapper path (Agent SDK) does not use LiteLLM. Consider noting which milestones introduce each stack element.

### [W6] No actor named per milestone
- **Pass**: Pass 2 — Actionability Check
- **What**: No milestone names who executes it. For a solo-project context this is low risk (Kaushik + Velasari is the implicit actor), but the plan has no explicit statement of this.
- **Suggestion**: Add a single line under the milestones header: "Actor for all milestones: Kaushik (decision authority) + Velasari (implementation). Each milestone's task.md names actors at the task level."

---

## Observations

### [O1] Plan's role vs spec's role is correctly scoped
The plan is a cross-milestone roadmap, not a task board. Each milestone explicitly defers detailed tasks to its own `design.md` / `task.md`. This is correct per CLAUDE.md conventions and means the low task-level actionability here is by design, not a gap.

### [O2] M1 spec supersedes the plan on M1 scope — intentional
The requirement note "supersedes `architecture.md` where they conflict" establishes that each milestone's requirement.md and design.md are the authoritative source for that milestone's scope. The plan sets direction and ordering; the spec sets binding decisions. This hierarchy is healthy but should be stated explicitly in the plan's preamble.

### [O3] Router milestone split (M1 stub → M6 full) needs re-anchoring post-C1 fix
Once C1 is fixed (no Router at M1), the M6 "Router (full)" bullet should clarify it is built from scratch at M6, not grown from a stub. This changes the dependency: M6 no longer depends on M1 delivering a Router seam — it starts fresh from the port-adapter boundary that M1 establishes.

### [O4] No timeline — acknowledged and appropriate
The plan has no dates or sprint estimates. Given the "build to learn" philosophy and the explicit statement that the plan flexes as milestones are observed, this is intentional and appropriate.

---

## Task Audit

| Milestone / Item | Actor? | Action? | Target? | Actionable? |
|---|---|---|---|---|
| M1 — Walking skeleton | No (implicit) | Implied "build" | Loop, CLI, Router (but Router conflicts — see C1) | Partial — Router conflict blocks |
| M2 — Observability | No | Implied "build" | Reasoning trace | Yes (high-level) |
| M3 — Memory | No | "CM-kind persistence" | CM store | Yes (high-level) |
| M4 — Tools | No | Implied "build" | Tools + code escape-hatch | Yes — sandboxing rationale present |
| M5 — Skills | No | "progressive disclosure; self-authoring" | agentskills.io | Yes (high-level) |
| M6 — Router (full) | No | Implied "build" | Intent→provider policy | Partial — M1 stub assumption breaks (see C1, O3) |
| M7 — Orchestrator | No | Implied "build" | Multi-provider consortium | Partial — "Velhari-pattern" undefined (see W4) |
| M8 — Self-correction | No | "Capture lessons + deliver at decision point" | Loop hooks | Yes (high-level) |
| M9 — Connectors | No | Implied "build" | Email/Slack/Drive intake | Yes (high-level) |
| Tech stack decisions | N/A | N/A | N/A | ✅ Locked, rationale present |
| Code structure decisions | N/A | N/A | N/A | Partial — `interfaces.py` name stale (see W2) |
| Router decision | N/A | N/A | N/A | ✅ Rationale present |
| M4 sandboxing decision | N/A | N/A | N/A | ✅ Rationale present |

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 2        | 6        | 4            |

**Verdict**: FAIL — needs revision

Two critical gaps must be resolved before the plan is used to scope future milestones:
- **C1**: M1 Router claim must be corrected to reflect the actual M1 decision (no Router, adapter wired in code).
- **C2**: Phase naming "think" must be replaced with "reason" everywhere to match all downstream documents and eventual code.

Warnings W1 and W2 are low-effort fixes worth doing alongside C1/C2. W3/W4 are documentation hygiene for future readers.
