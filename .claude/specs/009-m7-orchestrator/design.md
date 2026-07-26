# M7 · Orchestrator — Design

**Spec:** `009-m7-orchestrator`
**Milestone:** M7 — "Orchestrator. Multi-provider consortium — the 'committee.'"
**Status:** DRAFT
**Inputs:** `requirement.md` (this spec, co-designed with velasari over crosstalk); `001-agent-core/architecture.md` ("loop IS the orchestrator" constraint, Worker row's "multiple Workers may run per Act phase" framing); `006-m4-tools/design.md` D8-D9 (`ToolResult`/`WorkerSelection`-style "never raise, encode failure" pattern this design reuses); `008-m6-router/design.md` (the `Router`/`RoutePolicy` this milestone extends, not replaces); installed source read directly on `feature/m7-orchestrator` (branched from `master` post-M6 merge, `0710667`).

---

## 1. Overview

M7 adds exactly one new public method to `Router` (`select_committee()`) and one new branch to `loop.py`'s ACT dispatch — everything else (the `select_worker()` single-dispatch path, `RoutePolicy`'s existing fields, `WorkerSelection`, the wire-format `Intent` types) is untouched. This is deliberate, not an oversight: `requirement.md`'s OR-1 AC requires M6's existing behavior to be byte-for-byte unchanged when committee mode isn't triggered, and `architecture.md`'s "loop IS the orchestrator" constraint means synthesis must ride the loop's *existing* gather-then-reason seam, not a new one.

**The one precedence subtlety that needs its own decision (not derivable from M6's `evaluate()` alone):** `evaluate()` (M6, `policy.py`) has a `tuple[str, str]` return shape (one provider name, one reason) — it cannot express "return a list." Rather than reshape `evaluate()` (which would touch every M6 caller and test), committee-triggering gets its own small function, `should_form_committee()`, that independently re-checks privacy first (reusing `_matches_any`, not duplicating `evaluate()`'s full chain) before deciding committee applies — see §2.

