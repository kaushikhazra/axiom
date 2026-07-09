# M3 — Local Adapter: Requirements

**Spec:** `003-local-adapter`
**Authored:** 2026-07-09 (Velasari)
**Revised:** 2026-07-09 (Velasari — smolagents migration; supersedes litellm hand-rolled-tool design)
**Status:** Draft — ready for review + /dryrun-design

---

## Overview

M3 is the **open/closed extensibility proof** for the PRAO architecture established in M1. Its sole job is to prove:

> A second, non-Claude provider adapter (backed by a local model via smolagents + Ollama) slots into the **identical PraoLoop** with **zero changes** to `loop.py` and `interfaces.py`. The master loop stays the driver.

M3 also resolves the W3 design debt from M1: `perceive()` and `observe()` — provider-independent logic duplicated across adapters — are extracted into a shared location that both `ClaudeAdapter` and `LocalAdapter` use, achieving DRY without breaking any existing tests or contracts. (This extraction is already complete.)

The local adapter uses **qwen2.5:7b** via Ollama, accessed through **smolagents** (`LiteLLMModel` for model access, `CodeAgent` for tool-using action execution). Unlike the prior litellm hand-rolled design, LocalAdapter authors **zero tool code** — all tools (web search, code execution) come from smolagents' base toolbox via `add_base_tools=True`. This mirrors ClaudeAdapter's relationship with its SDK: the SDK provides tools; the adapter is a thin bridge.

**Architecture note:** LocalAdapter is NOT a conductor, NOT a router. It is a second concrete adapter (local smolagents/Ollama adapter) behind the same four port Protocols. The router/conductor is DEFERRED — out of scope. `agent.py` wires one adapter at a time; selecting between them is a manual code change in M3.

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
- `LocalAdapter` uses **smolagents** as the model/agent backend: `LiteLLMModel(model_id="ollama_chat/qwen2.5:7b", api_base=<OLLAMA_API_BASE>)` for model access, `CodeAgent` for tool-bearing action execution. No Google ADK dependency. No direct `litellm.completion()` calls as a primary dependency — litellm is a transitive dependency of smolagents.
- **Zero axiom-authored tool code.** No tool schemas, no tool executors, no tool registries defined in axiom source. All tools come from smolagents' base toolbox (`add_base_tools=True`): `DuckDuckGoSearchTool` (web search) and `PythonInterpreterTool` (code execution). The adapter is a thin bridge, not a tool provider.
- PraoLoop remains the sole outer driver (per-port calls). smolagents' `CodeAgent` owns a provider-internal worker loop inside `act()` only — this is KIND-B delegation, same pattern as ClaudeAdapter delegating to the Claude SDK's internal tool loop.
- `reason()` is tool-less (same as ClaudeAdapter); `act()` delegates to smolagents CodeAgent.
- The adapter handles all errors from the local model stack (Ollama down, model not loaded, timeout, smolagents errors) and raises `AdapterError` — same error contract as ClaudeAdapter.

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

### MLA-3: act() via smolagents CodeAgent — Provider-Owned Worker Loop

**As a** developer,
**I want** `LocalAdapter.act()` to delegate tool-using execution to a smolagents `CodeAgent` which owns its own internal multi-step loop (code generation → tool execution → iteration → final answer),
**so that** action tasks execute real tools (web search, Python code execution) without any axiom-authored tool code, tool schemas, or tool-execution harness.

**Acceptance Criteria:**
- `act()` creates or reuses a smolagents `CodeAgent` configured with `add_base_tools=True`, providing `DuckDuckGoSearchTool` (web search) and `PythonInterpreterTool` (code execution).
- `act()` calls `CodeAgent.run(instruction)` and returns the result string.
- **Zero axiom-authored tool implementations.** No `_execute_shell_tool`, no `SHELL_TOOL_SCHEMA`, no `_run_tool_loop`, no tool registry. All tool execution is handled by smolagents.
- CodeAgent uses **CodeAct** (acts by writing Python, not JSON tool-calls) — this is the reliability mechanism for weak local models like qwen2.5:7b.
- `max_steps` on the CodeAgent bounds the internal loop (replaces the old `MAX_TOOL_ITERATIONS`).
- Errors from the CodeAgent (model failures, tool execution errors) are caught and either fed back through the smolagents internal loop or raised as `AdapterError` at the boundary.
- **Security:** Code execution uses smolagents' `PythonInterpreterTool` — the SDK's own sandboxed interpreter with restricted namespace. `additional_authorized_imports` is scoped to the minimum needed. This closes the raw-shell (`subprocess.run(shell=True)`) security gap from the prior design. No raw subprocess execution.

