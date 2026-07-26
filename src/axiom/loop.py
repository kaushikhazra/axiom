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
  - awaits store() at RESPOND exit (cognitive tier — episodic exchange persist)
    Awaited (not create_task) so embed+insert completes before asyncio.run()
    teardown. Smart extraction is deferred to M8; M3 stores the full exchange.

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
    AdapterError,
    FinishIntent,
    MaxCyclesExceededError,
    ObservePort,
    PerceivePort,
    ReasonPort,
    RespondIntent,
    RunState,
    UseSkillIntent,
)
from axiom.memory.models import ConversationUnit
from axiom.memory.port import MemoryPort
from axiom.router.router import Router
from axiom.skills.port import SkillNotFoundError, SkillsPort

MAX_CYCLES: int = 10  # module-level constant; overridable via constructor


@contextmanager
def _maybe_record(
    phase: str,
    run_id: str | None,
    provider_kind: str,
) -> Generator[object, None, None]:
    """Wrap a PRAO phase in record_phase() when run_id is provided; else no-op.

    Keeps loop.py's core flow readable without duplicating if-guards at every phase.

    M6: yields the underlying Span (was bare `yield` before) so callers can
    set attributes discovered after the phase starts (e.g. RT-7's
    axiom.control_level, known only once the Router has selected a Worker).
    Yields None when run_id is omitted (no-op path) or when observability
    isn't wired -- callers must guard with `if span is not None`.
    """
    if run_id is None:
        yield None
        return

    # Lazy import — OTel never loaded if observability is not wired
    from axiom.observability.record import record_phase  # noqa: PLC0415

    with record_phase(phase=phase, run_id=run_id, provider_kind=provider_kind) as span:
        yield span


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
        observe: ObservePort,
        memory: MemoryPort,
        skills: SkillsPort,
        router: Router,
        max_cycles: int = MAX_CYCLES,
    ) -> None:
        self._perceive = perceive
        self._reason = reason
        self._observe = observe
        self._max_cycles = max_cycles
        self._memory = memory
        self._skills = skills
        self._router = router
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
                # M5: discovery catalog refreshed every cycle (not once per
                # turn like memory_context) so a skill authored mid-run via
                # ACT is picked up on the very next Perceive (design.md D3).
                run_state.skills_catalog = await asyncio.to_thread(
                    self._skills.list_skills
                )

                with _maybe_record("perceive", run_id, provider_kind):
                    context = await asyncio.to_thread(
                        self._perceive.perceive, run_state
                    )

                # M5: skill_activation_note is one-shot -- rendered into the
                # context just built, then cleared so it doesn't repeat on
                # subsequent cycles (design.md D5a).
                run_state.skill_activation_note = None

                with _maybe_record("reason", run_id, provider_kind):
                    run_state.spawn_count += 1
                    intent = await asyncio.to_thread(self._reason.reason, context)

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
                    # Finding 3 fix: persist each completed exchange to the cognitive tier
                    # as an episodic memory. Awaited (not create_task) so the embed+insert
                    # completes before asyncio.run() teardown — the same teardown-
                    # cancellation hazard fixed by B2 for reinforce. Smart extraction /
                    # distillation of what to store is deferred to M8; M3 stores the full
                    # exchange so cross-session learning is real from the first session.
                    exchange_content = f"User: {user_input}\nAgent: {intent.text}"
                    await self._memory.store(exchange_content, memory_type="episodic")
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

                if isinstance(intent, UseSkillIntent):
                    # M5: skill activation is loop-owned bookkeeping, not a
                    # provider Act call -- own phase label ("use_skill", not
                    # "act"), own result channel (skill_activation_note, not
                    # run_state.history -- see design.md D5a for why), own
                    # dedup check, and cycle_count incremented directly (no
                    # ObservePort.observe() call: that contract is
                    # specifically "append an ACT result to history," which
                    # this deliberately does not do). spawn_count is
                    # deliberately NOT incremented here -- it tracks provider
                    # query() dispatches, and skill activation makes none.
                    with _maybe_record("use_skill", run_id, provider_kind):
                        already_active_names = {s.name for s in run_state.active_skills}
                        if intent.skill_name in already_active_names:
                            run_state.skill_activation_note = (
                                f"[SKILL ALREADY ACTIVE] {intent.skill_name}"
                            )
                        else:
                            try:
                                content = await asyncio.to_thread(
                                    self._skills.get_skill, intent.skill_name
                                )
                                run_state.active_skills.append(content)
                                run_state.skill_activation_note = (
                                    f"[SKILL ACTIVATED] {intent.skill_name} -- "
                                    "its full instructions are now available "
                                    f"below under [ACTIVE SKILL: {intent.skill_name}]. "
                                    "Use them to inform your next ACT or RESPOND."
                                )
                            except SkillNotFoundError as exc:
                                run_state.skill_activation_note = f"[SKILL ERROR] {exc}"
                        run_state.cycle_count += 1

                    if run_state.cycle_count >= self._max_cycles:
                        raise MaxCyclesExceededError(
                            f"max cycles ({self._max_cycles}) exceeded without terminal intent"
                        )
                    continue

                # intent == ACT — execute, observe, then loop back to perceive
                if not isinstance(intent, ActIntent):
                    raise TypeError(
                        f"reason() returned unexpected type {type(intent).__name__!r}; "
                        "expected ActIntent"
                    )

                # M7: Router checks committee mode first (OR-1/OR-2) -- None
                # means "not triggered", falls through to M6's single-dispatch
                # path below, completely unmodified.
                committee = self._router.select_committee(intent.instruction)

                if committee is not None:
                    # M7: committee dispatch -- OR-3/OR-4/OR-6/OR-7.
                    with _maybe_record("act", run_id, provider_kind) as act_span:
                        if act_span is not None:
                            act_span.set_attribute(
                                "axiom.router.committee_size", len(committee)
                            )
                            act_span.set_attribute(
                                "axiom.router.providers",
                                ",".join(m.provider_name for m in committee),
                            )

                        run_state.spawn_count += len(
                            committee
                        )  # OR-3: one real dispatch per member
                        parts: list[str] = []
                        any_succeeded = False
                        for member in committee:
                            try:
                                member_result = await asyncio.to_thread(
                                    member.adapter.act, intent.instruction
                                )
                                parts.append(
                                    f"[{member.provider_name}]: {member_result}"
                                )
                                any_succeeded = True
                            except AdapterError as exc:
                                # OR-6: note the failure, keep going -- no
                                # fallback substitution (OR-7).
                                parts.append(
                                    f"[{member.provider_name}]: FAILED — {exc}"
                                )

                        if not any_succeeded:
                            # OR-6: a committee where nobody answered is not success.
                            raise AdapterError(
                                f"all {len(committee)} committee members failed"
                            )
                        result = "\n".join(parts)

                    with _maybe_record("observe", run_id, provider_kind):
                        run_state = await asyncio.to_thread(
                            self._observe.observe, result, run_state
                        )

                else:
                    # M6: Router selects the Worker fresh for this dispatch (RT-3)
                    # -- may differ from the Conductor (self._reason's provider).
                    selection = self._router.select_worker(intent.instruction)
                    with _maybe_record("act", run_id, provider_kind) as act_span:
                        if act_span is not None:
                            # Record what was ATTEMPTED before dispatch so a hard
                            # failure (no fallback, or fallback also fails) still
                            # carries routing attribution in the trace.
                            act_span.set_attribute(
                                "axiom.control_level", selection.control_level
                            )
                            act_span.set_attribute(
                                "axiom.router.provider", selection.provider_name
                            )

                        run_state.spawn_count += 1
                        try:
                            result = await asyncio.to_thread(
                                selection.adapter.act, intent.instruction
                            )
                            final_selection = selection
                        except AdapterError:
                            if not selection.fallback_allowed:
                                raise
                            fallback = self._router.select_fallback_worker(
                                selection.provider_name
                            )
                            if fallback is None:
                                raise
                            run_state.spawn_count += 1  # a second loop-dispatched call
                            result = await asyncio.to_thread(
                                fallback.adapter.act, intent.instruction
                            )
                            final_selection = fallback

                        if act_span is not None and final_selection is not selection:
                            # A fallback occurred -- overwrite with the ACTUAL outcome.
                            act_span.set_attribute(
                                "axiom.control_level", final_selection.control_level
                            )
                            act_span.set_attribute(
                                "axiom.router.provider", final_selection.provider_name
                            )

                    with _maybe_record("observe", run_id, provider_kind):
                        run_state = await asyncio.to_thread(
                            self._observe.observe, result, run_state
                        )

                if run_state.cycle_count >= self._max_cycles:
                    raise MaxCyclesExceededError(
                        f"max cycles ({self._max_cycles}) exceeded without terminal intent"
                    )
