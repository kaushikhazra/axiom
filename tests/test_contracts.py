"""
Phase-port contract tests — use FakeAdapter only (no live SDK spawns).

Test cases per the design §11 / task.md:
(a) RESPOND short-circuit: loop exits on first RESPOND, spawn_count=1, cycle_count=0
(b) ACT->RESPOND one cycle: correct state after one act cycle, spawn_count=3, cycle_count=1
(c) MAX_CYCLES breach: raises MaxCyclesExceededError after max_cycles act cycles
(d) AdapterError propagation: AdapterError from reason() propagates through the loop

Additional cases:
(e) FINISH intent: returns ("", run_state) with spawn_count=1, cycle_count=0
"""

from __future__ import annotations

import pytest

from axiom.interfaces import (
    ActIntent,
    AdapterError,
    FinishIntent,
    MaxCyclesExceededError,
    RespondIntent,
    UseSkillIntent,
)
from axiom.loop import PraoLoop
from axiom.router.router import WorkerSelection
from axiom.skills.port import SkillContent
from tests.fake_adapter import FakeAdapter, FakeMemory, FakeRouter, FakeSkills


def _make_loop(
    adapter: FakeAdapter,
    max_cycles: int = 10,
    skills: FakeSkills | None = None,
    router: FakeRouter | None = None,
) -> PraoLoop:
    """Helper: wire perceive/reason/observe to the same FakeAdapter instance.

    M3: memory is constitutive — always wired. FakeMemory is a no-op stub that
    satisfies MemoryPort without touching real storage or embeddings.
    M5: skills is constitutive too — FakeSkills defaults to an empty catalog
    (matching SkillsRegistry's own behavior for a missing/empty skills_dir).
    M6: router is constitutive too — defaults to a FakeRouter whose
    select_worker() always returns `adapter` itself, so every pre-M6 test
    asserting on adapter.act_calls keeps working unchanged; tests that need
    to exercise Router-specific behavior (per-cycle provider switching,
    fallback) pass their own FakeRouter.
    """
    if router is None:
        router = FakeRouter(default_worker=adapter)
    return PraoLoop(
        perceive=adapter,
        reason=adapter,
        observe=adapter,
        memory=FakeMemory(),
        skills=skills if skills is not None else FakeSkills(),
        router=router,
        max_cycles=max_cycles,
    )


# ---------------------------------------------------------------------------
# (a) RESPOND short-circuit
# ---------------------------------------------------------------------------


class TestRespondShortCircuit:
    """RESPOND intent on the first reason() call — no act() spawned."""

    def setup_method(self) -> None:
        self.adapter = FakeAdapter(intents=[RespondIntent(text="Hello back!")])
        self.loop = _make_loop(self.adapter)

    def test_returns_response_text(self) -> None:
        text, _state = self.loop.run("Hello")
        assert text == "Hello back!"

    def test_spawn_count_is_one(self) -> None:
        _text, state = self.loop.run("Hello")
        assert state.spawn_count == 1

    def test_cycle_count_is_zero(self) -> None:
        _text, state = self.loop.run("Hello")
        assert state.cycle_count == 0

    def test_act_not_called(self) -> None:
        self.loop.run("Hello")
        assert self.adapter.act_calls == []

    def test_user_input_preserved_in_state(self) -> None:
        _text, state = self.loop.run("Hello")
        assert state.user_input == "Hello"

    def test_history_is_empty(self) -> None:
        _text, state = self.loop.run("Hello")
        assert state.history == []

    def test_perceive_called_once(self) -> None:
        self.loop.run("Hello")
        assert len(self.adapter.perceive_calls) == 1

    def test_reason_called_once(self) -> None:
        self.loop.run("Hello")
        assert len(self.adapter.reason_calls) == 1


# ---------------------------------------------------------------------------
# (b) ACT -> RESPOND one cycle
# ---------------------------------------------------------------------------


