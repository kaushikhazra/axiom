# Code Dry-Run Report #1

**Scope**: `src/axiom/router/`, `src/axiom/loop.py`, `src/axiom/agent.py`, `src/axiom/interface/cli.py`, `src/axiom/providers/{claude_adapter,local_adapter}.py` (control_level additions), plus the M6 test suite
**Design**: `.claude/specs/008-m6-router/design.md` (dryrun-design-3, PASS)
**Reviewed**: 2026-07-26

---

## Bugs (will cause incorrect behavior)

### [B1] `RouterError` is never caught anywhere in the call chain — would crash the CLI with a raw traceback instead of the established clean `[Error: ...]` pattern
- **File**: `src/axiom/agent.py:253-269` (`Agent.run()`'s `try/except`), `src/axiom/interface/cli.py` (no top-level exception handling at all in `main()`)
- **Pass**: Pass 3 (Error Path Trace) — traced every raiser of `RouterError` (`src/axiom/router/router.py:78`, `:119`) up through `loop.py`'s ACT branch, `Agent.run()`, and `cli.py::main()`.
- **What**: `RouterError` (`router.py:32`) derives directly from `Exception` — it is **not** a subclass of `AdapterError` (`interfaces.py:140`, also a direct `Exception` subclass; sibling, not parent/child). `Agent.run()`'s exception handling (`agent.py:266-269`) catches exactly two types: `MaxCyclesExceededError` and `AdapterError`. `RouterError` matches neither. `cli.py::main()` (confirmed by reading the full file) has no `try`/`except` of its own at all. A `RouterError` raised anywhere inside the loop — `select_worker()` (`router.py:119`, the RT-4 privacy-gate-with-no-adapter case) or `_get()` (`router.py:78`, an unconfigured provider name) — propagates all the way to the top of the process uncaught, crashing `axiom-cli` with a raw Python traceback.
- **Impact**: This directly contradicts RT-4's own acceptance criterion (`requirement.md`): *"Router.select_worker() raises a clear, typed error... rather than silently substituted."* The AC's intent is a **clear, user-facing** error, not an unhandled crash — every other failure mode in this codebase (adapter failures, cycle-limit breaches) surfaces as a clean `"[Error: ...]"` string; a `RouterError` alone breaks that established, consistent UX pattern.
  **Reachability caveat, stated honestly**: neither current `RouterError` trigger is reachable through the *live* CLI today — `agent.py`'s wiring (`agent.py:171-176`) always configures **both** `"claude"` and `"local"` factories, so the "unconfigured provider" path never fires from real usage, and there is no way yet to set `RoutePolicy.privacy_patterns` from the CLI (`--router-config` is explicitly deferred per `requirement.md`'s Out of Scope) to trigger the privacy-gate path either. So this is a **latent** gap, not a live-observable one, per Pass 10's reachability standard — but it is a genuine correctness gap that will bite the moment a future milestone wires up `--router-config` or a caller constructs a single-provider `Router` directly (already possible via the Python API today, just not via the shipped CLI).
- **Fix**: Add `RouterError` to `Agent.run()`'s exception handling, mirroring the existing `AdapterError` branch:
  ```python
  from axiom.router.router import RouterError  # add to agent.py's imports
  ...
  except RouterError as e:
      return f"[Error: {e}]"
  ```
  Cheap, consistent with the existing pattern, and closes the gap before it becomes live-reachable in a later milestone.

---

## Gaps (missing implementation)

None — all 9 RT stories are implemented per the design, and the design itself passed dryrun-design-3 clean.

---

## Warnings (potential issues)

