"""Consolidation pipeline — 6-stage pipeline run at session close."""

from __future__ import annotations
import logging
import re
import uuid
from datetime import datetime, timezone

from axiom.memory.config import MemoryConfig
from axiom.memory.decay import compute_R, STABILITY_BY_TYPE
from axiom.memory.embeddings import EmbeddingService
from axiom.memory.models import Memory, Relationship
from axiom.memory.storage import StorageSeam

logger = logging.getLogger(__name__)

NEGATION_CUES = {
    "not",
    "never",
    "no",
    "wrong",
    "incorrect",
    "false",
    "mistake",
    "but",
    "however",
    "actually",
    "contradicts",
    "contradicted",
    "disagree",
    "disagrees",
    "retract",
    "retracted",
    "changed",
    "updated",
    "correction",
}

_PROCEDURAL_PATTERNS = re.compile(
    r"\b(how to|steps|workflow|process|procedure|guide|instructions|method)\b",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"\b\w+\b")


def _has_negation(content: str) -> bool:
    words = {w.lower() for w in _WORD_RE.findall(content)}
    return bool(words & NEGATION_CUES)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_days(last_accessed: datetime) -> float:
    now = _now_utc()
    la = last_accessed
    if la.tzinfo is None:
        la = la.replace(tzinfo=timezone.utc)
    return (now - la).total_seconds() / 86400.0