---

### MLA-4: Fast Unit Tests — Adapter + Shared Base + CodeAgent Delegation

**As a** developer,
**I want** fast unit tests covering the LocalAdapter, the shared perceive/observe base, and the act() CodeAgent delegation, all using fake/stubbed models (no live Ollama),
**so that** the adapter's logic is verified deterministically and quickly in CI without requiring GPU hardware or a running Ollama instance.

**Acceptance Criteria:**
- Unit tests cover:
  - `LocalAdapter.reason()` with a stubbed model returning valid JSON intent → correct `Intent` dataclass returned.
  - `LocalAdapter.reason()` with a stubbed model returning malformed JSON → parse-retry + fallback path exercised.
  - `LocalAdapter.act()` delegates to CodeAgent.run() and returns the result string.
  - `LocalAdapter.act()` CodeAgent error → `AdapterError` raised.
  - Shared `perceive()` produces correct context string from `RunState`.
  - Shared `observe()` correctly updates `RunState.history` and `cycle_count`.
  - `ClaudeAdapter` still passes its existing behaviour after adopting the shared base (covered by M1's 26 tests remaining green).
- All unit tests run without Ollama, without network, without GPU — pure in-process.
- Tests use `pytest` (same framework as M1).

---

### MLA-5: Live E2E on qwen2.5:7b — Three Scenarios

**As a** developer,
**I want** live end-to-end tests that run against the real qwen2.5:7b model via Ollama, covering three scenarios that exercise the full smolagents integration,
**so that** the local adapter is proven to work with a real model and real tools, not just stubs.

**Acceptance Criteria:**
- **E2E #1 — "hello" RESPOND-only:** Sending a simple conversational input (e.g. "Hello, how are you?") results in `reason()` returning `RESPOND` with a coherent text answer. `act()` is NOT called. The full PraoLoop runs and returns a response. No tools invoked.
- **E2E #2 — web search (DuckDuckGoSearchTool):** Sending "What is the current weather in Durgapur, West Bengal, India?" causes `reason()` to return `ACT`, `act()` to run the CodeAgent which uses `DuckDuckGoSearchTool` to perform a real web search, `observe()` to capture the result, and the loop to complete with a final `RESPOND` containing weather information grounded in search results.
- **E2E #3 — Python file creation + execution (literal requirement):** Sending "Create a python file in the current folder, which will print hello, execute it, and show the output" causes `reason()` to return `ACT`, `act()` to run the CodeAgent which: (1) writes a real `hello.py` file to the current working directory via `open('hello.py', 'w')`, (2) executes `hello.py` via `subprocess.run(['python', 'hello.py'], capture_output=True, text=True)` or equivalent, (3) captures and returns the stdout. `observe()` captures the result. The loop completes with a final response containing "hello world". **This is a real file written to disk and really executed — NOT merely running `print('hello world')` inline in the interpreter's memory.** `subprocess` is included in `additional_authorized_imports` for this purpose (see design SS5.2).
- All three tests run through the real `PraoLoop` — no mocking of the loop itself.
- Tests are marked with `@pytest.mark.e2e_local` so they can be skipped in CI environments without Ollama.
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
| Python >= 3.11 | Exists | Same as M1 |
| `smolagents` (Python) | Must be installed | Agentic SDK — provides `LiteLLMModel`, `CodeAgent`, `DuckDuckGoSearchTool`, `PythonInterpreterTool`. Depends on `litellm` transitively. |
| Ollama | Must be running locally | Serves qwen2.5:7b; `OLLAMA_API_BASE=http://localhost:11434` |
| qwen2.5:7b | Must be pulled in Ollama | `ollama pull qwen2.5:7b` — already installed on dev machine (16GB RAM, RTX 3060 4GB VRAM, Ryzen 7 5800H) |
| M1 codebase | Must be green | `loop.py`, `interfaces.py`, `claude_adapter.py`, `tests/` — all untouched by M3 |

---

## Out of Scope

- **Router / provider selection policy** — M3 wires one adapter at a time in `agent.py`; no runtime routing. Router is M6.
- **Conductor / multi-agent orchestration** — single master loop; no sub-agent dispatch.
- **ADK / Google ADK** — not a dependency of this milestone.
- **Direct litellm.completion() calls** — replaced by smolagents' model/agent abstractions. litellm is a transitive dependency only.
- **Axiom-authored tool code** — no tool schemas, no tool executors, no tool registries. Tools come from smolagents.
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
