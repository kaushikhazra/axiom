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

from axiom.router.policy import (
    RoutePolicy,
    RoutingDecision,
    evaluate,
    should_form_committee,
)

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
    provider_name: str  # "claude" | "local"
    control_level: str  # "KIND_A" | "KIND_B"
    fallback_allowed: bool  # False when override- or privacy-forced


class Router:
    def __init__(
        self,
        policy: RoutePolicy,
        adapter_factories: dict[str, Callable[[], RoutableAdapter]],
        forced_provider: str | None = None,
    ) -> None:
        """
        adapter_factories: {"claude": <zero-arg callable>, "local": <zero-arg
        callable>} -- called at most once each, lazily, cached.
        forced_provider: set from --provider when the user explicitly chose
        one (RT-8) -- None means policy-driven routing is active.
        """
        self._policy = policy
        self._factories = adapter_factories
        self._forced_provider = forced_provider
        self._cache: dict[str, RoutableAdapter] = {}
        self._conductor_provider: str | None = (
            None  # set once by select_conductor (RT-2)
        )

    @property
    def conductor_provider(self) -> str | None:
        """Public accessor for whichever provider select_conductor() picked
        -- None before select_conductor() has been called. agent.py uses
        this to derive self._provider_kind (existing, pre-M6 observability
        attribute) without reaching into a private attribute."""
        return self._conductor_provider

    def _get(self, provider_name: str) -> RoutableAdapter:
        if provider_name not in self._cache:
            if provider_name not in self._factories:
                raise RouterError(
                    f"no adapter factory configured for {provider_name!r}"
                )
            self._cache[provider_name] = self._factories[provider_name]()
        return self._cache[provider_name]

    def select_conductor(self) -> RoutableAdapter:
        """RT-2: called exactly once, at Agent.__init__ time. Caller (agent.py)
        is responsible for calling this only once -- Router does not enforce
        single-call itself (no hidden state machine), but stores the chosen
        provider so select_worker()'s CONDUCTOR_DEFAULT fallthrough can
        resolve against it."""
        conductor_override = (
            self._forced_provider if self._forced_provider != "committee" else None
        )  # M7: "committee" only ever selects Workers, never the Conductor
        provider_name = (
            conductor_override or "claude"
        )  # RT-2: capability-preferred default
        self._conductor_provider = provider_name
        return self._get(provider_name)

    def select_worker(self, instruction: str) -> WorkerSelection:
        """RT-3: called once per ACT dispatch."""
        if self._forced_provider is not None:
            # RT-8: bypasses ALL policy evaluation, including privacy.
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
            provider_name = next(iter(self._factories), None)
            if provider_name is None:
                # dryrun-code-1 W2: an empty adapter_factories dict must raise
                # RouterError like every other Router failure mode -- not a
                # bare StopIteration from an unguarded next().
                raise RouterError("no adapter factories configured for this session")

        adapter = self._get(provider_name)
        fallback_allowed = (
            reason != RoutingDecision.PRIVACY
        )  # RT-9: no fallback on privacy-gate
        return WorkerSelection(
            adapter=adapter,
            provider_name=provider_name,
            control_level=adapter.control_level,
            fallback_allowed=fallback_allowed,
        )

    def select_fallback_worker(self, excluded_provider: str) -> WorkerSelection | None:
        """RT-9: the other of exactly the two known providers. Returns None
        if no other provider is configured (single-adapter session) --
        caller (loop.py) treats None as "no fallback available", propagating
        the original error."""
        candidates = [p for p in self._factories if p != excluded_provider]
        if not candidates:
            return None
        provider_name = candidates[0]
        adapter = self._get(provider_name)
        logger.debug("[ROUTER_FALLBACK] %s -> %s", excluded_provider, provider_name)
        return WorkerSelection(
            adapter=adapter,
            provider_name=provider_name,
            control_level=adapter.control_level,
            fallback_allowed=False,  # exactly one fallback hop, never chained
        )

    def select_committee(self, instruction: str) -> list[WorkerSelection] | None:
        """M7 (OR-2): returns None when committee mode doesn't apply for this
        instruction -- caller falls through to the existing select_worker()
        single-dispatch path (M6, unmodified) in that case. When it applies,
        returns one WorkerSelection per configured adapter, capped by
        max_committee_size, in adapter_factories' insertion order (deterministic).
        """
        if not should_form_committee(instruction, self._policy, self._forced_provider):
            return None

        cap = self._policy.max_committee_size
        effective_cap = (
            min(cap, len(self._factories)) if cap is not None else len(self._factories)
        )
        member_names = list(self._factories)[:effective_cap]
        logger.debug(
            "[ROUTER_%s] %s", RoutingDecision.CONSORTIUM.upper(), ",".join(member_names)
        )

        selections: list[WorkerSelection] = []
        for provider_name in member_names:
            adapter = self._get(provider_name)
            selections.append(
                WorkerSelection(
                    adapter=adapter,
                    provider_name=provider_name,
                    control_level=adapter.control_level,
                    fallback_allowed=False,  # OR-7: committee members are never fallback-eligible
                )
            )
        return selections
