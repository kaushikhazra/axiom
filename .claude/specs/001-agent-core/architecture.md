# Axiom — Agent-Core: High-Level Architecture

**Document type:** High-level architecture — component responsibilities and structural shape only.
**Revised:** 2026-07-07 (supersedes 2026-07-05 draft; reflects decisions from Kaushik + Velasari design session).
**Next step:** Per-milestone design passes (`design.md`) that define contracts and interfaces.

---

## Architecture style: Ports-and-Adapters (Hexagonal)

A thin, sovereign **core** sits at the centre. It knows nothing about the outside world. Every external concern — model providers, memory stores, tools, skills, user interfaces — lives behind a **port**; each concrete implementation is an **adapter** plugged into that port.

**Rationale:** This directly fixes the mistake made in Velhari, which had no adapter layer between providers and the core. The result was tight coupling: swapping a provider required touching the core. The hexagonal shape enforces the open/closed principle cleanly — adding a new provider means writing a new adapter; the core is untouched.

---

## The 6 ports

All external concerns are accessed through exactly **six ports**. The Router (a core-side component) selects which adapter to use, but the port boundary itself is fixed.

| Port | What crosses the boundary |
|------|--------------------------|
| **Agent** | Provider agents — the Conductor (Reason phase) and Workers (Act phase) both use this single port. N adapters, distinguished by `control_level`. |
| **Memory** | Episodic / semantic / procedural stores. CM-kind: decay, multi-strategy recall. |
| **Tools** | Atomic action implementations (shell, file, API, browser) + registry. |
| **Skills** | Self-authored, packaged capabilities the agent saves / searches / reuses. Higher-order than a Tool. |
| **Connectors** | Knowledge-intake adapters (email, Slack, Drive, meeting transcripts). |
| **I/O Gateway** | Interface adapters — how the user reaches the agent (CLI now; web / chat later). |

**One Agent port, not two.** An earlier draft modelled Completion providers and Delegated-Agent providers as separate port shapes. That is superseded: every provider is wrapped so it presents as an **agent** (uniform port contract), and the structural distinction is expressed as a `control_level` field on the adapter. (See *Provider adapters and control-level* below.)

---

## Core components

The sovereign core owns the loop, the allocation brain, the persona, and the call-points for the three cross-cutting faculties. It imports nothing external — every external call crosses a port.

### Agent Loop

The engine. Runs the four-phase **perceive → reason → act → observe** cycle. ("reason" is the canonical name for the Think phase; "reason (think)" is used once here for continuity with earlier notes; thereafter "reason" only.)

**The loop IS the orchestrator.** There is no separate Orchestrator component. When the Act phase dispatches to multiple Worker agents and the Observe phase gathers their results, and Reason synthesises in the next cycle — that *is* orchestration. It is a **behaviour of the loop**, not a structural box. Design principle: **prefer behaviour over structure**.

**Self-similar recursion.** The master agent and any sub-agents it dispatches are structurally identical — same loop class, same six ports. The difference is role and configuration (which persona, which tools scope, what the agent perceives), not code structure. Terminology: **master agent** (also "root agent") — never "supervisor".

---

#### Conductor and Worker — two roles, one port

The Agent port is used in two distinct roles, determined by which phase invokes it:

| Role | Phase | Character |
|------|-------|-----------|
| **Conductor** | Reason (Think) | The model bound to the Reason phase — the system's "mind." Persona is injected here. The Router selects it; it should be the strongest available reasoner. Re-evaluated each cycle (reactive, not a pre-planned DAG). Its output feeds the Decision Interpreter. |
| **Worker** | Act | Agents dispatched to carry out bounded labour. May be lighter models. Multiple Workers may run per Act phase; results are gathered in Observe. |

**Regress-stopper.** The Reason phase must invoke the Conductor for a **single reasoning step** — one completion or one degenerate-agent call — and return a structured Intent. The loop provides iteration; Reason does not recurse. If Reason itself were a full nested loop, the result would be an orchestrator whose brain is an orchestrator — infinite regress.

---

#### Loop phase decomposition

##### Perceive
- **Perceiver / Context Assembler** — assembles the reasoning input: user input + recalled memory + persona + available tool/skill catalog + prior step state.

##### Reason (Think)
- **Reasoner** — calls the Agent port (Conductor role); produces the next Intent. *[Self-correction INJECT call-point fires immediately before this.]*
- **Decision Interpreter** — normalises the Conductor's raw output into a structured intent: RESPOND / ACT / FINISH.