class TestActRespondOneCycle:
    """One ACT intent followed by RESPOND — one full act cycle."""

    def setup_method(self) -> None:
        self.adapter = FakeAdapter(
            intents=[
                ActIntent(instruction="list /tmp"),
                RespondIntent(text="Files listed."),
            ],
            act_results=["file1.txt\nfile2.txt"],
        )
        self.loop = _make_loop(self.adapter)

    def test_returns_final_response(self) -> None:
        text, _state = self.loop.run("list files in /tmp")
        assert text == "Files listed."

    def test_spawn_count_is_three(self) -> None:
        """1 reason + 1 act + 1 final reason = spawn_count 3."""
        _text, state = self.loop.run("list files in /tmp")
        assert state.spawn_count == 3

    def test_cycle_count_is_one(self) -> None:
        _text, state = self.loop.run("list files in /tmp")
        assert state.cycle_count == 1

    def test_act_called_with_instruction(self) -> None:
        self.loop.run("list files in /tmp")
        assert self.adapter.act_calls == ["list /tmp"]

    def test_act_result_in_history(self) -> None:
        _text, state = self.loop.run("list files in /tmp")
        assert "file1.txt\nfile2.txt" in state.history

    def test_observe_called_once(self) -> None:
        self.loop.run("list files in /tmp")
        assert len(self.adapter.observe_calls) == 1

    def test_perceive_called_twice(self) -> None:
        """perceive is called at the start of each iteration: cycle 0 + cycle 1."""
        self.loop.run("list files in /tmp")
        assert len(self.adapter.perceive_calls) == 2


# ---------------------------------------------------------------------------
# (c) MAX_CYCLES breach
# ---------------------------------------------------------------------------


class TestMaxCyclesBreach:
    """All ACT intents — loop raises MaxCyclesExceededError after max_cycles."""

    MAX = 3

    def setup_method(self) -> None:
        self.adapter = FakeAdapter(
            intents=[ActIntent(instruction=f"step {i}") for i in range(20)],
            act_results=[f"result {i}" for i in range(20)],
        )
        self.loop = _make_loop(self.adapter, max_cycles=self.MAX)

    def test_raises_max_cycles_exceeded(self) -> None:
        with pytest.raises(MaxCyclesExceededError):
            self.loop.run("do many things")

    def test_observe_called_max_cycles_times(self) -> None:
        """observe() (which increments cycle_count) is called exactly max_cycles times."""
        try:
            self.loop.run("do many things")
        except MaxCyclesExceededError:
            pass
        assert len(self.adapter.observe_calls) == self.MAX

    def test_act_called_max_cycles_times(self) -> None:
        try:
            self.loop.run("do many things")
        except MaxCyclesExceededError:
            pass
        assert len(self.adapter.act_calls) == self.MAX

    def test_error_message_contains_max_cycles(self) -> None:
        with pytest.raises(MaxCyclesExceededError, match=str(self.MAX)):
            self.loop.run("do many things")


# ---------------------------------------------------------------------------
# (d) AdapterError propagation
# ---------------------------------------------------------------------------


class TestAdapterErrorPropagation:
    """AdapterError from reason() propagates unchanged through the loop."""

    def setup_method(self) -> None:
        self.adapter = FakeAdapter(raise_on_reason=True)
        self.loop = _make_loop(self.adapter)

    def test_adapter_error_propagates(self) -> None:
        with pytest.raises(AdapterError):
            self.loop.run("trigger error")

    def test_act_not_called_on_reason_error(self) -> None:
        try:
            self.loop.run("trigger error")
        except AdapterError:
            pass
        assert self.adapter.act_calls == []

    def test_error_message_preserved(self) -> None:
        with pytest.raises(AdapterError, match="fake adapter reason error"):
            self.loop.run("trigger error")


# ---------------------------------------------------------------------------
# (e) FINISH intent
# ---------------------------------------------------------------------------