---

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | `Router.select_committee(instruction) -> list[WorkerSelection] \| None` is a **new, separate method** — `select_worker()`'s signature, return type, and internal logic are completely unmodified. | OR-2's AC requires M6's existing single-dispatch contract untouched. A shared/overloaded method returning "sometimes one, sometimes many" would force every M6 caller (`loop.py`'s existing single-dispatch branch, all of M6's `select_worker()` tests) to handle a new union return type for no benefit. |
| D2 | Committee triggering is decided by a new `should_form_committee(instruction, policy, forced_provider) -> bool` function (`policy.py`), which re-checks `forced_provider` and privacy **before** checking `forced_provider == "committee"` or `consortium_patterns` — not by extending `evaluate()`. | `evaluate()`'s `tuple[str, str]` shape can't express a list result (Overview). Re-implementing privacy-first precedence in a small, independently-testable function is simpler and safer than reshaping a function nine other call sites already depend on. |
| D3 | `should_form_committee()`'s full precedence, in order: (1) `forced_provider not in (None, "committee")` → `False` (a single-provider override, RT-8, always wins — never re-evaluated for consortium eligibility); (2) privacy match → `False` (OR-5: absolute, even over an explicit `committee` override); (3) `forced_provider == "committee"` → `True`; (4) `consortium_patterns` match → `True`; (5) else `False`. | Directly encodes `requirement.md`'s precedence table (privacy > consortium > capability > bulk-default). Step 1 is the subtle one: without it, a user who forced `--provider claude` (wanting exactly one specific provider) could have that overridden by an incidental `consortium_patterns` match — RT-8's existing override guarantee ("this bypasses ALL policy evaluation") would silently not hold for committee-triggering specifically. Step 1 closes that gap before it can exist. |
| D4 | `max_committee_size` on `RoutePolicy` is typed `int \| None`, defaulting to `None` — `Router.select_committee()` resolves the effective cap as `min(policy.max_committee_size or len(self._factories), len(self._factories))` at call time. | `RoutePolicy` is a plain dataclass constructed independently of any `Router` (M6 precedent — `RoutePolicy()` has no knowledge of how many adapters a `Router` will later be given); it cannot know `len(adapter_factories)` in advance, so `None` defers that resolution to `select_committee()` call time (requirement.md OR-8, updated dryrun-design-1 W1 to match this mechanism exactly). |
| D5 | Committee membership is capped by taking adapters in `adapter_factories`' dict insertion order (not sorted, not random) — deterministic given the same `Router` construction. | OR-8's AC requires "deterministic... not left to iteration-order chance" — Python dicts preserve insertion order (3.7+, language guarantee, already relied on by M6's own `select_worker()` degrade-gracefully fallthrough, `router.py` D-notes). Explicitly documenting this (not just relying on it silently) satisfies the AC's own wording. |
| D6 | The loop's committee-dispatch branch gathers all members **sequentially** (`for member in committee: await asyncio.to_thread(member.adapter.act, ...)`), not concurrently via `asyncio.gather`. | `requirement.md`'s Out of Scope explicitly leaves this choice to `design.md`. Sequential is chosen for this milestone: M6's existing single-dispatch path is already sequential-per-cycle, `asyncio.to_thread` already parallelizes at the OS-thread level relative to the event loop (each call doesn't block other async work), and concurrent dispatch would need per-member exception isolation (`asyncio.gather(..., return_exceptions=True)`) plus careful ordering-independent result attribution — genuine added complexity for a 2-member committee today. Revisit if/when committee sizes grow enough for latency to matter (Future Work). |
| D7 | A failed committee member's contribution is recorded as `f"[{provider_name}]: FAILED — {exc}"` in the same combined result string successful members use (`f"[{provider_name}]: {result}"`) — one `ObservePort.observe()` call, one combined string, not per-member `observe()` calls. | OR-4's AC: "one combined, provider-attributed string... not N separate observe() calls." Matches M6's `AdapterError` message pattern (`str(exc)` is already human-readable, e.g. `local_adapter.py`'s `f"CodeAgent execution error: {e}"`). |
| D8 | If **every** committee member fails, `AdapterError` is raised directly from the committee-dispatch branch (not silently returning an all-failure combined string to Observe/Reason). | OR-6's AC: "a committee where nobody answered is not silently treated as success." Matches M6's existing single-dispatch failure semantics — an all-fail committee is exactly as fatal as a single-provider dispatch failure, propagating identically (`Agent.run()`'s existing `except AdapterError` branch, unchanged). |
| D9 | `run_state.spawn_count` increments by `len(committee)` (one per member actually dispatched), not by 1. | Matches `spawn_count`'s own documented contract ("loop-dispatched query() calls") and the precedent M6's own dryrun-design-1 C3 / dryrun-code-1 fixes already established for this exact field — undercounting real provider dispatches was a confirmed bug class in M6; committee mode must not reintroduce it. |
| D10 | The committee-dispatch act span sets `axiom.router.committee_size` and `axiom.router.providers` (comma-joined provider names) — **not** `axiom.control_level`/`axiom.router.provider` (M6's single-value attributes, which don't have a coherent meaning when the dispatch spans multiple, possibly mixed-`control_level`, providers). | Avoids setting a misleading single value (e.g. picking one member's `control_level` arbitrarily) on an attribute M6 established as meaning "the one provider that ran this act" — committee mode genuinely has no single answer to that question, so it gets its own, honestly-named attributes instead. |
| D11 | `select_fallback_worker()` is never called from the committee-dispatch branch — OR-7's own requirement, restated here as an implementation guarantee: the committee branch's `except AdapterError` handler only appends a failure note (D7), it never calls `Router.select_fallback_worker()`. | Direct implementation of OR-7's AC. Stated explicitly in the Decisions Log (not just implied by "the code doesn't call it") so a future reader can see this was a deliberate choice, not an oversight, if they're ever tempted to "helpfully" wire fallback into committee mode. |

---

## 2. `RoutePolicy` and `should_form_committee()` extensions

`src/axiom/router/policy.py` — additive to the existing M6 module.

```python
@dataclass(frozen=True)
class RoutePolicy:
    privacy_patterns: list[str] = field(default_factory=list)      # RT-4 (M6, unchanged)
    bulk_threshold_chars: int = 200                                 # RT-5 (M6, unchanged)
    capability_patterns: list[str] = field(default_factory=list)   # RT-6 (M6, unchanged)
    consortium_patterns: list[str] = field(default_factory=list)   # OR-2 (M7)
    max_committee_size: int | None = None                          # OR-8 (M7) -- None = "use however many adapters are configured" (D4)


class RoutingDecision:
    PRIVACY = "privacy"
    CAPABILITY = "capability"
    BULK_DEFAULT = "bulk_default"
    CONDUCTOR_DEFAULT = "conductor_default"
    CONSORTIUM = "consortium"  # M7 -- not returned by evaluate() (unchanged, D1/D2), used by
                                # Router.select_committee() for its own logging/tracing only.


def should_form_committee(
    instruction: str, policy: RoutePolicy, forced_provider: str | None
) -> bool:
    """M7 (D2/D3): decides whether this ACT dispatch is committee-mode,
    entirely independent of evaluate() (which stays single-provider-only,
    unmodified). Precedence: single-provider override > privacy > explicit
    committee override > consortium_patterns match.
    """
    if forced_provider is not None and forced_provider != "committee":
        return False  # D3 step 1: RT-8's single-provider override always wins
    if _matches_any(instruction, policy.privacy_patterns):
        return False  # D3 step 2 / OR-5: privacy is absolute, even over a committee override
    if forced_provider == "committee":
        return True  # D3 step 3
    return _matches_any(instruction, policy.consortium_patterns)  # D3 step 4
```

`evaluate()` itself (M6) is **not modified** — no new parameter, no new return value, no new branch. Confirmed by re-reading it: privacy/capability/bulk/conductor-fallthrough, exactly as M6 left it.

---

## 3. `Router.select_committee()`

`src/axiom/router/router.py` — additive method on the existing `Router` class.

```python
def select_committee(self, instruction: str) -> list[WorkerSelection] | None:
    """M7 (RT-2/OR-2): returns None when committee mode doesn't apply for
    this instruction -- caller falls through to the existing select_worker()
    single-dispatch path (M6, unmodified) in that case. When it applies,
    returns one WorkerSelection per configured adapter, capped by
    max_committee_size (D4), in adapter_factories' insertion order (D5).
    """
    if not should_form_committee(instruction, self._policy, self._forced_provider):
        return None

    cap = self._policy.max_committee_size
    effective_cap = min(cap, len(self._factories)) if cap is not None else len(self._factories)

    selections: list[WorkerSelection] = []
    for provider_name in list(self._factories)[:effective_cap]:
        adapter = self._get(provider_name)
        selections.append(
            WorkerSelection(
                adapter=adapter,
                provider_name=provider_name,
                control_level=adapter.control_level,
                fallback_allowed=False,  # D11/OR-7: committee members are never fallback-eligible
            )
        )
    return selections
```

`WorkerSelection` itself (M6) is reused as-is — no new dataclass. `fallback_allowed=False` on every committee member's `WorkerSelection` is a belt-and-suspenders signal (the loop's committee branch never reads it, since D11 means fallback logic is never invoked from that branch at all — but setting it correctly keeps the value honest for any future code that might inspect a `WorkerSelection` outside the branch that produced it).

**Fully-specified edge case (dryrun-design-1 W2):** if `should_form_committee()` returns `True` but zero adapters are configured (`self._factories` empty — never true in the real `agent.py` composition root, which always configures `{"claude": ..., "local": ...}`, but reachable via a hand-constructed `Router` in a test), `select_committee()` returns `[]`, not `None`. §4's `if committee is not None:` check treats `[]` as a real, empty committee, dispatches to zero members, and — since `any_succeeded` stays `False` — raises `AdapterError("all 0 committee members failed")` via the same D8 path a genuine all-member failure takes. This is deterministic, defined behavior (an empty committee is a degenerate case of "everybody failed" — there's nobody to succeed), not an unhandled gap; `test_router.py`'s `select_committee()` tests (Files Changed) cover it explicitly.

