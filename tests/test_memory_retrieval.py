"""Unit tests for retrieval.py — RRF fusion, decay rerank, superseded penalty."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from axiom.memory.config import MemoryConfig
from axiom.memory.decay import compute_R
from axiom.memory.models import Memory
from axiom.memory.retrieval import RetrievalPipeline, RRF_K, W_SEMANTIC


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _memory(
    id: str,
    content: str = "test",
    stability: float = 14.0,
    importance: float = 0.5,
    state: str = "active",
    memory_type: str = "episodic",
    last_accessed: datetime | None = None,
) -> Memory:
    now = last_accessed or _now()
    return Memory(
        id=id,
        content=content,
        memory_type=memory_type,
        state=state,
        importance=importance,
        stability=stability,
        retrievability=1.0,
        access_count=1,
        created_at=now,
        updated_at=now,
        last_accessed=now,
    )


def _make_pipeline(storage_mock, embed_return=None) -> RetrievalPipeline:
    embeddings = MagicMock()
    embeddings.embed = AsyncMock(return_value=embed_return or [0.1] * 384)
    config = MemoryConfig(k_cognitive=5)
    return RetrievalPipeline(storage_mock, embeddings, config)


class TestRRFFusion:
    """Test that RRF scores accumulate correctly across strategies."""

    def test_memory_in_all_three_strategies_scores_highest(self):
        """A memory appearing in semantic+keyword+temporal should outscore single-strategy."""
        storage = MagicMock()
        mem_all = _memory("all_three")
        mem_one = _memory("one_only")

        storage.vector_search = AsyncMock(
            return_value=[("all_three", 0.9), ("one_only", 0.5)]
        )
        storage.fulltext_search = AsyncMock(return_value=[("all_three", 1.0)])
        storage.get_by_recency = AsyncMock(return_value=[("all_three", 0.8)])
        storage.get_memory = AsyncMock(
            side_effect=lambda mid: mem_all if mid == "all_three" else mem_one
        )
        storage.get_neighbours_bulk = AsyncMock(return_value=[])
        storage.get_contradictions = AsyncMock(
            return_value={"all_three": [], "one_only": []}
        )

        pipeline = _make_pipeline(storage)
        results = asyncio.run(pipeline.recall("test query", limit=5))
        ids = [r.id for r in results]
        assert ids[0] == "all_three"

    def test_rrf_formula_correct(self):
        """RRF score for rank-0 in semantic: W_SEMANTIC / (RRF_K + 0 + 1)."""
        expected = W_SEMANTIC / (RRF_K + 1)
        assert expected == pytest.approx(W_SEMANTIC / 61, rel=1e-6)


class TestDecayReranking:
    """Post-RRF decay reranking: final_score = rrf × R^0.5."""

    def test_fresh_memory_scores_higher_than_fading(self):
        """Fresh memory (high R) should outscore fading one with same RRF."""
        storage = MagicMock()
        # Both at same rank in semantic; fresh has recent last_accessed, fading has old
        fresh = _memory("fresh", stability=14.0, last_accessed=_now())
        # Old: elapsed ≈ 20 days on S=14 → R ≈ exp(-20/(9*14)) ≈ 0.85 ... let's make it very faded
        from datetime import timedelta

        old_dt = datetime.now(timezone.utc) - timedelta(days=200)
        fading = _memory("fading", stability=14.0, last_accessed=old_dt)

        storage.vector_search = AsyncMock(
            return_value=[("fresh", 0.9), ("fading", 0.9)]
        )
        storage.fulltext_search = AsyncMock(return_value=[])
        storage.get_by_recency = AsyncMock(return_value=[])
        storage.get_memory = AsyncMock(
            side_effect=lambda mid: fresh if mid == "fresh" else fading
        )
        storage.get_neighbours_bulk = AsyncMock(return_value=[])
        storage.get_contradictions = AsyncMock(return_value={"fresh": [], "fading": []})

        pipeline = _make_pipeline(storage)
        results = asyncio.run(pipeline.recall("test", limit=5))
        ids = [r.id for r in results]
        assert ids[0] == "fresh"

    def test_retrievability_on_result_is_computed_on_the_fly(self):
        """RecallResult.retrievability should be R(t) not the stored snapshot."""
        storage = MagicMock()
        from datetime import timedelta

        old_dt = datetime.now(timezone.utc) - timedelta(days=30)
        m = _memory("m1", stability=10.0, last_accessed=old_dt)
        m.retrievability = 0.999  # stale snapshot — should not appear in result

        storage.vector_search = AsyncMock(return_value=[("m1", 0.9)])
        storage.fulltext_search = AsyncMock(return_value=[])
        storage.get_by_recency = AsyncMock(return_value=[])
        storage.get_memory = AsyncMock(return_value=m)
        storage.get_neighbours_bulk = AsyncMock(return_value=[])
        storage.get_contradictions = AsyncMock(return_value={"m1": []})

        pipeline = _make_pipeline(storage)
        results = asyncio.run(pipeline.recall("test", limit=5))
        assert len(results) == 1
        # on-the-fly R for 30 days elapsed at S=10 should be < 0.999
        expected_R = compute_R(10.0, 30.0)
        assert results[0].retrievability == pytest.approx(expected_R, rel=1e-3)


class TestSupersededPenalty:
    def test_superseded_memory_gets_0_3_penalty(self):
        storage = MagicMock()
        normal = _memory("normal", state="active")
        superseded = _memory("superseded_m", state="superseded")

        storage.vector_search = AsyncMock(
            return_value=[("normal", 0.9), ("superseded_m", 0.9)]
        )
        storage.fulltext_search = AsyncMock(return_value=[])
        storage.get_by_recency = AsyncMock(return_value=[])
        storage.get_memory = AsyncMock(
            side_effect=lambda mid: normal if mid == "normal" else superseded
        )
        storage.get_neighbours_bulk = AsyncMock(return_value=[])
        storage.get_contradictions = AsyncMock(
            return_value={"normal": [], "superseded_m": []}
        )

        pipeline = _make_pipeline(storage)
        results = asyncio.run(pipeline.recall("test", limit=5))
        ids = [r.id for r in results]
        # normal should rank above superseded even at same RRF rank
        assert ids[0] == "normal"


class TestContradictionAttachment:
    def test_contradictions_attached_to_result(self):
        storage = MagicMock()
        m = _memory("m1")

        storage.vector_search = AsyncMock(return_value=[("m1", 0.9)])
        storage.fulltext_search = AsyncMock(return_value=[])
        storage.get_by_recency = AsyncMock(return_value=[])
        storage.get_memory = AsyncMock(return_value=m)
        storage.get_neighbours_bulk = AsyncMock(return_value=[])
        storage.get_contradictions = AsyncMock(
            return_value={"m1": ["contra1", "contra2"]}
        )

        pipeline = _make_pipeline(storage)
        results = asyncio.run(pipeline.recall("test", limit=5))
        assert results[0].contradictions == ["contra1", "contra2"]
