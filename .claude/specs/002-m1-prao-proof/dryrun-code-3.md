# Code Dry-Run Report #3 — Confirming-Clean Gate

**Scope**: `src/axiom/` (interfaces.py, loop.py, agent.py, providers/claude_adapter.py, observability/timing.py, interface/cli.py, persona/__init__.py) + `tests/` — verification of the 3 items remaining after dryrun-code-2, plus a fresh full pass
**Design**: `.claude/specs/002-m1-prao-proof/design.md`
**Reviewed**: 2026-07-08

---

## Test Suite Evidence (run first, before review)

```
$ pytest tests/ -q
..........................                                               [100%]
26 passed in 0.38s
```

**26 passed, 0 failed, 0 errors.** Test files (`tests/test_contracts.py`, `tests/fake_adapter.py`) present and the offline contract suite is green.

---

## Verification of the 3 Remaining Items (dryrun-code-2)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| W4 | Debug-handler duplication | **RESOLVED** | `agent.py:38-42` — `_axiom_logger.setLevel(logging.DEBUG)` then `if not _axiom_logger.handlers:` guards the `StreamHandler` creation and `addHandler` call. A second `Agent(debug=True)` in the same process re-runs `setLevel` (idempotent) but skips `addHandler` — each DEBUG record, including `[M1 Latency]`, is emitted exactly once. Docstring (lines 34-36) documents the idempotence. In-process multi-turn / harness looping over `Agent(...)` is now safe for latency sign-off. |
| G1-doc | Design §7.6 missing error rows | **RESOLVED** | `design.md:420-421` — the §7.6 error table now has 9 rows. Row 420: `SDK run failed (ResultMessage.is_error=True)` → log `ERROR [ADAPTER_SDK_IS_ERROR]` with `subtype`/`errors` detail → raise `AdapterError("SDK run failed (...)")`, no empty return — matches `claude_adapter.py:90-97` exactly. Row 421: `Any other Exception (unhandled, non-AdapterError)` → log `ERROR [ADAPTER_UNEXPECTED]` → raise `AdapterError("unexpected error: {e}")`, with the note that `BaseException` subclasses pass through — matches `claude_adapter.py:244-248` exactly (the `isinstance(e, AdapterError): raise` guard prevents double-wrap). Design and code are in sync. |
| W5 | Unbounded `aclose()` in `finally` | **RESOLVED** | `claude_adapter.py:101-103` — `finally: with anyio.move_on_after(5): await gen.aclose()`. `move_on_after` is non-raising (silent scope exit on expiry), so a hanging SDK teardown can no longer stall the turn indefinitely after the 120s `fail_after` fires — worst case adds 5s, then the original `TimeoutError` continues propagating to `_run_query`'s `[ADAPTER_TIMEOUT]` handler. Scope-nesting check: the `finally` runs after `fail_after` has exited, so `move_on_after(5)` is the only active cancel scope there — no shielding needed (no outer cancellation in play under `anyio.run`). Correct implementation of the mitigation named in dryrun-code-2. |

**Score: 3/3 RESOLVED.** Combined with dryrun-code-2's 7 RESOLVED, all 12 findings across dryrun-code-1 and -2 (B0, G1 code+doc, W1–W5, S1–S4) are now closed.

---

## Fresh Pass (all 9 passes re-executed over the full scope)

- **Pass 1 (design conformance)**: §7.6 table (9 rows) matches the adapter's exception ladder one-for-one, including marker strings. §7.1–7.4 port behaviors, §4.1 wire format/parse rules, §11 import boundaries (loop → interfaces only; cli → agent only; timing → stdlib only via `TYPE_CHECKING`) all verified. No undocumented behavior remains.
- **Pass 2 (execution trace)**: cli `main()` → `Agent(debug)` → `timed_run` → `PraoLoop.run` → perceive/reason/act/observe. Happy paths (RESPOND, FINISH, ACT×N→RESPOND) trace clean; `field(init=False)` intents construct correctly; `spawn_count`/`cycle_count` semantics unchanged. No dead branches.
- **Pass 3 (error trace)**: every SDK exception, `TimeoutError`, and the catch-all map to `AdapterError` with a distinct ERROR marker; `KeyboardInterrupt`/`SystemExit` pass through; `AdapterError` propagates loop→timing (abort log, re-raise)→agent (`[Error: ...]`). `is_error` raise inside `reason()`'s first `_run_query` aborts the turn without consuming the parse-retry — correct.
- **Pass 4 (input/boundaries)**: `cli.py:35` `is not None` handles `""` arg; empty stdin → exit 1; empty `ResultMessage.result` → `""` per design row 419; `_parse_intent` rejects non-dict JSON, missing/non-str fields, unknown intents.
- **Pass 5 (resources)**: generator bound, `aclose()` in `finally` with the 5s bound (W5) — deterministic cleanup on success, is_error, and timeout paths. No other held resources.
- **Pass 6 (concurrency)**: sync ports, `anyio.run` per call, no shared mutable state across calls; module-level logger config guarded (W4).
- **Pass 7 (contracts)**: port Protocol signatures match `ClaudeAdapter` and `tests/fake_adapter.py`; `timed_run` signature matches `PraoLoop.run`; non-`ActIntent` foreign types hit the `TypeError` guard (`loop.py:84-88`, `-O`-safe).
- **Pass 8 (quality)**: no TODO/FIXME/HACK; constants named (`PER_QUERY_TIMEOUT_SECS`, `MAX_CYCLES`, `M1_ALLOWED_TOOLS`); logging markers consistent; the `5` in `move_on_after(5)` is commented inline and acceptable as a local best-effort bound.
- **Pass 9 (security)**: no shell/SQL/path construction from user input in Axiom code (tool execution is SDK-scoped via `allowed_tools`); no secrets logged.

## Bugs (will cause incorrect behavior)

None found.

## Gaps (missing implementation)

None found.

## Warnings (potential issues)

None found.

## Style (code quality, conventions)

None found.

## Observations (closed by analysis — no action required)

- **[O1] Exception raised *by* `gen.aclose()` itself on the timeout path** would propagate from the `finally` and supersede the in-flight `TimeoutError`, reaching the catch-all instead — the turn still aborts with a single `AdapterError`, only the marker differs (`[ADAPTER_UNEXPECTED]` vs `[ADAPTER_TIMEOUT]`). Termination guarantee (MPP-1) holds either way; theoretical path, SDK teardown normally absorbs `GeneratorExit`. Closed as acceptable.
- **[O2] The W4 guard keys on `_axiom_logger.handlers`** — if external code ever attaches its own handler to the `"axiom"` logger before `Agent(debug=True)`, the debug handler is skipped. No such code exists in M1 (grep-verified); by then records still flow to the external handler. Closed as acceptable.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 0 | 0 |

**Tests**: 26 passed, 0 failed (`pytest tests/ -q`, 0.38s).

**Verdict**: **PASS — READY FOR E2E**

All findings from dryrun-code-1 and dryrun-code-2 are resolved and verified in code and design; the fresh nine-pass review over the full M1 scope found zero bugs, zero gaps, zero warnings, and zero style issues. The two observations above are analyzed and closed — low-risk, watch-at-runtime details only. No further code review is needed before the live E2E scenarios (happy path, ACT path, web-search, error paths, timeout).
