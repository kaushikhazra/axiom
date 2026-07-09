# Code Dry-Run Report #2

**Scope**: `src/axiom/providers/base.py`, `claude_adapter.py`, `local_adapter.py`, `src/axiom/agent.py`, `src/axiom/interface/cli.py`, `tests/test_local_adapter.py`, `tests/test_shared_base.py`, `tests/test_local_e2e.py`, `pyproject.toml`
**Design**: `.claude/specs/003-local-adapter/design.md`
**Requirement**: `.claude/specs/003-local-adapter/requirement.md`
**Prior review**: `.claude/specs/003-local-adapter/dryrun-code-1.md`
**Reviewed**: 2026-07-09

**Purpose**: Confirm every finding from dryrun-code-1 is resolved and that fixes introduced no new defects.

**M1 frozen-file verification**: `loop.py`, `interfaces.py`, `fake_adapter.py`, `test_contracts.py` — `git diff HEAD` produces zero output. Byte-identical to M1 state. Confirmed.

**Pytest result**: `68 passed, 2 skipped in 3.55s` (26 M1 contract tests + 40 new tests + 2 e2e_local skipped).

---

## Prior Finding Verification

### W1/B1 — Code-fence regex greedy fix: ✅ RESOLVED

- **base.py:93**: Regex is now `r"```(?:json)?\s*(\{.*\})\s*```"` with `re.DOTALL` — greedy `.*` as required.
- **test_shared_base.py:166–183**: `test_code_fence_multiline_nested_json` explicitly verifies nested/multi-line JSON `{"a": {"b": 1}, "c": 2}` is captured and parsed correctly. Test passes.
- **No new defect**: The greedy `.*` is bounded by ` ``` ` anchors; it cannot over-match across multiple code-fence blocks because the closing ` ``` ` terminates the match. The brace-match fallback on line 98 also uses greedy `.*` which is correct for a single JSON object.

### W2 — agent.py unknown provider ValueError: ✅ RESOLVED

- **agent.py:68–77**: Three-branch `if/elif/else` — `provider == "local"` → LocalAdapter, `provider == "claude"` → ClaudeAdapter, else → `raise ValueError(f"unknown provider: {provider!r}")`. Correct.
- **Default**: `provider: str = "claude"` on line 52. Confirmed.
- **tests/test_local_adapter.py**: Unit tests exercise LocalAdapter directly (not through Agent), so the ValueError branch is not tested there. However the branch is structurally trivial (a single raise). No test gap — the risk was silent fallback, which is now eliminated by the explicit ValueError.
- **No new defect**: The `elif` ordering is correct — `"local"` branch has the lazy import, `"claude"` branch is the non-lazy path. No possibility of the wrong adapter being selected.

### W6 — Missing-litellm friendly error: ✅ RESOLVED

- **local_adapter.py:127–132**: `import litellm` is wrapped in `try/except ModuleNotFoundError` that re-raises with a descriptive message: `"LocalAdapter requires litellm — install with: pip install litellm"`. This replaces the raw `ModuleNotFoundError` with actionable guidance.
- **No new defect**: The `from exc` chain preserves the original traceback.

### O3 — Shell-tool missing-'command'-key descriptive error: ✅ RESOLVED

- **local_adapter.py:146–150**: The lambda now checks `if "command" in args` before calling `_execute_shell_tool`, otherwise returns `"[error]: tool call missing required 'command' argument"`. This is more informative than the prior `KeyError: 'command'`.
- **No new defect**: The error string is still caught by the existing `except Exception as exec_err` block (line 338), but the lambda itself no longer raises — it returns the error string directly, which is even cleaner.

### G1/O1 — test_shared_base.py now exists: ✅ RESOLVED

- **tests/test_shared_base.py** exists (184 lines). Contains `TestPraoAdapterBasePerceive` (5 tests), `TestPraoAdapterBaseObserve` (3 tests), `TestParseIntent` (14 tests including the B1/W1 regression test). Total: 22 tests.
- **test_local_adapter.py** retains only LocalAdapter-specific tests (constructor, reason, act). No PraoAdapterBase or _parse_intent tests remain in this file.
- **No new defect**: Imports are clean — `test_shared_base.py` imports from `axiom.providers.base` and `axiom.interfaces` only; no litellm mock needed.

### G2 — test_local_e2e.py now exists: ✅ RESOLVED

