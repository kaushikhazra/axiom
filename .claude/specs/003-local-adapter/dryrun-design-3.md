# Dry-Run Design Review #3 -- 003-local-adapter (smolagents migration)

**Reviewer:** Velasari
**Date:** 2026-07-09
**Scope:** Reviews the **smolagents-migrated** design (design.md rev 2026-07-09), NOT the superseded litellm hand-rolled-tool design reviewed in dryrun-design-1.md and -2.md.
**Inputs read:**
- `.claude/research/004-local-model-tool-sdk-landscape-2026-07-09.md` (decision doc)
- `.claude/specs/003-local-adapter/requirement.md` (163 lines, revised)
- `.claude/specs/003-local-adapter/design.md` (600 lines, revised)
- `.claude/specs/003-local-adapter/task.md` (67 lines, revised)
- `.claude/specs/002-m1-prao-proof/design.md` (M1 port contract)
- `src/axiom/providers/base.py` (live source, 250 lines)
- `src/axiom/providers/claude_adapter.py` (live source, 214 lines)
- `src/axiom/interfaces.py` (live source, 119 lines)
- `src/axiom/loop.py` (live source, 97 lines)

---

## Verdict: PASS

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Warning  | 3 |
| Observation | 5 |

No critical gaps found. The smolagents migration design is structurally sound, coherent with the M1 port contract, and correctly eliminates all hand-rolled tool code. Three warnings require attention at implementation time but do not block the build.

---

## Focus 1: smolagents -> PRAO Port Mapping Coherence

**Verdict: Sound. No gap found.**

The mapping is:

| Port | Implementation | Loop owner |
|------|---------------|------------|
| `perceive(RunState)->str` | Inherited from `PraoAdapterBase` | PraoLoop (outer) |
| `reason(str)->Intent` | Tool-less `LiteLLMModel` direct call + `_parse_intent` | PraoLoop (outer) |
| `act(str)->str` | Delegates to `CodeAgent.run(instruction)` -> `str(result)` | CodeAgent (inner worker, KIND-B) |
| `observe(str,RunState)->RunState` | Inherited from `PraoAdapterBase` | PraoLoop (outer) |

