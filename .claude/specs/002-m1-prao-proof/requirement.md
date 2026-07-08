# M1 — PRAO Proof: Walking Skeleton Requirements

**Spec:** `002-m1-prao-proof`
**Authored:** 2026-07-07 (Kaushik + Velasari, live design session)
**Status:** Draft — ready for human review + /dryrun-design

---

## Overview

M1 is the walking skeleton of the Axiom agent-core. Its sole job is to **prove two things**:

> **Structural alignment:** M1 uses the existing canonical package-per-component layout (`src/axiom/` with per-component sub-packages) locked by the roadmap Code Structure section (2026-07-04). No new file layout is introduced.

1. **The port-adapter PRAO loop holds** — swapping the provider adapter swaps the provider, with the master loop code unchanged.
2. **The real latency cost of the split design** — because each Agent SDK call spawns a `claude-code` CLI subprocess, the "split" (separate `reason()` and `act()` queries) means ~2 spawns per reason→act cycle. M1 must measure this empirically so the decision to split (or later fuse) is grounded in data, not assumption.

M1 is NOT a feature release. It is a structural proof — a minimal, wired-in skeleton whose shape every subsequent milestone will plug into.

**Architecture note (supersedes `architecture.md` where they conflict):** The master PRAO loop IS the orchestrator — orchestration is a behaviour of the loop, not a separate component. Master and sub-agents are structurally identical (same loop, same ports); the difference is role and config, not code structure. The Router (from the roadmap) is **not in M1** — there is one adapter, wired in code.

**Language:** Python (`axiom` package, `src/` layout).

---

## User Stories

### MPP-1: PRAO Loop Runs End-to-End via the Claude Adapter

**As a** developer,
**I want** the master PRAO loop to complete a full perceive → reason → act → observe cycle using the Claude adapter,
**so that** I can verify the port-adapter boundary holds — the master loop contains no provider-specific code, and the Claude adapter is a legitimate drop-in behind the port interface.

**Acceptance Criteria:**
- Running the CLI with any non-trivial prompt triggers at least one complete PRAO cycle (all four phases execute in sequence).
- The master loop (`loop.py` or equivalent) contains zero imports of `claude_agent_sdk` or any other provider library — all provider access is behind the port interface.
- The Claude adapter class implements the port interface (`PerceivePort`, `ReasonPort`, `ActPort`, `ObservePort` or the equivalent four-phase contract) without the master loop knowing its concrete type.
- The loop terminates on `RESPOND` or `FINISH` intent and returns control to the CLI without hanging.

---

### MPP-2: Trivial Input Short-Circuits at reason() — No act() Spawned

**As an** end-user,
**I want** a simple, conversational input (e.g. "Hello") to be handled by a single `reason()` call that returns `RESPOND` immediately — with no `act()` call made,
**so that** trivial exchanges are cheap (one subprocess spawn, not two), and the short-circuit triage works as designed.

**Acceptance Criteria:**
- Sending "Hello" (or equivalent trivial, no-tool input) results in exactly **one** Agent SDK query (the `reason()` call).
- `reason()` returns intent `RESPOND(text)` for this input.
- `act()` is **not** called — no second Agent SDK subprocess is spawned for this input.
- The user receives a coherent response in the CLI.
- The latency for this path is measured and reported (see MPP-5).

---

### MPP-3: Tool-Requiring Task Drives the Full reason → act → observe Loop

**As an** end-user,
**I want** a task that requires tool use to drive the full reason → act → observe → (repeat) → RESPOND cycle,
**so that** multi-step agent work executes correctly and the loop's iteration and stop-condition logic is exercised.

**Acceptance Criteria:**
- A prompt that requires at least one tool action causes `reason()` to return intent `ACT(instruction)`.
- `act()` is called with the bounded instruction from the intent; the Agent SDK runs its internal tool loop; the result is returned to `observe()`.
- `observe()` captures the result and feeds it back into the next `perceive()` → `reason()` call.
- The loop continues until `reason()` returns `RESPOND` or `FINISH`.
- The final response is delivered to the CLI user.
- The total latency for this multi-cycle path is measured and reported (see MPP-5).

---

### MPP-4: Provider Adapter is a Drop-In — Master Loop is Untouched for a Second Adapter

**As a** developer,
**I want** the port interface to be defined such that a second provider adapter (e.g. a local vLLM adapter) could be written and substituted **without changing any master loop code**,
**so that** the port-adapter seam is real and not just nominal — M1 structurally proves provider-agnosticity.

