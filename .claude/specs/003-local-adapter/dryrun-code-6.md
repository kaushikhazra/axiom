# Code Dry-Run Report #6 — CONFIRMING CLEAN GATE

**Scope**: `src/axiom/providers/local_adapter.py` (225 lines), `tests/test_local_adapter.py` (310 lines)
**Design**: `.claude/specs/003-local-adapter/design.md` (685 lines)
**Research**: `.claude/research/004-local-model-tool-sdk-landscape-2026-07-09.md`
**Prior report**: `dryrun-code-5.md` — 0 Bugs / 2 Gaps / 2 Warnings / 0 Style
**Fix commit**: `c3311d5` (code-fix worker 89041bae resolved all 4 findings)
**Reviewed**: 2026-07-09
**Purpose**: Confirm all prior findings are genuinely closed AND no new defects introduced.

---

## Prior Finding Closure Verification

### [G1] `PER_QUERY_TIMEOUT_SECS` — CLOSED

**Prior state**: Constant defined (line 34) but never referenced. No timeout enforcement.

**Current state** (lines 196–202):
```python
response = self._model(
    messages,
    stop_sequences=None,
    timeout=PER_QUERY_TIMEOUT_SECS,  # G1: enforce per-query timeout.
)
```

**Verification**:
- `PER_QUERY_TIMEOUT_SECS` (line 34, value `60`) is passed as `timeout=` kwarg to `self._model()`.
- Docstring (lines 183–191) documents that `**kwargs` are forwarded to `litellm.completion()`, so `timeout=` is honoured. Step 0 verification completed.
- `CodeAgent.run()` in `act()` has NO wall-clock timeout — documented as bounded by `max_steps` instead (docstring lines 189–190). This matches design SS4.5 error table: "Query timeout ... applies to LiteLLMModel calls only (reason phase)."
- The `[LOCAL_ADAPTER_TIMEOUT]` log tag (line 218) handles the timeout exception path.
- Design SS4.3 code sample and SS4.5 error table both updated to match.
- **No dead constant. No code<->design disagreement. CLOSED.**

### [G2] CodeAgent constructor failure not wrapped — CLOSED

**Prior state**: `CodeAgent(...)` constructor was outside the `try/except` in `act()`. Raw exceptions escaped.

**Current state** (lines 156–169):
```python
try:
    agent = CodeAgent(
        model=self._model,
        tools=[],
        add_base_tools=True,
        max_steps=self._max_steps,
        additional_authorized_imports=self._authorized_imports,
    )
    result = agent.run(instruction)
    return str(result)
except Exception as e:
    logger.error("[LOCAL_ADAPTER_ACT_ERROR] %s", e)
    raise AdapterError(f"CodeAgent execution error: {e}") from e
```

**Verification**:
- `CodeAgent(...)` constructor AND `agent.run(instruction)` are both inside the single `try/except`.
- Comment at line 154–155 documents the G2 fix rationale.
- Design SS4.4 code sample updated — constructor is inside try/except, matching code.
- Design SS4.5 error table updated: "CodeAgent constructor or run() error ... constructor failure now also covered (G2)".
- New test `test_act_codeagent_constructor_failure_raises_adapter_error` (test file lines 298–309) confirms: patches `MockCodeAgent.side_effect = RuntimeError("model config invalid")`, asserts `AdapterError` with match `"CodeAgent execution error"`. **Test is non-vacuous** — it exercises the real constructor-failure path.
- **No raw exception escape. Code<->design agree. Test covers. CLOSED.**

### [W1] Differentiated log tags — CLOSED

**Prior state**: Single generic `[LOCAL_ADAPTER_ERROR]` tag for all failure modes.

**Current state** (lines 207–224):
```python
except Exception as e:
    exc_name = type(e).__name__
    exc_msg = str(e).lower()
    if "Connection" in exc_name or "ServiceUnavailable" in exc_name:
        tag = "[LOCAL_ADAPTER_OLLAMA_DOWN]"
        msg = f"Ollama not reachable at {self._ollama_api_base}: {e}"
    elif "NotFound" in exc_name or "404" in exc_msg:
        tag = "[LOCAL_ADAPTER_MODEL_NOT_FOUND]"
        msg = f"model {self._model_id} not found in Ollama: {e}"
    elif "Timeout" in exc_name or "timeout" in exc_msg:
        tag = "[LOCAL_ADAPTER_TIMEOUT]"
        msg = f"local model timeout after {PER_QUERY_TIMEOUT_SECS}s: {e}"
    else:
        tag = "[LOCAL_ADAPTER_UNEXPECTED]"
        msg = f"local model error: {e}"
    logger.error("%s %s", tag, e)
    raise AdapterError(msg) from e
```