### [W1] `Agent.__init__`'s `provider` parameter lost its input validation — an invalid string now surfaces as an uncaught `RouterError` (see B1) deep inside `Router` construction, instead of an immediate, clear `ValueError`
- **File**: `src/axiom/agent.py:102-178`
- **Pass**: Pass 4 (Input Validation & Boundaries) — compared against the pre-M6 code (git history), which had `else: raise ValueError(f"unknown provider: {provider!r}")` as the final branch of the old `if/elif` block.
- **What**: That validation branch was removed along with the `if/elif` it belonged to (correctly, per RT-1's AC — the branching itself was the target of removal) — but nothing replaced it. `forced_provider=provider` is passed straight into `Router` unchecked. An invalid string (e.g. `Agent(provider="bogus")`, a plausible typo in direct Python API usage) now fails deep inside `select_conductor()` → `_get()` → `RouterError`, which (per B1) isn't even caught.
- **Risk**: Low in practice — the real CLI's `argparse choices=["claude", "local"]` (`cli.py`) rejects an invalid value before it ever reaches `Agent`, so this is a direct-Python-API-only concern, not a live CLI one. But it's a real regression in defensive validation for library callers, and the failure mode is strictly worse than before (was: immediate clear `ValueError`; now: a deferred, uncaught `RouterError` per B1).
- **Suggestion**: Either restore an explicit validation line at the top of `Agent.__init__` (`if provider is not None and provider not in ("claude", "local"): raise ValueError(...)`), or accept B1's fix as sufficient (at least the failure becomes a clean `[Error: ...]` instead of a crash) and treat the earlier-vs-later validation timing as a minor style preference, not a blocking issue.

### [W2] `Router.select_worker()`'s degrade-gracefully fallthrough raises `StopIteration` if `adapter_factories` is empty
- **File**: `src/axiom/router/router.py:127`
- **Pass**: Pass 4 (Input Validation & Boundaries)
- **What**: `provider_name = next(iter(self._factories))` — if `self._factories` is an empty dict, `next()` on an exhausted iterator raises `StopIteration` (unguarded, no default value passed to `next()`), not the module's own `RouterError`. This is inconsistent with every other Router failure mode, which all raise `RouterError`.
- **Risk**: Currently unreachable via `agent.py`'s real wiring (always provides both factories) — same reachability caveat as B1. A future caller constructing a `Router` with zero factories (a plausible test-authoring mistake, or a future single-adapter deployment mode) would get a confusing `StopIteration` rather than a clear `RouterError` message.
- **Suggestion**: `next(iter(self._factories), None)` with an explicit `if provider_name is None: raise RouterError("no adapter factories configured")` — costs one line, keeps all Router failure modes consistently typed.

### [W3] Default `RoutePolicy()` means fresh, no-flags `axiom-cli` usage now silently attempts the local provider first for typical short instructions — up to a 60-second stall for users without Ollama running, before RT-9's fallback correctly recovers
- **File**: `src/axiom/agent.py:169-178` (default `RoutePolicy()` wiring), `src/axiom/providers/local_adapter.py:37` (`PER_QUERY_TIMEOUT_SECS: int = 60`)
- **Pass**: Pass 10 (Value-Path Trace) — traced the real consequence of RT-5's default-to-local policy for the most common real-world starting state (no Ollama installed/running).
- **What**: This is **not a code deviation** — `requirement.md` RT-5 explicitly specifies exactly this behavior ("short, simple ACT instructions... default toward the local provider... when no privacy or capability signal overrides it"), and `agent.py`'s default `RoutePolicy()` (empty patterns, `bulk_threshold_chars=200`) is precisely what the design calls for. Confirmed live: a fresh `axiom-cli` invocation with **no flags at all** — previously 100% Claude, fast, no local dependency — now routes any ACT dispatch with an instruction ≤200 chars (the large majority of real instructions) to `LocalAdapter` first. Confirmed `LocalAdapter.act()`'s failure path (`local_adapter.py:485`, `raise AdapterError(msg)`) is correctly bounded by `PER_QUERY_TIMEOUT_SECS=60` and does correctly trigger RT-9's fallback to Claude on failure — the system does **not** hang forever or crash; it recovers.
- **Risk**: A real, material UX cost for the most common "brand new user, no Ollama installed" scenario: their very first ACT-requiring request now silently stalls for up to 60 seconds (with no user-visible indication anything unusual is happening — the `[ROUTER_FALLBACK]` log line is DEBUG-level, invisible without `--debug`) before falling back and succeeding via Claude. Pre-M6, the identical no-flags invocation was always fast. This is exactly the correct, spec'd behavior once a local provider IS available — the cost only bites the "no local provider configured at all" case, which is plausibly the *default* state for most users trying Axiom for the first time.
- **Suggestion**: Not a fix — a product observation worth explicit sign-off, since it's a real trade-off (RT-5's stated benefit: "subscription/API capacity is reserved for work that actually needs it" vs. this stall cost) that may not have been fully weighed when `bulk_threshold_chars=200`'s default was chosen. Options for a future iteration (not blocking this milestone, since the current behavior is exactly what was specified): shorten `LocalAdapter`'s connection-probe/timeout specifically for the Router's speculative first attempt, or make the fallback's occurrence visible at INFO level (not just DEBUG) so a user isn't left wondering why their first request was slow.

---

## Style (code quality, conventions)

None worth flagging — the new code is consistent with the project's established style (docstring conventions, `from __future__ import annotations`, logger naming pattern matching `axiom.router`/`axiom.skills`/`axiom.tools`).

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 1    | 0    | 3        | 0     |

**Verdict**: FAIL — has bugs