class TestFinishIntent:
    """FINISH intent — loop returns ("", run_state)."""

    def test_finish_returns_empty_string(self) -> None:
        adapter = FakeAdapter(intents=[FinishIntent()])
        loop = _make_loop(adapter)
        text, _state = loop.run("done")
        assert text == ""

    def test_finish_spawn_count_is_one(self) -> None:
        adapter = FakeAdapter(intents=[FinishIntent()])
        loop = _make_loop(adapter)
        _text, state = loop.run("done")
        assert state.spawn_count == 1

    def test_finish_cycle_count_is_zero(self) -> None:
        adapter = FakeAdapter(intents=[FinishIntent()])
        loop = _make_loop(adapter)
        _text, state = loop.run("done")
        assert state.cycle_count == 0

    def test_finish_act_not_called(self) -> None:
        adapter = FakeAdapter(intents=[FinishIntent()])
        loop = _make_loop(adapter)
        loop.run("done")
        assert adapter.act_calls == []


# ---------------------------------------------------------------------------
# (f) USE_SKILL intent (M5)
# ---------------------------------------------------------------------------


def _skill(
    name: str, description: str = "d", body: str = "do the thing"
) -> SkillContent:
    return SkillContent(name=name, description=description, body=body)


class TestUseSkillIntentActivation:
    """USE_SKILL -> successful activation: content appended to active_skills,
    skill_activation_note set, no history append, cycle_count advances,
    spawn_count does NOT advance (design.md D6/W1)."""

    def setup_method(self) -> None:
        self.skills = FakeSkills(skills={"csv-summarizer": _skill("csv-summarizer")})
        self.adapter = FakeAdapter(
            intents=[
                UseSkillIntent(skill_name="csv-summarizer"),
                RespondIntent(text="done"),
            ]
        )
        self.loop = _make_loop(self.adapter, skills=self.skills)

    def test_returns_final_response(self) -> None:
        text, _state = self.loop.run("summarize this csv")
        assert text == "done"

    def test_active_skills_contains_activated_skill(self) -> None:
        _text, state = self.loop.run("summarize this csv")
        assert [s.name for s in state.active_skills] == ["csv-summarizer"]

    def test_cycle_count_is_one(self) -> None:
        _text, state = self.loop.run("summarize this csv")
        assert state.cycle_count == 1

    def test_spawn_count_is_two_not_three(self) -> None:
        """2 reason() calls only -- USE_SKILL dispatches no provider query,
        unlike ACT (which would make this 3, per TestActRespondOneCycle)."""
        _text, state = self.loop.run("summarize this csv")
        assert state.spawn_count == 2

    def test_history_not_touched(self) -> None:
        """dryrun-design-1 C3 fix: skill activation must NOT go through
        run_state.history -- that channel is reserved for real ACT results."""
        _text, state = self.loop.run("summarize this csv")
        assert state.history == []

    def test_get_skill_called_with_name(self) -> None:
        self.loop.run("summarize this csv")
        assert self.skills.get_skill_calls == ["csv-summarizer"]

    def test_catalog_refreshed_before_each_perceive(self) -> None:
        """design.md D3: list_skills() called once per cycle, not once per turn --
        here, once before the USE_SKILL cycle's perceive, once before the
        RESPOND cycle's perceive."""
        self.loop.run("summarize this csv")
        assert self.skills.list_skills_calls == 2


class TestUseSkillIntentAlreadyActive:
    """Re-activating an already-active skill: no re-fetch, no duplicate
    append, status note set instead (design.md D6a / dryrun-design-1 W1)."""

    def setup_method(self) -> None:
        self.skills = FakeSkills(skills={"csv-summarizer": _skill("csv-summarizer")})
        self.adapter = FakeAdapter(
            intents=[
                UseSkillIntent(skill_name="csv-summarizer"),
                UseSkillIntent(skill_name="csv-summarizer"),
                RespondIntent(text="done"),
            ]
        )
        self.loop = _make_loop(self.adapter, skills=self.skills)

    def test_active_skills_has_no_duplicate(self) -> None:
        _text, state = self.loop.run("summarize twice")
        assert len(state.active_skills) == 1

    def test_get_skill_called_only_once(self) -> None:
        """The second USE_SKILL for the same name must not re-fetch."""
        self.loop.run("summarize twice")
        assert self.skills.get_skill_calls == ["csv-summarizer"]

    def test_cycle_count_is_two(self) -> None:
        """Both USE_SKILL cycles still advance cycle_count (runaway-loop guard)."""
        _text, state = self.loop.run("summarize twice")
        assert state.cycle_count == 2


