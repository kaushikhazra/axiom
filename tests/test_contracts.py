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
)
from axiom.loop import PraoLoop
from tests.fake_adapter import FakeAdapter


def _make_loop(adapter: FakeAdapter, max_cycles: int = 10) -> PraoLoop:
    """Helper: wire all four slots with the same FakeAdapter instance."""
    return PraoLoop(
        perceive=adapter,
        reason=adapter,
        act=adapter,
        observe=adapter,
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
        text, state = loop.run("done")
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
