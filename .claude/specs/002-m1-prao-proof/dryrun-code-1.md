# Code Dry-Run Report #1

**Scope**: `src/axiom/` (interfaces.py, loop.py, agent.py, persona/, providers/claude_adapter.py, observability/timing.py, interface/cli.py) + `tests/` + `pyproject.toml`
**Design**: `.claude/specs/002-m1-prao-proof/design.md` (post dryrun-design-4, BUILD READY)
**Reviewed**: 2026-07-08

**Verification method**: All 9 passes executed. In addition to static trace, the installed SDK was inspected live: `claude_agent_sdk` v0.1.55; `inspect.isasyncgenfunction(query) == True`; exception MROs confirmed (`CLINotFoundError` ⊂ `CLIConnectionError` ⊂ `ClaudeSDKError`; `ProcessError`, `CLIJSONDecodeError` ⊂ `ClaudeSDKError`); `ResultMessage` dataclass fields enumerated.

---

## Verified-correct highlights (what was checked and passed)

- **Async bridge** (`claude_adapter.py:81`): `async for message in sdk_query(prompt=..., options=...)` with **no** `await` before `sdk_query` — correct for the verified async-generator API (OQ-2 closed correctly). `anyio.run(_collect_query_result, prompt, options)` matches `anyio.run(func, *args)`. `message.result or ""` handles `result: str | None`.
- **Error-table coverage** (`claude_adapter.py:196-224`): all 7 design §7.6 rows are caught and wrapped in `AdapterError` with the exact log markers. Catch **ordering is correct**: `CLINotFoundError` before `CLIConnectionError` before `ClaudeSDKError` (verified against actual MRO — a wrong order would have shadowed the specific rows). `TimeoutError` (builtin, what `anyio.fail_after` raises on py≥3.11) caught. Empty-result row: no exception, returns `""` as designed.
- **Intent parse** (`claude_adapter.py:232-267`): implements all 7 rules of §4.1 — strip, `json.loads` with `JSONDecodeError`/`ValueError`, dict check, exact case-sensitive intent values, per-kind required string fields via `isinstance(x, str)` (rejects `None`, numbers, bools), FINISH extra fields ignored. Parse-failure → `[INTENT_PARSE_FAILURE]` WARNING → one retry with correction notice → `[INTENT_FALLBACK]` WARNING → `RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")` using the **first** raw text, exactly per §7.2(e).
- **Loop** (`loop.py:47-92`): `spawn_count += 1` immediately before each `reason()` (line 74) and `act()` (line 85) dispatch; adapter-internal retry not counted (correct §7.2 semantics). RESPOND → `(intent.text, state)`; FINISH → `("", state)`; RESPOND on cycle 1 short-circuits with zero `act()` calls (MPP-2); `cycle_count >= max_cycles` after `observe()` → `MaxCyclesExceededError` (matches §6.2 flow — raise after Nth observe, no extra reason). `AdapterError` not caught in the loop (loop stays dumb).
- **Timing** (`timing.py`): success variant logs `elapsed, cycle_count, spawn_count` from the returned tuple; abort path catches bare `Exception`, logs elapsed-only variant, re-raises. Runtime imports are stdlib-only (`logging`, `time`, `typing`); `RunState` behind `TYPE_CHECKING` + `from __future__ import annotations` — no `axiom.interfaces` import at runtime.
- **Boundaries** (§11 import table): `loop.py` imports `axiom.interfaces` only — zero provider code. `cli.py` imports `axiom.agent` only (+ stdlib). `persona/__init__.py` stdlib-only, raises `FileNotFoundError`/`ValueError` on missing/empty `persona.txt` (file exists and is non-empty). `tests/fake_adapter.py` imports `axiom.interfaces` only.
- **Wiring**: `M1_ALLOWED_TOOLS = ["Bash", "WebSearch"]` in `agent.py:23` → `ClaudeAdapter(allowed_tools=...)` → used only in `act()` options; `reason()` uses `allowed_tools=[]`. `--debug` → `Agent(debug=True)` → stderr DEBUG handler on the `axiom` logger; child loggers `axiom.providers` / `axiom.observability` inherit. `__main__` guard present in cli.py. `pyproject.toml` deps (`claude-agent-sdk>=0.1.55`, `anyio>=4.0`), script entry, and pytest config all consistent.

---

