"""
Tools port contract — the adapter-side seam for Axiom's structured tools.

Not a loop-level port: loop.py and interfaces.py import nothing from this
package. ToolsPort is consumed by provider adapters, the same relationship
they already have with claude_agent_sdk / smolagents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    destructive: bool  # mirrors GuardrailsGate.classify(name) at registration time


@dataclass
class ToolResult:
    output: str
    error: str | None = None
    denied: bool = False


class ToolsPort(Protocol):
    def list_tools(self) -> list[ToolSpec]:
        """Return the specs of every tool this registry exposes."""
        ...

    def execute(self, name: str, arguments: dict) -> ToolResult:
        """Run a tool by name. Never raises — failures and denials are
        encoded in the returned ToolResult (error / denied fields)."""
        ...