**Acceptance Criteria:**
- There exists a clearly defined port interface (abstract base class or protocol) with the four phase methods: `perceive()`, `reason()`, `act()`, `observe()` (or equivalent names consistent with the design).
- The Claude adapter is the only concrete implementation in M1, but it implements the interface fully.
- A second adapter could be written by implementing the same interface — confirmed by code inspection: the master loop accepts the interface type, not the concrete adapter type.
- No conditional branching on provider type exists in the master loop.
- A fake in-memory adapter (`tests/fake_adapter.py`) implementing all four Protocols exists in the test suite as the second-adapter existence proof — it confirms the port is implementable without the Claude SDK.

---

### MPP-5: M1 Measures and Reports Latency (Hello Floor + Real Task)

**As a** developer,
**I want** M1 to measure and surface the wall-clock latency of two scenarios — (a) the "Hello" floor (one subprocess spawn) and (b) a real multi-cycle task (multiple spawns),
**so that** I have empirical data on the split design's subprocess overhead to make an informed decision about the reason/act split cost before M2.

**Acceptance Criteria:**
- After each run, total wall-clock elapsed time is emitted via Python stdlib **`logging`** at **`DEBUG` level only** — never to CLI stdout, and not at `INFO` or `ERROR` level. Rationale: retained for debugging without cluttering normal output.
- The "Hello" scenario latency is captured in M1 acceptance testing and recorded in the design or a test result artifact (retrieved from DEBUG logs).
- The real-task scenario latency is captured across at least one complete multi-cycle run (reason→act→observe→reason→RESPOND or similar).
- Both numbers are available in the M1 sign-off deliverable via DEBUG log output. No formal dashboard; no persistent storage of timing.
- An `axiom`-namespaced logger is configured at DEBUG level, writing to stderr, enabled via the `--debug` CLI flag (configured by `agent.py`); the latency record is retrievable from this stream at sign-off by running `python -m axiom.interface.cli --debug`.
- **Known future lever (captured, not built):** because `reason()` uses no tools, it could later be replaced with a direct Client-SDK API call (no subprocess) to reduce the split latency floor. This is noted as a design seam but is explicitly out of scope for M1.
- **M2 note (not M1):** replacing stdlib logging with `structlog` for structured/machine-readable traces is a M2 Observability option — out of scope here.

---

### MPP-6: Agent Carries a Minimum Static Persona

**As an** end-user,
**I want** the agent to carry a minimal, static persona string injected into every `reason()` call,
**so that** responses have a consistent identity even at M1, without any evolving-persona machinery.

**Acceptance Criteria:**
- A persona string (loaded from `src/axiom/persona/persona.txt` by the `persona/` package) is injected into the `reason()` prompt context via `perceive()`.
- The persona is loaded and wired by the core assembly (`agent.py`), not the CLI. The CLI (`interface/cli.py`) is pure I/O — it never reads or passes the persona.
- The agent's responses reflect the persona (consistent voice/identity) across a multi-turn CLI session.
- No dynamic persona update, mutation, or persistence logic exists in M1 — the persona is read-only for this milestone.
- Swapping the persona requires only changing `persona.txt`, not code.

---

## Infrastructure Dependencies

| Dependency | Status | Notes |
|---|---|---|
| Python ≥ 3.11 | Must exist | Language for `axiom` package |
| `claude_agent_sdk` (Python) | Must be installed | Backs the Claude adapter; uses `query()` / `ClaudeSDKClient` |
| Claude Code CLI | Must be installed + authenticated | Agent SDK spawns it as subprocess; requires Claude Max subscription |
| `src/axiom` package layout | To be created in M1 | Standard Python `src/` layout; package name `axiom` |

---

## Out of Scope

- **Memory / CM** — no cross-session recall; memory is its own port for a later milestone.
- **Observability (M2)** — no structured reasoning trace in M1; measurement is manual timing only.
- **Tools registry / Skills** — M1 uses the Agent SDK's native tool capability inside `act()`; no Axiom-owned tool registry.
- **Full guardrail policy** — M1 guardrails = `allowed_tools` scoping on the `act()` query only (Agent SDK pre-run scoping).
- **Router / multi-provider** — one adapter, wired in code; no routing policy.
- **Orchestrator / multi-agent consortium** — single master loop only; no sub-agent dispatch.
- **Dynamic / evolving persona** — static persona string only.
- **YAML / declarative config** — master loop is wired in Python code; configurability is a later milestone.
- **Web interface** — CLI only.
- **Self-correction hooks** — M8 concern.
- **Connectors** — M9 concern.

---

## Open Questions

_(None at time of authoring. Ambiguities encountered during /dryrun-design or implementation will be tracked here.)_
