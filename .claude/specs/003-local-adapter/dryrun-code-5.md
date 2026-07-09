# Code Dry-Run Report #5

**Scope**: `src/axiom/providers/local_adapter.py` (195 lines), `tests/test_local_adapter.py` (291 lines)
**Design**: `.claude/specs/003-local-adapter/design.md` (661 lines)
**Research**: `.claude/research/004-local-model-tool-sdk-landscape-2026-07-09.md`
**Context**: smolagents-based rewrite replacing the superseded litellm hand-rolled tool harness. Dryrun-code 1-4 covered the litellm implementation; this is the first code review of the smolagents implementation.
**Reviewed**: 2026-07-09

---

## Frozen-File Verification

| File | Constraint | Status |
|------|-----------|--------|
| `src/axiom/loop.py` | Zero diff from M1 | **PASS** -- zero diff confirmed (`git diff 1cd203b..HEAD`) |
| `src/axiom/interfaces.py` | Zero diff from M1 | **PASS** -- zero diff confirmed |
| `src/axiom/providers/base.py` | New file (W3 extraction) | **PASS** -- new file, not a modification of a frozen file. Contains PraoAdapterBase, _parse_intent, INTENT_FORMAT_INSTRUCTIONS extracted from claude_adapter.py per design SS3. |
| `src/axiom/providers/claude_adapter.py` | Refactored to inherit PraoAdapterBase (design SS3.3) | **PASS** -- perceive/observe/parse_intent moved to base.py; now inherits PraoAdapterBase. Behavioral parity preserved. |

---

## Zero Axiom-Authored Tool Code Verification

| Removed artifact | Status |
|-----------------|--------|
| `_execute_shell_tool()` | **GONE** -- not in local_adapter.py |
| `SHELL_TOOL_SCHEMA` | **GONE** -- not in local_adapter.py |
| `_run_tool_loop()` | **GONE** -- not in local_adapter.py |
| Tool registry (`_tools`, `_tool_schemas`, `_tool_executors`) | **GONE** -- not in local_adapter.py |
| `MAX_TOOL_ITERATIONS` | **GONE** -- replaced by `max_steps` on CodeAgent |
| `TOOL_COMMAND_TIMEOUT_SECS` | **GONE** -- not in local_adapter.py |
| Module-level `import subprocess` | **GONE** -- `subprocess` only appears as a string in `authorized_imports` list |
| Module-level `import json` | **GONE** -- not needed (no tool-arg parsing) |

All hand-rolled tool code confirmed removed. Zero axiom-authored tool schemas, executors, or registries remain.

---

## Pass 1: Design Conformance

### reason() -- design SS4.3

