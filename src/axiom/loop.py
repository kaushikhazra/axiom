"""
Master PRAO loop — PraoLoop.

Owns the perceive→reason→act→observe iteration and all stop conditions.
Imports axiom.interfaces only — zero provider imports (port-adapter seam proof).

M2: Wraps each PRAO phase boundary with record_phase() context managers when
run_id and provider_kind are supplied (injected by the composition root via
ObservabilityFaculty.new_run()). When omitted, the loop runs without tracing —
this preserves backward compatibility with direct callers (tests, CLI) that do
not wire the observability faculty.

Import boundary rule (design.md §10): loop.py imports ONLY
axiom.observability.record (the record_phase context manager). It does not
import faculty.py, registry.py, processors.py, or any sink.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from axiom.interfaces import (
    ActIntent,
    ActPort,
    FinishIntent,
    MaxCyclesExceededError,
    ObservePort,
    PerceivePort,
    ReasonPort,
    RespondIntent,
    RunState,
)

MAX_CYCLES: int = 10  # module-level constant; overridable via constructor


@contextmanager
def _maybe_record(
    phase: str,
    run_id: str | None,
    provider_kind: str,
) -> Generator[None, None, None]:
    """Wrap a PRAO phase in record_phase() when run_id is provided; else no-op.

    Keeps loop.py's core flow readable without duplicating if-guards at every phase.
    """
    if run_id is None:
        yield
        return

    # Lazy import — OTel never loaded if observability is not wired
    from axiom.observability.record import record_phase  # noqa: PLC0415

    with record_phase(phase=phase, run_id=run_id, provider_kind=provider_kind):
        yield


class PraoLoop:
    """Executes the four-phase PRAO cycle for one user turn.

    The four-slot constructor preserves the ability to inject partial adapters in
    future milestones (e.g. a local vLLM for reason + ClaudeAdapter for act).
    All four parameters are satisfied by a single ClaudeAdapter instance in M1.
    """

    def __init__(
        self,
        perceive: PerceivePort,
        reason: ReasonPort,
        act: ActPort,
        observe: ObservePort,
        max_cycles: int = MAX_CYCLES,
    ) -> None:
        self._perceive = perceive
        self._reason = reason
        self._act = act
        self._observe = observe
        self._max_cycles = max_cycles

    def run(
        self,
        user_input: str,
        run_id: str | None = None,
        provider_kind: str = "KIND_A",
    ) -> tuple[str, RunState]:
        """Execute the PRAO loop for one user turn.

        Constructs initial RunState internally. Returns (response_text, run_state).
        - response_text is the agent reply string for RESPOND exits.
        - response_text is "" for FINISH exits.

        Args:
            user_input: The user's turn string.
            run_id: Optional UUID4 from ObservabilityFaculty.new_run(). When
                    provided, each PRAO phase is wrapped in a record_phase() span.
                    When None (default), loop runs without tracing.
            provider_kind: "KIND_A" or "KIND_B" — identifies the adapter family.
                           Used as an OTel attribute on every phase span.

        Raises:
            MaxCyclesExceededError: When cycle_count reaches max_cycles without a
                terminal intent. The timing utility in agent.py catches this and
                fires the abort-path log before re-raising.
            AdapterError: Propagated from adapter methods on SDK failure. Not caught
                here — propagates to agent.py via timing.timed_run.

        spawn_count tracks every reason() and act() dispatch made by the loop.
        Adapter-internal retries are NOT counted here (they are adapter-internal).
        """
        run_state = RunState(
            user_input=user_input,
            history=[],
            cycle_count=0,
            spawn_count=0,
        )

        with _maybe_record("run", run_id, provider_kind):
            while True:
                with _maybe_record("perceive", run_id, provider_kind):
                    context = self._perceive.perceive(run_state)

                with _maybe_record("reason", run_id, provider_kind):
                    run_state.spawn_count += 1
                    intent = self._reason.reason(context)

                if isinstance(intent, RespondIntent):
                    return (intent.text, run_state)

                if isinstance(intent, FinishIntent):
                    return ("", run_state)

                # intent == ACT — execute, observe, then loop back to perceive
                if not isinstance(intent, ActIntent):
                    raise TypeError(
                        f"reason() returned unexpected type {type(intent).__name__!r}; "
                        "expected ActIntent"
                    )

                with _maybe_record("act", run_id, provider_kind):
                    run_state.spawn_count += 1
                    result = self._act.act(intent.instruction)

                with _maybe_record("observe", run_id, provider_kind):
                    run_state = self._observe.observe(result, run_state)

                if run_state.cycle_count >= self._max_cycles:
                    raise MaxCyclesExceededError(
                        f"max cycles ({self._max_cycles}) exceeded without terminal intent"
                    )
