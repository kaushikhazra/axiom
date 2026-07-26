"""
Core assembly / composition root.

Wires persona + ClaudeAdapter + PraoLoop + observability timing.
Exposes a clean Agent.run(user_input: str) -> str API to the interface layer.

CLAUDE_SAFE_TOOLS: ["WebSearch"] (M4 renamed M1_ALLOWED_TOOLS; WebSearch is
required for the M1 web-search acceptance test, MPP-3/W5). "Bash" is
deliberately NOT bare-listed here as of M4 -- the PreToolUse Guardrails GATE
(ClaudeAdapter._gate_hook) is now the real guardrail and fires for every
tool call regardless of this list's contents; this list is minimal-privilege
practice, not the load-bearing mechanism (design.md D4).
"""

from __future__ import annotations

import logging
from pathlib import Path

from axiom import persona as persona_pkg
from axiom.interfaces import AdapterError, MaxCyclesExceededError
from axiom.loop import PraoLoop
from axiom.observability import timing
from axiom.providers.claude_adapter import ClaudeAdapter
from axiom.router.policy import RoutePolicy
from axiom.router.router import Router, RouterError
from axiom.tools.guardrails import GuardrailsGate

# Tool allowlist for act() queries — single source of truth (§7.3).
# WebSearch added for the M1 web-search acceptance test (MPP-3/W5).
CLAUDE_SAFE_TOOLS: list[str] = ["WebSearch"]

# Maps provider name to OTel provider_kind label used in trace records.
_PROVIDER_KIND: dict[str, str] = {
    "claude": "KIND_B",
    "local": "KIND_A",
}

_axiom_logger = logging.getLogger("axiom")


def _make_claude_adapter(persona_text: str, gate: GuardrailsGate) -> ClaudeAdapter:
    """M6: Router adapter factory -- zero-arg callable, called lazily at most
    once per session (Router caches the result)."""
    return ClaudeAdapter(
        persona=persona_text, allowed_tools=CLAUDE_SAFE_TOOLS, gate=gate
    )


