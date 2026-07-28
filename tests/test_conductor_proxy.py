"""
Unit tests for axiom.router.conductor_proxy.ConductorProxy (M10, design.md
D4) -- delegates perceive/reason/act/observe/control_level to whichever
adapter Router.select_conductor() CURRENTLY resolves, so Agent.set_provider()
can switch providers at runtime without PraoLoop ever being touched.
"""

from __future__ import annotations

from axiom.router.conductor_proxy import ConductorProxy
from axiom.router.policy import RoutePolicy
from axiom.router.router import Router


class _FakeRoutableAdapter:
    def __init__(self, control_level: str, name: str) -> None:
        self.control_level = control_level
        self._name = name

    def act(self, instruction: str) -> str:
        return f"{self._name}-act:{instruction}"

    def reason(self, context: str) -> object:
        return f"{self._name}-reason:{context}"

    def perceive(self, run_state: object) -> str:
        return f"{self._name}-perceive"

    def observe(self, result: str, run_state: object) -> object:
        return f"{self._name}-observe:{result}"


def _router(forced_provider: str | None = None) -> Router:
    return Router(
        RoutePolicy(),
        {
            "claude": lambda: _FakeRoutableAdapter("KIND_B", "claude"),
            "local": lambda: _FakeRoutableAdapter("KIND_A", "local"),
        },
        forced_provider=forced_provider,
    )


class TestControlLevel:
    def test_reflects_default_claude_conductor(self) -> None:
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.control_level == "KIND_B"

    def test_reflects_forced_local_conductor(self) -> None:
        router = _router(forced_provider="local")
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.control_level == "KIND_A"

    def test_unknown_conductor_defaults_to_kind_a(self) -> None:
        """Before select_conductor() has ever run, conductor_provider is
        None -- ConductorProxy must not raise, per its _PROVIDER_KIND.get()
        fallback (mirrors agent.py's own pre-M10 default)."""
        router = _router()
        proxy = ConductorProxy(router)
        assert proxy.control_level == "KIND_A"


class TestDelegation:
    def test_perceive_delegates_to_current_conductor(self) -> None:
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.perceive(run_state=object()) == "claude-perceive"

    def test_reason_delegates_to_current_conductor(self) -> None:
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.reason("ctx") == "claude-reason:ctx"

    def test_act_delegates_to_current_conductor(self) -> None:
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.act("do it") == "claude-act:do it"

    def test_observe_delegates_to_current_conductor(self) -> None:
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.observe("result", run_state=object()) == "claude-observe:result"


class TestRuntimeSwitching:
    def test_proxy_follows_router_after_set_forced_provider_and_reselect(
        self,
    ) -> None:
        """The core guarantee D4 exists for: one ConductorProxy instance,
        constructed once, must reflect a LATER provider switch without
        being reconstructed -- this is what lets Agent hand the same proxy
        to PraoLoop at __init__ time and still support runtime switching."""
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)
        assert proxy.act("x") == "claude-act:x"

        router.set_forced_provider("local")
        router.select_conductor()  # Agent.set_provider() does this re-resolution

        assert proxy.act("x") == "local-act:x"
        assert proxy.control_level == "KIND_A"

    def test_committee_forced_provider_does_not_affect_conductor(self) -> None:
        """Router.select_conductor()'s own rule: "committee" only ever
        selects Workers, never the Conductor (falls through to the
        capability-preferred default, "claude"). ConductorProxy must not
        special-case this -- it's already handled by select_conductor()."""
        router = _router()
        router.select_conductor()
        proxy = ConductorProxy(router)

        router.set_forced_provider("committee")
        router.select_conductor()

        assert proxy.control_level == "KIND_B"
        assert proxy.act("x") == "claude-act:x"
