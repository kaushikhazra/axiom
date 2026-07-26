"""Multi-strategy retrieval pipeline: semantic + keyword + temporal, RRF, decay rerank, graph."""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from axiom.memory.config import MemoryConfig
from axiom.memory.decay import compute_R, compute_spreading_boost
from axiom.memory.embeddings import EmbeddingService
from axiom.memory.models import Memory, RecallResult
from axiom.memory.storage import StorageSeam

logger = logging.getLogger(__name__)

RRF_K = 60
W_SEMANTIC = 1.0
W_KEYWORD = 0.7
W_TEMPORAL = 0.3
W_GRAPH = 0.5
SUPERSEDED_PENALTY = 0.3
TOP_SEEDS_FOR_GRAPH = 5


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_days(last_accessed: datetime) -> float:
    now = _now_utc()
    la = last_accessed
    if la.tzinfo is None:
        la = la.replace(tzinfo=timezone.utc)
    return (now - la).total_seconds() / 86400.0


class RetrievalPipeline:
    def __init__(
        self, storage: StorageSeam, embeddings: EmbeddingService, config: MemoryConfig
    ) -> None:
        self._storage = storage
        self._embeddings = embeddings
        self._config = config

    async def recall(
        self,
        query: str,
        context: dict | None = None,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[RecallResult]:
        limit = limit or self._config.k_cognitive
        candidate_limit = min(limit * 3, 30)

        # Embed the query
        query_embedding = await self._embeddings.embed(query)

        # Phase 1: concurrent strategies
        semantic_coro = self._storage.vector_search(
            query_embedding, candidate_limit, type_filter
        )
        keyword_coro = self._storage.fulltext_search(query, candidate_limit)
        temporal_coro = self._storage.get_by_recency(candidate_limit)

        semantic_results, keyword_results, temporal_results = await asyncio.gather(
            semantic_coro, keyword_coro, temporal_coro
        )

        # type_filter is only enforced by vector_search's own query (semantic
        # strategy) -- fulltext_search/get_by_recency have no type awareness.
        # Re-apply it here so a type_filter caller never sees another type's
        # memory compete for or win a final ranked slot (M8 finding: an
        # untyped keyword/temporal hit was crowding out real type_filter="lesson"
        # results in RRF fusion, silently and without error).
        if type_filter is not None:
            memories_for_filter: dict[str, Memory] = {}

            async def _keep(mid: str) -> bool:
                m = memories_for_filter.get(mid)
                if m is None:
                    m = await self._storage.get_memory(mid)
                    if m is None:
                        return False
                    memories_for_filter[mid] = m
                return m.memory_type == type_filter

            keyword_results = [
                (mid, score) for mid, score in keyword_results if await _keep(mid)
            ]
            temporal_results = [
                (mid, score) for mid, score in temporal_results if await _keep(mid)
            ]

        # RRF fusion
        rrf_scores: dict[str, float] = {}
        found_by: dict[str, list[str]] = {}

        def _add_strategy(
            results: list[tuple[str, float]], weight: float, name: str
        ) -> None:
            for rank, (mid, _score) in enumerate(results):
                rrf_scores[mid] = rrf_scores.get(mid, 0.0) + weight / (RRF_K + rank + 1)
                found_by.setdefault(mid, [])
                if name not in found_by[mid]:
                    found_by[mid].append(name)

        _add_strategy(semantic_results, W_SEMANTIC, "semantic")
        _add_strategy(keyword_results, W_KEYWORD, "keyword")
        _add_strategy(temporal_results, W_TEMPORAL, "temporal")

        # Fetch memories for scoring (need stability + last_accessed for R)
        all_ids = list(rrf_scores.keys())
        memories: dict[str, Memory] = {}
        for mid in all_ids:
            m = await self._storage.get_memory(mid)
            if m:
                memories[mid] = m

        # Post-RRF decay reranking
        decay_influence = self._config.decay_influence
        final_scores: dict[str, float] = {}
        for mid, rrf in rrf_scores.items():
            m = memories.get(mid)
            if m is None:
                continue
            elapsed = _elapsed_days(m.last_accessed)
            R = compute_R(m.stability, elapsed)
            score = rrf * (R**decay_influence)
            if m.state == "superseded":
                score *= SUPERSEDED_PENALTY
            final_scores[mid] = score

        # Sort Phase 1 results
        ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        top_seeds = [mid for mid, _ in ranked[:TOP_SEEDS_FOR_GRAPH]]

        # Phase 2: graph traversal
        if top_seeds:
            neighbours = await self._storage.get_neighbours_bulk(top_seeds, max_depth=3)
            for nid, depth, rel_strength in neighbours:
                if nid not in final_scores:
                    # Score graph neighbours
                    m = await self._storage.get_memory(nid)
                    if m is None:
                        continue
                    memories[nid] = m
                    graph_rank = len(final_scores)
                    graph_score = W_GRAPH / (RRF_K + graph_rank)
                    elapsed = _elapsed_days(m.last_accessed)
                    R = compute_R(m.stability, elapsed)
                    graph_score *= R**decay_influence
                    final_scores[nid] = graph_score
                    found_by.setdefault(nid, [])
                    if "graph" not in found_by[nid]:
                        found_by[nid].append("graph")

        # Final rank
        final_ranked = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]
        result_ids = [mid for mid, _ in final_ranked]

        # Contradiction lookup
        contradictions = await self._storage.get_contradictions(result_ids)

        # Build RecallResult objects
        results = []
        for mid, score in final_ranked:
            m = memories.get(mid)
            if m is None:
                continue
            elapsed = _elapsed_days(m.last_accessed)
            R = compute_R(m.stability, elapsed)
            results.append(
                RecallResult(
                    id=mid,
                    content=m.content,
                    memory_type=m.memory_type,
                    importance=m.importance,
                    retrievability=R,
                    score=score,
                    found_by=found_by.get(mid, []),
                    tags=m.tags,
                    created_at=m.created_at,
                    last_accessed=m.last_accessed,
                    contradictions=contradictions.get(mid, []),
                )
            )

        # Spreading activation write-back (fire-and-forget — does not block recall return).
        # Use only the Phase-1 top seeds as activation sources, not all result_ids.
        # This prevents recall results from excluding themselves as neighbour targets
        # (get_neighbours_bulk skips ids in original_ids set).
        if top_seeds:
            asyncio.create_task(self._spreading_activation_writeback(top_seeds))

        return results

    async def _spreading_activation_writeback(self, seed_ids: list[str]) -> None:
        """Update stability for graph neighbours of recalled memories (3-hop, fire-and-forget)."""
        try:
            neighbours = await self._storage.get_neighbours_bulk(seed_ids, max_depth=3)
            updates = []
            for nid, depth, rel_strength in neighbours:
                m = await self._storage.get_memory(nid)
                if m is None or m.state != "active":
                    continue
                boost = compute_spreading_boost(rel_strength, depth)
                new_s = m.stability * (1.0 + boost)
                updates.append((nid, new_s, 0.0))
            if updates:
                await self._storage.bulk_update_stability(updates)
        except Exception as e:
            logger.warning("Spreading activation writeback failed: %s", e)