**Verification**:
- Four differentiated tags match design SS4.5 error table exactly: `OLLAMA_DOWN`, `MODEL_NOT_FOUND`, `TIMEOUT`, `UNEXPECTED`.
- Classification logic: checks `type(e).__name__` for class-name matching, `str(e).lower()` for message matching. Sound for the exception types litellm/smolagents emit (e.g., `APIConnectionError`, `NotFoundError`, `Timeout`).
- Design SS4.3 code sample updated to show the differentiated handler.
- Test `test_reason_model_error_raises_adapter_error` (lines 187–197): uses `RuntimeError("something crashed")` — class name `"RuntimeError"` doesn't match Connection/NotFound/Timeout, and message doesn't contain "404" or "timeout". Hits the `[LOCAL_ADAPTER_UNEXPECTED]` branch. Asserts `match="local model error"`. **Exercises a real branch, non-vacuous.**
- **Classification is sound. Code<->design agree. CLOSED.**

### [W2] `hasattr` guard restored — CLOSED

**Prior state**: `hasattr` guard removed, replaced with direct `.content is not None` check.

**Current state** (lines 203–206):
```python
# W2: defensive hasattr guard + None-content -> "" for _parse_intent safety.
if not hasattr(response, "content"):
    return str(response)
return response.content if response.content is not None else ""
```

