# Code Dry-Run Report #1

**Scope**: `src/axiom/providers/base.py`, `src/axiom/providers/claude_adapter.py`, `src/axiom/providers/local_adapter.py`, `src/axiom/agent.py`, `src/axiom/interface/cli.py`, `tests/test_local_adapter.py`, `pyproject.toml`
**Design**: `.claude/specs/003-local-adapter/design.md`
**Requirement**: `.claude/specs/003-local-adapter/requirement.md`
**Reviewed**: 2026-07-09

**M1 frozen-file verification**: `interfaces.py`, `loop.py`, `fake_adapter.py`, `test_contracts.py` have zero diff from M1 state. Confirmed byte-identical.

**Pytest result**: `65 passed in 0.48s` (26 M1 contract tests + 39 new tests).

---

## Bugs (will cause incorrect behavior)

### [B1] `_extract_json_from_text` code-fence regex uses non-greedy `.*?` which fails on multi-line JSON

- **File**: `src/axiom/providers/base.py`:92
- **Pass**: Pass 4 (Input Validation & Boundaries)
- **What**: The regex `r"```(?:json)?\s*(\{.*?\})\s*```"` uses non-greedy `.*?` inside the capture group. For a JSON object that spans multiple lines (common for pretty-printed model output), `.*?` with `re.DOTALL` will match the *shortest* `{...}` substring, potentially stopping at the first `}` inside the JSON rather than the matching closing brace. Example: ` ```json\n{"intent": "RESPOND", "text": "hello"}\n``` ` works, but ` ```json\n{\n  "intent": "RESPOND",\n  "text": "hello"\n}\n``` ` would match only `{\n  "intent": "RESPOND"` up to the comma-less first `}` — wait, in this specific case it actually works since `}` appears only at the end. The real failure case is nested objects: ` ```json\n{"a": {"b": 1}, "c": 2}\n``` ` — the non-greedy match stops at the first `}`, capturing `{"a": {"b": 1}` which may or may not parse. Actually for the current intent JSON (flat, no nesting), this is unlikely to trigger. Downgrading to Warning.
- **Impact**: Would misparse nested JSON in code fences from weak models (current intent schema is flat, so low risk for M3).
- **Fix**: Change to greedy `.*` in the fence regex: `r"```(?:json)?\s*(\{.*\})\s*```"`. The `\`\`\`` boundary anchors prevent over-matching.

*Reconsidered: This is actually a Warning, not a Bug, because the M3 intent schema has no nested objects.*

---

## Gaps (missing implementation)

### [G1] `test_shared_base.py` file missing — tests merged into `test_local_adapter.py`

- **File**: `tests/test_shared_base.py` (missing file)
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §8 file layout specifies `tests/test_shared_base.py [NEW]` as a separate file. In practice, the `TestPraoAdapterBasePerceive` and `TestPraoAdapterBaseObserve` classes exist inside `test_local_adapter.py`. All specified test cases are present and passing.
- **Design ref**: §8 file layout, §11.2
- **Impact**: Low — all tests exist and pass; only the file organization deviates. This is a structural deviation, not a functional gap.

### [G2] `test_local_e2e.py` file missing

- **File**: `tests/test_local_e2e.py` (missing file)
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §8 specifies `tests/test_local_e2e.py [NEW]` with `@pytest.mark.e2e_local` live E2E tests (trivial RESPOND + tool task + pre-warming + Ollama-unavailable skip). This file does not exist yet.
- **Design ref**: §8 file layout, §11.4, MLA-5
- **Impact**: MLA-5 acceptance criterion is not met. The E2E tests are required to prove the adapter works with a real model. This is expected to be a separate task, but it is a gap against the design's file layout which lists it as `[NEW]` alongside the other M3 files.

### [G3] No multi-step tool loop test (model calls tools across 2+ iterations)

- **File**: `tests/test_local_adapter.py` (missing test case)
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §11.1 lists "act() tool loop -- multi-step: Model calls tool twice across 2 iterations; final text returned" as a specified unit test. No such test exists — `test_happy_path_single_tool_call` covers only one tool-call iteration before final text.
- **Design ref**: §11.1 test matrix row "multi-step"
- **Impact**: Medium — the multi-iteration path (loop body executing >1 iteration with successful tool calls) has no test coverage. This is a core correctness path for the harness.

