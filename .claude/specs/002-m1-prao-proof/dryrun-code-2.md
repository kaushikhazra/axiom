# Code Dry-Run Report #2

**Scope**: `src/axiom/` (interfaces.py, loop.py, agent.py, providers/claude_adapter.py, observability/timing.py, interface/cli.py) + `tests/` — regression verification of dryrun-code-1 findings + fresh pass over the fixed code
**Design**: `.claude/specs/002-m1-prao-proof/design.md`
**Reviewed**: 2026-07-08

---

## Test Suite Evidence (run first, before review)

```
$ pytest tests/ -q
..........................                                               [100%]
26 passed in 0.39s
```

**26 passed, 0 failed, 0 errors** — the offline contract suite (`tests/test_contracts.py`, cases a–e) is green after the fixes. Test file inspected: unchanged and un-weakened (all assertions on spawn/cycle counts, propagation, and short-circuit behavior intact).

---

## Regression Verification (dryrun-code-1 findings)

| # | Finding | Status | Evidence |
|---|---------|--------|----------|
| G1 | `ResultMessage.is_error` ignored | **PARTIAL** | Code side RESOLVED: `claude_adapter.py:90-97` — `if message.is_error:` extracts `subtype`/`errors` via `getattr`, logs `[ADAPTER_SDK_IS_ERROR]`, raises `AdapterError(f"SDK run failed ({detail})")`. No fake-empty return. The raise propagates through `anyio.run` into `_run_query`, where the final `except Exception` guard (`claude_adapter.py:243-245`) re-raises `AdapterError` unwrapped — no double-wrap. **BUT the design §7.6 row was NOT added**: the error table (design.md:411-419) still has exactly the original 7 rows; no `is_error=True` row (and no catch-all row for W1 either). Code and design table are now out of sync. |
| W1 | Non-SDK exceptions escape `_run_query` | **RESOLVED** | `claude_adapter.py:243-247` — final `except Exception as e:` with `if isinstance(e, AdapterError): raise` guard, then logs `[ADAPTER_UNEXPECTED]` and raises `AdapterError(f"unexpected error: {e}") from e`. `KeyboardInterrupt`/`SystemExit` (BaseException-derived) correctly pass through uncaught. `ExceptionGroup` (Exception-derived, py3.12) is now caught and wrapped. |
| W2 | Abandoned async generator | **RESOLVED** | `claude_adapter.py:85-102` — generator bound to `gen`, `try/finally: await gen.aclose()`, and the `break` was removed (comment lines 99-100: iterate to exhaustion; `ResultMessage` is terminal so `aclose()` is a no-op on success). Cleanup is deterministic on the `is_error` raise path and the timeout path. |
| W3 | Load-bearing `assert isinstance` | **RESOLVED** | `loop.py:84-88` — `if not isinstance(intent, ActIntent): raise TypeError(...)`. Survives `python -O`. RESPOND/FINISH isinstance checks precede it (lines 77-81), so the TypeError branch fires only for genuinely foreign types. |
| W4 | Debug-handler duplication | **NOT RESOLVED** | `agent.py:28-37` — `_configure_debug_logging()` still has **no idempotence guard**: `addHandler(handler)` unconditionally at line 37, called from `__init__` at line 55 on every `Agent(debug=True)` construction. Grep across `src/` confirms no `handlers` check or module flag anywhere. Two debug Agents in one process still duplicate every DEBUG line, corrupting `[M1 Latency]` collection in any harness that loops over `Agent(...)`. |
| S1 | Private `._errors` imports | **RESOLVED** | `claude_adapter.py:20-29` — all five exception classes plus `ClaudeAgentOptions`, `ResultMessage`, and `query` imported from public top-level `claude_agent_sdk`. No `._errors` or `.types` imports remain. |
| S2 | `kind` as first positional param | **RESOLVED** | `interfaces.py:35, 42, 47` — `kind: IntentKind = field(init=False, default=...)` on all three frozen intent dataclasses, with explanatory comments. `RespondIntent("hi")` now sets `text`. |
| S3 | Empty-string arg falls to stdin | **RESOLVED** | `cli.py:35` — `if args.input is not None:` — `axiom-cli ""` now reaches the "No input provided" exit (line 41-43). |
| S4 | Dead `response_text` variable | **RESOLVED** | `timing.py:50` — `_, run_state = result`. |

**Score: 7 RESOLVED, 1 PARTIAL (G1 — design doc half missing), 1 NOT RESOLVED (W4).**

---

## Fresh Pass (new defects introduced by the fixes)

All 9 passes re-executed over the changed files. Interaction paths specifically traced:

- **G1 raise × parse-retry**: `AdapterError` from `is_error` inside `reason()`'s first `_run_query` (claude_adapter.py:151) propagates immediately out of `reason()` — it does **not** consume the parse-retry or produce a `[FALLBACK_RESPOND]`. Correct: loop doesn't catch it (loop.py:47-96), `timed_run` logs abort and re-raises (timing.py:58-61), `agent.run` converts to `[Error: ...]` (agent.py:78-79). Clean.
- **W1 catch-all × AdapterError double-wrap**: the `isinstance` guard at claude_adapter.py:244 prevents re-wrapping. Verified `AdapterError` matches none of the earlier SDK-specific clauses (it subclasses plain `Exception`).
- **W2 aclose × control flow**: removing the `break` is safe — after the terminal `ResultMessage` the generator exhausts naturally; `result_text` set at line 98 is returned at line 103. Timeout path: `fail_after` raises `TimeoutError` at scope exit, `finally` closes the generator, `_run_query:236-242` wraps as `AdapterError`. No behavior change on any designed path.
- **Loop/interfaces/tests**: spawn/cycle semantics, exit conditions, import boundaries (§11) all unchanged and re-verified. `field(init=False)` on frozen dataclasses works correctly (defaults assigned via `__init__`-generated code; 26 tests confirm).

## Bugs (will cause incorrect behavior)

None found.

## Gaps (missing implementation)

### [G1-carryover] Design §7.6 error table missing the `is_error` row (and the catch-all row)
- **File**: `.claude/specs/002-m1-prao-proof/design.md:411-419`
- **Pass**: 1 (design conformance)
- **What**: The code now implements two error behaviors — `is_error=True` → `[ADAPTER_SDK_IS_ERROR]` → `AdapterError` (claude_adapter.py:90-97) and catch-all → `[ADAPTER_UNEXPECTED]` → `AdapterError` (claude_adapter.py:243-247) — that the §7.6 table does not enumerate. dryrun-code-1 G1's fix direction included adding the design row for consistency; only the code half was done.
- **Design ref**: §7.6 "Error scenarios and adapter behaviour" table.
- **Direction**: Add two rows to the §7.6 table: `SDK run failed (is_error=True)` → log `ERROR [ADAPTER_SDK_IS_ERROR]`, raise `AdapterError`; `Any other Exception` → log `ERROR [ADAPTER_UNEXPECTED]`, raise `AdapterError`. Doc-only change.

## Warnings (potential issues)

### [W4-carryover] `_configure_debug_logging()` still adds a handler per `Agent(debug=True)` construction
- **File**: `src/axiom/agent.py:28-37, 54-55`
- **Pass**: 8 (quality/patterns)
- **What**: Unchanged from dryrun-code-1 W4. No `if _axiom_logger.handlers:` guard or module flag; each debug Agent construction stacks another stderr handler, duplicating every DEBUG record including `[M1 Latency]`.
- **Risk**: In-process multi-turn or test-harness usage during M1 latency sign-off. One-shot CLI unaffected.

### [W5] `await gen.aclose()` in `finally` runs outside the timeout cancel scope
- **File**: `src/axiom/providers/claude_adapter.py:101-102`
- **Pass**: 5 (resource management)
- **What**: The `finally` block executes after `anyio.fail_after` has exited, so `aclose()` is awaited with **no timeout protection**. `aclose()` throws `GeneratorExit` into the SDK generator, whose cleanup performs transport disconnect/subprocess teardown. If that teardown itself hangs (the same unauthenticated-CLI-hang scenario the 120s timeout exists for), the turn hangs indefinitely *after* the timeout fired — the `TimeoutError` never reaches `_run_query`.
- **Risk**: Low-probability, timeout-path-only; `GeneratorExit` normally forces prompt teardown. Worth watching during the live timeout E2E scenario. Mitigation if it bites: wrap the `aclose()` in its own short `anyio.fail_after` with a shielded scope, or `with anyio.move_on_after(5):` around it.

## Style (code quality, conventions)

None new. S1–S4 all resolved and closed.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 1 (doc-only) | 2 (1 carryover, 1 new low-risk) | 0 |

**Tests**: 26 passed, 0 failed (pytest 8.4.2, py3.12).

**Verdict**: **PASS WITH WARNINGS** — not yet "READY FOR E2E" under the strict zero-findings bar.

The code fixes for G1, W1, W2, W3, S1–S4 are genuine and introduced no regressions; the interaction paths (is_error raise vs. parse-retry, catch-all vs. AdapterError, aclose vs. control flow) all trace clean, and the contract suite is green. Two items remain before a clean PASS:

1. **W4 was not applied at all** — add the idempotence guard in `agent.py:_configure_debug_logging()` (one `if` statement).
2. **G1's design half is missing** — add the `is_error` (and catch-all) rows to design §7.6 (doc-only edit).

W5 is a watch-item for the live timeout scenario, not a blocker. Once W4 + the §7.6 doc rows land, this is E2E-ready with no further code review needed.