class TestUseSkillIntentUnknownSkill:
    """USE_SKILL for a name not in the catalog: no crash, error note set,
    active_skills untouched, loop continues (design.md D5)."""

    def setup_method(self) -> None:
        self.skills = FakeSkills()  # empty catalog
        self.adapter = FakeAdapter(
            intents=[
                UseSkillIntent(skill_name="does-not-exist"),
                RespondIntent(text="done"),
            ]
        )
        self.loop = _make_loop(self.adapter, skills=self.skills)

    def test_does_not_crash_and_returns_response(self) -> None:
        text, _state = self.loop.run("use a fake skill")
        assert text == "done"

    def test_active_skills_remains_empty(self) -> None:
        _text, state = self.loop.run("use a fake skill")
        assert state.active_skills == []

    def test_cycle_count_still_advances(self) -> None:
        _text, state = self.loop.run("use a fake skill")
        assert state.cycle_count == 1


class TestUseSkillIntentMaxCyclesBreach:
    """All USE_SKILL intents for a valid skill (never terminal) -- loop
    raises MaxCyclesExceededError after max_cycles, same guard ACT gets."""

    MAX = 3

    def setup_method(self) -> None:
        # Distinct skill names each cycle so the dedup check (D6a) doesn't
        # short-circuit into the ALREADY_ACTIVE path -- this test exercises
        # the plain runaway-activation guard.
        skills_map = {f"skill-{i}": _skill(f"skill-{i}") for i in range(20)}
        self.skills = FakeSkills(skills=skills_map)
        self.adapter = FakeAdapter(
            intents=[UseSkillIntent(skill_name=f"skill-{i}") for i in range(20)]
        )
        self.loop = _make_loop(self.adapter, max_cycles=self.MAX, skills=self.skills)

    def test_raises_max_cycles_exceeded(self) -> None:
        with pytest.raises(MaxCyclesExceededError):
            self.loop.run("keep activating skills")

    def test_active_skills_has_max_cycles_entries(self) -> None:
        try:
            self.loop.run("keep activating skills")
        except MaxCyclesExceededError:
            pass
        # last one raises after incrementing cycle_count but before another
        # get_skill call, so exactly MAX skills were successfully activated.
        assert len(self.skills.get_skill_calls) == self.MAX


# ---------------------------------------------------------------------------
# (g) Router-driven ACT dispatch (M6)
# ---------------------------------------------------------------------------


class TestRouterSelectsWorkerPerCycle:
    """RT-3: select_worker() is called once per ACT dispatch, with the
    instruction from that cycle's ActIntent."""

    def test_select_worker_called_with_instruction(self) -> None:
        adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")],
            act_results=["x result"],
        )
        router = FakeRouter(default_worker=adapter)
        loop = _make_loop(adapter, router=router)
        loop.run("go")
        assert router.select_worker_calls == ["do x"]

    def test_two_act_cycles_call_select_worker_twice_with_different_instructions(
        self,
    ) -> None:
        adapter = FakeAdapter(
            intents=[
                ActIntent(instruction="step one"),
                ActIntent(instruction="step two"),
                RespondIntent(text="done"),
            ],
            act_results=["r1", "r2"],
        )
        router = FakeRouter(default_worker=adapter)
        loop = _make_loop(adapter, router=router)
        loop.run("go")
        assert router.select_worker_calls == ["step one", "step two"]

    def test_worker_can_differ_from_the_conductor_adapter(self) -> None:
        """A different adapter instance than perceive/reason/observe's can
        serve as the Worker -- proves the loop dispatches to whatever
        Router hands back, not always the same bound adapter."""
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        worker_adapter = FakeAdapter(act_results=["worker result"])
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=worker_adapter,
                    provider_name="local",
                    control_level="KIND_A",
                    fallback_allowed=True,
                )
            ]
        )
        loop = _make_loop(conductor_adapter, router=router)
        loop.run("go")
        assert worker_adapter.act_calls == ["do x"]
        assert (
            conductor_adapter.act_calls == []
        )  # never dispatched to the Conductor's own adapter


