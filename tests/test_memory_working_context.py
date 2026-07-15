"""Unit tests for working_context.py."""

from __future__ import annotations

from datetime import datetime, timezone

from axiom.memory.config import MemoryConfig
from axiom.memory.models import ConversationUnit
from axiom.memory.working_context import WorkingContext, _apply_token_cap


def _unit(
    user_text: str = "hello",
    agent_text: str = "world",
    turn_index: int = 0,
    embedding: list[float] | None = None,
) -> ConversationUnit:
    unit = ConversationUnit(
        user_text=user_text,
        agent_text=agent_text,
        turn_index=turn_index,
        timestamp=datetime.now(timezone.utc),
    )
    unit.embedding = embedding or [0.1, 0.2, 0.3]
    unit.token_count = len(user_text + agent_text) // 4
    return unit


def _config(**kwargs) -> MemoryConfig:
    defaults = dict(
        n_units=10,
        token_budget=10000,
        n_recency_floor=3,
        k_relevance=3,
    )
    defaults.update(kwargs)
    return MemoryConfig(**defaults)


class TestAddUnit:
    def test_add_single_unit(self):
        ctx = WorkingContext(_config())
        ctx.add_unit(_unit())
        assert len(ctx) == 1

    def test_overflow_evicts_oldest(self):
        ctx = WorkingContext(_config(n_units=3))
        u1 = _unit("first", turn_index=0)
        u2 = _unit("second", turn_index=1)
        u3 = _unit("third", turn_index=2)
        u4 = _unit("fourth", turn_index=3)
        for u in [u1, u2, u3, u4]:
            ctx.add_unit(u)
        assert len(ctx) == 3
        # u1 should be evicted (oldest)
        assembled = ctx.assemble([0.1, 0.2, 0.3])
        texts = [u.user_text for u in assembled]
        assert "first" not in texts

    def test_len_correct(self):
        ctx = WorkingContext(_config(n_units=5))
        for i in range(5):
            ctx.add_unit(_unit(turn_index=i))
        assert len(ctx) == 5


class TestAssemble:
    def test_empty_buffer_returns_empty(self):
        ctx = WorkingContext(_config())
        result = ctx.assemble([0.1, 0.2, 0.3])
        assert result == []

    def test_recency_floor_always_present(self):
        ctx = WorkingContext(_config(n_recency_floor=3, k_relevance=2))
        # Add 5 units — the last 3 should always be in recency floor
        units = [
            _unit(f"msg{i}", turn_index=i, embedding=[float(i) * 0.1] * 3)
            for i in range(5)
        ]
        for u in units:
            ctx.add_unit(u)
        result = ctx.assemble([0.9, 0.9, 0.9])
        # Last 3 units (indices 2,3,4) must be present
        result_texts = {u.user_text for u in result}
        assert "msg2" in result_texts
        assert "msg3" in result_texts
        assert "msg4" in result_texts

    def test_relevance_brings_older_unit(self):
        ctx = WorkingContext(_config(n_recency_floor=2, k_relevance=2))
        # Unit with embedding similar to query goes in slot 0 (oldest)
        old_relevant = _unit("relevant old", turn_index=0, embedding=[1.0, 0.0, 0.0])
        old_irrelevant = _unit(
            "irrelevant old", turn_index=1, embedding=[0.0, 1.0, 0.0]
        )
        recent1 = _unit("recent1", turn_index=2, embedding=[0.0, 0.0, 1.0])
        recent2 = _unit("recent2", turn_index=3, embedding=[0.0, 0.0, 1.0])
        for u in [old_relevant, old_irrelevant, recent1, recent2]:
            ctx.add_unit(u)
        # Query similar to old_relevant
        result = ctx.assemble([1.0, 0.0, 0.0])
        texts = [u.user_text for u in result]
        assert "relevant old" in texts

    def test_token_cap_truncates_from_front(self):
        # Units with high token counts should be truncated from relevance slice
        ctx = WorkingContext(_config(n_recency_floor=2, token_budget=50, k_relevance=5))
        # Add many units with high token counts
        for i in range(8):
            big = _unit("x" * 100, "y" * 100, turn_index=i, embedding=[0.1] * 3)
            big.token_count = 50  # force high count
            ctx.add_unit(big)
        result = ctx.assemble([0.1] * 3)
        total_tokens = sum(u.token_count for u in result)
        assert total_tokens <= 50

    def test_no_embedding_still_works(self):
        ctx = WorkingContext(_config(n_recency_floor=2))
        u = _unit("hello")
        u.embedding = []
        ctx.add_unit(u)
        result = ctx.assemble([])
        assert len(result) == 1


class TestApplyTokenCap:
    def test_within_budget_unchanged(self):
        units = [_unit() for _ in range(3)]
        for u in units:
            u.token_count = 10
        result = _apply_token_cap(units, budget=100)
        assert len(result) == 3

    def test_over_budget_truncates_oldest(self):
        units = [_unit(turn_index=i) for i in range(4)]
        for u in units:
            u.token_count = 30
        result = _apply_token_cap(units, budget=50)
        # 50 / 30 = 1.67 → 1 unit fits; must remove from front
        assert sum(u.token_count for u in result) <= 50
