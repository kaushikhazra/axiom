# Code Dry-Run Report #8 — TOOL-PROVISIONING FIX CONFIRMATION

**Scope**: `src/axiom/providers/local_adapter.py` (304 lines), `tests/test_local_adapter.py` (450 lines)
**Design**: `.claude/specs/003-local-adapter/design.md` (779 lines, SS20 added)
**Research**: `.claude/research/004-local-model-tool-sdk-landscape-2026-07-09.md`
**Prior report**: `dryrun-code-7.md` — 0/0/0/0, verdict PASS (post-E2E defect fix confirmation)
**Fix applied by**: worker 98c43161 (tool-provisioning fix in `act()` only)
**Reviewed**: 2026-07-09
**Purpose**: Confirm three tool-provisioning changes in `act()` are sound, tests are non-vacuous, prior clean findings did not regress, frozen-file invariants hold.

---

## 1. Tool-Set Change: `tools=[DuckDuckGoSearchTool()]`

### Correctness for E2E scenarios

| E2E scenario | Needs DuckDuckGoSearchTool? | Needs PythonInterpreterTool? | Verdict |
|---|---|---|---|
| #1 Hello (RESPOND-only) | No — reason() returns RESPOND, act() never called | N/A | OK |
| #2 Weather search | Yes — web search via ddgs | No — no Python execution needed beyond CodeAct | OK |
| #3 Write+run hello.py | No — uses subprocess directly | No — CodeAgent writes Python natively via LocalPythonExecutor; `subprocess.run()` is bare Python, not a tool call | OK |

### PythonInterpreterTool removal safety

CodeAgent in CodeAct mode executes Python natively via `LocalPythonExecutor` — that IS the code execution mechanism. `PythonInterpreterTool` as an explicit tool is a second, overlapping path. Its removal does NOT disable code execution; it eliminates the confusing dual-path that caused qwen to call `python_interpreter('hello.py')` as a shell executor. Design SS20 §18.3 documents this explicitly. **Removal is correct.**

### Zero axiom-authored tool code

`DuckDuckGoSearchTool` is imported from `smolagents` (line 199). No tool class defined in `local_adapter.py`. No `_execute_shell_tool`, no `SHELL_TOOL_SCHEMA`, no tool-loop code. Confirmed by reading full file. **Zero axiom tool code.**

### `add_base_tools` absent

`add_base_tools` is not passed to `CodeAgent` constructor (lines 231-240). Design SS20 §18.3 mandates this. Test `test_act_passes_correct_constructor_args` explicitly asserts `"add_base_tools" not in call_kwargs` (line 359-361). **Correct.**

---

## 2. `re` Pre-Population via `additional_functions`

### Mechanism validity

`LocalPythonExecutor(additional_functions={"re": _re})` (line 219). smolagents' `LocalPythonExecutor.__init__` merges `additional_functions` into the executor's initial namespace dict. This is the documented mechanism for injecting names into the sandbox — same as `{"open": builtins.open}` on the same line. **Valid mechanism.**

### Name resolution for `re.search(...)`

When model-generated code contains `re.search(pattern, text)` without `import re`, the executor looks up `re` in its namespace. `additional_functions["re"]` resolves to the `re` module object, so `re.search` attribute access works. **Correct.**

### Dual presence: `additional_functions` + `additional_authorized_imports`

`re` appears in both:
- `additional_authorized_imports` (line 79): permits explicit `import re` statements in generated code.
- `additional_functions` (line 219): pre-populates `re` in the namespace.

These are complementary, not conflicting. If the model writes `import re`, the import is authorized and succeeds (rebinding the same module). If the model omits it, the pre-populated name resolves. No shadowing risk — both paths bind to the same `re` module. **Consistent.**

### Scoping

`import re as _re` is inside `act()` (line 214), not module-level. `_re` is a local variable; the module-level `re` name is not polluted. **Scoped correctly.**

---

## 3. Prior Fixes — Regression Check

