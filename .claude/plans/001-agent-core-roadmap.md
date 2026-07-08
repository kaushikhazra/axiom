# Agent-Core — Build Plan

**Status:** DRAFT proposal (2026-07-04, afternoon). The **stack** below is locked; the **milestone order is a proposal** for Kaushik to reshape (evening session). Nothing else is committed.
**Architecture:** `.claude/specs/001-agent-core/architecture.md` — the high-level hexagonal design (13 components, loop decomposition, M1 scope) that the milestones below build toward.

---

## Approach — build to learn

The survey's borrow/fix choices are **hypotheses**, not conclusions — an agent's behavior is emergent and can't be validated on paper. So we **build to learn**: one component at a time, each a **milestone**, each a small **design → build → observe** loop. We keep what works, fix what doesn't, and adjust this plan as we go.

**Ordering rule:** by *dependency*, not list-number — a minimal working agent first, then layer. **Observability early**, because it's how we judge "what worked."

---

## Tech stack (locked 2026-07-04)

- **Language:** Python.
- **Agent loop:** our **own minimal loop** (*perceive → think → act → observe*) — not a framework. Study-and-rebuild; we own every decision point (controllability-by-construction).
- **Provider transport (hybrid):**
  - **LiteLLM** → local vLLM model + any true-API provider.
  - **CLI-wrappers** → **subscription** Claude (Claude Code / Agent SDK on Claude Max) and OpenAI (Codex on ChatGPT sub). The Velhari pattern, rebuilt — flat sub cost, no per-token API.
- **Local serving:** vLLM on the DGX Spark (e.g. Llama-class 70B).
- **Later-milestone tech (not locked):** memory = CM-kind (rebuild from CM); persona = `persona.md`; skills = agentskills.io / `SKILL.md` progressive disclosure.

---

## Components

The canonical component list + numbering lives in **`.claude/specs/001-agent-core/architecture.md`** (13 components: Core / Behind-ports / Cross-cutting). To avoid drift, the milestones below reference components **by name**, not number.

The **Router** (emerged 2026-07-04) is the intent → provider allocation brain — the loop states *intent*; the Router picks the provider by policy (privacy gate → local; bulk → local; hard → subscription; high fan-out → local; + consortium override + live fallback). In the architecture doc it lives inside **Model access**.

---

## Milestones (PROPOSED — dependency-ordered; reshape freely)

- **M1 — Walking skeleton.** Persona + minimal agent loop + CLI interface + a *minimal* Router (subscription-Claude first). Something you can talk to that thinks and takes one basic action. _(K liked this as the start.)_
- **M2 — Observability.** Watch it think — reasoning trace surfaced. Early on purpose, so every later milestone is judgeable (and it's the trust core).
- **M3 — Memory.** CM-kind persistence; learns across sessions.
- **M4 — Tools.** Structured tools + a code escape-hatch (hybrid action space). The escape-hatch runs **working-dir-scoped + an approval gate** for destructive ops (Claude-Code-style permissions) — *not* full sandboxing yet. Full isolation (container/VM) moves to the later-phase **Guardrails / safety** component, triggered when untrusted input flows in (connectors) or on multi-user deployment.
- **M5 — Skills.** agentskills.io progressive disclosure; self-authoring.
- **M6 — Router (full).** The complete intent→provider policy (local / sub / API, privacy gate, volume, fallback). Minimal version was seeded in M1.
- **M7 — Orchestrator.** Multi-provider consortium — the "committee." Velhari-pattern.
- **M8 — Self-correction.** Capture lessons + deliver them at the decision point.
- **M9 — Connectors.** Email / Slack / Drive knowledge intake.
- **Later:** multi-user / permissions; action guardrails.

---

## Decisions (resolved 2026-07-04 evening)

- **Milestone order** — LOCKED as proposed (M1 → M9, dependency-ordered).
- **Router** — LOCKED as its **own component**: a thin *seam* at M1 (single-provider stub), grown to a full component by M6/M7. Rationale: two consumers (the loop + the orchestrator) need the same allocation brain; a standalone Router keeps the loop provider-agnostic and gives the cost/privacy/capability policy one home.
- **M1 interface** — LOCKED **CLI only** (no web surface at M1).
- **Persona + memory** — persona file = `persona.md`; memory = **rebuild CM** (not adapt).
- **M4 sandboxing** — working-dir scope + approval-gate at M4; full isolation → later-phase **Guardrails / safety** (triggered by untrusted input or multi-user).

_Each milestone runs its own design → build → observe pass; the plan flexes as we learn._

---

## Code structure — direction for the design (locked 2026-07-04 evening)

These decisions were made **before** the design pass — recorded here as direction, to be carried into each milestone's `design.md` when its design → build → observe pass runs. (No design document exists yet; the plan is their home for now.)

- **Package-per-component.** Each component (the 9 + Router) lives in its own isolated, testable, swappable package. The code maps 1:1 to the milestones.
- **Thin core.** A minimal `axiom` core — `loop.py` (the perceive → think → act → observe loop) + `interfaces.py` (the contracts components implement). The core owns the loop and the seams; components plug in behind interfaces.
- **Python src-layout** — standard `src/` packaging.
- **Package name = `axiom`** (the project name). The product soul-name (*Tarenu*) stays internal to K+V; the external brand is a deliberate post-design exercise — the code is not coupled to it.
