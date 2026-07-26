# Code Dry-Run Report #1

**Scope**: `src/axiom/tools/` (new), `src/axiom/providers/local_adapter.py`, `src/axiom/providers/claude_adapter.py`, `src/axiom/agent.py`, `src/axiom/interface/cli.py` (all modified for M4)
**Design**: `.claude/specs/006-m4-tools/design.md`
**Reviewed**: 2026-07-24

---

## Bugs found and fixed during this review

Per the same convention used in `dryrun-design-1.md`, these were found and corrected in-place during this pass; the sections below assess the **resulting, corrected** code, which carries the verdict.

### [B1] `ToolRegistry.execute()` raised on wrong-argument-type, violating "never raises"
- **File**: `src/axiom/tools/registry.py:47-52` (pre-fix)
- **Pass**: Pass 4 (Input Validation & Boundaries)
- **What**: `_dispatch()` passes `arguments["content"]` straight into `write_file()` → `Path.write_text()`. A non-string value (e.g. `content=12345`) makes `write_text` raise a bare `TypeError`, which `execute()`'s `except ToolError` clause did not catch. Reproduced empirically: `registry.execute("write_file", {"path": "x.txt", "content": 12345})` raised `TypeError: data must be str, not int` uncaught. Same class of issue for `list_dir({"path": 123})` (`Path.__truediv__` with a non-string).
- **Impact**: Contradicts `ToolsPort.execute()`'s explicit docstring contract ("Never raises — failures and denials are encoded in the returned ToolResult"). Not reachable via the smolagents path today (smolagents' own `Tool.validate_arguments()` checks types before calling `forward()`), but reachable by any direct `execute()` caller — exactly the kind of caller the port is designed to support (design.md D1).
- **Fix applied**: `execute()`'s except clause broadened from `except (KeyError, TypeError)` (already covers KeyError from finding B1's sibling); error message changed from `"missing required argument: ..."` to the more general `"invalid arguments: ..."`. Two new tests added (`TestWrongArgumentType`), and the three existing `TestMissingArgument` tests' assertions updated to match the new message.

### [B2] The approval step itself (`GuardrailsGate.check`/`request_approval`) was not covered by any exception handling, on both providers
- **File**: `src/axiom/tools/registry.py:44-45` (pre-fix, KIND-A); `src/axiom/providers/claude_adapter.py:327-329` (pre-fix, KIND-B)
- **Pass**: Pass 3 (Error Path Trace)
- **What**: KIND-A: `ToolRegistry.execute()` called `self._gate.check(name, arguments)` *before* the `try` block that guards `_dispatch()`. KIND-B: `ClaudeAdapter._gate_hook` awaited `self._gate.request_approval(...)` with no surrounding try/except. In both cases, a raising `approval_fn` (a custom one, or the default CLI prompt hitting a closed/broken stdin — `sys.stdin.readline()` can raise `ValueError: I/O operation on closed file`) propagates uncaught. Reproduced empirically on the KIND-A side: a `ValueError` from a stub `approval_fn` escaped `execute()` uncaught.
- **Impact**: Same "never raises" contract violation for KIND-A (AC-01.1). For KIND-B, an uncaught exception inside the hook eventually surfaces as an `AdapterError` via `_run_query`'s broad catch-all (so it doesn't crash the process), but it turns what should be a graceful per-call denial into a hard failure of the entire `act()` call — inconsistent with AC-03.4's "never terminates the PRAO loop early" intent, and inconsistent with the KIND-A behavior for the identical failure mode.
- **Fix applied**: KIND-A — `self._gate.check(...)` moved inside its own `try/except Exception`, returning `ToolResult(error="approval check failed: ...")` on failure (fails closed, not silently approved). KIND-B — `_gate_hook`'s `request_approval` call wrapped the same way, returning a `permissionDecision: "deny"` payload with `permissionDecisionReason: "approval check failed: ..."` on failure. Four new tests added: two in `tests/test_tools_registry.py` (KIND-A) and two in the newly-created `tests/test_claude_adapter_gate.py` (KIND-B), the latter also filling a real pre-existing coverage gap — no test previously constructed `ClaudeAdapter` or exercised `_gate_hook` at all.

---

## Gaps found and fixed during this review

### [G1] Stale E2E test docstring described a mechanism M4 removed
- **File**: `tests/test_local_e2e.py:212-214` (pre-fix)
- **Pass**: Pass 1 (Design Conformance)
- **What**: `test_e2e_create_and_run_python_file`'s docstring said the CodeAgent "writes a real .py file via `open(..., 'w')` and executes it via `subprocess.run()`" and that `'subprocess'` is in `additional_authorized_imports`. M4 removed both (`AC-04.4`/`AC-05.4`) — the test now depends on the model choosing to call the new `WriteFileTool`/`RunShellTool` instead.
- **Design ref**: `design.md` §8, AC-04.4/AC-05.4
- **Fix applied**: Docstring rewritten to describe the actual M4-era mechanism. Functional behavior is unaffected (the test was already updated with `gate=GuardrailsGate(auto_approve=True)` so the new tools auto-approve); this was a documentation-accuracy fix only.

  This test is skip-gated in this environment (`_SKIP_NO_OLLAMA`, requires Ollama at `localhost:11434`; the reachable instance in this session is on the LAN at `192.168.0.235`), so whether qwen2.5:7b actually discovers and calls the new gated tools as readily as it previously called bare `open`/`subprocess` is an **empirical question, not a static-review one** — out of scope for this code-review gate (DoD item 2) by design; it's exactly what the separately-planned live-CLI verification gate (DoD item 8 / US-08, AC-08.1–AC-08.4) exists to answer. Noted here as a pointer, not carried forward as an open code-review finding: when running that live verification, the `--provider local` scenario should specifically include a write/execute task (not just a read or search task) to exercise this path for real.

---

## Style (code quality, conventions)

None. The auto-format hook active in this environment (Black-equivalent, confirmed by repeated re-formatting on every `Write`/`Edit`) already normalizes line length/formatting on save.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 (2 found + fixed) | 0 (1 found + fixed) | 0 | 0 |

**Verdict**: PASS

Two bugs and one documentation gap were found and corrected during this review — see the sections above for the full account (all in the "never raises" port contract, and one stale test docstring). The code as it now stands has zero open bugs, gaps, warnings, or style findings. Full suite re-run after fixes: 400 passed, 4 skipped (same pre-existing, unrelated skips as before M4), 0 failed.
