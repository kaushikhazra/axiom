"""CognitiveMemoryAdapter — implements MemoryPort. Composition root for the memory faculty."""

from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from axiom.memory.classification import classify_type, score_importance
from axiom.memory.config import MemoryConfig
from axiom.memory.consolidation import ConsolidationPipeline
from axiom.memory.decay import STABILITY_BY_TYPE
from axiom.memory.embeddings import EmbeddingService
from axiom.memory.models import (
    AssembledContext,
    ConversationUnit,
    Memory,
    RecallResult,
    Relationship,
)
from axiom.memory.retrieval import RetrievalPipeline
from axiom.memory.storage import StorageSeam
from axiom.memory.working_context import WorkingContext

logger = logging.getLogger(__name__)


class CognitiveMemoryAdapter:
    """Implements MemoryPort. Wired at composition time; injected into PraoLoop."""

    def __init__(self, config: MemoryConfig | None = None) -> None:
        self._config = config or MemoryConfig()
        # Init sequence per design §14
        self._storage = StorageSeam(self._config.storage_path)
        self._embeddings = EmbeddingService()
        self._embeddings.warmup()
        self._working = WorkingContext(self._config)
        self._retrieval = RetrievalPipeline(
            self._storage, self._embeddings, self._config
        )
        self._consolidation = ConsolidationPipeline(
            self._storage, self._embeddings, self._config
        )
        logger.info("CognitiveMemoryAdapter ready")

    # ── Awaited methods ───────────────────────────────────────────────────────

    async def assemble_context(
        self,
        query: str,
        conversation_id: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> AssembledContext:
        query_embedding = await self._embeddings.embed(query)
        working = self._working.assemble(query_embedding)
        cognitive = await self._retrieval.recall(
            query, tags=tags, limit=limit or self._config.k_cognitive
        )
        return AssembledContext(working_context=working, cognitive_memories=cognitive)

    async def recall(
        self,
        query: str,
        context: dict | None = None,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[RecallResult]:
        return await self._retrieval.recall(query, context, type_filter, tags, limit)

    async def append_unit(self, unit: ConversationUnit) -> None:
        """Working-context write path. Awaited. Embeds unit, sets token_count, appends to buffer."""
        embedding = await self._embeddings.embed(unit.user_text + " " + unit.agent_text)
        unit.embedding = embedding
        unit.token_count = len(unit.user_text + unit.agent_text) // 4
        self._working.add_unit(unit)

    async def consolidate(self) -> list[dict]:
        return await self._consolidation.consolidate()

    async def stats(self) -> dict:
        by_type = await self._storage.get_counts_by_type()
        by_state = await self._storage.get_counts_by_state()
        total = await self._storage.get_total_count()
        return {
            "total": total,
            "by_type": by_type,
            "by_state": by_state,
            "working_context_size": len(self._working),
        }

    async def health(self) -> dict:
        try:
            total = await self._storage.get_total_count()
            return {"status": "ok", "total_memories": total}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Cognitive store ───────────────────────────────────────────────────────

    async def store(
        self,
        content: str,
        memory_type: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> str:
        """Cognitive store ONLY. Awaits embed+insert end-to-end; does NOT write
        to working-context buffer.

        B3-store fix: _embed_and_store is awaited directly (not wrapped in
        create_task) so the work completes before the caller's asyncio.run()
        teardown can cancel pending tasks. This mirrors the B2 fix applied to
        reinforce() — fire-and-forget via create_task is cancelled on teardown;
        awaiting directly makes the write durable.
        """
        memory_id = str(uuid.uuid4())

        if memory_type is None:
            memory_type, _conf = classify_type(content)
        importance_val = score_importance(content, memory_type, importance)
        stability = STABILITY_BY_TYPE.get(memory_type, 2.0)
        now = datetime.now(timezone.utc)

        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            state="active",
            importance=importance_val,
            stability=stability,
            retrievability=1.0,
            access_count=0,
            created_at=now,
            updated_at=now,
            last_accessed=now,
            source=source,
            tags=tags or [],
        )

        # B3-store fix: await directly so embed+insert completes before teardown.
        await self._embed_and_store(memory)
        return memory_id

    async def _embed_and_store(self, memory: Memory) -> None:
        """Background task: embed content and write to cognitive store."""
        try:
            embedding = await self._embeddings.embed(memory.content)
            await self._storage.store_memory_with_embedding(memory, embedding)
            # Auto-link: find similar memories (cosine >= threshold)
            await self._auto_link(memory.id)
        except Exception as e:
            logger.error("_embed_and_store failed for %s: %s", memory.id, e)

    async def _auto_link(self, memory_id: str) -> None:
        """Create relates_to edges for similar memories (cosine >= auto_link_threshold)."""
        try:
            similar = await self._storage.vector_search_for_id(memory_id, top_k=10)
            now = datetime.now(timezone.utc)
            for other_id, cosine_score in similar:
                if cosine_score >= self._config.auto_link_threshold:
                    rel = Relationship(
                        id=str(uuid.uuid4()),
                        source_id=memory_id,
                        target_id=other_id,
                        rel_type="relates_to",
                        strength=cosine_score * 0.9,  # auto-links always < 1.0
                        created_at=now,
                    )
                    try:
                        await self._storage.store_relationship(rel)
                    except Exception as dup_err:
                        # W2: log at debug so duplicate-edge noise doesn't hide real errors
                        logger.debug(
                            "Auto-link store_relationship skipped: %s", dup_err
                        )
        except Exception as e:
            logger.debug("Auto-link failed for %s: %s", memory_id, e)

    async def reinforce(self, ids: list[str]) -> None:
        """Stability boost for used memories.

        B2 fix: _do_reinforce is awaited directly here (not double-wrapped in
        create_task). The loop is responsible for dispatching via create_task if
        fire-and-forget is desired; the adapter must not add a second layer.
        Direct await makes the work durable — it completes before the caller's
        task returns, so asyncio.run() teardown cannot cancel it.
        """
        await self._do_reinforce(ids)

    async def _do_reinforce(self, ids: list[str]) -> None:
        from axiom.memory.decay import compute_R, reinforce_stability  # noqa: PLC0415

        now = datetime.now(timezone.utc)
        try:
            updates = []
            for mid in ids:
                m = await self._storage.get_memory(mid)
                if m is None or m.state != "active":
                    continue
                la = m.last_accessed
                if la.tzinfo is None:
                    la = la.replace(tzinfo=timezone.utc)
                elapsed = (now - la).total_seconds() / 86400.0
                R = compute_R(m.stability, elapsed)
                new_s = reinforce_stability(m.stability, R, self._config.growth_factor)
                updates.append((mid, new_s, 0.0))
                # B1 fix: increment access_count for every reinforced memory
                await self._storage.update_memory(
                    mid, access_count=m.access_count + 1, updated_at=now
                )
            if updates:
                await self._storage.bulk_update_stability(updates)
        except Exception as e:
            logger.warning("reinforce failed: %s", e)

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
    ) -> None:
        asyncio.create_task(self._do_update(memory_id, content, importance, tags))

    async def _do_update(self, memory_id, content, importance, tags) -> None:
        now = datetime.now(timezone.utc)
        fields = {"updated_at": now}
        if content is not None:
            fields["content"] = content
        if importance is not None:
            fields["importance"] = importance
        if tags is not None:
            fields["tags"] = tags
        try:
            await self._storage.update_memory(memory_id, **fields)
        except Exception as e:
            logger.warning("update failed for %s: %s", memory_id, e)

    async def relate(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float = 1.0,
    ) -> None:
        asyncio.create_task(self._do_relate(source_id, target_id, rel_type, strength))

    def close(self) -> None:
        """G1 fix: release storage file handle and shut down embedding executor.

        Call after consolidate() in the shutdown sequence. Safe to call multiple times.
        """
        try:
            self._embeddings.shutdown()
        except Exception as e:
            logger.warning("EmbeddingService shutdown error: %s", e)
        try:
            self._storage.close()
        except Exception as e:
            logger.warning("StorageSeam close error: %s", e)
        logger.info("CognitiveMemoryAdapter closed")

    async def _do_relate(self, source_id, target_id, rel_type, strength) -> None:
        now = datetime.now(timezone.utc)
        rel = Relationship(
            id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            strength=strength,
            created_at=now,
        )
        try:
            await self._storage.store_relationship(rel)
        except Exception as e:
            logger.warning("relate failed: %s", e)
