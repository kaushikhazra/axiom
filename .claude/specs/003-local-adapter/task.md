# M3 — Local Adapter: Implementation Tasks

**Spec:** `003-local-adapter`
**Status:** In Progress

---

## 1. Shared Base (`providers/base.py`)

- [x] Developer creates `src/axiom/providers/base.py` defining: module-level `INTENT_FORMAT_INSTRUCTIONS` constant (exact string moved from `claude_adapter.py`), module-level `_parse_intent(raw: str) -> tuple[Intent | None, str | None]` with enhanced pre-processing (strip code fences, extract first `{...}` via regex before falling back), and `PraoAdapterBase` class with `__init__(self, persona: str)`, `perceive(run_state: RunState) -> str`, and `observe(result: str, run_state: RunState) -> RunState`. Imports `axiom.interfaces` only — zero SDK imports. **E2E refinement (post-implementation):** `perceive()` history section uses label `[TOOL EXECUTION RESULTS — read these carefully]` and appends an explicit RESPOND-nudge note, discovered during live E2E — fixes qwen2.5:7b looping ACT after tool output. Design §3.3 documents the exact text. **Base.py accepted change:** `_parse_intent()` and `_extract_json_from_text()` use `json.loads(..., strict=False)` to tolerate literal control characters (e.g. bare `\n`) inside JSON string values emitted by weak local models. Backward-compatible: Claude's clean JSON unaffected. Verified by M1's 26 contract tests passing. Documented in design §15.
  _MLA-2_

---

## 2. ClaudeAdapter Refactor (`providers/claude_adapter.py`)

- [x] Developer refactors `src/axiom/providers/claude_adapter.py` to inherit from `PraoAdapterBase`: removes `_INTENT_FORMAT_INSTRUCTIONS`, `perceive()`, `observe()`, and `_parse_intent()` (all moved to `base.py`); imports `PraoAdapterBase` and `_parse_intent` from `axiom.providers.base`; updates `ClaudeAdapter.__init__` to call `super().__init__(persona=persona)` and remove `self._persona`. Zero behaviour change — M1's 26 tests must pass without modification.
  _MLA-2, MLA-6_

---

## 3. LocalAdapter Rewrite — smolagents (`providers/local_adapter.py`)