class ConsolidationPipeline:
    def __init__(
        self, storage: StorageSeam, embeddings: EmbeddingService, config: MemoryConfig
    ) -> None:
        self._storage = storage
        self._embeddings = embeddings
        self._config = config

    async def consolidate(self) -> list[dict]:
        log: list[dict] = []

        # Check debounce
        if self._config.consolidation_debounce_sessions > 0:
            # Future: check session counter; for now always run
            pass

        memories = await self._storage.get_all_active()
        now = _now_utc()

        # Stage 1: Decay update
        log.extend(await self._stage1_decay_update(memories, now))

        # Stage 2: Type promotion
        memories = await self._storage.get_all_active()  # refresh
        log.extend(await self._stage2_promotion(memories, now))

        # Stage 3: Archive pass
        memories = await self._storage.get_all_active()
        log.extend(await self._stage3_archive(memories, now))

        # Stage 4: Cluster scan (find similar pairs)
        memories = await self._storage.get_all_active()
        candidate_pairs = await self._stage4_cluster_scan(memories)

        # Stage 5: Merge pass
        merged_ids: set[str] = set()
        log.extend(await self._stage5_merge(candidate_pairs, merged_ids))

        # Stage 6: Contradiction flag
        log.extend(await self._stage6_contradiction(candidate_pairs, merged_ids))

        # Log all actions to storage
        for action in log:
            try:
                await self._storage.log_consolidation_action(action)
            except Exception as e:
                logger.warning("Failed to log consolidation action: %s", e)

        logger.info("Consolidation complete: %d actions", len(log))
        return log

    async def _stage1_decay_update(
        self, memories: list[Memory], now: datetime
    ) -> list[dict]:
        """Recompute R for all active memories; write retrievability snapshot."""
        for m in memories:
            elapsed = _elapsed_days(m.last_accessed)
            R = compute_R(m.stability, elapsed)
            await self._storage.update_memory(
                m.id,
                retrievability=R,
                updated_at=now,
            )
        return []  # Stage 1 doesn't produce log entries

    async def _stage2_promotion(
        self, memories: list[Memory], now: datetime
    ) -> list[dict]:
        """Type promotion pass."""
        log = []
        for m in memories:
            elapsed = _elapsed_days(m.last_accessed)
            R = compute_R(m.stability, elapsed)
            new_type = None

            if m.memory_type == "working":
                # working -> episodic: access_count >= 3 AND importance >= 0.4, OR relationships >= 2
                if m.access_count >= 3 and m.importance >= 0.4:
                    new_type = "episodic"
                else:
                    # B3 fix: check the OR branch — relationships >= 2
                    rel_count = await self._storage.get_relationship_count(m.id)
                    if rel_count >= 2:
                        new_type = "episodic"

            elif m.memory_type == "episodic":
                if "person:" in " ".join(m.tags) and m.access_count >= 3:
                    new_type = "person"
                elif _PROCEDURAL_PATTERNS.search(m.content) and m.access_count >= 3:
                    new_type = "procedural"
                elif m.access_count >= 5 and R > 0.6:
                    new_type = "semantic"

            elif m.memory_type == "semantic":
                if "person:" in " ".join(m.tags) and m.access_count >= 3:
                    new_type = "person"

            if new_type:
                new_s = STABILITY_BY_TYPE.get(new_type, m.stability)
                await self._storage.update_memory(
                    m.id,
                    memory_type=new_type,
                    stability=new_s,
                    updated_at=now,
                )
                entry = {
                    "action": "promote",
                    "source_ids": [m.id],
                    "target_id": None,
                    "reason": f"{m.memory_type} -> {new_type}",
                }
                log.append(entry)
        return log

    async def _stage3_archive(
        self, memories: list[Memory], now: datetime
    ) -> list[dict]:
        """Archive pass: R < threshold, except identity never archived."""
        log = []
        for m in memories:
            if m.memory_type == "identity":
                continue
            elapsed = _elapsed_days(m.last_accessed)
            R = compute_R(m.stability, elapsed)
            threshold = 0.05 if m.memory_type == "person" else 0.2
            if R < threshold:
                await self._storage.archive_memory(m.id)
                entry = {
                    "action": "archive",
                    "source_ids": [m.id],
                    "target_id": None,
                    "reason": f"R={R:.3f} < {threshold} ({m.memory_type})",
                }
                log.append(entry)
        return log

    async def _stage4_cluster_scan(
        self, memories: list[Memory]
    ) -> list[tuple[Memory, Memory, float]]:
        """Find candidate similar pairs (cosine >= 0.75) for merge/contradiction."""
        pairs: list[tuple[Memory, Memory, float]] = []
        mem_map = {m.id: m for m in memories}

        for m in memories:
            similar = await self._storage.vector_search_for_id(m.id, top_k=10)
            for other_id, cosine_score in similar:
                if cosine_score >= 0.75 and other_id in mem_map:
                    other = mem_map[other_id]
                    # Avoid duplicate pairs (only add if m.id < other.id)
                    if m.id < other.id:
                        pairs.append((m, other, cosine_score))
        return pairs

    async def _stage5_merge(
        self,
        candidate_pairs: list[tuple[Memory, Memory, float]],
        merged_ids: set[str],
    ) -> list[dict]:
        """Merge pass: cosine >= 0.90 + no negation -> merge."""
        log = []
        now = _now_utc()
        for m1, m2, cosine in candidate_pairs:
            if cosine < 0.90:
                continue
            if m1.id in merged_ids or m2.id in merged_ids:
                continue
            if _has_negation(m1.content) or _has_negation(m2.content):
                continue  # let Stage 6 handle

            # Determine primary (higher importance × access_count)
            score1 = m1.importance * max(m1.access_count, 1)
            score2 = m2.importance * max(m2.access_count, 1)
            primary, secondary = (m1, m2) if score1 >= score2 else (m2, m1)

            # Archive secondary, mark superseded
            await self._storage.update_memory(
                secondary.id, state="superseded", updated_at=now
            )

            # Create SUPERSEDES relationship
            rel = Relationship(
                id=str(uuid.uuid4()),
                source_id=secondary.id,
                target_id=primary.id,
                rel_type="supersedes",
                strength=1.0,
                created_at=now,
            )
            try:
                await self._storage.store_relationship(rel)
            except Exception as e:
                logger.warning("Failed to store supersedes rel: %s", e)

            merged_ids.add(secondary.id)
            log.append(
                {
                    "action": "merge",
                    "source_ids": [secondary.id],
                    "target_id": primary.id,
                    "reason": f"cosine={cosine:.3f}, merged into primary",
                }
            )
        return log

    async def _stage6_contradiction(
        self,
        candidate_pairs: list[tuple[Memory, Memory, float]],
        merged_ids: set[str],
    ) -> list[dict]:
        """Contradiction flag: cosine >= 0.80 + negation -> CONTRADICTS edge."""
        log = []
        now = _now_utc()
        for m1, m2, cosine in candidate_pairs:
            if cosine < 0.80:
                continue
            if m1.id in merged_ids or m2.id in merged_ids:
                continue
            if not (_has_negation(m1.content) or _has_negation(m2.content)):
                continue

            rel = Relationship(
                id=str(uuid.uuid4()),
                source_id=m1.id,
                target_id=m2.id,
                rel_type="contradicts",
                strength=1.0,
                created_at=now,
            )
            try:
                await self._storage.store_relationship(rel)
            except Exception as e:
                logger.warning("Failed to store contradicts rel: %s", e)

            log.append(
                {
                    "action": "flag_contradiction",
                    "source_ids": [m1.id, m2.id],
                    "target_id": None,
                    "reason": f"cosine={cosine:.3f} with negation signals",
                }
            )
        return log
