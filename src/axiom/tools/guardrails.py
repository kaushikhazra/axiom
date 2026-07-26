"""
Guardrails GATE — the cross-cutting call-point named in architecture.md
("Before Act ... approval gate on consequential actions"), implemented here
as a plain, provider-agnostic component. Not a port: both adapters import
this module directly, the same way both would import a shared utility.

Single source of truth for SAFE vs DESTRUCTIVE classification (design.md D2) --
read by ToolRegistry (KIND-A dispatch) and by ClaudeAdapter's PreToolUse
hook callback (KIND-B dispatch). Never duplicated per adapter.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Callable

logger = logging.getLogger("axiom.tools")

# Axiom's own tools (KIND-A, registry.py) + Claude's native tools (KIND-B).
# A tool name not in this set is SAFE by default -- deliberately: the set
# names what's dangerous, not what's permitted, so adding a new SAFE tool
# (e.g. a future read-only Axiom tool) requires no change here.
DESTRUCTIVE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "write_file",
        "run_shell",
        "Bash",
        "Write",
        "Edit",
    }
)


class Classification(Enum):
    SAFE = auto()
    DESTRUCTIVE = auto()


def _cli_prompt_approval(tool_name: str, arguments: dict) -> bool:
    """Default approval UX: print the call, read a y/n from stdin.

    Mirrors Claude Code's own permission-prompt shape. Writes to stderr so
    it never pollutes stdout the way CLI response text does (interface/cli.py
    prints only agent.run()'s return value to stdout).
    """
    import sys

    print(f"\n[axiom] approval required -- tool: {tool_name}", file=sys.stderr)
    print(f"[axiom] arguments: {arguments!r}", file=sys.stderr)
    print("[axiom] allow? [y/N] ", end="", file=sys.stderr, flush=True)
    answer = sys.stdin.readline().strip().lower()
    return answer in ("y", "yes")


class GuardrailsGate:
    """Classify a tool call and, for DESTRUCTIVE calls, gate it on approval.

    auto_approve=True (wired from --auto-approve-tools) skips the *prompt*,
    not the *classification* or the *audit log* -- every DESTRUCTIVE call is
    still logged at DEBUG (AC-07.4).
    """

    def __init__(
        self,
        auto_approve: bool = False,
        approval_fn: Callable[[str, dict], bool] = _cli_prompt_approval,
    ) -> None:
        self._auto_approve = auto_approve
        self._approval_fn = approval_fn

    def classify(self, tool_name: str) -> Classification:
        return (
            Classification.DESTRUCTIVE
            if tool_name in DESTRUCTIVE_TOOL_NAMES
            else Classification.SAFE
        )

    def request_approval(self, tool_name: str, arguments: dict) -> bool:
        """Blocking call -- the caller is responsible for thread-bridging
        (design.md D10) when invoked from async context."""
        if self._auto_approve:
            logger.debug(
                "[GUARDRAILS_AUTO_APPROVE] tool=%s args=%r", tool_name, arguments
            )
            return True

        approved = self._approval_fn(tool_name, arguments)
        logger.debug(
            "[GUARDRAILS_%s] tool=%s args=%r",
            "APPROVED" if approved else "DENIED",
            tool_name,
            arguments,
        )
        return approved

    def check(self, tool_name: str, arguments: dict) -> bool:
        """Convenience for KIND-A dispatch: classify, then approve if needed.
        Returns True iff execution may proceed."""
        if self.classify(tool_name) is Classification.SAFE:
            return True
        return self.request_approval(tool_name, arguments)
