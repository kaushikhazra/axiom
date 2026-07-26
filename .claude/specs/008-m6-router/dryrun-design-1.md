# Design Dry-Run Report #1

**Document**: `.claude/specs/008-m6-router/design.md`
**Reviewed**: 2026-07-26

---

## Critical Gaps (must fix before implementation)

### [C1] The entire policy engine (RT-4/RT-5/RT-6) is unreachable from the real CLI — `--provider` always defaults to `"claude"`, which the design treats as a forced override
- **Pass**: Pass 10 (Behavioral DoD Challenge) — traced from the real `axiom-cli` entry point through to `Router.select_worker()`.
- **What**: `src/axiom/interface/cli.py:29-32` defines `--provider` with `choices=["claude", "local"]` and **`default="claude"`** — confirmed by reading the actual argparse call, not assumed. `Agent.__init__`'s own `provider: str = "claude"` parameter has the identical default (read directly, unchanged by this design). §6's wiring derives `forced_provider = provider if provider in ("claude", "local") else None` — but since `provider` is *always* either `"claude"` or `"local"` when it reaches `Agent.__init__` (there is no third value, no `None`, reachable from the real CLI or from `Agent`'s own constructor default), **`forced_provider` is never `None` in practice**. `Router.select_worker()`'s very first check is `if self._forced_provider is not None: ... bypass ALL policy evaluation ...` (§3) — so that branch fires on *every* real invocation, including the default "no flags passed" case, which today's CLI treats identically to `--provider claude` explicitly.
- **Risk**: RT-4 (privacy gate), RT-5 (cost/volume default), and RT-6 (capability override) — the actual substance `requirement.md`'s Purpose section frames as *the* point of this milestone ("the real policy engine `architecture.md` describes") — can never execute through `axiom-cli` as designed. Every one of RT-4/5/6's behavioral ACs would need `--provider` to be *unset* in a way that means "no preference, let policy decide," but no such CLI invocation exists. This is the exact unreachability failure class Pass 10 exists to catch: `dryrun-code` and unit tests could pass (a test can construct `Router(forced_provider=None)` directly), while the feature ships permanently dead from the real interface — worse, RT-1's own behavioral AC ("Running `axiom-cli` with no provider-forcing flags at all completes a normal turn successfully") reads as if it's testing the policy path, but it's actually testing the *override* path by accident, since "no flags" and "`--provider claude`" are indistinguishable today.
- **Fix**: Two coordinated changes, both needed:
  1. `cli.py`: remove `default="claude"` from the `--provider` argument (leave it truly optional — argparse produces `None` when the flag is omitted and no `default` is set).
  2. `agent.py`: change `Agent.__init__`'s signature to `provider: str | None = None` (from `provider: str = "claude"`). Then `forced_provider = provider` directly (no need for the `in ("claude", "local")` guard, since `choices=` on the CLI side already constrains the two non-`None` values).
  This makes "no `--provider` flag" and "`--provider claude`" genuinely distinct again — matching RT-8's own AC ("preserves the pre-M6 CLI contract exactly... for existing **explicit**-provider usage"), which only promises unchanged behavior when a provider *is* explicitly named, implicitly leaving room for the no-flag case to mean "policy decides," which is what this fix restores. Re-verify RT-1's own behavioral AC afterward — it needs to demonstrate the *policy* path completing successfully, not the override path.

---

### [C2] Fallback success is misreported in the observability trace — the `act` span always shows the pre-fallback provider/control_level, even when the fallback provider actually produced the result
- **Pass**: Pass 2 (Data Flow Trace) — traced `selection`'s value from computation through to the `_maybe_record()` call it feeds, across both the success and fallback-retry paths.
- **What**: §5's ACT branch code:
  ```python
  selection = self._router.select_worker(intent.instruction)
  with _maybe_record(
      "act", run_id, provider_kind,
      extra_attributes={
          "axiom.control_level": selection.control_level,
          "axiom.router.provider": selection.provider_name,
      },
  ):
      ...
      try:
          result = await asyncio.to_thread(selection.adapter.act, intent.instruction)
      except AdapterError:
          ...
          fallback = self._router.select_fallback_worker(selection.provider_name)
          ...
          result = await asyncio.to_thread(fallback.adapter.act, intent.instruction)
  ```
  `extra_attributes` is computed **once**, from the pre-fallback `selection`, when the `with` block is entered — before the `try` even runs. If the primary provider fails and the fallback succeeds, `result` came from `fallback.adapter`, but the span's `axiom.control_level`/`axiom.router.provider` attributes still describe the *original, failed* `selection` — never updated to reflect what `fallback` actually was.
- **Risk**: Directly violates RT-7's own AC: *"`--observe`'s trace for a live `axiom-cli` run shows `axiom.control_level` populated correctly (`KIND_B` for a Claude-routed span, `KIND_A` for a local-routed span)."* On any run that exercises RT-9's fallback path, the trace would misattribute which provider actually executed — exactly the kind of observability lie this project's own M2 milestone exists to prevent (`architecture.md`: Observability's whole purpose is "glass-box visibility"). A future debugging session trusting this trace to diagnose a fallback-related issue would be looking at the wrong provider's data.
- **Fix**: Set the span attributes dynamically, inside the block, after the actual dispatch succeeds — not via `_maybe_record()`'s single `extra_attributes` param computed at entry. Either (a) have `_maybe_record()` yield the underlying span (mirroring `record_phase()`'s own `Generator[Span, None, None]` yield, currently discarded by `_maybe_record()`'s `yield` with no value) so the loop can call `span.set_attribute(...)` after knowing the final `selection`, or (b) compute a second, corrected `extra_attributes` dict after the fallback branch and pass it — but (a) is more consistent with `record_phase()`'s existing yielded-`Span` pattern (already built, just not threaded through `_maybe_record()`'s wrapper today).

---

### [C3] `spawn_count` undercounts on the fallback path — RT-9's second dispatch isn't counted, contradicting the field's own documented contract
- **Pass**: Pass 2 (Data Flow Trace), same trace as C2.
- **What**: §5's code increments `run_state.spawn_count += 1` exactly once, before the `try` block, regardless of whether a fallback dispatch also occurs. `RunState.spawn_count`'s own docstring (`interfaces.py`, unchanged by this design): *"loop-dispatched query() calls (adapter-internal retries excluded)."* RT-9's fallback is explicitly a **loop-level** retry (dispatched by `loop.py`'s own `except AdapterError` branch calling a *different* adapter via `router.select_fallback_worker()`) — not an adapter-internal retry, so by the field's own definition it should count as a second dispatch.
- **Risk**: This is the same finding class M5's `dryrun-code-2` W1 already caught and fixed once in this codebase (`spawn_count` overcounting a non-dispatch there; undercounting a real dispatch here — same root issue, contract-vs-implementation drift). Anything trusting `spawn_count` as "how many provider calls did this run actually make" (cost estimation, rate-limit budgeting) would be wrong by one on every successful fallback.
- **Fix**: Increment `run_state.spawn_count` a second time in the fallback branch, immediately before (or after) the `fallback.adapter.act(...)` call — mirroring how the primary dispatch's increment sits immediately before its own call.

---

## Warnings (should fix, may cause issues)

### [W1] `RoutingDecision.CONDUCTOR_DEFAULT`'s degrade-gracefully fallthrough in `select_worker()` is unreachable via `agent.py`'s actual wiring, making its "Error Handling" table row untestable through the real composition root
- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: The Error Handling table's fourth row describes `RoutingDecision.CONDUCTOR_DEFAULT` resolving against a provider missing from `adapter_factories`, noting it's "only reachable in a hand-constructed single-adapter `Router`, not via `agent.py`'s wiring." That's self-consistent, but it means this path can only be unit-tested directly against `Router`, never demonstrated through `axiom-cli` — worth stating explicitly in `task.md`'s test-item scope (so the implementer doesn't go looking for a CLI-level repro that can't exist) rather than leaving it implicit.
- **Risk**: Low — purely a documentation-completeness nit, not a functional gap. Flagged so the corresponding `test_router.py` item doesn't get miscategorized as needing a live-CLI demonstration it structurally cannot have.
- **Suggestion**: Add one sentence to `task.md`'s `test_router.py` item (or `design.md`'s own Error Handling row) noting this specific path is unit-test-only by construction.

