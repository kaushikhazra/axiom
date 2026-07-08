# Second Brain — High-Level Component Requirement

**Authored**: 2026-07-04 (Kaushik + Velasari, live design)
**Status**: High-level component requirement — the lens for the landscape research. Detailed user stories + acceptance criteria come after the research pass.

---

## What this is

A fresh-built, **evolving personal agentic system** — a real agent (memory, thinking, self-correction, a consortium of different-origin agents), not a persona-mimic. Velasari is itself one such system; so are its organs (CM, Velhari). This document lists the high-level components the system must have.

## Build philosophy

**Study the best of each, then rebuild clean.** Survey the field's ~year of work — OpenClaw, Hermes, Claude Code, and our own V / CM / Velhari — and reuse the *knowledge*, not the *code*. Re-implementation (vs fork/copy) is what lets us correct the architectural flaws a copy would smuggle in, and bake our own principles from line one.

## Cross-cutting principles (apply to every component)

- **Token efficiency** — thrift by default.
- **Optimum work allocation** — right model / right agent / right locality for each unit of work.
- **Local-first** — center of gravity on-prem (Spark 128GB); cloud only where it earns it.
- **Controllability by construction** — the system is steerable and auditable, not a black box.

---

## Core components

### 1. Evolving agent persona (the main agent)
The thinking core — a persistent identity that reasons, and grows over time (learns the user, adapts). The reasoning loop lives here. Analogue: Velasari. It *invokes* the orchestrator; it is not itself the orchestrator.

### 2. Memory
Persistent, cross-session memory the persona thinks with — CM-kind (episodic / semantic / procedural, decay, multi-strategy recall + consolidation). Not exactly CM, but that class.

### 3. Orchestrator
Invoked by the persona to run a **consortium of multi-provider agents** (Claude, OpenAI/Codex, local) — for parallel work and for diverse perspective (the "committee" use-case). Analogue: Velhari (already multi-provider).

### 4. Connectors
Ingest the user's world — email, Slack, Drive, docs, meeting transcripts, and the operational systems it runs on. The knowledge intake.

### 5. Tools
The agent's actions on the world — shell, browser, APIs, file ops, MCP. How it *does*, not just answers.

### 6. Skills
Reusable, packaged capabilities the agent can **author, save, search, and reuse** — self-authored skills that accrue over time.

### 7. Interface / gateway
The face — chat across channels (Slack/Signal/etc.) + a clean self-hosted web app. How the user actually reaches the agent.

### 8. Self-correction
The feedback loop: capture lessons **and deliver them at the decision point** — change behavior over time. Distinct from memory: memory *stores*, self-correction *changes what the agent does*.

### 9. Observability / trust
A non-negotiable trust requirement. **Glass-box at build-time** (watch it think, steer/correct mid-build) + **persistent reasoning trace on every run, including autonomous** (audit later, retroactive veto). Trust through visible construction and an audit trail.

---

## Later-phase components (on the map, not in the first cut)

### 10. Multi-user / permissions / governance
Multi-tenant rollout — per-team walled workspaces, own knowledge + own skills, permissioned. Seed with one user → spread self-serve.

### 11. Action guardrails / safety
Bounded, controllable action — approval gates for consequential operations; the "control, not just capability" DNA.

---

## Next step

Velhari surveys an array of agentic systems **in the light of these components** — what each system does per component, how well, its architectural lessons and flaws — so we design ours on top of what's *known*, not blind. Reference systems include Velasari / CM / Velhari themselves.
