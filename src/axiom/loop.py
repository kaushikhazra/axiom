"""
Master PRAO loop — PraoLoop.

Owns the perceive→reason→act→observe iteration and all stop conditions.
Imports axiom.interfaces only — zero provider imports (port-adapter seam proof).

M2: Wraps each PRAO phase boundary with record_phase() context managers when
run_id and provider_kind are supplied (injected by the composition root via
ObservabilityFaculty.new_run()). When omitted, the loop runs without tracing —
this preserves backward compatibility with direct callers (tests, CLI) that do
not wire the observability faculty.

M3: memory: MemoryPort is constitutive — always required. The loop:
  - calls assemble_context() at Perceive (stored on loop-local variable)
  - calls append_unit() at RESPOND/FINISH exit (working-context write path)
  - awaits reinforce() for recalled memory IDs

Import boundary rule (design.md §10): loop.py imports ONLY
axiom.observability.record (the record_phase context manager) and
axiom.memory.port / axiom.memory.models. It does not import faculty.py,
registry.py, processors.py, any sink, or any adapter.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
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
from axiom.memory.models import ConversationUnit
from axiom.memory.port import MemoryPort

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
        memory: MemoryPort,
    ) -> None:
        self._perceive = perceive
        self._reason = reason
        self._act = act
        self._observe = observe
        self._max_cycles = max_cycles
        self._memory = memory
        # B4 fix: session-scoped monotonically increasing turn counter.
        # Incremented at Observe (after append_unit) on every RespondIntent or FinishIntent.
        # Never reset between run() calls so turn_index is unique across the session.
        self._turn_index: int = 0

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

        M3: Delegates to asyncio.run(_run_async()) so the async memory calls
        (assemble_context, append_unit, reinforce) can be awaited properly.
        asyncio.run is safe to call from sync context and is torn down cleanly
        after each call.
        """
        return asyncio.run(self._run_async(user_input, run_id, provider_kind))

    async def _run_async(
        self,
        user_input: str,
        run_id: str | None = None,
        provider_kind: str = "KIND_A",
    ) -> tuple[str, RunState]:
        """Async implementation of the PRAO loop.

        Same logic as the original run() but with await-able memory calls at
        Perceive (assemble_context) and at RESPOND/FINISH exit (append_unit +
        fire-and-forget reinforce).
        """
        run_state = RunState(
            user_input=user_input,
            history=[],
            cycle_count=0,
            spawn_count=0,
        )

        # M3: assemble context once per user turn at the Perceive phase.
        # Memory is constitutive — always present; no None guard.
        assembled_context = await self._memory.assemble_context(user_input)
        recalled_ids = [r.id for r in assembled_context.cognitive_memories]
        # B1 fix: wire assembled context into run_state so perceive() renders it
        # into the prompt — cognitive_memories as "Additional Context", working_context
        # as "Previous Conversations". Without this, the context was computed and dropped.
        run_state.memory_context = assembled_context

        with _maybe_record("run", run_id, provider_kind):
            while True:
                with _maybe_record("perceive", run_id, provider_kind):
                    context = self._perceive.perceive(run_state)

                with _maybe_record("reason", run_id, provider_kind):
                    run_state.spawn_count += 1
                    intent = self._reason.reason(context)

                if isinstance(intent, RespondIntent):
                    # Memory is constitutive — always present; no None guard.
                    unit = ConversationUnit(
                        user_text=user_input,
                        agent_text=intent.text,
                        turn_index=self._turn_index,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await self._memory.append_unit(unit)
                    # B2 fix: await reinforce directly instead of create_task so the
                    # work completes before asyncio.run() teardown cancels pending tasks.
                    # B4 fix: use session-scoped self._turn_index instead of local var.
                    if recalled_ids:
                        await self._memory.reinforce(recalled_ids)
                    self._turn_index += 1
                    return (intent.text, run_state)

                if isinstance(intent, FinishIntent):
                    # Memory is constitutive — always present; no None guard.
                    unit = ConversationUnit(
                        user_text=user_input,
                        agent_text="",
                        turn_index=self._turn_index,
                        timestamp=datetime.now(timezone.utc),
                    )
                    await self._memory.append_unit(unit)
                    self._turn_index += 1
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