##### Act
- **Actuator** — dispatches the structured intent to the right port and executes it. When the intent is ACT, the Actuator dispatches one or more Worker agents via the Agent port. *[Guardrails GATE call-point fires immediately before dispatch.]*

##### Observe
- **Observer / Evaluator** — captures the result, updates Run State, emits the trace, and decides continue-vs-stop (the loop's exit criterion). *[Self-correction CAPTURE call-point fires immediately after.]*

##### Spanning all four phases (the kernel)
- **Loop Controller** — drives the cycle; owns iteration count, stop conditions, budget.
- **Run State** — the in-flight working context carried across phases; distinct from long-term Memory.

---

### Persona

The identity and configuration the loop carries into every Reason phase. Loaded once at composition time from a static `persona.txt`; injected into each Reason prompt via Perceive. No mutation or dynamic update in early milestones — swapping the persona is a content edit, not a code change.

---

### Router

The intent → provider allocation brain. A **core-side component** (not a port): it receives the loop's intent and selects which Agent port adapter should handle this request, according to policy:

- **Privacy gate** — local-first when data sensitivity requires.
- **Cost / volume** — bulk or low-complexity tasks route to local.
- **Capability** — hard reasoning or rich tool use routes to the strongest available model.
- **Control-level preference** — KIND A (runtime-gatable) vs KIND B (pre-run scope only).
- **Consortium override / live fallback** — manual or automatic reassignment.

Policy lives in the Router (sovereign core). The Agent port and its adapters are the mechanism. In M1, the Router is a minimal single-provider stub wired in Python code — it grows into a full policy engine by M6.

---

## Cross-cutting faculties — call-points, not ports

Self-correction, Observability, and Guardrails are **not ports and not separate structural components**. They are **core-internal**, attached to the loop via named **call-points**. An event bus was explicitly considered and rejected as over-engineering — call-points are direct, testable, and impose zero indirection overhead.

| Call-point | When it fires | Faculty |
|-----------|---------------|---------|
| Before Reason | Immediately before the Reasoner invokes the Conductor | **Self-correction INJECT** — relevant lessons from Memory are retrieved and injected into the Reasoner context |
| Before Act | Immediately before the Actuator dispatches | **Guardrails GATE** — approval gate on consequential actions; may veto or redirect the intent |
| Each phase transition | At every perceive → reason → act → observe boundary | **Observability RECORD** — reasoning trace captured; glass-box visibility at build-time, persistent trace on every run |
| After Observe | Immediately after the Observer updates Run State | **Self-correction CAPTURE** — lessons extracted from this cycle and written to Memory |

These faculties use the Memory and Tools ports as needed — but they are wired into the loop as named call-points, not as peers in the port list or boxes in a component diagram.

---

## Provider adapters and control-level

Every provider — subscription CLI wrapper, cloud API, or local vLLM — is exposed behind the **Agent port** with a uniform interface. Completion-only models (local vLLM, direct API calls) are wrapped in a thin **"degenerate agent"** (a minimal perceive → call → return shell) so they satisfy the same port contract. Everything behind the Agent port is an agent; local LLMs are **first-class agents**.

Two control shapes exist, expressed as a **`control_level`** field on the adapter — not as separate ports:

| `control_level` | Who owns the loop | Guardrail model | Examples |
|----------------|------------------|-----------------|---------|
| **KIND A — we own the loop** | Our core loop (via the degenerate-agent wrapper) | **Runtime-gatable** — our loop can inspect and veto each action step | Local vLLM (Llama-class via LiteLLM); true-API models (Anthropic API direct) |
| **KIND B — provider owns the loop** | The provider's internal loop | **Pre-run scope** (tool-restriction + bounded mandate set before launch) **+ mid-run ABORT** (circuit-breaker via the streamed trace); no per-action mid-run veto | Subscription Claude via Claude Code / Agent SDK; OpenAI Codex |

**KIND B mid-run visibility.** The adapter MUST stream the delegated run's intermediate trace (tool-calls / messages) into Observability. The pattern is proven — the Velhari worker run-output approach. "Pre-run + abort" is not blind: we watch the trace; we simply cannot veto per-step mid-run.

**KIND B adapter requirement.** The Delegated-Agent adapter MUST enforce tool-restriction + bounded mandate before launch. If a provider cannot scope tools up front, the adapter must refuse or sandbox — otherwise the "pre-run guardrail" promise is hollow.

**Velhari reframe.** Delegating to a full external agent (the Velhari pattern) was the right instinct. What it lacked was the adapter seam this port now provides. The delegation was never the mistake; the missing seam was.

---

## Structural shape (ASCII overview)

```
╔══════════════════════════════════════════════════════════════════════════╗
║  SOVEREIGN CORE                                                          ║
║                                                                          ║
║  ┌────────────────────────────────────────────────────────────────────┐  ║
║  │  AGENT LOOP                                                        │  ║
║  │                                                                    │  ║
║  │  [Perceive]──►[Reason (Think)]──►[Act]──►[Observe]──► (repeat)   │  ║
║  │               │                  │       │                         │  ║
║  │  Self-corr.   │ INJECT           │ GATE  │ CAPTURE                 │  ║
║  │  call-points ─┘ (before Reason)  │(bef.) └─(after Observe)        │  ║
║  │                                  │ Act)                            │  ║
║  │  Observability RECORD ───────────┴ fires at every phase boundary  │  ║
║  │                                                                    │  ║
║  │  Loop Controller + Run State span all phases                       │  ║
║  └────────────────────────────────────────────────────────────────────┘  ║
║                                                                          ║
║  Persona (injected at Reason)                                            ║
║  Router  (core-side: intent → adapter selection by policy)               ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║  6 PORTS                                                                 ║
║                                                                          ║
║  ┌─────────────────────────────────────────────────────────────────┐     ║
║  │  Agent port — N adapters, each tagged control_level             │     ║
║  │    KIND A (we own loop, runtime-gatable): local vLLM, API       │     ║
║  │    KIND B (provider owns loop, pre-run+abort): SDK / Codex      │     ║
║  │  Conductor role → Reason phase  │  Worker role → Act phase      │     ║
║  └─────────────────────────────────────────────────────────────────┘     ║
║                                                                          ║
║  Memory  │  Tools  │  Skills  │  Connectors  │  I/O Gateway             ║
╚══════════════════════════════════════════════════════════════════════════╝
```

Each arrow from the core to an external concern crosses a port boundary. The core never imports an adapter; adapters import (and implement) port contracts.

---

## M1 — Walking skeleton scope

The first milestone builds the minimal frame that every subsequent component plugs into.

| Component / concern | M1 scope |
|--------------------|----------|
| Agent Loop | Minimal perceive → reason → act → observe cycle (`loop.py`) |
| Persona | Static `persona.txt`; loaded at composition time; injected in Reason |
| Agent port | One adapter: `ClaudeAdapter` (KIND B — Agent SDK, subscription Claude) |
| Router | Minimal stub — one provider, wired in Python (`agent.py`); grows at M6 |
| I/O Gateway | CLI only |
| Self-correction call-points | Wiring stubs only (no-op); full implementation at M8 |
| Guardrails GATE | `allowed_tools` scoping on `act()` — the sole guardrail in M1 |
| Observability RECORD | Wall-clock timing via stdlib `logging` at DEBUG level only; structured trace is M2 |

**M1 adapter internals — KIND B split design.** The `ClaudeAdapter` deliberately splits Reason and Act into separate Agent SDK queries to prove the port-seam is structural, not nominal:

- `reason()` → `query(allowed_tools=[])` → structured Intent returned (one subprocess spawn; zero side effects; the Decision Interpreter step is inside the adapter)
- `act()` → `query(allowed_tools=[...scoped])` → Agent SDK runs its own internal tool loop and returns a final result (one subprocess spawn per act call; Axiom writes no tool-execution harness)

**Future latency lever (captured, not built).** Because `reason()` uses no tools, a later adapter implementation could replace the Agent SDK subprocess with a direct Client-SDK API call — eliminating subprocess overhead for the Reason phase. The `ReasonPort` interface is the seam; only the adapter changes.

Nothing in M1 forces a core rewrite when later milestones arrive — later components plug into the same frame.

**M2 · Observability** lands immediately after M1, on purpose: it is the instrument that makes every subsequent milestone judgeable and is the foundational trust layer.

The remaining ports and faculties (Memory, Tools, Skills, Connectors, full Router, Self-correction) follow in dependency order per the roadmap milestones.

---

## Out of scope for this document

- Contracts and interfaces between components (per-milestone `design.md`).
- Implementation-level decisions (language constructs, library choices, file layout).
- Milestone sequencing rationale (see `001-agent-core-roadmap.md`).

---

## Open questions

| # | Question | Status |
|---|----------|--------|
| OQ-1 | **Conductor binding — fixed vs Router-swappable per task?** Should the Router commit to a single Conductor model for the session lifetime, or re-evaluate which model acts as Conductor on a per-task or per-cycle basis? Trade-off: stable identity and session coherence vs dynamic quality-cost optimisation. | Kaushik decision pending. |