## Bugs (will cause incorrect behavior)

None found. Every traced path returns/raises the type its caller expects, and the live-SDK call shape matches the installed v0.1.55 API.

---

## Gaps (missing implementation)

### [G1] `ResultMessage.is_error` is ignored — failed SDK runs masquerade as valid (possibly empty) output
- **File**: `src/axiom/providers/claude_adapter.py:82-84` (`_collect_query_result`)
- **Pass**: 7 (contract violations)
- **What**: The live `ResultMessage` (verified) carries `is_error: bool`, `subtype`, and `errors` fields. The adapter reads only `.result`. When the CLI run fails *without raising* (e.g. `subtype="error_during_execution"`, `is_error=True`, `result=None`), the adapter returns `""` and the run is treated as a **successful empty response**: in `reason()` it silently consumes the parse-retry (one wasted spawn) then emits a contentless `[FALLBACK_RESPOND] `; in `act()` an empty string is appended to history as if the instruction succeeded, and the loop keeps cycling with the model blind to the failure — worst case burning cycles toward `MaxCyclesExceededError` instead of surfacing the error.
- **Design ref**: §7.6 covers only the "empty text, no error flag" row; the `is_error=True` state is a real SDK contract state the design table doesn't enumerate. Not a design *violation*, but a live-path hole the offline FakeAdapter tests cannot catch.
- **Direction**: In `_collect_query_result`, when `message.is_error` is true, raise (or signal for `_run_query` to wrap as) `AdapterError` including `subtype`/`errors`, keeping the design's error-propagation path (`[Error: ...]` to the user) instead of a fake-success `""`.

---

## Warnings (potential issues)