### [G4] No test for exhaustion backward-scan finding assistant text

- **File**: `tests/test_local_adapter.py` (missing test case)
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: The exhaustion path in `_run_tool_loop` (lines 360-364) scans backwards for assistant messages with text content. The existing `test_max_tool_iterations_exhaustion` only exercises the "no assistant text found" path (all model_dump'd messages have `content: None`). The "assistant text found" branch is untested.
- **Impact**: Low-medium — the code is simple (dict lookup + string check) but it's a distinct code path with no coverage.

### [G5] `httpx` in wrong optional-dependency group

- **File**: `pyproject.toml`:30
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §9 specifies `httpx` under `[project.optional-dependencies] test = ["pytest", "httpx"]`. The actual pyproject.toml uses `dev = ["pytest>=7.0", "httpx"]` instead of `test`. Minor naming deviation.
- **Design ref**: §9 dependency additions
- **Impact**: Cosmetic — `pip install .[dev]` vs `pip install .[test]`. The group name `dev` is arguably better practice. Not a real gap.

---

## Warnings (potential issues)

### [W1] `_extract_json_from_text` code-fence regex non-greedy `.*?` vs nested JSON

- **File**: `src/axiom/providers/base.py`:92
- **Pass**: Pass 4 (Input Validation & Boundaries)
- **What**: As analyzed in B1 (reclassified): the non-greedy `.*?` in the code-fence regex could misparse code-fenced JSON with nested objects. Current intent schema is flat (no nesting), so this is not a live bug in M3.
- **Risk**: If future intents gain nested structure (e.g. metadata fields), this regex would silently extract a truncated substring. The fallback `{.*}` (greedy) on line 98 would catch it, but only if the code-fence regex doesn't match first (it does match first, returning the truncated candidate).

### [W2] `agent.py` silently falls back to Claude on unknown provider value

- **File**: `src/axiom/agent.py`:68-75
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: `Agent(provider="openai")` or `Agent(provider="typo")` silently constructs a `ClaudeAdapter`. No `ValueError` for unrecognized providers. The CLI's `argparse choices=["claude", "local"]` prevents this from the command line, but programmatic callers have no guard.
- **Risk**: Surprising silent behavior if a new provider is added later or a typo is passed programmatically. Matches the design's illustrative code (which also uses `if/else`), so this is design-conformant but still a footgun.
- **Fix**: Add `elif provider == "claude": ...` and a final `else: raise ValueError(f"unknown provider: {provider!r}")`.

### [W3] `_query_model` returns empty string when model returns content=None and no tool_calls

- **File**: `src/axiom/providers/local_adapter.py`:239, 293
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: Both `_query_model` (line 239: `return message.content or ""`) and the tool-loop's no-tool-calls path (line 293: `return message.content or ""`) return `""` when the model produces a response with `content=None` and no tool calls. In `reason()`, this empty string reaches `_parse_intent("")` which returns `(None, "no valid JSON found in: ''")`, triggering the retry path — correct. In `act()` via `_run_tool_loop`, an empty string is returned as the final answer — potentially surprising but not incorrect (the model had nothing to say).
- **Risk**: Low — the retry mechanism in `reason()` handles this; `act()` returning `""` is unusual but not a crash.

### [W4] Shell tool executes arbitrary commands — no sandboxing

- **File**: `src/axiom/providers/local_adapter.py`:79
- **Pass**: Pass 9 (Security)
- **What**: `subprocess.run(command, shell=True, ...)` executes arbitrary shell commands from the model. Acknowledged in design §5.2.1 security note: "M3 is a dev-machine proof, not a production deployment."
- **Risk**: Model could be prompted to execute destructive commands. Acceptable for M3 scope per design, but worth flagging for future milestone attention.

### [W5] `_run_tool_loop` raises `AdapterError` on LiteLLM exception but `act()` contract per design says exhaustion is NOT an AdapterError

- **File**: `src/axiom/providers/local_adapter.py`:283-287
- **Pass**: Pass 7 (Contract Violations)
- **What**: Mid-loop LiteLLM exceptions (Ollama dies during iteration 3 of 5) raise `AdapterError`. This is correct — it's a model-call failure, not iteration exhaustion. The design §5.4 exhaustion row says "NOT an AdapterError" for max-iteration exhaustion specifically — the code correctly distinguishes these: exhaustion returns a string (line 366), model errors raise AdapterError (line 287). No issue — confirming the C1 distinction is present.
- **Risk**: None — documenting for clarity that the two paths are correctly separated.

### [W6] `litellm` imported eagerly at `LocalAdapter.__init__` — constructor will fail if litellm not installed

- **File**: `src/axiom/providers/local_adapter.py`:127
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: `import litellm as _litellm_mod` is inside `__init__`, so `LocalAdapter("p")` will raise `ModuleNotFoundError` if litellm is not pip-installed. This is the intended design (fail-fast at construction), and the test suite handles this via `sys.modules.setdefault("litellm", mock)`. For live E2E, litellm must be installed.
- **Risk**: Developer confusion if they run `--provider local` without `pip install litellm`. The error message will be a raw `ModuleNotFoundError`, not a friendly message. Consider wrapping the import in a try/except with a clear message. Low priority for M3.

---

## Observations

### [O1] Test file consolidation: shared base tests live in `test_local_adapter.py`

- **File**: `tests/test_local_adapter.py`
- **What**: Design §8/§11.2 specifies a separate `test_shared_base.py`. The implementation consolidated all 39 tests (including 8 PraoAdapterBase + 12 _parse_intent tests) into `test_local_adapter.py`. This is a pragmatic choice — single file, single import-mock setup. All specified test cases are present.

### [O2] `sys.modules` mock injection pattern is well-executed

- **File**: `tests/test_local_adapter.py`:26-27
- **What**: The `sys.modules.setdefault("litellm", mock)` pattern correctly handles the deferred import without requiring litellm to be installed in the test environment. Clean and idiomatic.

### [O3] Tool executor lambda captures `args["command"]` — could KeyError on malformed args dict

- **File**: `src/axiom/providers/local_adapter.py`:141
- **What**: The lambda `lambda args: _execute_shell_tool(args["command"])` would raise `KeyError` if the model produces valid JSON that lacks the `"command"` key (e.g. `{"cmd": "ls"}`). However, this KeyError is caught by the `except Exception as exec_err` block (line 326) and fed back to the model as an error string. So it's handled — just noting that the error message would be `KeyError: 'command'` rather than a more descriptive tool-argument-validation error.

### [O4] `model_dump()` assumption documented in design, verified in tests

- **File**: `src/axiom/providers/local_adapter.py`:299
- **What**: The design note O4 (§5.3) flags that `message.model_dump()` assumes a Pydantic response. The tests mock this correctly via `msg.model_dump.return_value = {...}`. Live verification depends on LiteLLM's actual response type — deferred to E2E.

### [O5] W5 is actually confirmed-correct — included as Warning only for documentation

- Exhaustion returns string (line 366); model error raises AdapterError (line 287). Design's C1 fix is present in code.

---

## Summary

| Bugs | Gaps | Warnings | Observations |
|------|------|----------|--------------|
| 0 | 5 | 6 | 5 |

**Gap breakdown**: G1 (test file location, cosmetic), G2 (E2E test file missing — likely separate task), G3 (multi-step tool loop test missing, **medium risk**), G4 (exhaustion backward-scan branch untested, low-medium), G5 (optional-dep group name, cosmetic).

**Critical findings**: None. The highest-risk code (act() tool harness) is correctly implemented with all error paths handled per design. The C1 fix (exhaustion backward-scan for assistant text, not raw tool result) is present. All M1 frozen files are byte-identical. The base-class refactor preserves ClaudeAdapter behavior. Lazy import of litellm is correctly implemented.

**Verdict**: **PASS WITH WARNINGS**

The implementation is solid and design-conformant. No bugs found. The two actionable gaps are:
1. **G3** — add a multi-step tool loop test (design-specified, missing).
2. **G2** — `test_local_e2e.py` is not yet created (may be a separate task gating).

The warnings are all low-risk items or confirmed-correct documentation. The code is ready for E2E testing once litellm is pip-installed and Ollama is running.
