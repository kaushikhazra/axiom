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
