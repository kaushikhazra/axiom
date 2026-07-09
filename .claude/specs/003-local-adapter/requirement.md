# M3 — Local Adapter: Requirements

**Spec:** `003-local-adapter`
**Authored:** 2026-07-09 (Velasari)
**Status:** Draft — ready for review + /dryrun-design

---

## Overview

M3 is the **open/closed extensibility proof** for the PRAO architecture established in M1. Its sole job is to prove:

> A second, non-Claude provider adapter (backed by a local model via LiteLLM + Ollama) slots into the **identical PraoLoop** with **zero changes** to `loop.py` and `interfaces.py`. The master loop stays the driver.

M3 also resolves the W3 design debt from M1: `perceive()` and `observe()` — provider-independent logic duplicated across adapters — are extracted into a shared location that both `ClaudeAdapter` and `LocalAdapter` use, achieving DRY without breaking any existing tests or contracts.

The local adapter uses **qwen2.5:7b** via Ollama, accessed through **direct `litellm.completion()` calls** (no Google ADK). Unlike ClaudeAdapter (which delegates tool execution to the Claude SDK's internal tool loop), LocalAdapter must supply its **own tool-execution harness** inside `act()` — local completion models have no built-in tool loop.

**Architecture note:** LocalAdapter is NOT a conductor, NOT a router. It is a second concrete adapter (local LiteLLM/Ollama adapter) behind the same four port Protocols. The router/conductor is DEFERRED — out of scope. `agent.py` wires one adapter at a time; selecting between them is a manual code change in M3.

**Language:** Python (`axiom` package, `src/` layout — same as M1).

---

## User Stories

### MLA-1: LocalAdapter Satisfies All Four Port Protocols — Same PraoLoop, Zero Loop Changes

**As a** developer,
**I want** a `LocalAdapter` class that implements `PerceivePort`, `ReasonPort`, `ActPort`, and `ObservePort` from `interfaces.py`, wired into the same `PraoLoop` with zero changes to `loop.py` or `interfaces.py`,
**so that** the port-adapter seam proven in M1 is confirmed to be real — a second provider genuinely drops in, and the open/closed principle holds.

**Acceptance Criteria:**
- `LocalAdapter` implements all four port Protocol methods with the exact signatures defined in `interfaces.py`.
- `PraoLoop` can be constructed with a `LocalAdapter` instance in all four slots, identically to how `ClaudeAdapter` was wired in M1.
- **`loop.py` has zero diff from its M1 state.** No imports added, no logic changed, no conditional branching on provider type.
- **`interfaces.py` has zero diff from its M1 state.** No new protocols, no signature changes, no new types.
- `LocalAdapter` uses LiteLLM directly as the model backend: `litellm.completion(model="ollama_chat/qwen2.5:7b")` against a local Ollama at `OLLAMA_API_BASE=http://localhost:11434`. No Google ADK dependency.
- PraoLoop remains the sole driver (per-port calls). No external runner or agent loop is used.
- `reason()` is tool-less (same as ClaudeAdapter); `act()` has tools via the LocalAdapter's own tool-execution harness.
- The adapter handles all errors from the local model stack (Ollama down, model not loaded, timeout) and raises `AdapterError` — same error contract as ClaudeAdapter.

---

### MLA-2: Shared perceive()/observe() — W3 Design Debt Resolved

**As a** developer,
**I want** the provider-independent `perceive()` and `observe()` logic extracted into a shared location used by both `ClaudeAdapter` and `LocalAdapter`,
**so that** the W3 design debt from M1 is resolved — no duplication of context-assembly or state-update logic across adapters.

**Acceptance Criteria:**
- A shared base class or mixin provides `perceive()` and `observe()` implementations.
- `ClaudeAdapter` adopts the shared implementation with **zero behaviour change** — its `perceive()` output and `observe()` state mutations remain identical.
- `LocalAdapter` uses the same shared implementation.
- M1's existing 26 tests (`tests/test_contracts.py`) pass without modification — the refactor is invisible to the test layer.
- `FakeAdapter` in `tests/fake_adapter.py` is NOT required to adopt the shared base (it is a test double with its own tracking logic).
- `loop.py` and `interfaces.py` remain untouched.

---

### MLA-3: act() Tool-Execution Harness — Local Tool Loop

**As a** developer,
**I want** `LocalAdapter.act()` to implement its own tool-execution harness that gives qwen2.5:7b a tool schema, runs a tool-calling loop (model proposes → harness executes → feed result back → repeat), bounded by a max-tool-iterations guard,
**so that** action tasks can execute real tools despite the local model having no built-in tool loop.

**Acceptance Criteria:**
- `act()` exposes at least one self-contained local tool: a **shell/command execution tool** (mirrors M1's MPP-3 exemplar: "list files in a directory and summarise").
- The tool-calling loop iterates: send instruction + tool schemas to model → parse tool-call response → execute tool → feed result back → repeat until model produces a final text answer (no tool call).
- A `MAX_TOOL_ITERATIONS` guard (default: 5) prevents infinite loops — if exceeded, `act()` returns the best partial result accumulated so far (or an error message).
- Tool-call parsing handles the model's tool-call format (OpenAI function-calling format, as standardised by LiteLLM).
- Errors during tool execution (command fails, timeout) are caught and fed back to the model as error results — the model can retry or adjust.
- A web-search tool is OPTIONAL/stretch — the milestone's E2E does NOT depend on it.
- The harness is unit-testable with a stubbed/fake model (no live Ollama required for unit tests).

---

### MLA-4: Fast Unit Tests — Adapter + Shared Base + Tool Harness

**As a** developer,
**I want** fast unit tests covering the LocalAdapter, the shared perceive/observe base, and the act() tool-harness loop, all using fake/stubbed models (no live Ollama),
**so that** the adapter's logic is verified deterministically and quickly in CI without requiring GPU hardware or a running Ollama instance.

**Acceptance Criteria:**
- Unit tests cover:
  - `LocalAdapter.reason()` with a stubbed model returning valid JSON intent → correct `Intent` dataclass returned.
  - `LocalAdapter.reason()` with a stubbed model returning malformed JSON → parse-retry + fallback path exercised.
  - `LocalAdapter.act()` tool-harness loop: stubbed model proposes tool call → tool executes → result fed back → model produces final answer.
  - `LocalAdapter.act()` MAX_TOOL_ITERATIONS guard: stubbed model always proposes tool calls → harness stops at limit.
  - Shared `perceive()` produces correct context string from `RunState`.
  - Shared `observe()` correctly updates `RunState.history` and `cycle_count`.
  - `ClaudeAdapter` still passes its existing behaviour after adopting the shared base (covered by M1's 26 tests remaining green).
- All unit tests run without Ollama, without network, without GPU — pure in-process.
- Tests use `pytest` (same framework as M1).

---

### MLA-5: Live E2E on qwen2.5:7b — Trivial + Real Tool Cycle

**As a** developer,
**I want** live end-to-end tests that run against the real qwen2.5:7b model via Ollama, covering both a trivial RESPOND short-circuit and a real reason→act→observe cycle using a self-contained local tool,
**so that** the local adapter is proven to work with a real model, not just stubs.

**Acceptance Criteria:**
- **E2E trivial test:** Sending a simple conversational input (e.g. "What is the capital of France?") results in `reason()` returning `RESPOND` with a coherent text answer. `act()` is NOT called. The full PraoLoop runs and returns a response.
- **E2E tool test:** Sending a task requiring tool use (e.g. "List the files in the current directory and summarise") causes `reason()` to return `ACT`, `act()` to run the tool-harness loop executing the shell tool, `observe()` to capture the result, and the loop to complete with a final `RESPOND`.
- Both tests run through the real `PraoLoop` — no mocking of the loop itself.
- Tests are marked with `@pytest.mark.e2e_local` (or equivalent) so they can be skipped in CI environments without Ollama.
- **Pre-warming:** E2E tests pre-warm the model via Ollama's `keep_alive` before timing, to separate cold-load latency from inference latency.
- Latency is logged at DEBUG level (same pattern as M1's timing utility).
- **Prerequisite:** Ollama must be running with qwen2.5:7b loaded. Tests skip gracefully (not fail) if Ollama is unavailable.

---

### MLA-6: M1 Test Suite Remains Green

**As a** developer,
**I want** all 26 existing M1 tests in `tests/test_contracts.py` to pass without any modification after the M3 changes (shared perceive/observe extraction + LocalAdapter addition),
**so that** the refactoring does not introduce regressions in the proven M1 architecture.

**Acceptance Criteria:**
- Running `pytest tests/test_contracts.py` passes all 26 tests with zero failures, zero errors.
- No test file from M1 is modified — the refactor is invisible to the existing test suite.
- `FakeAdapter` in `tests/fake_adapter.py` remains unchanged (it is a test double with its own logic, not required to adopt the shared base).
- `loop.py` and `interfaces.py` are untouched — import paths and contracts are stable.

---

## Infrastructure Dependencies

| Dependency | Status | Notes |
|---|---|---|
| Python ≥ 3.11 | Exists | Same as M1 |
| `litellm` (Python) | Must be installed | LLM gateway — `litellm.completion()` routes to Ollama for local models |
| Ollama | Must be running locally | Serves qwen2.5:7b; `OLLAMA_API_BASE=http://localhost:11434` |
| qwen2.5:7b | Must be pulled in Ollama | `ollama pull qwen2.5:7b` — already installed on dev machine (16GB RAM, RTX 3060 4GB VRAM, Ryzen 7 5800H) |
| M1 codebase | Must be green | `loop.py`, `interfaces.py`, `claude_adapter.py`, `tests/` — all untouched by M3 |

---

## Out of Scope

- **Router / provider selection policy** — M3 wires one adapter at a time in `agent.py`; no runtime routing. Router is M6.
- **Conductor / multi-agent orchestration** — single master loop; no sub-agent dispatch.
- **ADK / Google ADK** — not a dependency of this milestone. LiteLLM is used directly. PraoLoop is the sole orchestrator.
- **Web-search tool** — optional/stretch; E2E does NOT depend on it.
- **Memory / cross-session recall** — same as M1: ephemeral `RunState.history` only.
- **Streaming** — no streaming from local model to CLI in M3.
- **Dynamic persona** — static persona, same as M1.
- **YAML / declarative config** — Python wiring only.
- **Performance tuning / quantisation** — qwen2.5:7b runs as-is via Ollama defaults.
- **Fused reason+act optimisation** — the split design is maintained; fusion is a separate concern.
- **Changes to loop.py or interfaces.py** — hard constraint; these files are frozen for M3.

---

## Open Questions

_(None at time of authoring. Ambiguities encountered during /dryrun-design or implementation will be tracked here.)_
