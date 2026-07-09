# M3 — Local Adapter: Implementation Tasks

**Spec:** `003-local-adapter`
**Status:** In Progress

---

## 1. Shared Base (`providers/base.py`)

- [x] Developer creates `src/axiom/providers/base.py` defining: module-level `INTENT_FORMAT_INSTRUCTIONS` constant (exact string moved from `claude_adapter.py`), module-level `_parse_intent(raw: str) -> tuple[Intent | None, str | None]` with enhanced pre-processing (strip code fences, extract first `{...}` via regex before falling back), and `PraoAdapterBase` class with `__init__(self, persona: str)`, `perceive(run_state: RunState) -> str`, and `observe(result: str, run_state: RunState) -> RunState`. Imports `axiom.interfaces` only — zero SDK imports. **E2E refinement (post-implementation):** `perceive()` history section uses label `[TOOL EXECUTION RESULTS — read these carefully]` and appends an explicit RESPOND-nudge note, discovered during live E2E — fixes qwen2.5:7b looping ACT after tool output. Design §3.3 documents the exact text.
  _MLA-2_

---

## 2. ClaudeAdapter Refactor (`providers/claude_adapter.py`)

- [x] Developer refactors `src/axiom/providers/claude_adapter.py` to inherit from `PraoAdapterBase`: removes `_INTENT_FORMAT_INSTRUCTIONS`, `perceive()`, `observe()`, and `_parse_intent()` (all moved to `base.py`); imports `PraoAdapterBase` and `_parse_intent` from `axiom.providers.base`; updates `ClaudeAdapter.__init__` to call `super().__init__(persona=persona)` and remove `self._persona`. Zero behaviour change — M1's 26 tests must pass without modification.
  _MLA-2, MLA-6_

---

## 3. LocalAdapter (`providers/local_adapter.py`)

- [x] Developer creates `src/axiom/providers/local_adapter.py` defining: module-level constants (`MAX_TOOL_ITERATIONS = 5`, `PER_QUERY_TIMEOUT_SECS = 60`, `TOOL_COMMAND_TIMEOUT_SECS = 30`), `SHELL_TOOL_SCHEMA` dict in OpenAI function-calling format, `_execute_shell_tool(command: str) -> str` function (subprocess.run, bounded timeout, returns stdout+stderr+exit-code string; errors returned as strings, not raised), `LocalAdapter(PraoAdapterBase)` class with: `__init__` (deferred `import litellm` stored as `self._litellm`; tool registry as list of (schema, executor) tuples), `reason()` (tool-less `_query_model` call + `_parse_intent` + retry + fallback), `act()` (delegates to `_run_tool_loop`), `_query_model()` (sync litellm.completion, raises `AdapterError` on failure), `_run_tool_loop()` (bounded tool-calling loop: send→parse→execute→feed back→repeat; malformed args feed error string; executor exceptions feed error string; exhaustion returns last assistant text or explicit summary).
  _MLA-1, MLA-3_

---

## 4. Agent Wiring (`agent.py`)

- [x] Developer updates `src/axiom/agent.py`: adds `provider: str = "claude"` parameter to `Agent.__init__`; adds lazy import branch (`if provider == "local": from axiom.providers.local_adapter import LocalAdapter; adapter = LocalAdapter(persona=persona_text)`) before the existing ClaudeAdapter path; keeps M1 default behaviour (`provider="claude"`) unchanged.
  _MLA-1_

---

## 5. CLI Flag (`interface/cli.py`)

- [x] Developer updates `src/axiom/interface/cli.py`: adds `--provider` argument (choices `["claude", "local"]`, default `"claude"`) to the argparse parser; passes `provider=args.provider` to `Agent(...)`. Default `"claude"` preserves M1 behaviour.
  _MLA-1_

---

## 6. Dependency Update (`pyproject.toml`)

- [x] Developer updates `pyproject.toml`: adds `litellm` to `[project].dependencies`; adds `httpx` to `[project.optional-dependencies].dev`; adds `[tool.pytest.ini_options].markers` declaring `"e2e_local: marks tests requiring local Ollama (deselect with '-m not e2e_local')"`.
  _MLA-1, MLA-5_

---

## 7. Shared Base Unit Tests (`tests/test_shared_base.py`)

- [x] Developer creates `tests/test_shared_base.py` covering: `perceive()` with empty history (output has persona + request + intent instructions, no history section); `perceive()` with history (numbered steps present); `perceive()` persona injection; `observe()` appends result to `run_state.history`; `observe()` increments `cycle_count`; `observe()` returns the same `RunState` object; `_parse_intent()` clean JSON RESPOND/ACT/FINISH; `_parse_intent()` JSON wrapped in markdown code fence; `_parse_intent()` JSON embedded in explanation text; `_parse_intent()` invalid JSON returns `(None, error_str)`.
  _MLA-2, MLA-4_

---

## 8. LocalAdapter Unit Tests (`tests/test_local_adapter.py`)

- [x] Developer creates `tests/test_local_adapter.py` covering: constructor defaults; `reason()` with valid JSON intent (mocked litellm); `reason()` with malformed JSON then retry succeeds; `reason()` with malformed JSON + retry fail → `[FALLBACK_RESPOND]`; `reason()` with JSON in code fences (pre-processing path); `act()` single tool call happy path (mocked litellm: tool call → text response); `act()` malformed tool args → error string fed back; `act()` executor exception → error string fed back; `act()` MAX_TOOL_ITERATIONS exhaustion → returns partial text or exhaustion message; `act()` unknown tool → error string fed back; `_query_model()` error → `AdapterError` raised.
  _MLA-3, MLA-4_

---

## 9. Live E2E Tests (`tests/test_local_e2e.py`)

- [ ] Developer creates `tests/test_local_e2e.py` with `@pytest.mark.e2e_local` tests: skip gracefully if Ollama unreachable; pre-warm model before timing; trivial RESPOND test ("What is the capital of France?" → RESPOND with coherent answer); tool-use test ("List the files in the current directory and summarise" → ACT → shell tool executes → RESPOND). Both tests run through the real `PraoLoop` with a real `LocalAdapter`.
  _MLA-5_
