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
from axiom.skills.port import SkillContent
from tests.fake_adapter import FakeAdapter, FakeMemory, FakeSkills


def _make_loop(
    adapter: FakeAdapter, max_cycles: int = 10, skills: FakeSkills | None = None
) -> PraoLoop:
    """Helper: wire all four slots with the same FakeAdapter instance.

    M3: memory is constitutive — always wired. FakeMemory is a no-op stub that
    satisfies MemoryPort without touching real storage or embeddings.
    M5: skills is constitutive too — FakeSkills defaults to an empty catalog
    (matching SkillsRegistry's own behavior for a missing/empty skills_dir).
    """
    return PraoLoop(
        perceive=adapter,
        reason=adapter,
        act=adapter,
        observe=adapter,
        memory=FakeMemory(),
        skills=skills if skills is not None else FakeSkills(),
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
