"""
Unit tests for PraoAdapterBase (perceive/observe) and _parse_intent (shared base).

These cover design §8/§11.2 — the shared base module (providers/base.py) that is
provider-independent. No litellm dependency — these tests run without any mocking
of sys.modules.
"""

from __future__ import annotations

from axiom.interfaces import (
    ActIntent,
    FinishIntent,
    RespondIntent,
    RunState,
)
from axiom.providers.base import (
    INTENT_FORMAT_INSTRUCTIONS,
    PraoAdapterBase,
    _extract_json_from_text,
    _parse_intent,
)


# ============================================================
# PraoAdapterBase — perceive() / observe()
# ============================================================


class TestPraoAdapterBasePerceive:
    def _base(self, persona: str = "My Persona") -> PraoAdapterBase:
        return PraoAdapterBase(persona=persona)

    def _state(self, history: list[str] | None = None) -> RunState:
        return RunState(user_input="What is 2+2?", history=history or [], cycle_count=0)

    def test_empty_history_has_no_history_section(self) -> None:
        result = self._base().perceive(self._state())
        assert "[TOOL EXECUTION RESULTS" not in result

    def test_contains_persona(self) -> None:
        result = self._base(persona="I am Velasari").perceive(self._state())
        assert "[PERSONA]\nI am Velasari" in result

    def test_contains_current_request(self) -> None:
        result = self._base().perceive(self._state())
        assert "[CURRENT REQUEST]\nWhat is 2+2?" in result

    def test_contains_intent_format_instructions(self) -> None:
        result = self._base().perceive(self._state())
        assert INTENT_FORMAT_INSTRUCTIONS in result

    def test_with_history_includes_numbered_steps(self) -> None:
        state = self._state(history=["Tool ran OK", "Found the answer"])
        result = self._base().perceive(state)
        assert "[TOOL EXECUTION RESULTS — read these carefully]" in result
        assert "Step 1: Tool ran OK" in result
        assert "Step 2: Found the answer" in result
        # E2E-discovered: after tool output the model should be nudged to RESPOND
        assert "RESPOND" in result
        assert "do NOT request another ACT" in result


class TestPraoAdapterBaseObserve:
    def _base(self) -> PraoAdapterBase:
        return PraoAdapterBase(persona="p")

    def _state(self) -> RunState:
        return RunState(user_input="hi", history=[], cycle_count=0)

    def test_appends_result_to_history(self) -> None:
        state = self._state()
        self._base().observe("tool result here", state)
        assert state.history == ["tool result here"]

    def test_increments_cycle_count(self) -> None:
        state = self._state()
        state.cycle_count = 3
        self._base().observe("r", state)
        assert state.cycle_count == 4

    def test_returns_same_state_object(self) -> None:
        state = self._state()
        returned = self._base().observe("r", state)
        assert returned is state


# ============================================================
# _parse_intent() — shared intent parser
# ============================================================


class TestParseIntent:
    def test_clean_respond_json(self) -> None:
        intent, err = _parse_intent('{"intent": "RESPOND", "text": "Hello!"}')
        assert err is None
        assert isinstance(intent, RespondIntent)
        assert intent.text == "Hello!"

    def test_clean_act_json(self) -> None:
        intent, err = _parse_intent('{"intent": "ACT", "instruction": "Do something"}')
        assert err is None
        assert isinstance(intent, ActIntent)
        assert intent.instruction == "Do something"

    def test_clean_finish_json(self) -> None:
        intent, err = _parse_intent('{"intent": "FINISH"}')
        assert err is None
        assert isinstance(intent, FinishIntent)

    def test_invalid_json_returns_none_and_error_string(self) -> None:
        intent, err = _parse_intent("not json at all")
        assert intent is None
        assert isinstance(err, str) and len(err) > 0

    def test_json_wrapped_in_markdown_code_fence(self) -> None:
        raw = '```json\n{"intent": "RESPOND", "text": "Paris."}\n```'
        intent, err = _parse_intent(raw)
        assert err is None
        assert isinstance(intent, RespondIntent)
        assert intent.text == "Paris."

    def test_json_embedded_in_explanation_prose(self) -> None:
        raw = (
            'Sure, here is the intent: {"intent": "ACT", "instruction": "ls -la"} done.'
        )
        intent, err = _parse_intent(raw)
        assert err is None
        assert isinstance(intent, ActIntent)
        assert intent.instruction == "ls -la"

    def test_unknown_intent_value(self) -> None:
        intent, err = _parse_intent('{"intent": "DANCE"}')
        assert intent is None
        assert "DANCE" in err

    def test_respond_missing_text_field(self) -> None:
        intent, err = _parse_intent('{"intent": "RESPOND"}')
        assert intent is None
        assert err is not None

    def test_act_missing_instruction_field(self) -> None:
        intent, err = _parse_intent('{"intent": "ACT"}')
        assert intent is None
        assert err is not None

    def test_clean_json_not_altered_by_preprocessing(self) -> None:
        """OQ-3 regression: clean JSON from Claude must pass through unchanged."""
        intent, err = _parse_intent('{"intent": "FINISH"}')
        assert err is None
        assert isinstance(intent, FinishIntent)

    def test_extract_json_from_text_code_fence(self) -> None:
        """Direct test of _extract_json_from_text: strips markdown code fences."""
        result = _extract_json_from_text('```json\n{"key": "val"}\n```')
        assert result == '{"key": "val"}'

    def test_extract_json_from_text_prose(self) -> None:
        """Direct test of _extract_json_from_text: extracts first {...} from prose."""
        result = _extract_json_from_text('Here: {"a": 1} and more text')
        assert result is not None
        assert '"a"' in result

    def test_extract_json_from_text_no_json(self) -> None:
        """Direct test of _extract_json_from_text: returns None when no JSON found."""
        result = _extract_json_from_text("no braces here at all")
        assert result is None

    def test_code_fence_multiline_nested_json(self) -> None:
        """B1/W1 regression: greedy regex must capture nested/multi-line JSON in full.

        A non-greedy .*? would stop at the first '}' inside the JSON object
        (e.g. inside {"a": {"b": 1}, "c": 2}) producing a truncated/invalid candidate.
        The greedy .* captures the full object up to the last '}' before the fence.
        """
        raw = '```json\n{"a": {"b": 1}, "c": 2}\n```'
        result = _extract_json_from_text(raw)
        assert result is not None, (
            "Expected a non-None result from code-fenced nested JSON"
        )
        import json as _json

        parsed = _json.loads(result)
        assert parsed == {"a": {"b": 1}, "c": 2}, (
            f"Parsed object should match original; got {parsed!r}"
        )

    def test_multi_fence_extracts_first_parseable_json(self) -> None:
        """Multi-fence edge case: greedy single-fence regex spans both fences.

        When the model response contains a prose/text fence followed by a JSON
        fence, the old greedy pattern r"```(?:json)?\\s*(\\{.*\\})\\s*```" with
        DOTALL matches from the first ``` to the last ```, swallowing the
        intermediate fence delimiters into the capture group and producing
        un-parseable content.  The fixed implementation uses re.finditer with a
        non-greedy inter-fence pattern to isolate each block, then tries each
        block in order — so the correct JSON object is extracted.
        """
        raw = (
            "```text\n"
            "Here is the explanation.\n"
            "```\n"
            "```json\n"
            '{"intent": "RESPOND", "text": "Paris."}\n'
            "```"
        )
        intent, err = _parse_intent(raw)
        assert err is None, f"Expected successful parse; got error: {err!r}"
        assert isinstance(intent, RespondIntent)
        assert intent.text == "Paris."