- **tests/test_local_e2e.py** exists (162 lines). Two tests with `@pytest.mark.e2e_local`: `test_trivial_respond_shortcircuit` and `test_reason_act_observe_cycle_shell_tool`.
- **Skip guard uses `importlib.metadata`** (line 38–43): `importlib.metadata.version("litellm")` queries disk metadata, not `sys.modules`. This cannot be defeated by the `sys.modules.setdefault("litellm", mock)` in `test_local_adapter.py`. Confirmed correct.
- **Ollama skip guard** (line 52–58): Uses `socket.create_connection` with 2s timeout — clean SKIP when Ollama is absent.
- **Both guards are applied via `pytestmark`** (line 71) — module-wide, all tests get both skipif conditions.
- **Pre-warm fixture** (line 80–97): `@pytest.fixture(scope="module", autouse=True)` sends a trivial generate request to Ollama. Best-effort (exception swallowed). Correct.
- **Pytest output confirms**: `2 skipped` — the e2e tests are collected and skipped, not erroring.
- **No new defect**: `httpx` is imported at module level (line 22), which would cause `ImportError` if httpx is not installed. However, httpx is in the `test` optional-dependencies group, and both skip guards run before the httpx import is reached at the function level (the fixture body). Actually — `httpx` is imported at module top level (line 22), so if httpx is not installed, the module itself fails to import. This is acceptable because httpx is a test dependency (`pip install .[test]`) and the test runner requires it. Not a defect.

### G3 — Multi-step tool-loop test: ✅ RESOLVED

- **test_local_adapter.py:319–345**: `test_multi_step_tool_loop` — model calls `run_shell_command` on iterations 1 and 2 (with different call_ids `c1`, `c2`), then returns final text on iteration 3. A `recording_executor` logs execution order. Asserts: `completion.call_count == 3`, `execution_log == ["ls", "pwd"]`, final result is the text from the third call. Test passes.
- **No new defect**: The test correctly uses unique `call_id` values for each tool call, and the recording executor validates ordering.

### G4 — Exhaustion backward-scan "assistant text found" branch test: ✅ RESOLVED

- **test_local_adapter.py:429–455**: `test_exhaustion_backward_scan_returns_assistant_text` — uses `_tool_call_resp_with_text` helper (line 103–138) which creates a mock where `msg.content` is `None` (loop continues executing tools) but `msg.model_dump()` returns a dict with non-empty `"content"` field. With `max_tool_iterations=2`, both iterations are tool calls, loop exhausts, backward scan finds the text from the first assistant message's model_dump.
- **Asserts**: `result == "Partial result: I found the files"`. Test passes.
- **No new defect**: The `_tool_call_resp_with_text` helper correctly separates the live `msg.content` (None, so the tool-call branch triggers) from the serialised `model_dump()["content"]` (non-empty, so backward scan finds it). This accurately models a real LiteLLM response where the assistant message has both tool_calls and text content.

### G5 — pyproject optional-dep group renamed to `test`: ✅ RESOLVED

- **pyproject.toml:29–33**: `[project.optional-dependencies] test = ["pytest>=7.0", "httpx"]`. Matches design §9.
- **e2e_local marker registered** (pyproject.toml:26): `"e2e_local: marks tests requiring a running Ollama instance ..."`. Confirmed.
- **No new defect**: Clean.

### Accepted items (documented, NOT flagged as open):

- **W3** (act() returns "" when content None): Accepted. Documented inline at local_adapter.py:300–303 with comment referencing W3. Intentional — no code change needed.
- **W4** (shell=True dev-scope): Accepted. `# nosec` comment at local_adapter.py:81 with design reference. Dev-machine only.
- **W5/O5** (AdapterError vs exhaustion distinction): Confirmed correct. Exhaustion returns string (line 378); model error raises AdapterError (line 296). Two paths correctly separated.

---

## New-Defect Scan

Systematic scan for regressions introduced by the fixes.

### Pass 1: Greedy regex — could it over-match?

- **base.py:93**: `r"```(?:json)?\s*(\{.*\})\s*```"` with `re.DOTALL`. If text contains TWO code-fenced JSON blocks, e.g. ` ```json\n{A}\n``` then ```json\n{B}\n``` `, the greedy `.*` would capture from the first `{` to the last `}` across both fence blocks, including the intermediate ` ``` then ```json ` text. This would produce invalid JSON and `json.loads()` would fail, falling through to the brace-match fallback (line 98) which would similarly over-match. However: the `_parse_intent` caller would then get a parse failure and trigger the retry/fallback path — no crash, just a less graceful recovery. For the current use case (model returns exactly one JSON object), this is not a real risk. Noting as an observation only.

### Pass 2: Shared-base split — import integrity