| Fix | Status | Evidence |
|-----|--------|----------|
| Fresh CodeAgent per act() (W2) | Intact | Constructor stores `_max_steps`/`_authorized_imports`; `act()` creates `CodeAgent(...)` inside method body (lines 231-240). No `self._agent`. |
| verbosity_level=0 (Defect B) | Intact | Line 236: `verbosity_level=0` in CodeAgent constructor kwargs. |
| Defect-A RESPOND-forcing framing | Intact | Lines 131-151 in `reason()`: sentinel check + framing prepend unchanged. |
| Timeout (G1) | Intact | Line 281: `timeout=PER_QUERY_TIMEOUT_SECS` in `_query_model()`. |
| hasattr guard (W2) | Intact | Line 284: `if not hasattr(response, "content")`. |
| strict=False in _parse_intent | Intact | Lives in `base.py` (frozen file). Not touched. |
| Error tags (W1) | Intact | Lines 289-303: differentiated `[LOCAL_ADAPTER_*]` tags. |
| G2 try/except scope | Intact | Lines 203-245: entire CodeAgent construction + run inside single try/except. |

**No regressions detected.**

---

## 4. Tests — Non-Vacuity Check

### `test_act_passes_correct_constructor_args` (lines 327-376)

Patches: `smolagents.CodeAgent`, `smolagents.LocalPythonExecutor`, `smolagents.DuckDuckGoSearchTool`.

Assertions (all non-vacuous — they inspect actual mock call kwargs, not truthy checks):
- `call_kwargs["tools"] == [mock_ddg_instance]` — verifies exact tool list.
- `"add_base_tools" not in call_kwargs` — verifies absence.
- `call_kwargs["max_steps"] == 3` — verifies custom value propagated.
- `call_kwargs["executor"] is mock_executor_instance` — verifies executor wiring.
- `call_kwargs["verbosity_level"] == 0` — verifies Defect-B.
- `executor_kwargs["additional_functions"]["re"] is _re_check` — verifies `re` module identity (not just presence).

**All assertions are concrete and non-vacuous.**

---

## 5. Frozen-File Invariants

| File | Status | Evidence |
|------|--------|---------|
| `src/axiom/loop.py` | Untouched | `git diff HEAD` — no output |
| `src/axiom/interfaces.py` | Untouched | `git diff HEAD` — no output |
| `src/axiom/providers/claude_adapter.py` | Untouched | `git diff HEAD` — no output |
| `src/axiom/providers/base.py` | Untouched | `git diff HEAD` — no output |

**M1's 26 green**: 77 passed, 3 skipped (the 3 skips are E2E tests requiring live Ollama). Contract tests unaffected.

---

## 6. Design ↔ Code Consistency

### SS20 (tool-provisioning fix)

Design §18.3 documents: replace `tools=[], add_base_tools=True` with `tools=[DuckDuckGoSearchTool()]`. Code line 233 matches. Design code snippet (lines 85-101 of design.md) matches implementation. **Consistent.**

### SS20 (`re` pre-population)

Design §18.4 documents: add `"re": _re` to `additional_functions`. Code line 219 matches. **Consistent.**

### Stale references in design (noted, not blocking)

- **Design line 609-610**: Architecture diagram still shows `PythonInterpreterTool (sandboxed)` as a branch under CodeAgent. This tool was removed by SS20. Diagram is stale.
- **Design line 118**: SS4.1 table says act() "executes via PythonInterpreterTool or DuckDuckGoSearchTool". Should say "DuckDuckGoSearchTool" only; Python execution is native CodeAct.
- **Design line 125**: SS4.2 narrative says "using DuckDuckGoSearchTool, PythonInterpreterTool, or bare Python". Same staleness.

These are documentation inconsistencies only. The normative sections (§18.3, tool table at line 298-302, MLA-3 at line 629) are all updated and correct. The stale references are in older narrative sections that were not swept. **No code impact — flagged as Style.**

---

## Findings Summary

| Category | Count | Details |
|----------|-------|---------|
| **Bugs** | 0 | — |
| **Gaps** | 0 | — |
| **Warnings** | 0 | — |
| **Style** | 1 | S1: Design diagram (line 609-610) + two narrative sentences (lines 118, 125) still reference `PythonInterpreterTool` after SS20 removal. Doc-only; no code impact. |

---

## Verdict: **PASS** — 0 bugs / 0 gaps / 0 warnings / 1 style

Code is sound. The tool-provisioning fix correctly narrows the tool list, the `re` pre-population uses a valid smolagents mechanism, no regressions in prior fixes, tests are non-vacuous, frozen files untouched, 77 tests green.

**READY-FOR-E2E-RERUN.**