---

## Observations (worth discussing)

### [O1] `RoutePolicy()`'s all-empty default means C1's fix alone doesn't yet give users an actual routing *decision* to observe — only unlocks the mechanism
- Once C1 is fixed (policy path reachable), the *default* `RoutePolicy()` still has empty `privacy_patterns`/`capability_patterns` (§6: `policy=RoutePolicy()`), so every instruction falls through to RT-5's bulk-default rule (`len(instruction) <= 200` → local) or the Conductor-default fallthrough for longer instructions. That's coherent and matches `requirement.md`'s Out of Scope framing (`--router-config` deferred) — just noting that RT-4/RT-6's behavioral ACs (which need a *configured* pattern to demonstrate) will need their live-CLI verification step to construct a non-default `RoutePolicy` directly (not purely through CLI flags, since none exist yet for policy configuration) — consistent with `requirement.md`'s own Configuration Summary already anticipating this ("A `--router-config <path>` CLI flag... is left to design.md to decide as trivial-or-deferred").

---

### Pass 9: Design-to-Task-to-AC Traceability

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| `src/axiom/router/policy.py` — new | task.md item 1 | RT-4, RT-5, RT-6 |
| `src/axiom/router/router.py` — new | task.md item 2 | RT-1, RT-2, RT-3, RT-4, RT-8, RT-9 |
| `src/axiom/providers/claude_adapter.py` — control_level | task.md item 3 | RT-7 |
| `src/axiom/providers/local_adapter.py` — control_level | task.md item 4 | RT-7 |
| `src/axiom/loop.py` — router wiring, fallback, extra_attributes | task.md item 5 | RT-1, RT-3, RT-7, RT-9 |
| `src/axiom/agent.py` — Router construction | task.md item 6 | RT-1, RT-2, RT-8 |
| `tests/test_router_policy.py` — new | task.md item 7 | RT-4, RT-5, RT-6 |
| `tests/test_router.py` — new | task.md item 8 | RT-1, RT-2, RT-3, RT-4, RT-8, RT-9 |
| `tests/test_contracts.py` — extended | task.md item 9 | RT-3, RT-7, RT-9 |
| Existing `PraoLoop(...)` call sites — updated | task.md item 10 | RT-1 |
| `tests/fake_adapter.py` — FakeRouter | task.md item 11 | RT-1, RT-2, RT-3, RT-9 |

**Result**: All 11 file-level prescriptions traced to tasks and ACs. No traceability gaps. (C1/C2/C3 above are correctness gaps within already-traced work, not untraced prescriptions.)

---

### Pass 10: Behavioral DoD Challenge (continued — per-story summary)

RT-2, RT-7, RT-8 each have a Purpose and a behavioral AC that is genuinely reachable and would exercise real behavior once C1 is fixed. RT-1, RT-3, RT-4, RT-5, RT-6, RT-9's behavioral ACs are all correctly *written* (interface-exercised, not structural-proxy) but are currently **unreachable in practice** per C1 — the single root cause behind six stories' worth of DoD risk, reported once as C1 rather than six times.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 3        | 1        | 1             |

**Verdict**: FAIL — needs revision