class TestRouterFallback:
    """RT-9: primary Worker fails with AdapterError -> loop retries once via
    select_fallback_worker() when fallback_allowed; no fallback otherwise."""

    def test_fallback_succeeds_after_primary_failure(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        healthy_adapter = FakeAdapter(act_results=["fallback result"])
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=True,
                )
            ],
            fallback_selection=WorkerSelection(
                adapter=healthy_adapter,
                provider_name="local",
                control_level="KIND_A",
                fallback_allowed=False,
            ),
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        text, state = loop.run("go")
        assert text == "done"
        assert healthy_adapter.act_calls == ["do x"]
        assert router.select_fallback_worker_calls == ["claude"]

    def test_spawn_count_counts_both_dispatch_attempts_on_fallback(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        healthy_adapter = FakeAdapter(act_results=["fallback result"])
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=True,
                )
            ],
            fallback_selection=WorkerSelection(
                adapter=healthy_adapter,
                provider_name="local",
                control_level="KIND_A",
                fallback_allowed=False,
            ),
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        _text, state = loop.run("go")
        # 1 reason (ActIntent) + 1 reason (final RESPOND) + 2 act dispatches
        # (primary failure + fallback success) = 4.
        assert state.spawn_count == 4

    def test_no_fallback_when_fallback_not_allowed(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=False,  # e.g. override- or privacy-forced
                )
            ]
        )
        conductor_adapter = FakeAdapter(intents=[ActIntent(instruction="do x")])
        loop = _make_loop(conductor_adapter, router=router)
        with pytest.raises(AdapterError):
            loop.run("go")
        assert router.select_fallback_worker_calls == []

    def test_error_propagates_when_no_fallback_available(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=True,
                )
            ],
            fallback_selection=None,  # no other provider configured
        )
        conductor_adapter = FakeAdapter(intents=[ActIntent(instruction="do x")])
        loop = _make_loop(conductor_adapter, router=router)
        with pytest.raises(AdapterError):
            loop.run("go")
        assert router.select_fallback_worker_calls == ["claude"]

    def test_error_propagates_when_fallback_also_fails(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        also_failing_adapter = FakeAdapter(raise_on_act=True)
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=True,
                )
            ],
            fallback_selection=WorkerSelection(
                adapter=also_failing_adapter,
                provider_name="local",
                control_level="KIND_A",
                fallback_allowed=False,
            ),
        )
        conductor_adapter = FakeAdapter(intents=[ActIntent(instruction="do x")])
        loop = _make_loop(conductor_adapter, router=router)
        with pytest.raises(AdapterError):
            loop.run("go")


