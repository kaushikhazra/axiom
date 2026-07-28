"""
ConductorProxy — M10 (design.md D4): lets Agent.set_provider() switch the
Conductor at runtime without PraoLoop ever knowing a switch happened.

Duck-types the perceive/reason/act/observe + control_level surface Router's
own RoutableAdapter Protocol already defines, delegating every call to
whichever adapter Router.select_conductor() currently resolves. Constructed
once at Agent.__init__ time and handed to PraoLoop instead of a raw adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from axiom.router.router import Router

# Maps provider name to OTel provider_kind label. agent.py used to keep its
# own copy of this table; it now reads provider_kind dynamically via
# self._conductor_proxy.control_level instead (this is the single source),
# since set_provider() can change the Conductor mid-session.
_PROVIDER_KIND: dict[str, str] = {
    "claude": "KIND_B",
    "local": "KIND_A",
}


@dataclass
class ConductorProxy:
    """Not itself Router-typed as RoutableAdapter -- it deliberately has no
    .act() dispatch responsibility of its own; it only ever forwards to the
    real, currently-selected Conductor adapter."""

    router: "Router"

    @property
    def control_level(self) -> str:
        return _PROVIDER_KIND.get(self.router.conductor_provider, "KIND_A")

    def perceive(self, run_state: object) -> str:
        return self.router.select_conductor().perceive(run_state)

    def reason(self, context: str) -> object:
        return self.router.select_conductor().reason(context)

    def act(self, instruction: str) -> str:
        return self.router.select_conductor().act(instruction)

    def observe(self, result: str, run_state: object) -> object:
        return self.router.select_conductor().observe(result, run_state)
