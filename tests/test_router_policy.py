"""
Unit tests for axiom.router.policy -- evaluate() precedence: privacy (RT-4)
> capability (RT-6) > bulk default (RT-5) > Conductor-provider fallthrough.
"""

from __future__ import annotations

from axiom.router.policy import RoutePolicy, RoutingDecision, evaluate


class TestPrivacyOnly:
    def test_privacy_glob_match_routes_local(self) -> None:
        policy = RoutePolicy(privacy_patterns=["*secrets*"])
        provider, reason = evaluate("read the secrets.env file", policy)
        assert provider == "local"
        assert reason == RoutingDecision.PRIVACY

    def test_privacy_regex_match_routes_local(self) -> None:
        policy = RoutePolicy(privacy_patterns=[r"password|token"])
        provider, reason = evaluate("look up the api token", policy)
        assert provider == "local"
        assert reason == RoutingDecision.PRIVACY

    def test_no_privacy_pattern_configured_does_not_match(self) -> None:
        policy = RoutePolicy()
        provider, reason = evaluate("read the secrets.env file", policy)
        assert reason != RoutingDecision.PRIVACY


class TestCapabilityOnly:
    def test_capability_match_routes_claude(self) -> None:
        policy = RoutePolicy(capability_patterns=["*complex*"])
        provider, reason = evaluate("do a complex multi-step refactor", policy)
        assert provider == "claude"
        assert reason == RoutingDecision.CAPABILITY


class TestBulkDefaultOnly:
    def test_short_instruction_under_threshold_routes_local(self) -> None:
        policy = RoutePolicy(bulk_threshold_chars=200)
        provider, reason = evaluate("short task", policy)
        assert provider == "local"
        assert reason == RoutingDecision.BULK_DEFAULT

    def test_instruction_exactly_at_threshold_routes_local(self) -> None:
        policy = RoutePolicy(bulk_threshold_chars=10)
        provider, reason = evaluate("0123456789", policy)  # exactly 10 chars
        assert provider == "local"
        assert reason == RoutingDecision.BULK_DEFAULT

    def test_instruction_over_threshold_falls_through_to_conductor(self) -> None:
        policy = RoutePolicy(bulk_threshold_chars=5)
        provider, reason = evaluate(
            "this instruction is longer than five chars", policy
        )
        assert provider == "__conductor__"
        assert reason == RoutingDecision.CONDUCTOR_DEFAULT


class TestNoMatch:
    def test_long_instruction_no_patterns_falls_through_to_conductor(self) -> None:
        policy = RoutePolicy(bulk_threshold_chars=5)
        provider, reason = evaluate(
            "a fairly long instruction with no patterns", policy
        )
        assert provider == "__conductor__"
        assert reason == RoutingDecision.CONDUCTOR_DEFAULT


class TestPrecedence:
    def test_privacy_beats_capability(self) -> None:
        """An instruction matching BOTH privacy and capability patterns must
        route privacy -- privacy is checked first and is unconditional."""
        policy = RoutePolicy(
            privacy_patterns=["*secret*"],
            capability_patterns=["*complex*"],
        )
        provider, reason = evaluate("a complex task involving a secret", policy)
        assert provider == "local"
        assert reason == RoutingDecision.PRIVACY

    def test_capability_beats_bulk_default(self) -> None:
        """A SHORT instruction (would qualify for RT-5's bulk default) that
        ALSO matches a capability pattern must route to capability (claude),
        not bulk default (local)."""
        policy = RoutePolicy(
            capability_patterns=["*complex*"],
            bulk_threshold_chars=200,
        )
        provider, reason = evaluate(
            "a complex bug", policy
        )  # short AND capability-matching
        assert provider == "claude"
        assert reason == RoutingDecision.CAPABILITY

    def test_privacy_beats_bulk_default(self) -> None:
        policy = RoutePolicy(
            privacy_patterns=["*secret*"],
            bulk_threshold_chars=200,
        )
        provider, reason = evaluate("a secret", policy)  # short AND privacy-matching
        assert provider == "local"
        assert reason == RoutingDecision.PRIVACY

    def test_all_three_configured_privacy_wins(self) -> None:
        policy = RoutePolicy(
            privacy_patterns=["*secret*"],
            capability_patterns=["*complex*"],
            bulk_threshold_chars=200,
        )
        provider, reason = evaluate("a complex secret task", policy)
        assert provider == "local"
        assert reason == RoutingDecision.PRIVACY


class TestPatternMatching:
    def test_invalid_regex_pattern_does_not_crash(self) -> None:
        """A pattern that's invalid regex (but not a glob match either) is
        skipped silently, not raised -- policy evaluation must never crash
        on a malformed pattern."""
        policy = RoutePolicy(privacy_patterns=["[unclosed"])
        provider, reason = evaluate("some instruction", policy)
        assert reason != RoutingDecision.PRIVACY  # pattern didn't match, no crash

    def test_empty_pattern_lists_never_match(self) -> None:
        policy = RoutePolicy()
        provider, reason = evaluate("anything at all, short", policy)
        assert (
            reason == RoutingDecision.BULK_DEFAULT
        )  # falls through, not privacy/capability