| Design element | Code (local_adapter.py) | Match? |
|---------------|------------------------|--------|
| Tool-less `_query_model()` call | Line 108: `raw_text = self._query_model(context)` | YES |
| `_parse_intent()` shared from base.py | Line 110: `intent, error = _parse_intent(raw_text)` | YES |
| Retry-once on parse failure | Lines 114-128: logs `[INTENT_PARSE_FAILURE]`, appends correction notice, calls `_query_model(retry_context)` | YES |
| `[FALLBACK_RESPOND]` on double parse failure | Line 137: `RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")` | YES |
| Model error -> AdapterError | Lines 193-195: `except Exception as e: ... raise AdapterError(...)` | YES |
| LiteLLMModel calling convention: `self._model(messages, stop_sequences=None)` | Lines 187-189 | YES (W1 resolved; docstring confirms Step 0 verification) |
| Response accessor: `.content` | Line 192: `response.content if response.content is not None else ""` | YES (verified; design's `hasattr` guard replaced with `is not None` post-verification) |

### act() -- design SS4.4

| Design element | Code | Match? |
|---------------|------|--------|
| Fresh CodeAgent per call (W2) | Lines 152-161: `from smolagents import CodeAgent; agent = CodeAgent(...)` inside `act()` body | YES |
| No `self._agent` stored | Line 109 in test confirms `not hasattr(adapter, "_agent")`; constructor stores only config | YES |
| `tools=[]` | Line 156 | YES |
| `add_base_tools=True` | Line 157 | YES |
| `max_steps=self._max_steps` | Line 158 | YES |
| `additional_authorized_imports=self._authorized_imports` | Line 159 | YES |
| `str(result)` conversion | Line 164 | YES |
| Error wrapping -> AdapterError | Lines 165-167 | YES |
| No custom `system_prompt` (O2) | Lines 160-161 comment documents decision | YES |

### Constructor -- design SS6

| Design element | Code | Match? |
|---------------|------|--------|
| Deferred smolagents import inside `__init__` | Lines 65-70 | YES |
| Import guard with helpful error | Lines 67-70: `ModuleNotFoundError` with install guidance | YES |
| `LiteLLMModel(model_id=..., api_base=...)` | Lines 72-75 | YES |
| Default model_id `"ollama_chat/qwen2.5:7b"` | Line 58 | YES |
| Default api_base `"http://localhost:11434"` | Line 59 | YES |
| Default `max_steps=5` | Line 60 | YES |
| Default authorized_imports includes subprocess | Lines 77-84 | YES |
| Stores config, not CodeAgent instance | Lines 86-95 | YES |

### _query_model() -- design SS4.3

Design shows a PROVISIONAL implementation with `hasattr(response, 'content') else str(response)`. Code uses `response.content if response.content is not None else ""`. The docstring at lines 178-184 documents that Step 0 verification (W1 mandatory) was completed, confirming the calling convention. The `hasattr` fallback was intentionally replaced with a direct `is not None` check post-verification. This is an accepted, documented deviation.

---

## Pass 2: Execution Path Trace

### reason() happy path
1. `reason("context")` called (line 101)
2. `_query_model("context")` called (line 108)
3. `self._model([{"role":"user","content":"context"}], stop_sequences=None)` called (lines 185-189)
4. Returns `response.content` (or `""` if None) (line 192)
5. `_parse_intent(raw_text)` called (line 110)
6. Valid JSON -> Intent returned (line 112)
7. All branches reachable: valid intent / parse failure + retry success / parse failure + retry failure -> fallback

### act() happy path
1. `act("instruction")` called (line 143)
2. `from smolagents import CodeAgent` (line 152, cached after __init__)
3. `CodeAgent(model=..., tools=[], add_base_tools=True, ...)` constructed (lines 154-161)
4. `agent.run(instruction)` called (line 163)
5. `str(result)` returned (line 164)

### Dead code check
- `PER_QUERY_TIMEOUT_SECS` (line 35): Defined but never referenced anywhere in the file. See G1.

---

## Pass 3: Error Path Trace

### _query_model() error path
- Line 193: `except Exception as e` catches ALL exceptions from `self._model(...)`.
- Re-raises as `AdapterError`. Chain preserved via `from e`. Correct.
- But: no differentiation by exception type (see W1).

### act() error path
- Lines 165-167: `except Exception as e` catches exceptions from `agent.run(instruction)`.
- Re-raises as `AdapterError`. Chain preserved. Correct.
- **Gap**: `CodeAgent(...)` constructor (lines 154-161) is OUTSIDE the try/except. If CodeAgent construction fails (e.g., model config issue, smolagents internal error), the raw exception escapes the adapter boundary without being wrapped in `AdapterError`. See G2.

### reason() error propagation
- If `_query_model()` raises `AdapterError` on the first call, it propagates from `reason()` immediately. Correct -- model unreachable is not a parse failure.
- If `_query_model()` raises on the retry call, AdapterError propagates. Also correct.
- Parse failures (not model errors) follow the retry/fallback path. Correct.

---

## Pass 4: Input Validation & Boundaries

- `reason("")`: sends empty prompt to model. Model returns something. `_parse_intent()` handles whatever comes back. No crash path. OK.
- `act("")`: passes empty string to `agent.run("")`. CodeAgent handles it. No crash path. OK.
- `_query_model()` with None content: `response.content is not None` check (line 192) returns `""`. `_parse_intent("")` fails to parse `""` as JSON -> retry -> fallback. Covered by test `test_none_content_returned_as_empty_string`. Correct.

---

## Pass 5: Resource Management

- `CodeAgent` created per `act()` call, not stored. No leak. OK.
- `LiteLLMModel` stored on instance. HTTP client internally managed by litellm. No leak concern. OK.
- No files, sockets, or handles opened in adapter code. OK.

---

## Pass 6: Concurrency & Async

- No async code in LocalAdapter. smolagents/litellm is synchronous. OK.
- `self._model` is shared across calls. If two threads call `reason()` concurrently, they share the LiteLLMModel instance. LiteLLMModel delegates to litellm.completion() which is stateless per-call. No shared mutable state in LocalAdapter. OK.
- Each `act()` call creates a fresh CodeAgent with no instance-level side effects. Thread-safe by construction. OK.

---

## Pass 7: Contract Violations

### Port signatures

| Port | Expected signature | LocalAdapter | Match? |
|------|-------------------|-------------|--------|
| `PerceivePort.perceive` | `(RunState) -> str` | Inherited from PraoAdapterBase | YES |
| `ReasonPort.reason` | `(str) -> Intent` | `reason(self, context: str) -> Intent` | YES |
| `ActPort.act` | `(str) -> str` | `act(self, instruction: str) -> str` | YES |
| `ObservePort.observe` | `(str, RunState) -> RunState` | Inherited from PraoAdapterBase | YES |

### Error contract

Design SS4.5 and `interfaces.py` line 112: "Raised by any adapter method on unrecoverable SDK or subprocess failure." All adapter methods should raise only `AdapterError` for operational failures.

- `_query_model()`: wraps all exceptions in AdapterError. **PASS**.
- `act()` `agent.run()` path: wraps all exceptions in AdapterError. **PASS**.
- `act()` `CodeAgent(...)` constructor path: **NOT wrapped**. Raw exception escapes. **FAIL** -- see G2.

### smolagents calling convention

- `LiteLLMModel.__call__` verified per Step 0 (W1). Docstring lines 178-184 document the verification. Calling convention `self._model(messages, stop_sequences=None)` and `response.content` are confirmed correct for smolagents 1.26.0. **PASS**.

---

## Pass 8: Code Quality & Patterns

- No TODO/FIXME/HACK comments. Clean.
- No magic numbers beyond `PER_QUERY_TIMEOUT_SECS = 60` (documented constant, though unused).
- Logging at appropriate levels: `logger.warning` for parse failures, `logger.error` for model errors.
- Code follows PEP 8. Clean.
- DRY: `_query_model()` factored out, shared `_parse_intent()` from base.py. Good.
- SOLID: single responsibility per method. Good.
- Import boundary respected: only `axiom.interfaces`, `axiom.providers.base`, `smolagents` (deferred), `logging`, stdlib. No direct litellm import. No subprocess import. **PASS**.

---

## Pass 9: Security

- No user input reaches shell commands in adapter code. `subprocess` is only a string in the authorized_imports list -- it grants `subprocess` to model-generated code inside smolagents' PythonInterpreterTool sandbox, not to axiom adapter code. Correct per design SS5.2 / O4.
- No secrets logged. Error messages contain exception text (acceptable -- smolagents exceptions don't contain sensitive data).
- No injection vulnerabilities in adapter code.

---

## Bugs (will cause incorrect behavior)

_(None found.)_

---

## Gaps (missing implementation)

### [G1] `PER_QUERY_TIMEOUT_SECS` defined but never used -- no timeout enforcement

- **File**: `src/axiom/providers/local_adapter.py:35`
- **Pass**: Pass 2 (Execution Path Trace) + Pass 8 (Code Quality)
- **What**: `PER_QUERY_TIMEOUT_SECS: int = 60` is defined at module level but never referenced anywhere in the file. Neither `_query_model()` nor `act()` applies any timeout. By contrast, ClaudeAdapter wraps its SDK calls in `anyio.fail_after(PER_QUERY_TIMEOUT_SECS)`. A local model query or CodeAgent run that hangs indefinitely will block the caller with no timeout protection.
- **Design ref**: Design SS4.3 declares the constant but its code sample for `_query_model()` also does not apply it. The design's error table (SS4.5) lists "Query timeout" as a handled scenario with log tag `[LOCAL_ADAPTER_TIMEOUT]`, implying timeout enforcement was intended. The constant's presence + the error table row constitute an unfulfilled design intent.
- **Fix**: Either (a) apply a timeout wrapper around `self._model(...)` in `_query_model()` and around `agent.run()` in `act()` (e.g., using `signal.alarm` on Unix or a threading timeout), or (b) remove `PER_QUERY_TIMEOUT_SECS` and the corresponding error table row if timeout enforcement is intentionally deferred. Option (a) is preferred for parity with ClaudeAdapter.

### [G2] CodeAgent constructor failure not wrapped in AdapterError

- **File**: `src/axiom/providers/local_adapter.py:154-161`
- **Pass**: Pass 3 (Error Path Trace) + Pass 7 (Contract Violations)
- **What**: The `try/except` block in `act()` (lines 162-167) only wraps `agent.run(instruction)`. The `CodeAgent(...)` constructor call (lines 154-161) is outside the try/except. If the constructor raises (e.g., smolagents internal error during agent initialization, model validation failure), the raw exception escapes past the adapter boundary without being wrapped in `AdapterError`.
- **Design ref**: Design SS4.5 error table: "Any other exception -> raise AdapterError(...)". The adapter error contract (`interfaces.py` line 112) states "Raised by any adapter method on unrecoverable SDK or subprocess failure." A raw smolagents exception leaking from `act()` violates this contract. Note: the design's code sample in SS4.4 has the same structure (try/except only around `agent.run()`), so this is a design-code consistency issue -- both have the gap.
- **Fix**: Move the `try/except` to wrap both the constructor and the `agent.run()` call:
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

---

## Warnings (potential issues)

### [W1] Differentiated error logging from design SS4.5 not implemented

- **File**: `src/axiom/providers/local_adapter.py:193-195`
- **Pass**: Pass 3 (Error Path Trace)
- **What**: Design SS4.5 specifies differentiated error handling by exception type: connection error -> `[LOCAL_ADAPTER_OLLAMA_DOWN]`, 404 -> `[LOCAL_ADAPTER_MODEL_NOT_FOUND]`, timeout -> `[LOCAL_ADAPTER_TIMEOUT]`, unexpected -> `[LOCAL_ADAPTER_UNEXPECTED]`. The code uses a single generic `except Exception` with `[LOCAL_ADAPTER_ERROR]` for all failure modes. The error contract (raise AdapterError) is satisfied, but the operational visibility is reduced -- an operator cannot distinguish "Ollama is down" from "model not loaded" from "timeout" in logs without reading the exception message.
- **Risk**: Debugging production issues. When Ollama is down vs model not loaded vs timeout, the log tag is identical. Low severity for M3 (dev-machine proof) but will matter if LocalAdapter reaches production.

### [W2] `hasattr(response, 'content')` defensive guard removed

- **File**: `src/axiom/providers/local_adapter.py:192`
- **Pass**: Pass 1 (Design Conformance) + Pass 7 (Contract Violations)
- **What**: Design SS4.3 shows `return response.content if hasattr(response, 'content') else str(response)` as a defensive fallback. The implemented code uses `return response.content if response.content is not None else ""`, dropping the `hasattr` guard. This is justified by the Step 0 verification (docstring lines 178-184 confirm `.content` exists on `ChatMessage`). However, if a future smolagents version changes the return type, this will raise `AttributeError` instead of gracefully falling back.
- **Risk**: smolagents API change in a future version. Low -- the Step 0 verification is documented and the dependency version is pinnable. Acceptable for M3.

---

## Style (code quality, conventions)

_(None -- code is clean, follows PEP 8, and adheres to project conventions.)_

---

## Test Quality Assessment

### Mocking strategy correctness

The test file injects a mock `smolagents` module into `sys.modules` before importing `LocalAdapter`:
```python
_mock_smolagents = MagicMock()
_mock_smolagents.LiteLLMModel.return_value = _mock_LiteLLMModel_instance
sys.modules.setdefault("smolagents", _mock_smolagents)
```

This ensures the deferred `from smolagents import CodeAgent, LiteLLMModel` inside `__init__` resolves to mocks. The `_make_adapter()` helper then replaces `adapter._model` with a fresh MagicMock for test isolation. This strategy is correct for smolagents 1.26.0.

For `act()` tests, `patch("smolagents.CodeAgent")` correctly targets the attribute on the injected mock module. Since `act()` does `from smolagents import CodeAgent` inside the function body (re-resolving from `sys.modules` each time), the patch intercepts the import. Verified correct.

### Coverage matrix

| Contract element | Test(s) | Vacuous? |
|-----------------|---------|----------|
| Constructor defaults (model_id, api_base, max_steps) | `test_default_model_id`, `test_default_ollama_api_base`, `test_default_max_steps` | NO -- asserts stored values |
| Custom max_steps | `test_custom_max_steps` | NO |
| Default authorized_imports includes subprocess | `test_default_authorized_imports_includes_subprocess` | NO |
| Custom authorized_imports | `test_custom_authorized_imports` | NO |
| No self._agent stored (W2) | `test_no_agent_stored_on_instance` | NO -- `assert not hasattr(adapter, "_agent")` |
| smolagents import failure | `test_smolagents_import_failure_raises_helpful_error` | NO -- patches sys.modules, asserts exception |
| reason() valid RESPOND | `test_valid_respond_intent` | NO -- asserts isinstance + text + call count |
| reason() valid ACT | `test_valid_act_intent` | NO |
| reason() valid FINISH | `test_valid_finish_intent` | NO |
| reason() retry path | `test_malformed_first_call_retry_succeeds` | NO -- uses side_effect, asserts retry worked + call count |
| reason() fallback path | `test_malformed_both_attempts_returns_fallback_respond` | NO -- asserts FALLBACK_RESPOND tag + call count |
| reason() code fence pre-processing | `test_json_in_code_fence_resolved_without_retry` | NO -- asserts no retry (call_count==1) |
| reason() model error | `test_reason_model_error_raises_adapter_error` | NO -- asserts AdapterError with message |
| reason() None content | `test_none_content_returned_as_empty_string` | NO -- both calls return None -> fallback |
| act() happy path | `test_happy_path_returns_result_string` | NO -- asserts result + CodeAgent.run called |
| act() fresh per call (W2) | `test_act_creates_fresh_codeagent_per_call` | NO -- asserts constructor called twice |
| act() constructor args | `test_act_passes_correct_constructor_args` | NO -- asserts each kwarg |
| act() non-string result | `test_act_result_non_string_converted_to_str` | NO -- passes int, asserts str |
| act() CodeAgent error | `test_act_codeagent_error_raises_adapter_error` | NO |
| act() error message wrapping | `test_act_error_message_contains_original_exception` | NO |

**21 tests, 0 vacuous.** All tests exercise the real contract with meaningful assertions.

### Missing test coverage

- No test for CodeAgent constructor failure (related to G2 -- the code doesn't handle it, so there's nothing to test yet).

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 2 | 2 | 0 |

**Verdict: PASS WITH WARNINGS**

Zero bugs found in implemented code paths. Two gaps identified:

- **G1** (medium): `PER_QUERY_TIMEOUT_SECS` is dead code; no timeout enforcement exists. Design's error table implies timeout handling was intended. Risk: hung model call blocks indefinitely.
- **G2** (medium): CodeAgent constructor failure in `act()` leaks raw exceptions past the adapter boundary, violating the AdapterError contract. Note: the design's own code sample has the same gap.

Two warnings:

- **W1** (low): Generic error log tags instead of differentiated tags per design SS4.5. Functional behavior correct; operational visibility reduced.
- **W2** (low): `hasattr` defensive guard removed in favor of direct `.content` access, justified by Step 0 API verification. Risk only on future API change.

**Against the stated goal bar (0 bug / 0 gap / 0 open-warning): NOT MET** -- 2 gaps and 2 warnings remain. Both gaps are fixable with small, surgical changes before E2E. The code is structurally sound and the smolagents integration is correct.