class TestActSpanRoutingAttributes:
    """RT-7: the act phase span carries axiom.control_level /
    axiom.router.provider, set from the selection that actually ran."""

    def _run_with_mocked_span(self, adapter, router):
        """Patches record_phase (the lazy-imported name inside
        _maybe_record) with a context manager yielding a MagicMock span,
        so we can assert on set_attribute calls without a real OTel
        TracerProvider."""
        from unittest.mock import MagicMock, patch

        mock_span = MagicMock()

        class _FakeRecordPhaseCM:
            def __enter__(self):
                return mock_span

            def __exit__(self, *exc):
                return False

        with patch(
            "axiom.observability.record.record_phase",
            return_value=_FakeRecordPhaseCM(),
        ):
            loop = _make_loop(adapter, router=router)
            loop.run("go", run_id="fake-run-id", provider_kind="KIND_B")
        return mock_span

    def test_attributes_set_from_selection_on_success(self) -> None:
        adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")],
            act_results=["x result"],
        )
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=adapter,
                    provider_name="local",
                    control_level="KIND_A",
                    fallback_allowed=True,
                )
            ]
        )
        mock_span = self._run_with_mocked_span(adapter, router)
        calls = {c.args[0]: c.args[1] for c in mock_span.set_attribute.call_args_list}
        assert calls["axiom.control_level"] == "KIND_A"
        assert calls["axiom.router.provider"] == "local"

    def test_attributes_reflect_fallback_provider_on_success(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        healthy_adapter = FakeAdapter(act_results=["fallback result"])
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=True,
                )
            ],
            fallback_selection=WorkerSelection(
                adapter=healthy_adapter,
                provider_name="local",
                control_level="KIND_A",
                fallback_allowed=False,
            ),
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        mock_span = self._run_with_mocked_span(conductor_adapter, router)
        calls = [c.args for c in mock_span.set_attribute.call_args_list]
        # The LAST value set for each key must reflect the fallback outcome
        # (local/KIND_A), not the failed primary (claude/KIND_B).
        control_level_calls = [v for k, v in calls if k == "axiom.control_level"]
        provider_calls = [v for k, v in calls if k == "axiom.router.provider"]
        assert control_level_calls[-1] == "KIND_A"
        assert provider_calls[-1] == "local"

    def test_attributes_present_on_hard_failure(self) -> None:
        """dryrun-design-2 W1: a failed dispatch with no fallback must still
        carry routing attribution (what was attempted), not be silent."""
        from unittest.mock import MagicMock, patch

        mock_span = MagicMock()

        class _FakeRecordPhaseCM:
            def __enter__(self):
                return mock_span

            def __exit__(self, *exc):
                return False

        failing_adapter = FakeAdapter(raise_on_act=True)
        router = FakeRouter(
            worker_selections=[
                WorkerSelection(
                    adapter=failing_adapter,
                    provider_name="claude",
                    control_level="KIND_B",
                    fallback_allowed=False,
                )
            ]
        )
        conductor_adapter = FakeAdapter(intents=[ActIntent(instruction="do x")])
        with patch(
            "axiom.observability.record.record_phase",
            return_value=_FakeRecordPhaseCM(),
        ):
            loop = _make_loop(conductor_adapter, router=router)
            with pytest.raises(AdapterError):
                loop.run("go", run_id="fake-run-id", provider_kind="KIND_B")
        calls = {c.args[0]: c.args[1] for c in mock_span.set_attribute.call_args_list}
        assert calls["axiom.control_level"] == "KIND_B"
        assert calls["axiom.router.provider"] == "claude"