**Verification**:
- `hasattr` guard restored ahead of the `is not None` check. Both guards present.
- Design SS4.3 code sample shows `hasattr` guard with comment "W2: defensive hasattr guard retained".
- Docstring (lines 192–194) documents: `.content` verified present on `ChatMessage` (Step 0), but guard future-proofs against API changes.
- Test `test_none_content_returned_as_empty_string` (lines 199–209) covers the `content is None` -> `""` path. The `hasattr` fallback is a future-proofing guard not exercised by current tests (acceptable — it's defensive).
- **Code<->design agree. CLOSED.**

---

## Regression Verification — Invariants

### Frozen files

| File | Constraint | Status |
|------|-----------|--------|
| `src/axiom/loop.py` | Zero diff from M1 | **PASS** — 97 lines, imports only `axiom.interfaces`, identical to M1 commit `1cd203b` |
| `src/axiom/interfaces.py` | Zero diff from M1 | **PASS** — 121 lines, all contracts intact |
| `src/axiom/providers/base.py` | Unchanged from dryrun-5 | **PASS** — 250 lines, `PraoAdapterBase` + `_parse_intent` + `INTENT_FORMAT_INSTRUCTIONS` |

### Zero axiom-authored tool code

| Artifact | Status |
|----------|--------|
| `_execute_shell_tool()` | **GONE** |
| `SHELL_TOOL_SCHEMA` | **GONE** |
| `_run_tool_loop()` | **GONE** |
| Tool registry (`_tools`, `_tool_schemas`, `_tool_executors`) | **GONE** |
| `MAX_TOOL_ITERATIONS` | **GONE** — replaced by `max_steps` on CodeAgent |
| `TOOL_COMMAND_TIMEOUT_SECS` | **GONE** |
| Module-level `import subprocess` | **GONE** — confirmed via grep: zero matches. `subprocess` appears only as a string in `authorized_imports` list (line 83) |
| Module-level `import json` | **GONE** |

### PRAO port mapping coherence

| Port | Expected | LocalAdapter | Match? |
|------|----------|-------------|--------|
| `perceive(RunState) -> str` | Inherited from PraoAdapterBase | Inherited | **YES** |
| `reason(str) -> Intent` | Tool-less LiteLLMModel call + _parse_intent | Lines 101–137 | **YES** |
| `act(str) -> str` | Fresh CodeAgent per call | Lines 143–169 | **YES** |
| `observe(str, RunState) -> RunState` | Inherited from PraoAdapterBase | Inherited | **YES** |

Intent: reason() uses tool-less LiteLLMModel (no CodeAgent). Act: fresh CodeAgent per call (no `self._agent` stored). Perceive/observe: inherited, provider-independent. **Coherent.**

### Import boundary

`local_adapter.py` imports: `logging` (stdlib), `axiom.interfaces` (AdapterError, Intent, RespondIntent), `axiom.providers.base` (PraoAdapterBase, _parse_intent). `smolagents` imported inside `__init__` (deferred, line 66) and inside `act()` (line 152, cached). **No** direct litellm import. **No** subprocess import. **PASS.**

### M1 test regression

All 26 tests in `test_contracts.py` pass. All 23 tests in `test_local_adapter.py` pass. **49 total, 0 failures.**

---

## Test Non-Vacuousness Audit (23 local-adapter tests)

| # | Test | Assertion quality | Vacuous? |
|---|------|------------------|----------|
| 1 | `test_default_model_id` | Asserts stored `_model_id` value | NO |
| 2 | `test_default_ollama_api_base` | Asserts stored `_ollama_api_base` value | NO |
| 3 | `test_default_max_steps` | Asserts `_max_steps == 5` | NO |
| 4 | `test_custom_max_steps` | Asserts `_max_steps == 3` | NO |
| 5 | `test_default_authorized_imports_includes_subprocess` | Asserts `"subprocess" in` list | NO |
| 6 | `test_custom_authorized_imports` | Asserts exact list equality | NO |
| 7 | `test_no_agent_stored_on_instance` | Asserts `not hasattr(adapter, "_agent")` | NO |
| 8 | `test_smolagents_import_failure_raises_helpful_error` | Patches sys.modules, asserts exception type+message | NO |
| 9 | `test_valid_respond_intent` | Asserts isinstance + text + call_count==1 | NO |
| 10 | `test_valid_act_intent` | Asserts isinstance + instruction | NO |
| 11 | `test_valid_finish_intent` | Asserts isinstance FinishIntent | NO |
| 12 | `test_malformed_first_call_retry_succeeds` | side_effect list, asserts retry intent + call_count==2 | NO |
| 13 | `test_malformed_both_attempts_returns_fallback_respond` | Asserts FALLBACK_RESPOND tag + call_count==2 | NO |
| 14 | `test_json_in_code_fence_resolved_without_retry` | Asserts parsed intent + call_count==1 (no retry) | NO |
| 15 | `test_reason_model_error_raises_adapter_error` | RuntimeError -> AdapterError with "local model error" | NO |
| 16 | `test_none_content_returned_as_empty_string` | None content -> fallback RESPOND | NO |
| 17 | `test_happy_path_returns_result_string` | Asserts result + CodeAgent.run called | NO |
| 18 | `test_act_creates_fresh_codeagent_per_call` | Asserts constructor called twice for two act() calls | NO |
| 19 | `test_act_passes_correct_constructor_args` | Asserts each kwarg (model, tools, add_base_tools, max_steps, authorized_imports) | NO |
| 20 | `test_act_result_non_string_converted_to_str` | int 42 -> str "42" | NO |
| 21 | `test_act_codeagent_error_raises_adapter_error` | RuntimeError -> AdapterError | NO |
| 22 | `test_act_error_message_contains_original_exception` | ValueError message preserved in AdapterError | NO |
| 23 | `test_act_codeagent_constructor_failure_raises_adapter_error` | Constructor raises -> AdapterError (G2 fix) | NO |

**23 tests, 0 vacuous. All exercise real contract elements with meaningful assertions.**

---

## New Defect Scan

### Code quality re-check

- No TODO/FIXME/HACK comments. Clean.
- No dead code. `PER_QUERY_TIMEOUT_SECS` is now used (line 201).
- Logging: `logger.warning` for parse failures, `logger.error` for model errors (differentiated). Appropriate levels.
- PEP 8 compliant. Docstrings accurate and current.
- DRY: `_query_model()` factored out, shared `_parse_intent()` from base.py.
- SOLID: single responsibility per method.

### Error path completeness

- `_query_model()`: all exceptions -> differentiated log tag -> AdapterError. **Complete.**
- `act()`: constructor + run() both inside try/except -> AdapterError. **Complete.**
- `reason()`: model errors propagate as AdapterError; parse errors follow retry/fallback. **Complete.**

### Security re-check

- No user input reaches shell commands in adapter code.
- `subprocess` is only a string in the authorized_imports list — grants to model-generated code inside smolagents sandbox, NOT to adapter code.
- No secrets logged. Error messages contain exception text only.

### Concurrency re-check

- `self._model` shared across calls. LiteLLMModel delegates to `litellm.completion()` which is stateless per-call. Safe.
- Each `act()` creates fresh CodeAgent. No shared mutable state. Safe.

### No new findings detected.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 0 | 0 |

**Prior findings closure**: G1 CLOSED, G2 CLOSED, W1 CLOSED, W2 CLOSED — all 4 genuinely fixed with code<->design agreement and test coverage.

**Regression check**: 49 tests green (23 local-adapter + 26 M1 contracts). Frozen files untouched. Zero axiom-authored tool code. Import boundary clean. PRAO port mapping coherent.

**Verdict: PASS — READY-FOR-E2E**

Goal bar met: 0 bug / 0 gap / 0 open-warning. The smolagents-based local adapter is structurally sound, its prior findings are genuinely resolved, and no new defects or regressions were introduced. Proceed to live E2E testing against Ollama + qwen2.5:7b.
