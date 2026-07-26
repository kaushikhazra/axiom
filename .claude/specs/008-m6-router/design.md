# M6 · Router (full) — Design

**Spec:** `008-m6-router`
**Milestone:** M6 — "Router (full)"
**Status:** DRAFT
**Inputs:** `requirement.md` (this spec); `001-agent-core/architecture.md` (Router as core-side component, Conductor/Worker table, OQ-1 resolution); installed source read directly — `src/axiom/loop.py`, `src/axiom/agent.py`, `src/axiom/providers/{base,claude_adapter,local_adapter}.py`, `src/axiom/observability/record.py` (all on `feature/m6-router`, branched from `master` post-M4/M5 merge, commit `2593fe8`).

---

## 1. Overview

The core structural finding driving this design: **`provider_kind` today is a single static label for an entire `PraoLoop.run()` call**, passed once from `agent.py` and threaded unchanged through every phase span (`perceive`/`reason`/`act`/`observe` all get the identical value). `PraoLoop.__init__` also takes a single fixed `act: ActPort` — one adapter instance, bound at construction, used for every ACT dispatch for the whole session.

Both of these directly conflict with RT-3 (Worker re-selected per ACT dispatch, potentially to a *different* provider each cycle) and RT-7 (observability must reflect *which provider actually ran that specific phase*, not a session-wide constant). This is not a superficial extension — **`PraoLoop`'s constructor changes shape**: `act: ActPort` is replaced by `router: Router`, and the loop asks the Router for a Worker fresh on every ACT dispatch instead of calling a fixed bound method.

`perceive()`/`observe()` do **not** need the same treatment — both are pure, provider-independent logic inherited unchanged from `PraoAdapterBase` (confirmed by reading `base.py`: neither method touches anything provider-specific). They stay bound to a single adapter instance for the loop's lifetime — in practice, the Conductor's own adapter instance, since it's guaranteed to exist and already implements `PraoAdapterBase`. No separate "which adapter runs perceive" policy is needed.

