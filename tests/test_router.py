"""
Unit tests for axiom.router.router.Router -- lazy adapter construction,
Conductor/Worker selection, override bypass, fallback (RT-1, RT-2, RT-3,
RT-4, RT-8, RT-9).
"""

from __future__ import annotations

import pytest

from axiom.router.policy import RoutePolicy
from axiom.router.router import Router, RouterError


class _FakeRoutableAdapter:
    """Minimal RoutableAdapter -- just enough surface for Router tests."""

    def __init__(self, control_level: str) -> None:
        self.control_level = control_level

    def act(self, instruction: str) -> str:
        return f"acted: {instruction}"

    def reason(self, context: str) -> object:
        return None

    def perceive(self, run_state: object) -> str:
        return ""

    def observe(self, result: str, run_state: object) -> object:
        return run_state


def _factories(claude_calls: list, local_calls: list) -> dict:
    def make_claude():
        claude_calls.append(1)
        return _FakeRoutableAdapter("KIND_B")

    def make_local():
        local_calls.append(1)
        return _FakeRoutableAdapter("KIND_A")

    return {"claude": make_claude, "local": make_local}


class TestLazyConstruction:
    def test_no_adapters_constructed_until_needed(self) -> None:
        claude_calls: list = []
        local_calls: list = []
        Router(RoutePolicy(), _factories(claude_calls, local_calls))
        assert claude_calls == []
        assert local_calls == []

    def test_select_conductor_constructs_only_claude(self) -> None:
        claude_calls: list = []
        local_calls: list = []
        router = Router(RoutePolicy(), _factories(claude_calls, local_calls))
        router.select_conductor()
        assert claude_calls == [1]
        assert local_calls == []

    def test_repeated_worker_selection_of_same_provider_does_not_reconstruct(
        self,
    ) -> None:
        claude_calls: list = []
        local_calls: list = []
        router = Router(RoutePolicy(), _factories(claude_calls, local_calls))
        router.select_conductor()  # constructs claude once
        router.select_worker("short")  # bulk default (empty policy) -> local
        router.select_worker("also short")  # -> local again, same cached instance
        assert claude_calls == [1]  # unaffected by worker selection
        assert local_calls == [1]  # local constructed exactly once, then reused