class TestCommitteeDispatch:
    """M7 (OR-3, OR-4, OR-6, OR-7): committee dispatch — same instruction to
    every member, combined-result synthesis via the existing observe() call,
    per-slot failure tolerance, no fallback substitution."""

    def test_same_instruction_dispatched_to_every_member(self) -> None:
        claude_adapter = FakeAdapter(act_results=["claude result"])
        local_adapter = FakeAdapter(act_results=["local result"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=claude_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=local_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        text, _state = loop.run("go")
        assert text == "done"
        assert claude_adapter.act_calls == ["do x"]
        assert local_adapter.act_calls == ["do x"]

    def test_each_member_result_captured_independently_no_overwrite(self) -> None:
        claude_adapter = FakeAdapter(act_results=["claude answer"])
        local_adapter = FakeAdapter(act_results=["local answer"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=claude_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=local_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        loop.run("go")
        # OR-4: one combined observe() call, both members' results present,
        # provider-attributed.
        assert len(conductor_adapter.observe_calls) == 1
        combined_result, _run_state = conductor_adapter.observe_calls[0]
        assert "[claude]: claude answer" in combined_result
        assert "[local]: local answer" in combined_result

    def test_combined_result_reaches_history_via_existing_observe(self) -> None:
        claude_adapter = FakeAdapter(act_results=["claude answer"])
        local_adapter = FakeAdapter(act_results=["local answer"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=claude_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=local_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        _text, state = loop.run("go")
        assert any("claude answer" in h and "local answer" in h for h in state.history)

    def test_one_member_failing_does_not_abort_the_cycle(self) -> None:
        failing_adapter = FakeAdapter(raise_on_act=True)
        healthy_adapter = FakeAdapter(act_results=["local answer"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=failing_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=healthy_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        text, state = loop.run("go")
        assert text == "done"  # cycle completed despite one failure
        combined_result, _run_state = conductor_adapter.observe_calls[0]
        assert "[claude]: FAILED" in combined_result
        assert "[local]: local answer" in combined_result

    def test_all_members_failing_raises_adapter_error(self) -> None:
        failing_1 = FakeAdapter(raise_on_act=True)
        failing_2 = FakeAdapter(raise_on_act=True)
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=failing_1,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=failing_2,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(intents=[ActIntent(instruction="do x")])
        loop = _make_loop(conductor_adapter, router=router)
        with pytest.raises(AdapterError, match="all 2 committee members failed"):
            loop.run("go")

    def test_select_fallback_worker_never_called_from_committee_path(self) -> None:
        """OR-7: even with a failing member, the committee path must not
        reach for Router.select_fallback_worker() -- that mechanism is
        exclusively single-provider-dispatch."""
        failing_adapter = FakeAdapter(raise_on_act=True)
        healthy_adapter = FakeAdapter(act_results=["local answer"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=failing_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=healthy_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        loop.run("go")
        assert router.select_fallback_worker_calls == []

    def test_spawn_count_increments_by_committee_size(self) -> None:
        claude_adapter = FakeAdapter(act_results=["claude answer"])
        local_adapter = FakeAdapter(act_results=["local answer"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=claude_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=local_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        loop = _make_loop(conductor_adapter, router=router)
        _text, state = loop.run("go")
        # 1 reason (ActIntent) + 1 reason (final RESPOND) + 2 committee dispatches = 4.
        assert state.spawn_count == 4

    def test_act_span_carries_committee_size_and_providers(self) -> None:
        from unittest.mock import MagicMock, patch

        mock_span = MagicMock()

        class _FakeRecordPhaseCM:
            def __enter__(self):
                return mock_span

            def __exit__(self, *exc):
                return False

        claude_adapter = FakeAdapter(act_results=["claude answer"])
        local_adapter = FakeAdapter(act_results=["local answer"])
        router = FakeRouter(
            committee_selections=[
                [
                    WorkerSelection(
                        adapter=claude_adapter,
                        provider_name="claude",
                        control_level="KIND_B",
                        fallback_allowed=False,
                    ),
                    WorkerSelection(
                        adapter=local_adapter,
                        provider_name="local",
                        control_level="KIND_A",
                        fallback_allowed=False,
                    ),
                ]
            ]
        )
        conductor_adapter = FakeAdapter(
            intents=[ActIntent(instruction="do x"), RespondIntent(text="done")]
        )
        with patch(
            "axiom.observability.record.record_phase",
            return_value=_FakeRecordPhaseCM(),
        ):
            loop = _make_loop(conductor_adapter, router=router)
            loop.run("go", run_id="fake-run-id", provider_kind="KIND_B")
        calls = {c.args[0]: c.args[1] for c in mock_span.set_attribute.call_args_list}
        assert calls["axiom.router.committee_size"] == 2
        assert calls["axiom.router.providers"] == "claude,local"