---

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | `PraoLoop.__init__` replaces its `act: ActPort` parameter with `router: Router`. `perceive`/`reason`/`observe` stay as single fixed port params, bound to the Conductor adapter instance. | RT-3 requires per-cycle Worker re-selection; a single fixed `act` port cannot express that. `perceive`/`observe` are provider-agnostic (confirmed by reading `base.py`) — no equivalent change needed for them, keeping the diff minimal (RT-1's "don't over-design" instinct). |
| D2 | `Router` lazily constructs and caches each named adapter ("claude"/"local") via zero-arg factory callables, not eagerly at `Router.__init__` time. | Preserves the existing M1-era guarantee ("Claude-only installs never pay the litellm import cost") — `agent.py` already defers `LocalAdapter`'s import for exactly this reason (D-something in M1's own design); Router must not silently break that by eagerly constructing both adapters regardless of policy. |
| D3 | `Router.select_worker()` returns a `WorkerSelection` value object (`adapter`, `provider_name`, `control_level`, `fallback_allowed: bool`), not a bare adapter. | The loop needs `control_level` for RT-7's trace attribute and `fallback_allowed` for RT-9's exclusion rules (no fallback on override or privacy-gate) without re-deriving either — the Router is the one place that knows *why* a given adapter was selected, so it's the natural owner of `fallback_allowed`. |
| D4 | Precedence is evaluated in a fixed function, tested explicitly for all combinations: RT-4 (privacy) checked first and unconditional; RT-6 (capability) checked second; RT-5 (cost/volume) is the fallthrough default when neither matches. No match at all (long instruction, no capability pattern) defaults to the Conductor's own provider. | Matches `requirement.md`'s explicit precedence statement (RT-6's AC). The "no match, default to Conductor's provider" fallthrough isn't explicitly named in any RT story as its own rule — it's the simplest coherent behavior filling the one gap the stories leave open (a long instruction matching neither privacy nor capability patterns), consistent with RT-2's "capability-preferred default" framing applied to the one under-specified case. |
| D5 | RT-8's override (`--provider` forced) bypasses privacy/cost/capability evaluation **entirely**, including RT-4's privacy gate. | `requirement.md` RT-8's AC states this explicitly ("no privacy/cost/capability pattern evaluation occurs at all... not even privacy — an explicit human override is trusted"). Documented here because it's easy to misread as a bug (a hard-override skipping a "hard" privacy gate looks contradictory until RT-8's own rationale — explicit human intent is trusted — is read). |
| D6 | `control_level` is a **class attribute** on each adapter (`ClaudeAdapter.control_level = "KIND_B"`, `LocalAdapter.control_level = "KIND_A"`), not computed. | RT-7's AC: "readable without constructing a full adapter instance." A class attribute satisfies this trivially; a computed property would need an instance. |
| D7 | `_maybe_record()` (`loop.py`) gains an `extra_attributes: dict \| None` passthrough to `record_phase()`, which already accepts one — no signature change needed on `record_phase()` itself. | `record_phase()` (`observability/record.py`) already has `extra_attributes` in its signature, unused by `loop.py` today. RT-7's `axiom.control_level` attribute threads through this existing, already-built mechanism — zero new observability surface needed. |
| D8 | RT-9's fallback wraps the **loop's** Act-phase dispatch (a `try/except AdapterError` around `worker.act()`, retrying via `router.select_fallback_worker()`), not something inside `Router.select_worker()` itself. | `select_worker()` is a pure selection decision (given inputs, which provider); *retrying after a failure* is a control-flow concern that belongs where the actual dispatch and its exception happen — the loop, matching how `MaxCyclesExceededError` and `AdapterError` propagation are already loop-owned concerns (D1 in the original M1 design, unchanged). |
| D9 | `Router.select_fallback_worker(excluded_provider: str)` returns the other of exactly the two known providers — no N-provider ranking logic. | `requirement.md` Out of Scope: "retry beyond one fallback attempt," and only two adapters exist today (per Purpose section — a third true-API adapter is a later, unlocked milestone tech choice). A 2-provider "give me the other one" function is honest about current scope; a general N-provider ranking algorithm would be speculative for adapters that don't exist yet. |
| D10 | **(Added after dryrun-design-1, C1)** `cli.py`'s `--provider` flag drops its `default="claude"` (stays optional, `choices=["claude","local"]`, no default — `args.provider` is `None` when omitted). `Agent.__init__`'s `provider` parameter changes from `provider: str = "claude"` to `provider: str \| None = None`. `forced_provider = provider` directly (no `in (...)` guard needed — `choices=` already constrains the two non-`None` values on the CLI side). | dryrun-design-1 C1: with the old `default="claude"`, "no `--provider` flag" and "`--provider claude`" were indistinguishable, so `Router`'s override-bypass branch fired on every real invocation and the entire policy engine (RT-4/5/6) was unreachable from the real CLI. `None` now genuinely means "no preference, let policy decide" — restoring RT-8's own AC scope ("preserves the pre-M6 CLI contract... for existing **explicit**-provider usage") to what it always meant: unchanged behavior only when a provider *is* named. |
| D11 | **(Added after dryrun-design-1, C2)** `_maybe_record()` yields the underlying `Span` (mirroring `record_phase()`'s own `Generator[Span, None, None]`, previously discarded). The ACT branch sets `axiom.control_level`/`axiom.router.provider` on that span **after** the dispatch (primary or fallback) actually completes, not via `extra_attributes` computed at `with`-entry. | dryrun-design-1 C2: `extra_attributes` computed once from the pre-fallback `selection` meant a successful fallback still reported the *failed* provider's `control_level`/`provider_name` in the trace — a genuine observability lie on exactly the path RT-9 exists to handle gracefully. |
| D12 | **(Added after dryrun-design-1, C3)** `run_state.spawn_count` is incremented a second time in the fallback branch, immediately before `fallback.adapter.act(...)`. | dryrun-design-1 C3: a fallback dispatch is a second loop-dispatched provider call by `spawn_count`'s own documented contract ("loop-dispatched query() calls") — the original design counted only the primary attempt, undercounting by one on every successful fallback. Same contract-drift issue class M5's dryrun-code-2 W1 already caught once (there: overcounting; here: undercounting). |

---

## 2. `RoutePolicy` and precedence evaluation

`src/axiom/router/policy.py`

```python
"""
RoutePolicy -- the declarative, pattern-based routing rules RT-4/RT-5/RT-6
evaluate. Deliberately NOT an NLP classifier (requirement.md Purpose) --
every field here is a plain glob/regex/length rule, kept together so the
precedence order (privacy > capability > cost/volume default) has exactly
one place to be evaluated and exactly one place to be tested.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutePolicy:
    privacy_patterns: list[str] = field(default_factory=list)      # RT-4
    bulk_threshold_chars: int = 200                                 # RT-5
    capability_patterns: list[str] = field(default_factory=list)   # RT-6


def _matches_any(instruction: str, patterns: list[str]) -> bool:
    """glob-style match (fnmatch) OR regex match, tried in that order per
    pattern -- lets simple patterns stay simple (e.g. '*.env', '*/secrets/*')
    while still allowing a regex when a caller needs one (e.g. 'password|token')."""
    for pattern in patterns:
        if fnmatch.fnmatch(instruction, pattern):
            return True
        try:
            if re.search(pattern, instruction):
                return True
        except re.error:
            continue  # not a valid regex -- fnmatch already tried; skip silently
    return False


class RoutingDecision:
    PRIVACY = "privacy"
    CAPABILITY = "capability"
    BULK_DEFAULT = "bulk_default"
    CONDUCTOR_DEFAULT = "conductor_default"


def evaluate(instruction: str, policy: RoutePolicy) -> tuple[str, str]:
    """Returns (provider_name, decision_reason). provider_name is "local" or
    "claude" (or a sentinel the caller resolves against the Conductor's own
    provider for CONDUCTOR_DEFAULT -- see Router.select_worker).

    Precedence (D4): privacy (RT-4) > capability (RT-6) > bulk default (RT-5)
    > Conductor-provider fallthrough.
    """
    if _matches_any(instruction, policy.privacy_patterns):
        return "local", RoutingDecision.PRIVACY
    if _matches_any(instruction, policy.capability_patterns):
        return "claude", RoutingDecision.CAPABILITY
    if len(instruction) <= policy.bulk_threshold_chars:
        return "local", RoutingDecision.BULK_DEFAULT
    return "__conductor__", RoutingDecision.CONDUCTOR_DEFAULT
```

---

## 3. `Router`

`src/axiom/router/router.py`

```python
"""
Router -- the intent -> provider allocation brain (architecture.md).
Core-side component, NOT a port (RT-1): imports only axiom.interfaces-level
concepts and the provider adapter classes it selects between. Does not
import axiom.loop.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Protocol

from axiom.router.policy import RoutePolicy, RoutingDecision, evaluate

logger = logging.getLogger("axiom.router")


class RoutableAdapter(Protocol):
    """The subset of adapter surface Router cares about -- avoids importing
    ClaudeAdapter/LocalAdapter concretely, matching PraoLoop's own
    port-typing style."""

    control_level: str  # "KIND_A" | "KIND_B"

    def act(self, instruction: str) -> str: ...
    def reason(self, context: str) -> object: ...
    def perceive(self, run_state: object) -> str: ...
    def observe(self, result: str, run_state: object) -> object: ...


class RouterError(Exception):
    """Raised when policy demands a provider that isn't available (RT-4's
    privacy gate with no local adapter configured). Never silently
    substituted -- see requirement.md RT-4's AC."""


@dataclass
class WorkerSelection:
    adapter: RoutableAdapter
    provider_name: str          # "claude" | "local"
    control_level: str          # "KIND_A" | "KIND_B"
    fallback_allowed: bool      # False when override- or privacy-forced (D3/RT-9)


class Router:
    def __init__(
        self,
        policy: RoutePolicy,
        adapter_factories: dict[str, Callable[[], RoutableAdapter]],
        forced_provider: str | None = None,
    ) -> None:
        """
        adapter_factories: {"claude": <zero-arg callable>, "local": <zero-arg
        callable>} -- called at most once each, lazily, cached (D2).
        forced_provider: set from --provider when the user explicitly chose
        one (RT-8) -- None means policy-driven routing is active.
        """
        self._policy = policy
        self._factories = adapter_factories
        self._forced_provider = forced_provider
        self._cache: dict[str, RoutableAdapter] = {}
        self._conductor_provider: str | None = None  # set once by select_conductor (RT-2)

    def _get(self, provider_name: str) -> RoutableAdapter:
        if provider_name not in self._cache:
            if provider_name not in self._factories:
                raise RouterError(f"no adapter factory configured for {provider_name!r}")
            self._cache[provider_name] = self._factories[provider_name]()
        return self._cache[provider_name]

    def select_conductor(self) -> RoutableAdapter:
        """RT-2: called exactly once, at Agent.__init__ time. Caller (agent.py)
        is responsible for calling this only once -- Router does not enforce
        single-call itself (no hidden state machine), but stores the chosen
        provider so select_worker()'s CONDUCTOR_DEFAULT fallthrough (D4) can
        resolve against it."""
        provider_name = self._forced_provider or "claude"  # RT-2: capability-preferred default
        self._conductor_provider = provider_name
        return self._get(provider_name)

    def select_worker(self, instruction: str) -> WorkerSelection:
        """RT-3: called once per ACT dispatch."""
        if self._forced_provider is not None:
            # RT-8: bypasses ALL policy evaluation, including privacy (D5).
            adapter = self._get(self._forced_provider)
            return WorkerSelection(
                adapter=adapter,
                provider_name=self._forced_provider,
                control_level=adapter.control_level,
                fallback_allowed=False,  # RT-9: no fallback when override forced
            )

        provider_name, reason = evaluate(instruction, self._policy)
        if provider_name == "__conductor__":
            assert self._conductor_provider is not None, (
                "select_worker() called before select_conductor() -- "
                "Router requires the Conductor to be selected first"
            )
            provider_name = self._conductor_provider

        if provider_name not in self._factories:
            if reason == RoutingDecision.PRIVACY:
                # RT-4: privacy is a hard constraint -- no silent fallback.
                raise RouterError(
                    f"privacy pattern matched but no {provider_name!r} adapter "
                    "is configured for this session"
                )
            # Non-privacy reasons degrade to whatever IS available rather than
            # hard-failing (only reachable if a session is configured with
            # exactly one factory -- e.g. an explicit single-provider setup
            # without --provider forcing).
            provider_name = next(iter(self._factories))

        adapter = self._get(provider_name)
        fallback_allowed = reason != RoutingDecision.PRIVACY  # RT-9: no fallback on privacy-gate
        return WorkerSelection(
            adapter=adapter,
            provider_name=provider_name,
            control_level=adapter.control_level,
            fallback_allowed=fallback_allowed,
        )

    def select_fallback_worker(self, excluded_provider: str) -> WorkerSelection | None:
        """RT-9: the other of exactly the two known providers (D9). Returns
        None if no other provider is configured (single-adapter session) --
        caller (loop.py) treats None as "no fallback available", propagating
        the original error."""
        candidates = [p for p in self._factories if p != excluded_provider]
        if not candidates:
            return None
        provider_name = candidates[0]
        adapter = self._get(provider_name)
        logger.debug(
            "[ROUTER_FALLBACK] %s -> %s", excluded_provider, provider_name
        )
        return WorkerSelection(
            adapter=adapter,
            provider_name=provider_name,
            control_level=adapter.control_level,
            fallback_allowed=False,  # D8: exactly one fallback hop, never chained
        )
```

---

## 4. `control_level` on adapters (RT-7)

Additive, one line each — no other change to either adapter class.

`src/axiom/providers/claude_adapter.py`:
```python
class ClaudeAdapter(PraoAdapterBase):
    control_level: str = "KIND_B"
    ...
```

`src/axiom/providers/local_adapter.py`:
```python
class LocalAdapter(PraoAdapterBase):
    control_level: str = "KIND_A"
    ...
```

---

## 5. Loop wiring

`src/axiom/loop.py` — `PraoLoop.__init__` signature change (D1):

```python
def __init__(
    self,
    perceive: PerceivePort,
    reason: ReasonPort,
    observe: ObservePort,
    memory: MemoryPort,
    skills: SkillsPort,
    router: Router,             # replaces `act: ActPort`
    max_cycles: int = MAX_CYCLES,
) -> None:
    self._perceive = perceive
    self._reason = reason
    self._observe = observe
    self._max_cycles = max_cycles
    self._memory = memory
    self._skills = skills
    self._router = router
    ...
```

`_maybe_record()` gains the `extra_attributes` passthrough (D7) **and now yields the `Span`** (D11 — was previously `yield` with no value, discarding `record_phase()`'s own yielded span):

```python
@contextmanager
def _maybe_record(
    phase: str,
    run_id: str | None,
    provider_kind: str,
    extra_attributes: dict | None = None,
) -> Generator["Span | None", None, None]:
    if run_id is None:
        yield None
        return
    from axiom.observability.record import record_phase  # noqa: PLC0415
    with record_phase(
        phase=phase, run_id=run_id, provider_kind=provider_kind,
        extra_attributes=extra_attributes,
    ) as span:
        yield span
```

The ACT branch (previously `with _maybe_record("act", run_id, provider_kind): result = await asyncio.to_thread(self._act.act, intent.instruction)`) becomes Router-driven, with RT-9's single-hop fallback. Per D11/D12, the span's routing attributes are set **after** dispatch completes (reflecting whichever provider actually produced `result`), and `spawn_count` increments once per actual dispatch attempt:

```python
# intent == ACT
if not isinstance(intent, ActIntent):
    raise TypeError(...)

selection = self._router.select_worker(intent.instruction)
with _maybe_record("act", run_id, provider_kind) as act_span:
    run_state.spawn_count += 1
    try:
        result = await asyncio.to_thread(selection.adapter.act, intent.instruction)
        final_selection = selection
    except AdapterError:
        if not selection.fallback_allowed:
            raise
        fallback = self._router.select_fallback_worker(selection.provider_name)
        if fallback is None:
            raise
        run_state.spawn_count += 1  # D12: fallback is a second loop-dispatched call
        result = await asyncio.to_thread(fallback.adapter.act, intent.instruction)
        final_selection = fallback

    if act_span is not None:  # D11: set attrs from whichever selection actually ran
        act_span.set_attribute("axiom.control_level", final_selection.control_level)
        act_span.set_attribute("axiom.router.provider", final_selection.provider_name)

with _maybe_record("observe", run_id, provider_kind):
    run_state = await asyncio.to_thread(self._observe.observe, result, run_state)
```

**Note on `provider_kind` (the pre-existing, session-wide parameter):** left unchanged in meaning — it continues to label the *Conductor's* control-level for the run-level and reason/perceive/observe spans (those all still run on the fixed Conductor adapter, D1). Only the `act` span additionally carries the per-dispatch `axiom.control_level`/`axiom.router.provider` attributes (now correctly reflecting the *actual* dispatch, D11), which may legitimately differ from the run's `provider_kind` when the Worker differs from the Conductor (RT-3). This is not a rename or a breaking change to `provider_kind`'s existing meaning — it's an additive, more granular attribute alongside it.

---

## 6. Composition root (`agent.py`)

Replaces the `if provider == "local": ... elif provider == "claude": ...` block (RT-1's AC: "`agent.py` no longer contains provider-selection branching itself").

```python
from axiom.router.policy import RoutePolicy
from axiom.router.router import Router

def _make_claude_adapter(persona_text: str, gate: GuardrailsGate) -> ClaudeAdapter:
    return ClaudeAdapter(persona=persona_text, allowed_tools=CLAUDE_SAFE_TOOLS, gate=gate)

def _make_local_adapter(
    persona_text: str, working_dir: Path, gate: GuardrailsGate, ollama_host: str | None
) -> "LocalAdapter":
    from axiom.providers.local_adapter import LocalAdapter  # noqa: PLC0415 (lazy, D2)
    kwargs = {}
    if ollama_host is not None:
        kwargs["ollama_api_base"] = ollama_host
    return LocalAdapter(persona=persona_text, working_dir=working_dir, gate=gate, **kwargs)

# inside Agent.__init__, replacing the existing if/elif block:
# D10 (dryrun-design-1 C1 fix): `provider` defaults to None now, not "claude"
# -- Agent.__init__ signature changes to `provider: str | None = None`, and
# cli.py's --provider argparse flag drops its `default="claude"` to match.
# Without this, "no --provider flag" and "--provider claude" were
# indistinguishable, and Router's override-bypass branch fired on every real
# invocation -- the entire policy engine (RT-4/5/6) was unreachable.
forced_provider = provider  # None means "no preference, let policy decide" (RT-4/5/6 active)
# NOTE: when explicitly passed ("claude" or "local"), this keeps the pre-M6
# CLI contract exactly (RT-8's AC) -- it now maps to Router's forced_provider
# instead of directly picking an adapter, but the observable behavior for an
# explicit choice is unchanged.

router = Router(
    policy=RoutePolicy(),  # default policy (empty patterns, 200-char bulk threshold) -- RT-4/5/6 patterns are a future config surface (Out of Scope: --router-config)
    adapter_factories={
        "claude": lambda: _make_claude_adapter(persona_text, gate),
        "local": lambda: _make_local_adapter(persona_text, resolved_working_dir, gate, ollama_host),
    },
    forced_provider=forced_provider,
)
conductor_adapter = router.select_conductor()  # RT-2: called exactly once, here

self._loop = PraoLoop(
    perceive=conductor_adapter,
    reason=conductor_adapter,
    observe=conductor_adapter,
    max_cycles=10,
    memory=self._memory_adapter,
    skills=skills_registry,
    router=router,
)
```

`self._provider_kind` (used for the run-level `provider_kind` param to `loop.run()`) is now derived from `router`'s chosen Conductor rather than the raw `provider` string, via the existing `_PROVIDER_KIND` mapping — same value as before for the common case (`provider="claude"` → `"KIND_B"`), since `forced_provider` defaults to the same choice `select_conductor()` would make anyway when no override is given (D4's Conductor default is `"claude"`, matching `_PROVIDER_KIND`'s pre-existing default mapping).

---

## Error Handling

| Failure | Behavior |
|---|---|
| RT-4 privacy pattern matches, no `"local"` factory configured | `RouterError` raised from `select_worker()` — not silently substituted (D-level guarantee, RT-4's AC). Propagates as an uncaught `RouterError` through the loop (a configuration error, not a runtime one — matches the "fail loud on misconfiguration" posture M4's D11/D6 already established for `gate`/`working_dir`). |
| Worker's `act()` raises `AdapterError`, fallback allowed | Loop retries once via `router.select_fallback_worker()` (D8). If that also raises `AdapterError`, it propagates uncaught — exactly one hop (D9), no retry loop. |
| Worker's `act()` raises `AdapterError`, fallback NOT allowed (override or privacy-gated) | Propagates immediately, unchanged from pre-M6 behavior for an explicitly-forced provider (RT-8's AC: "a forced-provider failure propagates immediately, unchanged"). |
| `select_worker()` called before `select_conductor()` | `AssertionError` — a programming error (composition root wiring bug), not a runtime/user-facing condition; `agent.py`'s wiring order (D6 in §6) makes this unreachable in practice. |
| `RoutingDecision.CONDUCTOR_DEFAULT` resolves against a provider not in `adapter_factories` (only reachable in a hand-constructed single-adapter `Router`, not via `agent.py`'s wiring) | Falls through to `next(iter(self._factories))` — degrades to whatever's available rather than hard-failing, since this isn't a privacy guarantee (only RT-4's path is exempted from this degrade-gracefully rule). |

---

## Files Changed

| File | Change | AC Trace |
|------|--------|----------|
| `src/axiom/router/policy.py` | New. `RoutePolicy`, `RoutingDecision`, `evaluate()` — precedence-ordered pattern matching. | RT-4, RT-5, RT-6 |
| `src/axiom/router/router.py` | New. `Router`, `WorkerSelection`, `RouterError`, `RoutableAdapter` protocol — lazy adapter construction, Conductor/Worker selection, fallback. | RT-1, RT-2, RT-3, RT-4, RT-8, RT-9 |
| `src/axiom/providers/claude_adapter.py` | Add `control_level: str = "KIND_B"` class attribute. | RT-7 |
| `src/axiom/providers/local_adapter.py` | Add `control_level: str = "KIND_A"` class attribute. | RT-7 |
| `src/axiom/loop.py` | `PraoLoop.__init__` replaces `act: ActPort` with `router: Router`; ACT branch asks Router per dispatch, wraps with RT-9 fallback; `_maybe_record()` gains `extra_attributes` passthrough. | RT-1, RT-3, RT-7, RT-9 |
| `src/axiom/agent.py` | Replace `if provider == ...` block with `Router` construction (lazy adapter factories) + `router.select_conductor()`; wire `router=` into `PraoLoop` instead of `act=`. `provider` parameter default changes from `"claude"` to `None` (D10). | RT-1, RT-2, RT-8 |
| `src/axiom/interface/cli.py` | `--provider` argparse argument drops `default="claude"` (stays optional, `choices=` unchanged) (D10). | RT-1, RT-4, RT-5, RT-6 |
| `tests/test_router_policy.py` | New. `evaluate()` precedence — all combinations (privacy-only, capability-only, bulk-only, none-match, privacy-beats-capability, capability-beats-bulk). | RT-4, RT-5, RT-6 |
| `tests/test_router.py` | New. `Router.select_conductor()`/`select_worker()`/`select_fallback_worker()` — lazy construction/caching, override bypass (incl. privacy bypass), `RouterError` on unconfigured privacy target, fallback-allowed flag correctness per selection reason. | RT-1, RT-2, RT-3, RT-4, RT-8, RT-9 |
| `tests/test_contracts.py` | Extend. Loop-level: Worker selection called per ACT cycle (not cached across cycles), `axiom.control_level`/`axiom.router.provider` span attributes present, fallback retry-once behavior, no-fallback-on-override/privacy paths. | RT-3, RT-7, RT-9 |
| Existing `PraoLoop(...)` construction call sites (`tests/test_contracts.py`, `tests/test_local_e2e.py`, `tests/test_memory_integration.py` x4, `src/axiom/agent.py`) | Updated to pass `router=` instead of `act=` — breaking-change ripple, same shape as M4's D11 / M5's skills= ripple. Grep `PraoLoop(` across the tree before implementation to enumerate exact sites (do not assume the M5-era list is unchanged — re-grep). | RT-1 |
| `tests/fake_adapter.py` | Add a `FakeRouter` test double (mirrors `FakeSkills`'s shape) — configurable `select_conductor()`/`select_worker()`/`select_fallback_worker()` return values, call-tracking lists for assertions. | RT-1, RT-2, RT-3, RT-9 |

---

## Future Work (Out of Scope)

- **`--router-config` CLI flag** to load `RoutePolicy` patterns from a file — deferred per `requirement.md`'s own Out of Scope; today's default `RoutePolicy()` has empty privacy/capability pattern lists (no gating/override happens unless a caller constructs `Router` with a non-default policy directly — not yet CLI-reachable).
- **NLP/LLM-based classification** for privacy/cost/capability signals — explicitly out of scope per `requirement.md` Purpose.
- **Simultaneous multi-provider consortium dispatch** — M7 (Orchestrator) territory, not this milestone.
- **A third (true-API) adapter** — `Router`'s shape (`dict[str, Callable[[], RoutableAdapter]]`) is not hardcoded to exactly two providers, so adding one later is additive to `agent.py`'s factory dict, not a `Router`/`policy.py` redesign — but building that adapter itself is not this milestone's job.
- **Retry beyond one fallback hop** — D9/D8, explicitly one hop only.
- **Learned/persisted routing policy** — M8 (Self-correction) territory.