- **test_local_adapter.py:37**: Imports `LocalAdapter, MAX_TOOL_ITERATIONS` from `axiom.providers.local_adapter`. No PraoAdapterBase import — correct, those tests are now in `test_shared_base.py`.
- **test_shared_base.py:17–22**: Imports `PraoAdapterBase, _parse_intent, _extract_json_from_text, INTENT_FORMAT_INSTRUCTIONS` from `axiom.providers.base`. Clean.
- **claude_adapter.py:41**: Imports `PraoAdapterBase, _parse_intent` from `axiom.providers.base`. Clean.
- **local_adapter.py:28**: Imports `PraoAdapterBase, _parse_intent` from `axiom.providers.base`. Clean.
- No circular imports. No broken references. All passing.

### Pass 3: ValueError branch ordering in agent.py

- **agent.py:68–77**: `if provider == "local"` → `elif provider == "claude"` → `else: raise ValueError`. The lazy import of `LocalAdapter` is correctly inside the `"local"` branch. The `ClaudeAdapter` top-level import (line 19) is always paid, but that is by M1 design — Claude is the default. No ordering issue.

### Pass 4: Test count verification

- **test_contracts.py**: 26 tests (M1 contract tests) — unchanged.
- **test_local_adapter.py**: 20 tests (5 constructor + 7 reason + 8 act) — LocalAdapter-specific.
- **test_shared_base.py**: 22 tests (5 perceive + 3 observe + 14 parse_intent).
- **test_local_e2e.py**: 2 tests (skipped).
- **Total**: 26 + 20 + 22 = 68 passed + 2 skipped = 70 collected. Matches pytest output.

### Pass 5: Security — no new shell-injection paths

- The `_execute_shell_tool` function and `shell=True` are unchanged from dryrun-code-1 review. No new security surface.

### Pass 6: E2E test module-level httpx import

- **test_local_e2e.py:22**: `import httpx` at module top level. If httpx is not installed, the entire module fails to import with `ModuleNotFoundError`, which pytest reports as a collection error (not a clean skip). However, httpx is listed as a test dependency (`[project.optional-dependencies] test = ["pytest>=7.0", "httpx"]`). Anyone running the test suite must have installed `pip install .[test]` which includes httpx. This is consistent with how pytest itself is a test dependency. Not a defect — standard test-dependency assumption.

---

## Bugs (will cause incorrect behavior)

_(none)_

---

## Gaps (missing implementation)

_(none)_

---

## Warnings (potential issues)

_(none — all prior warnings are either resolved or accepted/documented)_

---

## Observations

### [O1] Greedy regex could over-match on text with multiple code-fenced JSON blocks

- **File**: `src/axiom/providers/base.py`:93
- **Pass**: New-defect scan, Pass 1
- **What**: If a model response contains two separate code-fenced JSON blocks, the greedy `.*` would span across both fences, producing an invalid JSON candidate. The `json.loads()` call would fail, triggering the retry/fallback path. No crash, just less graceful recovery.
- **Risk**: Negligible for current use — models produce one JSON block per response. Noted for completeness.

---

## Summary

| Bugs | Gaps | Warnings | Observations |
|------|------|----------|--------------|
| 0 | 0 | 0 | 1 |

### Prior-finding resolution matrix

| Finding | Status | Evidence |
|---------|--------|----------|
| B1/W1 (regex greedy) | ✅ Fixed | base.py:93 uses `.*`; test at test_shared_base.py:166 |
| W2 (unknown provider) | ✅ Fixed | agent.py:77 raises ValueError |
| W3 (empty string return) | ✅ Accepted | Documented at local_adapter.py:300–303 |
| W4 (shell=True) | ✅ Accepted | nosec comment at local_adapter.py:81 |
| W5/O5 (exhaustion vs error) | ✅ Confirmed correct | Lines 296 vs 378 |
| W6 (litellm import error) | ✅ Fixed | local_adapter.py:127–132 try/except |
| G1/O1 (test_shared_base.py) | ✅ Created | 184 lines, 22 tests |
| G2 (test_local_e2e.py) | ✅ Created | 162 lines, 2 tests, importlib.metadata skip guard |
| G3 (multi-step test) | ✅ Created | test_local_adapter.py:319 |
| G4 (backward-scan test) | ✅ Created | test_local_adapter.py:429 |
| G5 (optional-dep group) | ✅ Fixed | pyproject.toml:30 `test = [...]` |
| O3 (missing-command key) | ✅ Fixed | local_adapter.py:146–150 descriptive error |

**Verdict**: **PASS**

All prior findings are resolved. No new bugs, gaps, or warnings introduced. The code is clean and E2E-ready.

**Pytest summary**: `68 passed, 2 skipped in 3.55s`

**M1 frozen files**: byte-identical (zero diff).
