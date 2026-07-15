"""
FakeAdapter — in-memory implementation of all four PRAO port Protocols.

Second-adapter existence proof (MPP-4): confirms the port interface is implementable
without the Claude SDK. Used as the fast test enabler — no subprocess spawns,
no live SDK calls, deterministic and milliseconds-fast.

FakeMemory — in-memory stub satisfying MemoryPort. Used in tests that need to
wire PraoLoop without a real CognitiveMemoryAdapter. Returns empty AssembledContext
and records calls for assertion.
"""

from __future__ import annotations

from collections import deque

from axiom.interfaces import (
    AdapterError,
    Intent,
    RespondIntent,
    RunState,
)


class FakeAdapter:
    """Scripted in-memory adapter satisfying PerceivePort, ReasonPort, ActPort, ObservePort.

    Args:
        intents: Sequence of Intent objects returned from reason() in order.
                 When exhausted, returns RespondIntent(text="[FAKE] done").
        act_results: Sequence of str results returned from act() in order.
                     When exhausted, returns "[FAKE] act result".
        raise_on_reason: If True, reason() raises AdapterError on the first call
                         (for error-propagation tests).
    """

    def __init__(
        self,
        intents: list[Intent] | None = None,
        act_results: list[str] | None = None,
        raise_on_reason: bool = False,
    ) -> None:
        self._intents: deque[Intent] = deque(intents or [])
        self._act_results: deque[str] = deque(act_results or [])
        self._raise_on_reason = raise_on_reason

        # Call-tracking lists for test assertions
        self.perceive_calls: list[RunState] = []
        self.reason_calls: list[str] = []
        self.act_calls: list[str] = []
        self.observe_calls: list[tuple[str, RunState]] = []

    # ------------------------------------------------------------------
    # PerceivePort
    # ------------------------------------------------------------------

    def perceive(self, run_state: RunState) -> str:
        self.perceive_calls.append(run_state)
        return (
            f"[FAKE context] user={run_state.user_input!r} "
            f"cycle={run_state.cycle_count}"
        )

    # ------------------------------------------------------------------
    # ReasonPort
    # ------------------------------------------------------------------

    def reason(self, context: str) -> Intent:
        self.reason_calls.append(context)
        if self._raise_on_reason:
            raise AdapterError("fake adapter reason error")
        if self._intents:
            return self._intents.popleft()
        return RespondIntent(text="[FAKE] done")

    # ------------------------------------------------------------------
    # ActPort
    # ------------------------------------------------------------------

    def act(self, instruction: str) -> str:
        self.act_calls.append(instruction)
        if self._act_results:
            return self._act_results.popleft()
        return "[FAKE] act result"

    # ------------------------------------------------------------------
    # ObservePort
    # ------------------------------------------------------------------

    def observe(self, result: str, run_state: RunState) -> RunState:
        self.observe_calls.append((result, run_state))
        run_state.history.append(result)
        run_state.cycle_count += 1
        return run_state


class FakeMemory:
    """In-memory stub satisfying MemoryPort — for tests that wire PraoLoop directly.

    Returns empty AssembledContext from assemble_context() and is a no-op for
    append_unit/reinforce. Isolates loop contract tests from the real memory layer.
    """

    def __init__(self) -> None:
        self.appended_units: list = []
        self.reinforced_ids: list[list[str]] = []

    async def assemble_context(self, query: str, **kwargs):  # type: ignore[return]
        from axiom.memory.models import AssembledContext  # noqa: PLC0415

        return AssembledContext(working_context=[], cognitive_memories=[])

    async def append_unit(self, unit) -> None:
        self.appended_units.append(unit)

    async def reinforce(self, ids: list[str]) -> None:
        self.reinforced_ids.append(ids)