---

## 4. Loop wiring

`src/axiom/loop.py` — the ACT branch gains a committee check **before** the existing `select_worker()` call, as an `if/else`:

```python
# intent == ACT — execute, observe, then loop back to perceive
if not isinstance(intent, ActIntent):
    raise TypeError(...)

committee = self._router.select_committee(intent.instruction)  # M7: None if not committee mode

if committee is not None:
    # M7: committee dispatch -- OR-3/OR-4/OR-6/OR-7.
    with _maybe_record("act", run_id, provider_kind) as act_span:
        if act_span is not None:
            act_span.set_attribute("axiom.router.committee_size", len(committee))
            act_span.set_attribute(
                "axiom.router.providers", ",".join(m.provider_name for m in committee)
            )

        run_state.spawn_count += len(committee)  # D9: one real dispatch per member
        parts: list[str] = []
        any_succeeded = False
        for member in committee:
            try:
                member_result = await asyncio.to_thread(
                    member.adapter.act, intent.instruction
                )
                parts.append(f"[{member.provider_name}]: {member_result}")
                any_succeeded = True
            except AdapterError as exc:
                # D7/OR-6: note the failure, keep going -- no fallback (D11/OR-7).
                parts.append(f"[{member.provider_name}]: FAILED — {exc}")

        if not any_succeeded:
            # D8/OR-6: a committee where nobody answered is not success.
            raise AdapterError(
                f"all {len(committee)} committee members failed"
            )
        result = "\n".join(parts)

    with _maybe_record("observe", run_id, provider_kind):
        run_state = await asyncio.to_thread(self._observe.observe, result, run_state)

else:
    # M6's existing single-dispatch path -- completely unmodified.
    selection = self._router.select_worker(intent.instruction)
    with _maybe_record("act", run_id, provider_kind) as act_span:
        ...  # (unchanged from M6 -- see 008-m6-router/design.md §5)

if run_state.cycle_count >= self._max_cycles:
    raise MaxCyclesExceededError(
        f"max cycles ({self._max_cycles}) exceeded without terminal intent"
    )
```