- [x] Developer rewrites `src/axiom/providers/local_adapter.py` to use smolagents instead of litellm hand-rolled-tool harness.
  - **Step 0 (W1 — mandatory first):** Developer verifies the `LiteLLMModel.__call__` call signature and return type against the **installed** smolagents version before writing `_query_model()`. Checks: (a) is `model(messages, stop_sequences=...)` the correct callable form? (b) does the return object have `.content` or a different attribute? Updates the PROVISIONAL comments in `_query_model()` once confirmed.
  - **Removes:** `SHELL_TOOL_SCHEMA`, `_execute_shell_tool()`, `_run_tool_loop()`, tool registry (`_tools`, `_tool_schemas`, `_tool_executors`), `MAX_TOOL_ITERATIONS`, `TOOL_COMMAND_TIMEOUT_SECS`, `import subprocess` (from module top-level — `subprocess` is now used inside the PythonInterpreterTool sandbox by model-generated code, not by axiom's adapter code), `import json` (if no longer needed).
  - **Adds:** deferred `from smolagents import CodeAgent, LiteLLMModel` inside `__init__`; `self._model = LiteLLMModel(model_id=..., api_base=...)`; stores `self._max_steps` and `self._authorized_imports` (default: `["math", "statistics", "datetime", "json", "re", "subprocess"]`). **Does NOT create `self._agent`** in `__init__` (W2 — fresh-per-call default).
  - **`act()` (W2):** Developer creates a fresh `CodeAgent(model=self._model, tools=[], add_base_tools=True, max_steps=self._max_steps, additional_authorized_imports=self._authorized_imports)` at the start of each `act()` call. Delegates to `agent.run(instruction)`, returns `str(result)`.
  - **Keeps:** `PraoAdapterBase` inheritance, `reason()` (tool-less model call + `_parse_intent` + retry + fallback), `AdapterError` error contract.
  _MLA-1, MLA-3_

---

## 4. Agent Wiring (`agent.py`)

- [x] Developer updates `src/axiom/agent.py`: already has `provider: str = "claude"` parameter and lazy import branch for `LocalAdapter`. No changes needed — `LocalAdapter` class name and constructor signature (`persona=persona_text`) are preserved.
  _MLA-1_

---

## 5. CLI Flag (`interface/cli.py`)

- [x] Developer updates `src/axiom/interface/cli.py`: already has `--provider` argument. No changes needed.
  _MLA-1_

---

## 6. Dependency Update (`pyproject.toml`)

- [x] Developer updates `pyproject.toml`: replaces `litellm` with `smolagents` in `[project].dependencies`; keeps `httpx` in `[project.optional-dependencies].dev`; keeps `[tool.pytest.ini_options].markers` declaring `"e2e_local"`.
  _MLA-1, MLA-5_

---

## 7. Shared Base Unit Tests (`tests/test_shared_base.py`)

- [x] Developer creates `tests/test_shared_base.py` — already exists and passes. No changes needed.
  _MLA-2, MLA-4_

---

## 8. LocalAdapter Unit Tests — smolagents (`tests/test_local_adapter.py`)

- [x] Developer rewrites `tests/test_local_adapter.py` for smolagents mocking. Covers: constructor defaults (model_id, ollama_api_base, max_steps); constructor smolagents import failure → `ModuleNotFoundError`; `reason()` with valid JSON intent (mocked `self._model` call); `reason()` with malformed JSON then retry succeeds; `reason()` with malformed JSON + retry fail → `[FALLBACK_RESPOND]`; `reason()` with JSON in code fences; `act()` happy path (mock `CodeAgent` class via `unittest.mock.patch('axiom.providers.local_adapter.CodeAgent')` so the freshly-constructed instance returns a result string from `.run()`); `act()` CodeAgent error → `AdapterError`; `act()` result type conversion (`str()` applied to non-string return from `.run()`). Note: since `act()` creates a fresh `CodeAgent` per call, tests patch the `CodeAgent` constructor, not `self._agent`. All tests use `unittest.mock.patch` / `MagicMock` — no live Ollama, no network.
  _MLA-3, MLA-4_

---

## 9. Post-E2E Defect Fixes (`providers/local_adapter.py`)

- [x] Developer fixes Defect A (loop non-termination) in `LocalAdapter.reason()` (`src/axiom/providers/local_adapter.py`): adds a sentinel check for `[TOOL EXECUTION RESULTS` in the `context` string (the label produced by `PraoAdapterBase.perceive()` when `run_state.history` is non-empty). When the sentinel is present, `reason()` prepends a LOCAL-ADAPTER-ONLY "SYSTEM INSTRUCTION" framing block to the prompt before calling `_query_model()`, explicitly directing qwen2.5:7b to respond with `RESPOND` and not re-issue `ACT`. The framing block is also retained in the retry path (`augmented_context` replaces bare `context` in `retry_context`). `loop.py`, `interfaces.py`, `base.py`, `claude_adapter.py` UNTOUCHED.
  _MLA-1, MLA-5_

- [x] Developer fixes Defect B (Windows cp1252 console crash) in `LocalAdapter.act()` (`src/axiom/providers/local_adapter.py`): adds `verbosity_level=0` kwarg to the `CodeAgent` constructor call. This suppresses all rich console logging from smolagents, preventing `UnicodeEncodeError` on Windows when emoji-containing content (e.g. DuckDuckGo search results) would otherwise be written to the cp1252 console. Applied at construction time on the fresh-per-call `CodeAgent`.
  _MLA-5_

- [x] Developer adds unit tests for Defect A and Defect B in `tests/test_local_adapter.py`: four new tests in `TestLocalAdapterReason` covering the sentinel detection, framing-block prepend, absence of framing without history, RESPOND intent return, and retry-path framing retention. One new test in `TestLocalAdapterAct` (`test_act_verbosity_level_zero_suppresses_console_logging`) and updated `test_act_passes_correct_constructor_args` to assert `verbosity_level=0`. All 77 tests pass.
  _MLA-4_

---

## 11. Live E2E Tests — 3 Scenarios (`tests/test_local_e2e.py`)

- [ ] Developer rewrites `tests/test_local_e2e.py` with `@pytest.mark.e2e_local` tests covering three scenarios: **(1)** "Hello" RESPOND-only — simple greeting → reason() returns RESPOND, act() NOT called, coherent text returned; **(2)** DuckDuckGo web search — "What is the current weather in Durgapur, West Bengal, India?" → reason() returns ACT, act() runs CodeAgent using DuckDuckGoSearchTool, observe() captures, loop completes with weather info; **(3)** Python file creation + execution (W3 — literal requirement) — "Create a python file in the current folder, which will print hello, execute it, and show the output" → reason() returns ACT, act() runs CodeAgent which writes a real `hello.py` to disk, executes it via `subprocess.run()`, captures stdout; observe() captures result; test assertion checks output contains "hello world". Test input MUST use Kaushik's literal phrasing (file creation + execution), NOT a rephrased "code execution only" variant. All tests: real PraoLoop + real LocalAdapter + real Ollama; pre-warm model before timing; skip gracefully if Ollama unreachable; latency logged at DEBUG.
  _MLA-5_
