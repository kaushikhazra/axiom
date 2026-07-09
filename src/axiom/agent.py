"""
Core assembly / composition root.

Wires persona + ClaudeAdapter + PraoLoop + observability timing.
Exposes a clean Agent.run(user_input: str) -> str API to the interface layer.

M1_ALLOWED_TOOLS: ["Bash", "WebSearch"]
WebSearch is required for the M1 web-search acceptance test (MPP-3/W5).
"""

from __future__ import annotations

import logging

from axiom import persona as persona_pkg
from axiom.interfaces import AdapterError, MaxCyclesExceededError
from axiom.loop import PraoLoop
from axiom.observability import timing
from axiom.providers.claude_adapter import ClaudeAdapter

# Tool allowlist for act() queries — single source of truth (§7.3).
# WebSearch added for the M1 web-search acceptance test (MPP-3/W5).
M1_ALLOWED_TOOLS: list[str] = ["Bash", "WebSearch"]

_axiom_logger = logging.getLogger("axiom")


def _configure_debug_logging() -> None:
    """Configure the axiom logger to emit DEBUG records to stderr.

    Called once at startup when Agent(debug=True). Not a global mutation —
    only the 'axiom' logger hierarchy is affected.

    Idempotent: if the logger already has handlers (a second Agent(debug=True)
    in the same process), the addHandler call is skipped so DEBUG records are
    not duplicated (e.g. [M1 Latency] lines appear exactly once per turn).
    """
    _axiom_logger.setLevel(logging.DEBUG)
    if not _axiom_logger.handlers:
        handler = logging.StreamHandler()  # writes to sys.stderr
        handler.setLevel(logging.DEBUG)
        _axiom_logger.addHandler(handler)


class Agent:
    """Fully assembled Axiom agent for one-turn interactions.

    Composition root: loads persona, constructs the chosen adapter, wires PraoLoop.
    Wraps loop execution via timing.timed_run for latency measurement.
    """

    def __init__(self, debug: bool = False, provider: str = "claude") -> None:
        """Wire the composition root.

        Args:
            debug: When True, configures the 'axiom' logger to emit DEBUG records
                   to stderr. Constructor parameter — not an env-var or global mutation.
            provider: Which adapter to use — "claude" (default, M1 behaviour) or
                      "local" (LiteLLM + Ollama via LocalAdapter). LocalAdapter is
                      imported lazily inside the "local" branch so that Claude-only
                      installs never pay the litellm import cost.
        """
        if debug:
            _configure_debug_logging()

        persona_text = persona_pkg.load()

        if provider == "local":
            from axiom.providers.local_adapter import LocalAdapter  # noqa: PLC0415 (lazy)

            adapter = LocalAdapter(persona=persona_text)
        elif provider == "claude":
            adapter = ClaudeAdapter(
                persona=persona_text, allowed_tools=M1_ALLOWED_TOOLS
            )
        else:
            raise ValueError(f"unknown provider: {provider!r}")

        self._loop = PraoLoop(
            perceive=adapter,
            reason=adapter,
            act=adapter,
            observe=adapter,
            max_cycles=10,
        )

    def run(self, user_input: str) -> str:
        """Execute one user turn. Returns the agent's response string.

        On MaxCyclesExceededError or AdapterError (re-raised by timed_run after
        the abort-path log), returns a user-visible "[Error: ...]" string.
        """
        try:
            response_text, _run_state = timing.timed_run(self._loop.run, user_input)
            return response_text
        except MaxCyclesExceededError as e:
            return f"[Error: max cycles exceeded — {e}]"
        except AdapterError as e:
            return f"[Error: {e}]"