**Synthesis mechanism (OR-4), traced explicitly:** `result` (the combined, provider-attributed string) is passed to `self._observe.observe(result, run_state)` — the **exact same** `ObservePort.observe()` call the single-dispatch path already uses (`PraoAdapterBase.observe()`, M1, unchanged: appends `result` to `run_state.history`, increments `cycle_count`). The next cycle's `perceive()` call (also unchanged, M1) renders `run_state.history` under `[TOOL EXECUTION RESULTS — read these carefully]` exactly as it already does for a single ACT result — now containing multiple `[provider]: ...` lines instead of one. The next Reason cycle sees this richer text and synthesizes as part of its own normal reasoning. **No code changes to `perceive()`, `observe()`, or the wire-format `Intent` types are needed for synthesis to work** — this is the concrete proof that OR-4's "no new intent or phase" requirement holds.

---

## 5. CLI / composition root

`src/axiom/interface/cli.py`:
```python
parser.add_argument(
    "--provider",
    choices=["claude", "local", "committee"],  # "committee" added (OR-1)
    default=None,
    help=(
        "Provider adapter: 'claude' (cloud), 'local' (Ollama), or 'committee' "
        "(dispatch every ACT to all configured providers, M7). Forces that mode "
        "for the whole session, bypassing the Router's policy engine. Omit to "
        "let the Router decide (M6 default)."
    ),
)
```

`agent.py` — **two changes needed** (found live in dryrun-design-1 C1; corrected here):

1. `Agent.__init__`'s existing input-validation guard (`dryrun-code-1` W1, M6) currently reads:
   ```python
   if provider is not None and provider not in ("claude", "local"):
       raise ValueError(f"unknown provider: {provider!r}")
   ```
   This must be extended to accept `"committee"`:
   ```python
   if provider is not None and provider not in ("claude", "local", "committee"):
       raise ValueError(f"unknown provider: {provider!r}")
   ```
   Without this, `Agent(provider="committee")` raises `ValueError` immediately — `Router` is never even constructed, and `--provider committee` is unreachable from the CLI (the same failure class OR-1's own Purpose section names as precedent to avoid).

2. `provider` still flows straight into `Router(forced_provider=provider)` unmodified — `Router` itself already treats `forced_provider` as an opaque string. The only new *interpretation* of that string is `should_form_committee()`'s `forced_provider == "committee"` check (§2) and `select_conductor()`'s guard (§3, below) — no other composition-root wiring changes.

`router.py`'s `select_conductor()` — **guarded, per Error Handling below.** Its existing line `provider_name = self._forced_provider or "claude"` would, if `forced_provider == "committee"`, set the *Conductor* to a nonexistent `"committee"` "provider" and raise `RouterError` from `_get()` (uncaught by `Agent.__init__`, which only wraps `Router` construction, not `select_conductor()`'s call — and `Agent.run()`'s `except RouterError` handler never gets a chance to run since construction itself fails). Fixed by treating `forced_provider == "committee"` the same as `None` for Conductor-selection purposes specifically:
```python
def select_conductor(self) -> RoutableAdapter:
    conductor_override = (
        self._forced_provider if self._forced_provider != "committee" else None
    )
    provider_name = conductor_override or "claude"  # RT-2: capability-preferred default
    self._conductor_provider = provider_name
    return self._get(provider_name)
```

---

## Error Handling

| Failure | Behavior |
|---|---|
| `--provider committee` passed — what does `select_conductor()` do? | Does **not** blindly use `"committee"` as the Conductor's provider name — `select_conductor()`'s guard (§5) resolves the Conductor to the capability-preferred default (`"claude"`) when `forced_provider == "committee"`, matching M6's existing "no override" default exactly. Committee mode only ever affects *Worker* selection (OR-1's own framing: "the Conductor's wire-format contract... stays provider-agnostic") — the Conductor itself is never plural. |
| `--provider committee` passed — does `Agent.__init__` accept it at all? | Yes, once the whitelist (§5) includes `"committee"` — found missing in dryrun-design-1 C1; without it, construction raises `ValueError` before `Router` is ever built, and the CLI flag is unreachable. |
| A committee member's `.act()` raises `AdapterError` | Caught per-member (D7); noted as a failure line in the combined result; dispatch continues to remaining members (OR-6). |
| Every committee member fails | `AdapterError` raised directly from the committee branch (D8) — propagates through `Agent.run()`'s existing `except AdapterError` handler (M6, unmodified) to a clean `[Error: ...]` string. |
| Privacy pattern matches **and** `--provider committee` is forced | `should_form_committee()` returns `False` (D3 step 2) — falls through to `select_worker()`, which (M6, unmodified) routes to local-only per RT-4. Committee mode never sees privacy-gated instructions (OR-5). |
| `consortium_patterns` matches **and** `--provider claude`/`--provider local` is forced | `should_form_committee()` returns `False` (D3 step 1) — the single-provider override wins outright, matching RT-8's existing "bypasses ALL policy evaluation" guarantee. |
| `max_committee_size` configured larger than the number of adapters actually configured | `effective_cap = min(cap, len(self._factories))` (§3) — never over-caps past what's actually available; no error, just a smaller committee than requested. |