This matches the M1 contract exactly:
- Port signatures are preserved verbatim (confirmed against live `interfaces.py`).
- `reason()` is tool-less (uses `self._model` directly, never `CodeAgent`) -- consistent with M1 design SS8 ("reason uses no tools").
- `act()` is string-in/string-out; the `str()` conversion at the boundary handles any wrapper type from `CodeAgent.run()`.
- KIND-B delegation (CodeAgent's internal loop is invisible to PraoLoop) mirrors ClaudeAdapter's delegation to the Claude SDK's internal tool loop.
- The outer PRAO loop can still drive multiple cycles (`reason->ACT->act->observe->reason->...`) if the first `act()` result is insufficient -- the CodeAgent's inner loop and the PraoLoop's outer loop are independent iteration domains.

No bypass of the port contract detected. CodeAgent never touches `RunState`, never calls `perceive()` or `observe()` -- it receives a string instruction and returns a string result.

---

## Focus 2: Zero Axiom-Authored Tool Code

**Verdict: Clean. No residual hand-rolled tool logic.**

The design explicitly removes (task.md item 3, design SS5.1, SS9):
- `SHELL_TOOL_SCHEMA` -- gone
- `_execute_shell_tool()` -- gone
- `_run_tool_loop()` -- gone
- `_tool_schemas`, `_tool_executors` (tool registry) -- gone
- `MAX_TOOL_ITERATIONS`, `TOOL_COMMAND_TIMEOUT_SECS` -- gone (replaced by CodeAgent's `max_steps`)
- `import subprocess` -- gone

All tools come from smolagents via `add_base_tools=True`:
- `DuckDuckGoSearchTool` (web search, no API key, local execution)
- `PythonInterpreterTool` (sandboxed Python execution)
- Other base tools (VisitWebpageTool, etc.) available but not explicitly tested

The `tools=[]` parameter on `CodeAgent(tools=[], add_base_tools=True)` means zero custom tools -- only the SDK's built-in toolbox. This mirrors ClaudeAdapter's relationship with its SDK (`allowed_tools` scoping, no axiom tool implementations).

No residual tool code found in the design. The import boundary rule (SS11) explicitly prohibits `subprocess` import in `local_adapter.py`.

---

## Focus 3: Open Questions OQ-1..OQ-4 -- Deferral Safety

### W1 -- OQ-1: LiteLLMModel Standalone API (WARNING)

**Risk:** `_query_model()` calls `self._model(messages, stop_sequences=None)` and accesses `response.content`. The `LiteLLMModel` class is designed as `CodeAgent`'s model backend -- using it standalone for a direct tool-less completion is an unverified API path. The calling convention (positional `messages` list, `stop_sequences` kwarg) and return type (`response.content` attribute) are assumptions, not confirmed from the installed smolagents version.

**Why this matters:** If the API is different (e.g., `LiteLLMModel.__call__` requires additional parameters, or returns a different type), `reason()` is 100% broken -- not degraded, not fallback, completely non-functional. Every PRAO cycle starts with reason().

**Deferral assessment:** Contained to `_query_model()` (single function, ~10 lines). Fails loudly on the first call -- no silent data corruption. **Deferrable with loud failure**, but implementer should verify the smolagents `Model.__call__` signature **before** writing `_query_model()`, not after. The "verify at implementation" status is acceptable only if the implementer treats this as step 0, not a post-hoc test.

### W2 -- OQ-3: CodeAgent Statefulness Across act() Calls (WARNING)

**Risk:** The design creates `CodeAgent` once in `__init__` and reuses it across `act()` calls (design SS4.1, line 99: "Key architectural point: The CodeAgent is instantiated once... and reused"). If `CodeAgent.run()` accumulates conversation history or state between runs, then:
- Second `act()` call in the same session carries stale context from the first.
- Multi-cycle PRAO loops (reason->ACT->act->observe->reason->ACT->act) would have the second act() contaminated by the first act()'s internal history.

The design asserts "CodeAgent.run() method is stateless per-call (each run is independent)" but marks OQ-3 as "Verify at implementation."

**Deferral assessment:** If CodeAgent IS stateful, the fix is trivial (create fresh per `act()` call instead of reusing), and the design already anticipates this: "we may need to create a fresh CodeAgent per act() call." However, the **default** in the design is reuse-first, which means if the implementer doesn't verify statefulness before shipping, multi-cycle E2E tests (E2E #2, #3) could exhibit subtle contamination. **Recommend: default to create-fresh-per-call (defensive) and switch to reuse ONLY after confirming statelessness.** The cost of fresh construction (one LiteLLMModel + CodeAgent instantiation per act()) is negligible compared to model inference time.

### OQ-2 (CodeAgent.run() return type): Safe deferral. The `str()` conversion in `act()` handles any wrapper type. Contained. No concern.

### OQ-4 (DuckDuckGo rate limits): Genuinely a test-time concern, not a design gap. The design doesn't depend on DuckDuckGo availability for structural correctness -- only E2E #2 validation. Acceptable deferral.

---

## Focus 4: Security Posture (U2)

**Verdict: Adequately stated for M3 dev-machine proof.**

The design explicitly addresses the security migration (SS5.2):

| Aspect | Prior (litellm) | New (smolagents) |
|--------|-----------------|-------------------|
| Code execution | `subprocess.run(shell=True)` -- arbitrary shell | `PythonInterpreterTool` -- sandboxed interpreter, restricted namespace |
| Import control | None | `additional_authorized_imports=["math", "statistics", "datetime", "json", "re"]` |
| Dangerous builtins | Full access (`os.system`, `shutil.rmtree`, etc.) | Blocked by default in smolagents' interpreter |
| Production hardening | None | E2B/Docker path exists (out of scope for M3) |

### W3 -- E2E #3 "Create a Python script" vs Sandbox Restrictions (WARNING)

**Risk:** E2E #3 requirement says: "Create a Python script that prints 'hello world', execute it, and show me the output." Under CodeAct, the CodeAgent writes Python code executed in PythonInterpreterTool's sandbox. Two possible model behaviors:

1. **In-memory execution:** Model writes `print('hello world')` directly -- works in sandbox. This is the expected happy path.
2. **File creation attempt:** Model interprets "create a Python script" literally and writes `open('hello.py', 'w').write(...)` then tries to execute it -- may be blocked by sandbox restrictions on file I/O builtins.

The design doesn't clarify which behavior is expected or tested. If the model chooses path 2, the E2E test could fail not because of a design flaw but because of a prompt/sandbox mismatch.

**Mitigation:** The CodeAgent's own system prompt guides it toward writing executable Python code, not creating files. Path 1 is overwhelmingly likely. But the E2E test assertion should verify the output contains "hello world" regardless of the execution path (which the design already does), and the test name/description should clarify that it tests "code execution" not "file creation on disk."

---

## Focus 5: Frozen Files and M1 Test Regression

**Verdict: Fully honored.**

The design's file layout (SS9) marks as [UNCHANGED]:
- `loop.py` -- confirmed: no imports, no logic changes, no conditional branching
- `interfaces.py` -- confirmed: no new protocols, no signature changes, no new types
- `base.py` -- confirmed: already extracted, no changes needed
- `claude_adapter.py` -- confirmed: already refactored to inherit PraoAdapterBase

Cross-verified against live source:
- `loop.py` (97 lines): imports only `axiom.interfaces` -- zero provider imports. PraoLoop constructor takes port-typed params. No LocalAdapter awareness.
- `interfaces.py` (119 lines): four Protocols, Intent types, RunState, AdapterError, MaxCyclesExceededError. No changes required.
- `base.py` (250 lines): PraoAdapterBase with perceive()/observe()/_parse_intent(). Import boundary: `axiom.interfaces` only. No SDK imports.
- `claude_adapter.py` (214 lines): inherits PraoAdapterBase, implements reason()/act() via Claude SDK. Already refactored.

M1's 26 tests (`test_contracts.py`):
- Depend on: `axiom.interfaces`, `axiom.loop`, `tests.fake_adapter` -- none of these change.
- `FakeAdapter` remains unchanged (not required to adopt shared base).
- No test file from M1 is modified.

**Constraint fully honored by the design.**

---

## Focus 6: E2E Coverage Mapping

**Verdict: Maps cleanly with one clarification needed (W3 above).**

| E2E | Requirement | smolagents Mechanism | Clean? |
|-----|-------------|---------------------|--------|
| #1 "hello" RESPOND-only | reason() returns RESPOND, act() NOT called | LiteLLMModel direct call -> JSON intent parsing -> RESPOND. No CodeAgent involved. | Yes |
| #2 Weather search | reason() returns ACT, act() runs CodeAgent with DuckDuckGoSearchTool | CodeAgent.run(instruction) -> CodeAct writes `search("weather Durgapur")` -> DuckDuckGoSearchTool executes -> result returns through act() -> observe() captures | Yes (subject to OQ-4 rate limits) |
| #3 Python execution | reason() returns ACT, act() runs CodeAgent with PythonInterpreterTool | CodeAgent.run(instruction) -> CodeAct writes `print('hello world')` -> PythonInterpreterTool executes in sandbox -> result returns through act() -> observe() captures | Yes (subject to W3 clarification) |

All three scenarios flow through the real PraoLoop. The pre-warming strategy (send trivial generate to Ollama before timing) is specified. Graceful skip on Ollama unavailability is specified. `@pytest.mark.e2e_local` marker is specified.

---

## Findings Summary

### Warnings (3)

| # | Finding | Location | Recommendation |
|---|---------|----------|----------------|
| W1 | `LiteLLMModel` standalone API for reason() is unverified -- calling convention and return type are assumptions | design.md SS4.3, `_query_model()` | Verify `Model.__call__` signature from installed smolagents source as implementation step 0, before writing `_query_model()` |
| W2 | CodeAgent statefulness across act() calls -- design defaults to reuse but statefulness is unverified (OQ-3) | design.md SS4.1 line 99, SS6 constructor | Default to create-fresh-per-call (defensive); switch to reuse only after confirming statelessness via test |
| W3 | E2E #3 "create a Python script" ambiguity -- model may attempt file I/O blocked by PythonInterpreterTool sandbox | requirement.md MLA-5 E2E #3, design.md SS5.2 | Clarify E2E #3 tests code execution (not file creation on disk); ensure test assertion checks output content, not execution path |

### Observations (5)

| # | Finding | Location |
|---|---------|----------|
| O1 | Security posture trusts smolagents' sandbox enforcement without independent verification -- acceptable for M3 dev-machine proof, but production deployments should verify the sandbox claims or use E2B/Docker | design.md SS5.2 |
| O2 | No custom `system_prompt` specified for CodeAgent -- relies on smolagents' default system prompt for code generation/tool use. If the default prompt causes unexpected behavior (e.g., verbose preamble, refusal patterns), a custom prompt may be needed | design.md SS4.4, SS6 constructor |
| O3 | `max_steps=5` preserves behavioral parity with the prior design's `MAX_TOOL_ITERATIONS=5` -- good continuity | design.md SS6 |
| O4 | Import boundary and frozen-file constraints are fully honored -- `local_adapter.py` imports smolagents (deferred), `axiom.interfaces`, `axiom.providers.base`, stdlib only. No `subprocess`, no `litellm` direct import | design.md SS11 |
| O5 | The `additional_authorized_imports` list is configurable via the LocalAdapter constructor -- a caller could pass dangerous imports. Acceptable for M3 (dev-machine proof); production should validate/restrict this parameter | design.md SS6, SS5.2 |

---

## Architectural Consistency Check

| Constraint | Status |
|------------|--------|
| PraoLoop drives outer cycle; CodeAgent owns inner worker loop (KIND-B) | Honored |
| Port signatures match M1 contract verbatim | Honored |
| loop.py imports zero provider code | Honored |
| interfaces.py has zero diff from M1 | Honored |
| base.py has zero diff (already extracted) | Honored |
| claude_adapter.py has zero diff (already refactored) | Honored |
| Zero axiom-authored tool code | Honored |
| AdapterError error contract consistent with M1 | Honored |
| M1's 26 tests unaffected | Honored |
| FakeAdapter unchanged | Honored |

---

*Reviewed by Velasari, 2026-07-09. This is review iteration 3 (first review of the smolagents-migrated design; iterations 1-2 reviewed the superseded litellm-era design).*
