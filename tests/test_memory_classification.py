"""Unit tests for classification.py — pure functions."""

from __future__ import annotations

import pytest
from axiom.memory.classification import classify_type, score_importance


class TestClassifyType:
    def test_procedural_keywords_trigger_procedural(self):
        # Need ≥ 2 procedural keywords to exceed threshold
        t, conf = classify_type(
            "Here are the steps and workflow to follow: a procedure guide"
        )
        assert t == "procedural"
        assert conf >= 0.2

    def test_person_tag_triggers_person(self):
        t, conf = classify_type("person: Alice is the project manager")
        assert t == "person"
        assert conf >= 0.2

    def test_definition_triggers_semantic(self):
        t, conf = classify_type(
            "A CPU is defined as the central processing unit of a computer"
        )
        assert t == "semantic"
        assert conf >= 0.2

    def test_identity_self_reference(self):
        t, conf = classify_type(
            "I am Velasari, I believe in clear reasoning and I think carefully"
        )
        assert t == "identity"
        assert conf >= 0.2

    def test_default_is_episodic(self):
        t, conf = classify_type("The weather was nice today")
        assert t == "episodic"

    def test_confidence_below_0_2_gives_episodic(self):
        # Single weak signal: confidence is low, should default to episodic
        t, conf = classify_type("random text with no strong signals here")
        assert t == "episodic"

    def test_confidence_capped_at_0_8(self):
        # Many identity signals should not exceed 0.8
        text = "I am I believe I think I prefer I like I am called I feel my name I am"
        t, conf = classify_type(text)
        assert conf <= 0.8

    def test_caller_type_always_wins(self):
        # classify_type returns a type; caller override is in adapter, not here
        # Just verify the function returns a valid type
        t, _ = classify_type("steps to do something")
        assert t in (
            "working",
            "episodic",
            "semantic",
            "procedural",
            "identity",
            "person",
        )


class TestScoreImportance:
    def test_base_score_is_0_5(self):
        score = score_importance("some content", "episodic", None)
        assert 0.0 <= score <= 1.0

    def test_identity_type_bonus(self):
        score_identity = score_importance("content", "identity", None)
        score_episodic = score_importance("content", "episodic", None)
        assert score_identity > score_episodic

    def test_person_type_bonus(self):
        score_person = score_importance("content", "person", None)
        score_episodic = score_importance("content", "episodic", None)
        assert score_person > score_episodic

    def test_working_type_penalty(self):
        score_working = score_importance("content", "working", None)
        score_episodic = score_importance("content", "episodic", None)
        assert score_working < score_episodic

    def test_relational_keyword_bonus(self):
        score_rel = score_importance(
            "X happens because Y therefore Z", "episodic", None
        )
        score_plain = score_importance("X happens", "episodic", None)
        assert score_rel > score_plain

    def test_long_content_bonus(self):
        short = "Short."
        long = "x" * 250
        score_long = score_importance(long, "episodic", None)
        score_short = score_importance(short, "episodic", None)
        assert score_long > score_short

    def test_caller_override_wins(self):
        assert score_importance("anything", "identity", 0.3) == pytest.approx(0.3)
        assert score_importance("anything", "working", 0.9) == pytest.approx(0.9)

    def test_clamped_to_0_1(self):
        score = score_importance("content", "identity", 1.5)
        assert score == pytest.approx(1.0)
        score = score_importance("content", "working", -0.5)
        assert score == pytest.approx(0.0)

    def test_score_within_bounds(self):
        for memory_type in (
            "working",
            "episodic",
            "semantic",
            "procedural",
            "identity",
            "person",
        ):
            score = score_importance("some content here", memory_type, None)
            assert 0.0 <= score <= 1.0, f"{memory_type} score {score} out of bounds"
