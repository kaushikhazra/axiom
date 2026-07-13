"""
Core assembly / composition root.

Wires persona + ClaudeAdapter + PraoLoop + observability timing.
Exposes a clean Agent.run(user_input: str) -> str API to the interface layer.

M1_ALLOWED_TOOLS: ["Bash", "WebSearch"]
WebSearch is required for the M1 web-search acceptance test (MPP-3/W5).
"""

from __future__ import annotations

import logging
from pathlib import Path

from axiom import persona as persona_pkg
from axiom.interfaces import AdapterError, MaxCyclesExceededError
from axiom.loop import PraoLoop
from axiom.observability import timing
from axiom.providers.claude_adapter import ClaudeAdapter

# Tool allowlist for act() queries — single source of truth (§7.3).
# WebSearch added for the M1 web-search acceptance test (MPP-3/W5).
M1_ALLOWED_TOOLS: list[str] = ["Bash", "WebSearch"]

# Maps provider name to OTel provider_kind label used in trace records.
_PROVIDER_KIND: dict[str, str] = {
    "claude": "KIND_B",
    "local": "KIND_A",
}

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

    M2: When observe=True, constructs an ObservabilityFaculty and threads the
    generated run_id into PraoLoop.run() so all PRAO phase-boundary _maybe_record
    call-points fire and emit spans to the JSONL FileSink.
    """

    def __init__(
        self,
        debug: bool = False,
        provider: str = "claude",
        observe: bool = False,
    ) -> None:
        """Wire the composition root.

        Args:
            debug: When True, configures the 'axiom' logger to emit DEBUG records
                   to stderr. Constructor parameter — not an env-var or global mutation.
            provider: Which adapter to use — "claude" (default, M1 behaviour) or
                      "local" (LiteLLM + Ollama via LocalAdapter). LocalAdapter is
                      imported lazily inside the "local" branch so that Claude-only
                      installs never pay the litellm import cost.
            observe: When True, constructs ObservabilityFaculty and wires run_id into
                     the loop so phase spans are emitted to ~/.axiom/traces/<run_id>.jsonl.
                     Off by default — backward compatible; no OTel cost unless enabled.
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

        self._provider_kind: str = _PROVIDER_KIND.get(provider, "KIND_A")

        # M2 observability — off by default; wired only when observe=True.
        # OTel imports are confined to the faculty; nothing leaks into this module.
        self._faculty = None
        self._run_id: str | None = None
        self._trace_path: Path | None = None

        if observe:
            from axiom.observability.config import ObservabilityConfig  # noqa: PLC0415
            from axiom.observability.faculty import ObservabilityFaculty  # noqa: PLC0415

            config = ObservabilityConfig(tui_enabled=False)
            faculty = ObservabilityFaculty(config=config)
            run_id = faculty.new_run()

            self._faculty = faculty
            self._run_id = run_id
            # Faculty registers its own atexit/SIGTERM handlers; shutdown is also
            # called here explicitly so callers driving multiple turns have a clean path.
            self._trace_path = config.trace_dir / f"{run_id}.jsonl"

    @property
    def trace_path(self) -> Path | None:
        """Path of the JSONL trace file for this run, or None when observability is off."""
        return self._trace_path

    def run(self, user_input: str) -> str:
        """Execute one user turn. Returns the agent's response string.

        When observe=True was passed at construction, threads run_id into
        PraoLoop.run() so every PRAO phase boundary emits an OTel span that is
        flushed to the JSONL trace file.

        On MaxCyclesExceededError or AdapterError (re-raised by timed_run after
        the abort-path log), returns a user-visible "[Error: ...]" string.

        Shutdown: when observability is active, calls faculty.shutdown() in the
        finally block so the FileSink drainer receives its sentinel promptly and
        the process exits cleanly without waiting for the atexit fallback.
        faculty.shutdown() is idempotent — the atexit handler registered at
        construction becomes a no-op after this call.
        """
        try:
            if self._run_id is not None:
                run_id = self._run_id
                provider_kind = self._provider_kind
                response_text, _run_state = timing.timed_run(
                    lambda u: self._loop.run(
                        u, run_id=run_id, provider_kind=provider_kind
                    ),
                    user_input,
                )
            else:
                response_text, _run_state = timing.timed_run(self._loop.run, user_input)
            return response_text
        except MaxCyclesExceededError as e:
            return f"[Error: max cycles exceeded — {e}]"
        except AdapterError as e:
            return f"[Error: {e}]"
        finally:
            if self._faculty is not None:
                self._faculty.shutdown()