---

## Files Changed

| File | Change | AC Trace |
|------|--------|----------|
| `src/axiom/router/policy.py` | Add `consortium_patterns`, `max_committee_size` to `RoutePolicy`; add `RoutingDecision.CONSORTIUM`; add `should_form_committee()`. | OR-2, OR-5, OR-8 |
| `src/axiom/router/router.py` | Add `Router.select_committee()`; guard `select_conductor()` against `forced_provider == "committee"` (Error Handling row 1). | OR-1, OR-2, OR-5, OR-8 |
| `src/axiom/loop.py` | ACT branch: `select_committee()` check before the existing `select_worker()` path; committee dispatch loop with per-slot failure tolerance and combined-result synthesis via the existing `observe()` call. | OR-1, OR-3, OR-4, OR-6, OR-7, OR-9 |
| `src/axiom/interface/cli.py` | `--provider` gains `"committee"` as a third choice. | OR-1 |
| `src/axiom/agent.py` | Extend `Agent.__init__`'s provider whitelist to accept `"committee"` (dryrun-design-1 C1 fix — was missing from this table entirely at iteration 1). | OR-1 |
| `tests/test_router_policy.py` | Extend. `should_form_committee()` — all precedence combinations (single-override beats consortium, privacy beats committee-override, consortium match, no match). | OR-1, OR-2, OR-5 |
| `tests/test_router.py` | Extend. `select_committee()` — membership, capping (OR-8), determinism (D5), `None` when not triggered, Conductor guard against `"committee"` (Error Handling row 1). | OR-1, OR-2, OR-8 |
| `tests/test_contracts.py` | Extend. Loop-level: committee dispatch calls every member with the same instruction (OR-3), combined result reaches `observe()`/history unchanged (OR-4), one member failing doesn't abort the cycle (OR-6), all-fail raises `AdapterError` (OR-6), `select_fallback_worker()` never called from the committee path (OR-7), `spawn_count` increments by committee size (D9), trace attributes (D10). | OR-3, OR-4, OR-6, OR-7 |
| `tests/fake_adapter.py` | `FakeRouter` gains a `committee_selections` configuration option (mirrors `worker_selections`) so committee-mode loop tests don't need a real `Router`. | OR-3, OR-4, OR-6 |

---

## Future Work (Out of Scope)

- **Concurrent committee dispatch** (`asyncio.gather`) — D6 explicitly defers this; revisit once committee sizes or latency sensitivity grow beyond today's 2-member case.
- **Weighted/ranked synthesis** — `requirement.md`'s own Out of Scope; OR-4 leaves all synthesis to the Conductor's ordinary reasoning.
- **`--router-config` for `consortium_patterns`** — same deferred posture M6 already established for its own pattern fields.
- **Committee size beyond the count of distinct configured providers** (e.g. sampling the same provider N times) — explicitly out of scope per `requirement.md`.
