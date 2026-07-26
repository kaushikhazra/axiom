"""
Unit tests for axiom.providers.base.PraoAdapterBase.perceive() -- M8's new
[LESSONS FROM PAST CORRECTIONS] rendering block specifically.
"""

from __future__ import annotations

from axiom.interfaces import RunState
from axiom.providers.base import PraoAdapterBase


def _run_state(**kwargs) -> RunState:
    defaults = dict(user_input="hello", history=[])
    defaults.update(kwargs)
    return RunState(**defaults)


class TestLessonsRendering:
    def test_lessons_section_present_when_populated(self) -> None:
        adapter = PraoAdapterBase(persona="test persona")
        state = _run_state(lessons=["local provider failed on X; claude succeeded"])
        context = adapter.perceive(state)
        assert "[LESSONS FROM PAST CORRECTIONS]" in context
        assert "local provider failed on X; claude succeeded" in context

    def test_lessons_section_absent_when_empty(self) -> None:
        adapter = PraoAdapterBase(persona="test persona")
        state = _run_state(lessons=[])
        context = adapter.perceive(state)
        assert "[LESSONS FROM PAST CORRECTIONS]" not in context

    def test_multiple_lessons_each_rendered(self) -> None:
        adapter = PraoAdapterBase(persona="test persona")
        state = _run_state(lessons=["lesson one", "lesson two"])
        context = adapter.perceive(state)
        assert "lesson one" in context
        assert "lesson two" in context
