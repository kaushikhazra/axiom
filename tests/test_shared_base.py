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
    UseSkillIntent,
)
from axiom.providers.base import (
    INTENT_FORMAT_INSTRUCTIONS,
    MAX_SKILL_BODY_CHARS,
    PraoAdapterBase,
    _extract_json_from_text,
    _parse_intent,
)
from axiom.skills.port import SkillContent, SkillSpec


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

    # ------------------------------------------------------------------
    # M5: skills catalog / active skills / skill_activation_note rendering
    # ------------------------------------------------------------------

    def test_empty_skills_catalog_has_no_available_skills_section(self) -> None:
        # Note: the wire-format instructions themselves mention "[AVAILABLE
        # SKILLS]" in prose (the USE_SKILL rule), so check for the actual
        # rendered section header (with its list-formatting newline), not a
        # bare substring match.
        result = self._base().perceive(self._state())
        assert "\n[AVAILABLE SKILLS]\n  -" not in result

    def test_skills_catalog_rendered(self) -> None:
        state = self._state()
        state.skills_catalog = [
            SkillSpec(name="csv-summarizer", description="Summarizes CSV files.")
        ]
        result = self._base().perceive(state)
        assert "[AVAILABLE SKILLS]" in result
        assert "csv-summarizer: Summarizes CSV files." in result

    def test_no_active_skills_has_no_active_skill_section(self) -> None:
        result = self._base().perceive(self._state())
        assert "[ACTIVE SKILL" not in result

    def test_active_skill_body_rendered(self) -> None:
        state = self._state()
        state.active_skills = [
            SkillContent(
                name="csv-summarizer", description="d", body="Step 1: read the CSV."
            )
        ]
        result = self._base().perceive(state)
        assert "[ACTIVE SKILL: csv-summarizer]" in result
        assert "Step 1: read the CSV." in result

    def test_active_skill_body_truncated_when_oversized(self) -> None:
        state = self._state()
        oversized_body = "x" * (MAX_SKILL_BODY_CHARS + 500)
        state.active_skills = [
            SkillContent(name="big-skill", description="d", body=oversized_body)
        ]
        result = self._base().perceive(state)
        assert "[truncated 500 chars]" in result
        # The full untruncated body must not appear verbatim -- proves the
        # cap actually cut it rather than just appending a suffix.
        assert oversized_body not in result

    def test_no_skill_activation_note_has_no_section(self) -> None:
        result = self._base().perceive(self._state())
        assert "[SKILL ACTIVATION]" not in result

    def test_skill_activation_note_rendered(self) -> None:
        state = self._state()
        state.skill_activation_note = "[SKILL ACTIVATED] csv-summarizer"
        result = self._base().perceive(state)
        assert "[SKILL ACTIVATION]\n[SKILL ACTIVATED] csv-summarizer" in result

    def test_skill_activation_note_not_in_tool_execution_results_section(self) -> None:
        """dryrun-design-1 C3 regression guard: the note must NOT be folded
        into [TOOL EXECUTION RESULTS] (whose fixed instructional text tells
        the Conductor to RESPOND immediately -- wrong guidance right after
        a skill activation)."""
        state = self._state()
        state.skill_activation_note = "[SKILL ACTIVATED] csv-summarizer"
        result = self._base().perceive(state)
        tool_results_idx = result.find("[TOOL EXECUTION RESULTS")
        activation_idx = result.find("[SKILL ACTIVATION]")
        assert tool_results_idx == -1  # no history -> no tool-results section at all
        assert activation_idx != -1


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

    def test_clean_use_skill_json(self) -> None:
        intent, err = _parse_intent(
            '{"intent": "USE_SKILL", "skill_name": "csv-summarizer"}'
        )
        assert err is None
        assert isinstance(intent, UseSkillIntent)
        assert intent.skill_name == "csv-summarizer"

    def test_use_skill_missing_skill_name_field(self) -> None:
        intent, err = _parse_intent('{"intent": "USE_SKILL"}')
        assert intent is None
        assert err is not None

    def test_use_skill_empty_skill_name_rejected(self) -> None:
        intent, err = _parse_intent('{"intent": "USE_SKILL", "skill_name": ""}')
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
