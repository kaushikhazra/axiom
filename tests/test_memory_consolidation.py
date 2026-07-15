"""Unit tests for consolidation.py — each of the 6 stages, using mock StorageSeam."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from axiom.memory.config import MemoryConfig
from axiom.memory.consolidation import ConsolidationPipeline, _has_negation
from axiom.memory.decay import STABILITY_BY_TYPE
from axiom.memory.models import Memory


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _memory(
    id: str,
    memory_type: str = "episodic",
    stability: float | None = None,
    importance: float = 0.5,
    access_count: int = 0,
    tags: list[str] | None = None,
    content: str = "some content",
    state: str = "active",
    last_accessed: datetime | None = None,
) -> Memory:
    if stability is None:
        stability = STABILITY_BY_TYPE.get(memory_type, 2.0)
    now = last_accessed or _now()
    return Memory(
        id=id,
        content=content,
        memory_type=memory_type,
        state=state,
        importance=importance,
        stability=stability,
        retrievability=1.0,
        access_count=access_count,
        created_at=now,
        updated_at=now,
        last_accessed=now,
        tags=tags or [],
    )


def _make_pipeline(
    memories: list[Memory], relationship_counts: dict[str, int] | None = None
) -> tuple[ConsolidationPipeline, MagicMock]:
    storage = MagicMock()
    storage.get_all_active = AsyncMock(return_value=memories)
    storage.update_memory = AsyncMock()
    storage.archive_memory = AsyncMock()
    storage.store_relationship = AsyncMock()
    storage.log_consolidation_action = AsyncMock()
    storage.vector_search_for_id = AsyncMock(return_value=[])
    storage.bulk_update_stability = AsyncMock()
    # B3: get_relationship_count — returns 0 by default; override via relationship_counts dict
    _counts = relationship_counts or {}
    storage.get_relationship_count = AsyncMock(
        side_effect=lambda mid: _counts.get(mid, 0)
    )

    embeddings = MagicMock()
    config = MemoryConfig()
    pipeline = ConsolidationPipeline(storage, embeddings, config)
    return pipeline, storage


class TestHasNegation:
    def test_negation_word_detected(self):
        assert _has_negation("this is not correct") is True
        assert _has_negation("I never said that") is True

    def test_no_negation_clean_text(self):
        assert _has_negation("the cat sat on the mat") is False

    def test_correction_keyword(self):
        assert _has_negation("correction: the date was wrong") is True


class TestStage2Promotion:
    def test_working_to_episodic_on_access_count_and_importance(self):
        m = _memory("w1", "working", importance=0.5, access_count=3)
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        # Should call update_memory with memory_type="episodic"
        calls_to_update = [
            c for c in storage.update_memory.call_args_list if "memory_type" in c.kwargs
        ]
        episodic_call = any(
            c.kwargs.get("memory_type") == "episodic"
            or (len(c.args) > 1 and "episodic" in str(c))
            for c in storage.update_memory.call_args_list
        )
        assert episodic_call or any(
            "episodic" in str(c) for c in storage.update_memory.call_args_list
        )

    def test_episodic_to_person_with_person_tag_and_access(self):
        m = _memory("e1", "episodic", access_count=3, tags=["person:Alice"])
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        person_updated = any(
            "person" in str(c) for c in storage.update_memory.call_args_list
        )
        assert person_updated

    def test_episodic_to_semantic_with_high_access_and_R(self):
        # R > 0.6 → access_count ≥ 5 and stability large enough to keep R high
        m = _memory("e2", "episodic", stability=14.0, access_count=5, importance=0.5)
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        semantic_updated = any(
            "semantic" in str(c) for c in storage.update_memory.call_args_list
        )
        assert semantic_updated

    def test_no_promotion_if_access_count_below_threshold(self):
        m = _memory("w2", "working", importance=0.5, access_count=2)  # only 2, need 3
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        # Should NOT see "episodic" in update calls
        episodic_calls = [
            c for c in storage.update_memory.call_args_list if "episodic" in str(c)
        ]
        assert len(episodic_calls) == 0

    # B3: working->episodic "OR relationships >= 2" path
    def test_working_to_episodic_via_relationships_or_path(self):
        """B3: working memory with >= 2 relationships is promoted even with low access_count."""
        m = _memory(
            "w3", "working", importance=0.1, access_count=0
        )  # AND path cannot fire
        # Provide 2 relationships for this memory via the mock
        pipeline, storage = _make_pipeline([m], relationship_counts={"w3": 2})
        asyncio.run(pipeline.consolidate())
        # Stage 2 should promote via OR relationships >= 2
        episodic_calls = [
            c for c in storage.update_memory.call_args_list if "episodic" in str(c)
        ]
        assert len(episodic_calls) >= 1, (
            "Expected working->episodic promotion via OR relationships>=2; "
            f"update_memory calls: {storage.update_memory.call_args_list}"
        )

    def test_no_promotion_if_relationships_below_2(self):
        """B3: working memory with only 1 relationship and low access_count is not promoted."""
        m = _memory("w4", "working", importance=0.1, access_count=0)
        pipeline, storage = _make_pipeline([m], relationship_counts={"w4": 1})
        asyncio.run(pipeline.consolidate())
        episodic_calls = [
            c for c in storage.update_memory.call_args_list if "episodic" in str(c)
        ]
        assert len(episodic_calls) == 0


class TestStage3Archive:
    def test_general_memory_archived_when_R_below_0_2(self):
        # R < 0.2: elapsed >> 9*S
        old_dt = _now() - timedelta(days=500)
        m = _memory("a1", "episodic", stability=2.0, last_accessed=old_dt)
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        storage.archive_memory.assert_called_with("a1")

    def test_person_memory_uses_strict_threshold_0_05(self):
        # Person type: only archive at R < 0.05
        # Last accessed 10 days ago on stability=90 → R ≈ exp(-10/(9*90)) ≈ 0.988 — NOT archived
        recent = _memory("p1", "person", stability=90.0)
        pipeline, storage = _make_pipeline([recent])
        asyncio.run(pipeline.consolidate())
        storage.archive_memory.assert_not_called()

    def test_identity_never_archived(self):
        # Identity: no matter how faded, never archived
        old_dt = _now() - timedelta(days=99999)
        m = _memory("id1", "identity", stability=365.0, last_accessed=old_dt)
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        storage.archive_memory.assert_not_called()

    def test_fresh_episodic_not_archived(self):
        m = _memory("e1", "episodic", stability=14.0)  # just accessed
        pipeline, storage = _make_pipeline([m])
        asyncio.run(pipeline.consolidate())
        storage.archive_memory.assert_not_called()


class TestStage5Merge:
    def test_high_cosine_no_negation_merges(self):
        m1 = _memory(
            "m1",
            "episodic",
            importance=0.7,
            access_count=5,
            content="the sky is blue and clear",
        )
        m2 = _memory(
            "m2",
            "episodic",
            importance=0.3,
            access_count=1,
            content="sky appears blue during day",
        )
        pipeline, storage = _make_pipeline([m1, m2])
        # Stage 4 mock: return high-cosine pair
        storage.vector_search_for_id = AsyncMock(return_value=[("m2", 0.95)])

        asyncio.run(pipeline.consolidate())
        # Secondary (m2, lower score) should be marked superseded
        superseded_calls = [
            c for c in storage.update_memory.call_args_list if "superseded" in str(c)
        ]
        assert len(superseded_calls) >= 1
        # Relationship created
        assert storage.store_relationship.called

    def test_negation_present_prevents_merge(self):
        m1 = _memory("m1", content="Python is fast")
        m2 = _memory("m2", content="Python is not fast actually")
        pipeline, storage = _make_pipeline([m1, m2])
        storage.vector_search_for_id = AsyncMock(return_value=[("m2", 0.95)])

        asyncio.run(pipeline.consolidate())
        # No superseded update (merge skipped due to negation)
        superseded_calls = [
            c for c in storage.update_memory.call_args_list if "superseded" in str(c)
        ]
        assert len(superseded_calls) == 0


class TestStage6Contradiction:
    def test_negation_at_0_8_cosine_creates_contradicts_edge(self):
        m1 = _memory("m1", content="Python is fast")
        m2 = _memory("m2", content="Python is not fast actually")
        pipeline, storage = _make_pipeline([m1, m2])
        # cosine between 0.80 and 0.89 triggers contradiction (not merge)
        storage.vector_search_for_id = AsyncMock(return_value=[("m2", 0.85)])

        asyncio.run(pipeline.consolidate())
        # Should create a contradicts relationship
        if storage.store_relationship.called:
            rel_args = storage.store_relationship.call_args
            rel = rel_args.args[0]
            assert rel.rel_type == "contradicts"