class TestSelectConductor:
    def test_default_no_override_picks_claude(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        adapter = router.select_conductor()
        assert adapter.control_level == "KIND_B"
        assert router.conductor_provider == "claude"

    def test_forced_local_picks_local(self) -> None:
        router = Router(RoutePolicy(), _factories([], []), forced_provider="local")
        adapter = router.select_conductor()
        assert adapter.control_level == "KIND_A"
        assert router.conductor_provider == "local"

    def test_conductor_provider_none_before_selection(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        assert router.conductor_provider is None


class TestSetForcedProvider:
    """M10 (design.md D4): runtime provider switching -- select_worker()/
    select_committee() already re-read _forced_provider fresh on every
    call, so this is a thin setter, but its effect must be observable."""

    def test_switches_worker_selection_immediately(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        router.set_forced_provider("local")
        selection = router.select_worker("anything")
        assert selection.provider_name == "local"

    def test_switching_back_to_none_restores_policy_driven_routing(self) -> None:
        policy = RoutePolicy(bulk_threshold_chars=1000)
        router = Router(policy, _factories([], []), forced_provider="local")
        router.set_forced_provider(None)
        # A short instruction with no policy match falls through to
        # bulk-default (RT-5) -- proves override was genuinely lifted, not
        # just re-forced to a different fixed value.
        selection = router.select_worker("short")
        assert selection.fallback_allowed is True  # override forcing sets False

    def test_conductor_reflects_new_forced_provider_after_reselection(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        router.select_conductor()
        assert router.conductor_provider == "claude"
        router.set_forced_provider("local")
        router.select_conductor()  # caller (Agent.set_provider) re-resolves
        assert router.conductor_provider == "local"


class TestSelectWorkerPolicyDriven:
    def test_privacy_pattern_routes_local(self) -> None:
        policy = RoutePolicy(privacy_patterns=["*secret*"])
        router = Router(policy, _factories([], []))
        router.select_conductor()
        selection = router.select_worker("a secret file")
        assert selection.provider_name == "local"
        assert selection.control_level == "KIND_A"
        assert selection.fallback_allowed is False  # RT-9: no fallback on privacy-gate

    def test_capability_pattern_routes_claude(self) -> None:
        policy = RoutePolicy(capability_patterns=["*complex*"])
        router = Router(policy, _factories([], []))
        router.select_conductor()
        selection = router.select_worker("a complex task")
        assert selection.provider_name == "claude"
        assert selection.fallback_allowed is True

    def test_bulk_default_routes_local(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        router.select_conductor()
        selection = router.select_worker("short")
        assert selection.provider_name == "local"
        assert selection.fallback_allowed is True

    def test_no_match_falls_through_to_conductor_provider(self) -> None:
        policy = RoutePolicy(bulk_threshold_chars=1)
        router = Router(policy, _factories([], []), forced_provider=None)
        router.select_conductor()  # picks "claude" (default)
        selection = router.select_worker("a long instruction over the threshold")
        assert selection.provider_name == "claude"  # matches conductor's own choice

    def test_two_different_instructions_can_route_differently(self) -> None:
        """RT-3: per-dispatch, not cached across cycles."""
        policy = RoutePolicy(
            capability_patterns=["*complex*"], bulk_threshold_chars=200
        )
        router = Router(policy, _factories([], []))
        router.select_conductor()
        s1 = router.select_worker("a complex task")
        s2 = router.select_worker("short")
        assert s1.provider_name == "claude"
        assert s2.provider_name == "local"

    def test_empty_factories_raises_router_error_not_stop_iteration(self) -> None:
        """dryrun-code-1 W2: the degrade-gracefully fallthrough must raise
        RouterError (like every other Router failure mode), not a bare
        StopIteration from an unguarded next(iter(...))."""
        policy = RoutePolicy(bulk_threshold_chars=0)  # forces CONDUCTOR_DEFAULT
        router = Router(policy, {}, forced_provider=None)
        router._conductor_provider = "claude"  # bypass select_conductor() for this test
        with pytest.raises(RouterError, match="no adapter factories configured"):
            router.select_worker("a long instruction over the threshold")

    def test_privacy_match_with_no_local_factory_raises_router_error(self) -> None:
        policy = RoutePolicy(privacy_patterns=["*secret*"])
        router = Router(policy, {"claude": lambda: _FakeRoutableAdapter("KIND_B")})
        router.select_conductor()
        with pytest.raises(RouterError, match="privacy"):
            router.select_worker("a secret file")

    def test_select_worker_before_select_conductor_asserts(self) -> None:
        policy = RoutePolicy(
            bulk_threshold_chars=1
        )  # forces CONDUCTOR_DEFAULT fallthrough
        router = Router(policy, _factories([], []))
        with pytest.raises(AssertionError):
            router.select_worker("a long instruction over the threshold")


class TestSelectWorkerOverride:
    def test_forced_provider_bypasses_all_policy(self) -> None:
        policy = RoutePolicy(capability_patterns=["*"])  # would match everything
        router = Router(policy, _factories([], []), forced_provider="local")
        router.select_conductor()
        selection = router.select_worker("anything")
        assert selection.provider_name == "local"

    def test_forced_provider_bypasses_privacy_too(self) -> None:
        """D5: an explicit override is trusted, even over the privacy gate."""
        policy = RoutePolicy(privacy_patterns=["*secret*"])
        router = Router(policy, _factories([], []), forced_provider="claude")
        router.select_conductor()
        selection = router.select_worker("a secret file")
        assert selection.provider_name == "claude"

    def test_forced_provider_selection_never_allows_fallback(self) -> None:
        router = Router(RoutePolicy(), _factories([], []), forced_provider="claude")
        router.select_conductor()
        selection = router.select_worker("anything")
        assert selection.fallback_allowed is False


class TestSelectFallbackWorker:
    def test_returns_the_other_provider(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        router.select_conductor()
        fallback = router.select_fallback_worker("claude")
        assert fallback is not None
        assert fallback.provider_name == "local"
        assert fallback.fallback_allowed is False  # exactly one hop, never chained

    def test_returns_none_when_no_other_provider_configured(self) -> None:
        router = Router(
            RoutePolicy(), {"claude": lambda: _FakeRoutableAdapter("KIND_B")}
        )
        router.select_conductor()
        fallback = router.select_fallback_worker("claude")
        assert fallback is None

    def test_fallback_reuses_cached_adapter_if_already_constructed(self) -> None:
        claude_calls: list = []
        local_calls: list = []
        router = Router(RoutePolicy(), _factories(claude_calls, local_calls))
        router.select_conductor()  # constructs claude
        router.select_worker("short")  # bulk default -> constructs local
        assert local_calls == [1]
        router.select_fallback_worker("claude")  # should reuse cached local
        assert local_calls == [1]  # not reconstructed


class TestSelectConductorCommitteeGuard:
    def test_forced_committee_does_not_leak_into_conductor_selection(self) -> None:
        """dryrun-design-1 C1: "committee" must never be used as a literal
        provider name for the Conductor -- it degrades to the capability-
        preferred default ("claude"), same as no override at all."""
        router = Router(RoutePolicy(), _factories([], []), forced_provider="committee")
        adapter = router.select_conductor()
        assert adapter.control_level == "KIND_B"
        assert router.conductor_provider == "claude"


class TestSelectCommittee:
    def test_returns_none_when_not_triggered(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        router.select_conductor()
        assert router.select_committee("anything") is None

    def test_forced_committee_returns_one_selection_per_configured_adapter(
        self,
    ) -> None:
        router = Router(RoutePolicy(), _factories([], []), forced_provider="committee")
        router.select_conductor()
        committee = router.select_committee("anything")
        assert committee is not None
        assert {s.provider_name for s in committee} == {"claude", "local"}
        assert all(s.fallback_allowed is False for s in committee)

    def test_consortium_pattern_match_returns_committee(self) -> None:
        policy = RoutePolicy(consortium_patterns=["*second opinion*"])
        router = Router(policy, _factories([], []))
        router.select_conductor()
        committee = router.select_committee("get a second opinion")
        assert committee is not None
        assert len(committee) == 2

    def test_members_have_real_distinct_control_levels(self) -> None:
        router = Router(RoutePolicy(), _factories([], []), forced_provider="committee")
        router.select_conductor()
        committee = router.select_committee("anything")
        control_levels = {s.provider_name: s.control_level for s in committee}
        assert control_levels == {"claude": "KIND_B", "local": "KIND_A"}

    def test_capped_by_max_committee_size(self) -> None:
        policy = RoutePolicy(max_committee_size=1)
        router = Router(policy, _factories([], []), forced_provider="committee")
        router.select_conductor()
        committee = router.select_committee("anything")
        assert len(committee) == 1

    def test_cap_never_exceeds_configured_adapter_count(self) -> None:
        """A generous cap larger than what's actually configured must not
        over-select -- effective_cap is min(cap, len(factories))."""
        policy = RoutePolicy(max_committee_size=10)
        router = Router(policy, _factories([], []), forced_provider="committee")
        router.select_conductor()
        committee = router.select_committee("anything")
        assert len(committee) == 2

    def test_default_cap_is_the_configured_adapter_count(self) -> None:
        """max_committee_size=None (default) -- no explicit cap configured,
        resolves to len(adapter_factories) -- a no-op cap in today's 2-provider
        world (OR-8)."""
        router = Router(RoutePolicy(), _factories([], []), forced_provider="committee")
        router.select_conductor()
        committee = router.select_committee("anything")
        assert len(committee) == 2

    def test_membership_order_is_deterministic_insertion_order(self) -> None:
        policy = RoutePolicy(max_committee_size=1)
        router = Router(policy, _factories([], []), forced_provider="committee")
        router.select_conductor()
        committee = router.select_committee("anything")
        assert committee[0].provider_name == "claude"  # first key in _factories()

    def test_single_provider_override_returns_none_even_with_consortium_pattern(
        self,
    ) -> None:
        policy = RoutePolicy(consortium_patterns=["*"])  # would match everything
        router = Router(policy, _factories([], []), forced_provider="claude")
        router.select_conductor()
        assert router.select_committee("anything") is None

    def test_privacy_match_returns_none_even_with_forced_committee(self) -> None:
        policy = RoutePolicy(privacy_patterns=["*secret*"])
        router = Router(policy, _factories([], []), forced_provider="committee")
        router.select_conductor()
        assert router.select_committee("a secret file") is None

    def test_reuses_cached_adapters_already_constructed(self) -> None:
        claude_calls: list = []
        local_calls: list = []
        router = Router(
            RoutePolicy(),
            _factories(claude_calls, local_calls),
            forced_provider="committee",
        )
        router.select_conductor()  # constructs claude
        assert claude_calls == [1]
        router.select_committee("anything")
        assert claude_calls == [1]  # not reconstructed
        assert local_calls == [1]  # constructed exactly once


class TestSelectExtractionWorker:
    """M8: cheapest configured provider, bypasses RoutePolicy entirely."""

    def test_prefers_local_when_configured(self) -> None:
        router = Router(RoutePolicy(), _factories([], []))
        selection = router.select_extraction_worker()
        assert selection.provider_name == "local"
        assert selection.control_level == "KIND_A"
        assert selection.fallback_allowed is False

    def test_bypasses_policy_even_with_forced_provider(self) -> None:
        """Extraction is an internal task -- forced_provider (RT-8-style
        override) is irrelevant to it; it always prefers local regardless."""
        router = Router(RoutePolicy(), _factories([], []), forced_provider="claude")
        selection = router.select_extraction_worker()
        assert selection.provider_name == "local"

    def test_falls_back_to_whatever_is_configured_when_local_absent(self) -> None:
        router = Router(
            RoutePolicy(), {"claude": lambda: _FakeRoutableAdapter("KIND_B")}
        )
        selection = router.select_extraction_worker()
        assert selection.provider_name == "claude"

    def test_raises_router_error_on_zero_adapters(self) -> None:
        router = Router(RoutePolicy(), {})
        with pytest.raises(RouterError, match="no adapter factories configured"):
            router.select_extraction_worker()

    def test_reuses_cached_local_adapter(self) -> None:
        claude_calls: list = []
        local_calls: list = []
        router = Router(RoutePolicy(), _factories(claude_calls, local_calls))
        router.select_conductor()  # constructs claude only
        router.select_extraction_worker()  # should construct local fresh
        assert local_calls == [1]
        router.select_extraction_worker()  # should reuse cached local
        assert local_calls == [1]