### [W1] Non-SDK exceptions escape `_run_query` unwrapped and crash the CLI with a raw traceback
- **File**: `src/axiom/providers/claude_adapter.py:196-224`; `src/axiom/agent.py:73-79`
- **Pass**: 3 (error path trace)
- **What**: `_run_query` catches exactly the designed exception set. Anything else — `OSError`/`PermissionError` from subprocess spawn machinery outside the SDK's own wrapping, `RuntimeError`, or an `ExceptionGroup`/`BaseExceptionGroup` leaking from the SDK's internal anyio task groups (notably plausible on the **timeout/cancellation** path, where the cancel scope tears down the SDK's transport task group mid-flight) — propagates unwrapped. `timing.timed_run` still logs the abort (bare `Exception` — though an ExceptionGroup deriving from BaseException-only paths would even skip that), but `agent.run()` catches only `MaxCyclesExceededError` and `AdapterError`, so the user gets a Python traceback instead of `[Error: ...]`, violating the spirit of MPP-1 "the loop never hangs / terminates the turn cleanly".
- **Risk**: First live run on an unanticipated environment fault (or a 120s timeout racing SDK-internal cleanup). Mitigation direction: a final `except Exception` → `AdapterError` row in `_run_query` (or an outer catch in `agent.run`).

### [W2] Early `break` + timeout abandon the SDK async generator — subprocess cleanup is deferred to event-loop shutdown
- **File**: `src/axiom/providers/claude_adapter.py:80-84`
- **Pass**: 5 (resource management)
- **What**: On the first `ResultMessage` the code `break`s out of `async for` without `aclose()`-ing the generator; on timeout the cancel scope abandons it mid-yield. Cleanup then relies on `asyncio.run`'s `shutdown_asyncgens()` inside `anyio.run()` to fire the SDK's `finally`/disconnect. This works in the current one-shot-loop-per-call design, but it is implicit: if the SDK's cleanup during shutdown hits its own cancel scopes, "attempted to exit cancel scope in a different task" style errors can be printed to stderr, and a timed-out `claude-code` subprocess may outlive the query by the shutdown interval.
- **Risk**: Noisy stderr / lingering CLI processes precisely in the failure scenarios M1 wants clean signals from. An explicit `finally: await gen.aclose()` (or iterating to exhaustion — `ResultMessage` is terminal anyway) would make cleanup deterministic.

### [W3] `assert isinstance(intent, ActIntent)` is load-bearing control flow
- **File**: `src/axiom/loop.py:84`
- **Pass**: 2 (execution path trace)
- **What**: Under `python -O` the assert is stripped; a port implementation returning a non-Intent object would then fall through to `intent.instruction` and die with `AttributeError` instead of a clear contract error. With the two `ClaudeAdapter`/`FakeAdapter` implementations this is unreachable today.
- **Risk**: Only when a third adapter or optimized bytecode enters the picture. A plain `if not isinstance(...): raise TypeError(...)` is the assert-free form.

### [W4] `_configure_debug_logging()` adds a new handler per `Agent(debug=True)` construction
- **File**: `src/axiom/agent.py:28-37, 54-55`
- **Pass**: 8 (quality/patterns)
- **What**: No idempotence guard — constructing two debug Agents in one process duplicates every DEBUG line (double `[M1 Latency]` records would corrupt manual latency collection at sign-off if a test harness loops over `Agent(...)`). The one-shot CLI path is unaffected.
- **Risk**: Any in-process multi-turn or test-harness usage. Guard with `if not _axiom_logger.handlers:` or a module flag.

---

## Style (code quality, conventions)

### [S1] Imports from SDK-private module `claude_agent_sdk._errors`
- **File**: `src/axiom/providers/claude_adapter.py:21-27`
- **What**: All five exception classes are re-exported at the public top level (`from claude_agent_sdk import CLINotFoundError, ...` — verified against the installed package). Importing from the underscore module couples the adapter to SDK internals that can move without notice on a minor bump (`>=0.1.55` is an open range). Same applies (milder) to `claude_agent_sdk.types` at line 28 — `ClaudeAgentOptions`/`ResultMessage` are also public top-level exports.

### [S2] Frozen intent dataclasses expose `kind` as the first positional parameter
- **File**: `src/axiom/interfaces.py:31-46`
- **What**: `RespondIntent("hello")` silently sets `kind="hello"`, not `text`. All current call sites use keywords, but the footgun is one refactor away. `kind` as a `field(init=False, default=...)` — or keyword-only fields — would remove it. (Also: `kind` is never actually read; the loop dispatches on `isinstance`. Harmless duplication, worth a note.)

### [S3] CLI: explicit empty-string argument falls through to the interactive prompt
- **File**: `src/axiom/interface/cli.py:35-39`
- **What**: `if args.input:` is a truthiness test, so `axiom-cli ""` silently switches to stdin mode instead of hitting the "No input provided" exit. `if args.input is not None:` distinguishes "absent" from "empty". Cosmetic for M1.

### [S4] `response_text` unpacked but unused in `timed_run`
- **File**: `src/axiom/observability/timing.py:50`
- **What**: Only `run_state` is used in the log call; `response_text, run_state = result` leaves a dead variable (`_` convention).

---

## Contract-vs-design drift check

| Contract | Status |
|---|---|
| §4.1 wire format + parse rules (7 rules) | Match (incl. verbatim format-instruction block) |
| §5 RunState fields + mutate-and-return + count semantics | Match |
| §6.1/6.2 loop API, four exits, spawn-count ownership, MAX_CYCLES=10 | Match |
| §7.1 perceive prompt layout | Match (history section correctly omitted when empty — consistent with §7.1's "for each prior result") |
| §7.2 retry/fallback with first-raw fallback text + distinct log markers | Match |
| §7.3 `M1_ALLOWED_TOOLS` single source of truth in agent.py, `["Bash", "WebSearch"]` | Match |
| §7.5 async bridge, `PER_QUERY_TIMEOUT_SECS=120`, fail_after | Match (design's illustrative `await sdk_query` was correctly *not* copied — OQ-2 resolved to plain `async for`) |
| §7.6 error table (7 rows) | Match; see G1 for a state outside the table |
| §10 two log variants, DEBUG-only, stderr handler via constructor param | Match (agent.py error strings are slightly richer than the table's literal `"[Error: max cycles exceeded]"` — informative superset, not a drift) |
| §11 import boundary table | Match, all 8 rows |

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 1 | 4 | 4 |

**Verdict**: **PASS WITH WARNINGS**

The code is faithful to the design across every locked contract, and the live-SDK call shape is verified correct against the installed v0.1.55. No blocking defect for the live end-to-end test. G1 (`is_error` ignored) and W1 (unwrapped non-SDK exceptions) are the two findings most likely to surface *during* live testing — if the E2E run shows empty responses or raw tracebacks, they are the first suspects and should be fixed before M1 sign-off. W2 is worth watching on the timeout scenario specifically.