def _make_local_adapter(
    persona_text: str,
    working_dir: Path,
    gate: GuardrailsGate,
    ollama_host: str | None,
):
    """M6: Router adapter factory. Imports LocalAdapter lazily (deferred,
    same as the pre-M6 if/elif branch) so Claude-only installs never pay
    the smolagents/litellm import cost unless Router actually needs a
    local adapter (policy match, or explicit --provider local)."""
    from axiom.providers.local_adapter import LocalAdapter  # noqa: PLC0415 (lazy)

    kwargs = {}
    if ollama_host is not None:
        kwargs["ollama_api_base"] = ollama_host
    return LocalAdapter(
        persona=persona_text, working_dir=working_dir, gate=gate, **kwargs
    )


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

    M3: CognitiveMemoryAdapter is always constructed — memory is constitutive, not
    optional. Imports are lazy so installs without sentence-transformers still work
    in unit-test contexts where the memory path is stubbed.
    """

    def __init__(
        self,
        debug: bool = False,
        provider: str | None = None,
        observe: bool = False,
        memory_config: object = None,
        ollama_host: str | None = None,
        working_dir: str | Path | None = None,
        auto_approve_tools: bool = False,
        skills_dir: str | Path | None = None,
    ) -> None:
        """Wire the composition root.

        Args:
            debug: When True, configures the 'axiom' logger to emit DEBUG records
                   to stderr. Constructor parameter — not an env-var or global mutation.
            provider: M6 — "claude"/"local" explicitly FORCES that provider for
                      both Conductor and every Worker dispatch, bypassing Router's
                      policy evaluation entirely (RT-8). M7 — "committee" FORCES
                      every Worker dispatch to every configured provider at once
                      (the Conductor itself still resolves to "claude", the
                      capability-preferred default -- committee mode only ever
                      affects Worker selection, OR-1). None (default) means "no
                      preference" — Router's policy engine (privacy/cost/capability/
                      consortium, RT-4/5/6, OR-2) actually decides. LocalAdapter is
                      imported lazily so Claude-only installs never pay the litellm
                      import cost unless a local adapter is actually needed.
            ollama_host: Optional Ollama API base URL, e.g. "http://192.168.0.235:11434".
                         Only used when provider="local"; ignored otherwise. Defaults to
                         LocalAdapter's own localhost default when None.
            observe: When True, constructs ObservabilityFaculty and wires run_id into
                     the loop so phase spans are emitted to ~/.axiom/traces/<run_id>.jsonl.
                     Off by default — backward compatible; no OTel cost unless enabled.
            memory_config: Optional MemoryConfig instance. When None, a default
                           MemoryConfig() is constructed. Callers (e.g., tests) may
                           pass an isolated config with a tmp storage_path.
            working_dir: M4 — root directory Axiom's own file/shell tools (KIND-A
                         only) are scoped to. Defaults to the process cwd when None.
            auto_approve_tools: M4 — when True, GuardrailsGate.request_approval()
                                 returns True unconditionally instead of prompting.
                                 Off by default — the safe, prompting behavior is
                                 the default (AC-07.3).
            skills_dir: M5 — root directory SkillsRegistry discovers SKILL.md
                        directories under. Defaults to {working_dir}/skills
                        when None (SK-6).
        """
        if debug:
            _configure_debug_logging()

        # dryrun-code-1 W1: restore the input validation the old if/elif
        # block used to provide -- an invalid provider string should fail
        # loudly and immediately here, not deep inside Router construction.
        # M7 (dryrun-design-1 C1): "committee" added -- without it here,
        # --provider committee would raise before Router is even constructed.
        if provider is not None and provider not in ("claude", "local", "committee"):
            raise ValueError(f"unknown provider: {provider!r}")

        persona_text = persona_pkg.load()

        # M4: GuardrailsGate is shared by whichever adapter is constructed below
        # — the single classification table + approval seam for both providers
        # (design.md D2).
        resolved_working_dir = (
            Path(working_dir) if working_dir is not None else Path.cwd()
        )
        # M5: skills_dir defaults to {working_dir}/skills (SK-6) — mirrors
        # working_dir's own default-resolution pattern.
        resolved_skills_dir = (
            Path(skills_dir)
            if skills_dir is not None
            else resolved_working_dir / "skills"
        )
        gate = GuardrailsGate(auto_approve=auto_approve_tools)

        # M6: Router replaces the pre-M6 if/elif provider-selection block.
        # `provider` (None by default) maps directly to forced_provider --
        # None means "no preference, let policy decide" (RT-4/5/6 active);
        # "claude"/"local" forces that provider everywhere, unchanged CLI
        # contract for explicit usage (RT-8).
        router = Router(
            policy=RoutePolicy(),
            adapter_factories={
                "claude": lambda: _make_claude_adapter(persona_text, gate),
                "local": lambda: _make_local_adapter(
                    persona_text, resolved_working_dir, gate, ollama_host
                ),
            },
            forced_provider=provider,
        )
        conductor_adapter = router.select_conductor()  # RT-2: called exactly once

        # M3 memory — constitutive: always wired, never optional.
        # Lazy imports so installs without sentence-transformers still start when
        # the memory path is stubbed in tests.
        from axiom.memory.adapter import CognitiveMemoryAdapter  # noqa: PLC0415
        from axiom.memory.config import MemoryConfig  # noqa: PLC0415

        _mem_cfg = memory_config if memory_config is not None else MemoryConfig()
        self._memory_adapter = CognitiveMemoryAdapter(_mem_cfg)

        # M5 skills — loop-level port, constructed here the same way memory is.
        from axiom.skills.registry import SkillsRegistry  # noqa: PLC0415

        skills_registry = SkillsRegistry(skills_dir=resolved_skills_dir)

        self._loop = PraoLoop(
            perceive=conductor_adapter,
            reason=conductor_adapter,
            observe=conductor_adapter,
            max_cycles=10,
            memory=self._memory_adapter,
            skills=skills_registry,
            router=router,
        )

        # M6: derived from Router's chosen Conductor (public conductor_provider
        # property), not the raw `provider` string -- same value as before for
        # the common case, since Router's Conductor default is "claude" too.
        self._provider_kind: str = _PROVIDER_KIND.get(
            router.conductor_provider, "KIND_A"
        )

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
        except RouterError as e:
            # dryrun-code-1 B1: RouterError is a sibling of AdapterError (both
            # derive directly from Exception, not from each other) -- without
            # this branch it propagated uncaught, crashing the CLI with a raw
            # traceback instead of RT-4's promised "clear, typed error."
            return f"[Error: {e}]"
        finally:
            if self._faculty is not None:
                self._faculty.shutdown()
            # M3: consolidate + close memory at session end (loop already exited).
            # Memory is constitutive — always present; no None guard.
            import asyncio  # noqa: PLC0415

            try:
                asyncio.run(self._memory_adapter.consolidate())
            except Exception as exc:
                _axiom_logger.warning("Memory consolidation failed: %s", exc)
            # G1 fix: release storage file handle and embedding executor
            try:
                self._memory_adapter.close()
            except Exception as exc:
                _axiom_logger.warning("Memory close failed: %s", exc)
