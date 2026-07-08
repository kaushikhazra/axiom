"""
Master PRAO loop — PraoLoop.

Owns the perceive→reason→act→observe iteration and all stop conditions.
Imports axiom.interfaces only — zero provider imports (port-adapter seam proof).
"""

from __future__ import annotations

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

    def run(self, user_input: str) -> tuple[str, RunState]:
        """Execute the PRAO loop for one user turn.

        Constructs initial RunState internally. Returns (response_text, run_state).
        - response_text is the agent reply string for RESPOND exits.
        - response_text is "" for FINISH exits.

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

        while True:
            context = self._perceive.perceive(run_state)

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
            run_state.spawn_count += 1
            result = self._act.act(intent.instruction)
            run_state = self._observe.observe(result, run_state)

            if run_state.cycle_count >= self._max_cycles:
                raise MaxCyclesExceededError(
                    f"max cycles ({self._max_cycles}) exceeded without terminal intent"
                )
