"""StorageSeam — thin abstraction over embedded SurrealKV. ONLY file that imports surrealdb."""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from surrealdb import Surreal

from axiom.memory.models import Memory, Relationship
from axiom.memory.schema import init_schema

logger = logging.getLogger(__name__)

REL_TABLES = {
    "causes": "causes",
    "follows": "follows",
    "contradicts": "contradicts",
    "supports": "supports",
    "relates_to": "relates_to",
    "supersedes": "supersedes",
    "part_of": "part_of",
    "describes": "describes",
}


def _to_surrealkv_uri(storage_path: str) -> str:
    """Convert a storage_path to a surrealkv:// URI with forward slashes (Windows compat)."""
    path = os.path.expanduser(storage_path)
    # Ensure parent directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # Windows: convert backslashes to forward slashes for the URI
    uri_path = path.replace("\\", "/")
    return f"surrealkv://{uri_path}"


def _extract_id(surreal_id) -> str:
    """Extract the plain ID from a SurrealDB RecordID (strips table prefix and angle brackets)."""
    s = str(surreal_id)
    if ":" in s:
        s = s.split(":", 1)[1]
    return s.strip("\u27e8\u27e9")


def _parse_dt(val) -> datetime:
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val))


def _rows(result) -> list[dict]:
    """Normalize SurrealDB query result to a flat list of dicts."""
    if not result:
        return []
    if isinstance(result, list):
        if result and isinstance(result[0], dict):
            return result
        flat = []
        for item in result:
            if isinstance(item, list):
                flat.extend(item)
            elif isinstance(item, dict):
                if "result" in item:
                    r = item["result"]
                    flat.extend(r if isinstance(r, list) else [r])
                else:
                    flat.append(item)
        return flat
    if isinstance(result, dict):
        return [result]
    return []


class StorageSeam:
    """Thin Axiom abstraction over embedded SurrealKV.

    All methods are async (per design §10.2) but call surrealdb synchronously
    (the embedded SDK is blocking). No executor needed — DB ops are fast (<5ms).
    """

    def __init__(self, storage_path: str) -> None:
        uri = _to_surrealkv_uri(storage_path)
        logger.info("StorageSeam: opening %s", uri)
        self._db = Surreal(uri)
        self._db.connect()
        self._db.use("axiom", "memory")
        init_schema(self._db)
        logger.info("StorageSeam: ready")

    def _row_to_memory(self, row: dict) -> Memory:
        return Memory(
            id=_extract_id(row["id"]),
            content=row["content"],
            memory_type=row["memory_type"],
            state=row["state"],
            importance=row["importance"],
            stability=row["stability"],
            retrievability=row["retrievability"],
            access_count=row["access_count"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            last_accessed=_parse_dt(row["last_accessed"]),
            source=row.get("source"),
            conversation_id=row.get("conversation_id"),
            tags=row.get("tags") or [],
        )

    # ── Memory CRUD ──────────────────────────────────────────────────────────

    async def store_memory(self, memory: Memory) -> None:
        self._db.query(
            "CREATE type::thing('memory', $id) SET "
            "content = $content, memory_type = $mtype, state = $state, "
            "importance = $imp, stability = $stab, retrievability = $retr, "
            "access_count = $ac, created_at = $cat, updated_at = $uat, "
            "last_accessed = $la, source = $src, conversation_id = $cid, "
            "tags = $tags, embedding = NONE",
            {
                "id": memory.id,
                "content": memory.content,
                "mtype": memory.memory_type,
                "state": memory.state,
                "imp": memory.importance,
                "stab": memory.stability,
                "retr": memory.retrievability,
                "ac": memory.access_count,
                "cat": memory.created_at,
                "uat": memory.updated_at,
                "la": memory.last_accessed,
                "src": memory.source,
                "cid": memory.conversation_id,
                "tags": memory.tags,
            },
        )

    async def store_memory_with_embedding(
        self, memory: Memory, embedding: list[float]
    ) -> None:
        self._db.query(
            "CREATE type::thing('memory', $id) SET "
            "content = $content, memory_type = $mtype, state = $state, "
            "importance = $imp, stability = $stab, retrievability = $retr, "
            "access_count = $ac, created_at = $cat, updated_at = $uat, "
            "last_accessed = $la, source = $src, conversation_id = $cid, "
            "tags = $tags, embedding = $emb",
            {
                "id": memory.id,
                "content": memory.content,
                "mtype": memory.memory_type,
                "state": memory.state,
                "imp": memory.importance,
                "stab": memory.stability,
                "retr": memory.retrievability,
                "ac": memory.access_count,
                "cat": memory.created_at,
                "uat": memory.updated_at,
                "la": memory.last_accessed,
                "src": memory.source,
                "cid": memory.conversation_id,
                "tags": memory.tags,
                "emb": embedding,
            },
        )

    async def get_memory(self, memory_id: str) -> Memory | None:
        result = self._db.query(
            "SELECT * FROM type::thing('memory', $id)", {"id": memory_id}
        )
        rows = _rows(result)
        return self._row_to_memory(rows[0]) if rows else None

    async def update_memory(self, memory_id: str, **fields) -> None:
        if not fields:
            return
        set_parts, params = [], {"id": memory_id}
        for key, value in fields.items():
            pname = f"f_{key}"
            set_parts.append(f"{key} = ${pname}")
            params[pname] = value
        self._db.query(
            f"UPDATE type::thing('memory', $id) SET {', '.join(set_parts)}", params
        )

    async def update_embedding(self, memory_id: str, embedding: list[float]) -> None:
        self._db.query(
            "UPDATE type::thing('memory', $id) SET embedding = $emb",
            {"id": memory_id, "emb": embedding},
        )

    async def archive_memory(self, memory_id: str) -> None:
        now = datetime.now(timezone.utc)
        self._db.query(
            "UPDATE type::thing('memory', $id) SET state = 'archived', updated_at = $now",
            {"id": memory_id, "now": now},
        )

    async def get_all_active(self) -> list[Memory]:
        result = self._db.query("SELECT * FROM memory WHERE state = 'active'")
        return [self._row_to_memory(r) for r in _rows(result)]

    # ── Search ───────────────────────────────────────────────────────────────

    async def vector_search(
        self, embedding: list[float], limit: int, type_filter: str | None = None
    ) -> list[tuple[str, float]]:
        if type_filter:
            result = self._db.query(
                "SELECT id, vector::similarity::cosine(embedding, $vec) AS score "
                "FROM memory WHERE state = 'active' AND memory_type = $mtype AND embedding != NONE "
                "ORDER BY score DESC LIMIT $lim",
                {"vec": embedding, "mtype": type_filter, "lim": limit},
            )
        else:
            result = self._db.query(
                "SELECT id, vector::similarity::cosine(embedding, $vec) AS score "
                "FROM memory WHERE state = 'active' AND embedding != NONE "
                "ORDER BY score DESC LIMIT $lim",
                {"vec": embedding, "lim": limit},
            )
        return [(_extract_id(r["id"]), r["score"]) for r in _rows(result)]

    async def fulltext_search(self, query: str, limit: int) -> list[tuple[str, float]]:
        result = self._db.query(
            "SELECT id, search::score(1) AS score FROM memory "
            "WHERE content @1@ $q AND state = 'active' ORDER BY score DESC LIMIT $lim",
            {"q": query, "lim": limit},
        )
        return [(_extract_id(r["id"]), r.get("score", 0.0)) for r in _rows(result)]

    async def get_by_recency(self, limit: int) -> list[tuple[str, float]]:
        """Return (id, recency_score) where recency_score = e^(-elapsed_days/30)."""
        result = self._db.query(
            "SELECT id, last_accessed FROM memory WHERE state = 'active' "
            "ORDER BY last_accessed DESC LIMIT $lim",
            {"lim": limit},
        )
        now = datetime.now(timezone.utc)
        out = []
        for r in _rows(result):
            la = _parse_dt(r["last_accessed"])
            if la.tzinfo is None:
                la = la.replace(tzinfo=timezone.utc)
            elapsed_days = (now - la).total_seconds() / 86400.0
            score = math.exp(-elapsed_days / 30.0)
            out.append((_extract_id(r["id"]), score))
        return out

    async def vector_search_for_id(
        self, memory_id: str, top_k: int
    ) -> list[tuple[str, float]]:
        """Find memories similar to an existing memory (two sequential queries, no LET)."""
        # Step 1: get embedding
        result1 = self._db.query(
            "SELECT embedding FROM type::thing('memory', $id)", {"id": memory_id}
        )
        rows1 = _rows(result1)
        if not rows1 or rows1[0].get("embedding") is None:
            return []
        embedding = rows1[0]["embedding"]
        # Step 2: vector search with that embedding
        result2 = self._db.query(
            "SELECT id, vector::similarity::cosine(embedding, $vec) AS score "
            "FROM memory WHERE state = 'active' AND embedding != NONE "
            "AND id != type::thing('memory', $excl) ORDER BY score DESC LIMIT $lim",
            {"vec": embedding, "excl": memory_id, "lim": top_k},
        )
        return [(_extract_id(r["id"]), r["score"]) for r in _rows(result2)]

    # ── Relationships ─────────────────────────────────────────────────────────

    async def store_relationship(self, rel: Relationship) -> None:
        table = REL_TABLES[rel.rel_type]
        # Embedded SDK does not support type::thing() inside RELATE.
        # Use record-ID literal syntax instead: memory:⟨uuid⟩ → table → memory:⟨uuid⟩.
        # The angle-bracket form handles UUIDs that contain hyphens without quoting issues.
        src_rid = f"memory:\u27e8{rel.source_id}\u27e9"
        tgt_rid = f"memory:\u27e8{rel.target_id}\u27e9"
        self._db.query(
            f"RELATE {src_rid}->{table}->{tgt_rid} "
            f"SET strength = $strength, created_at = $cat",
            {
                "strength": rel.strength,
                "cat": rel.created_at,
            },
        )

    async def get_neighbours_bulk(
        self, ids: list[str], max_depth: int = 3
    ) -> list[tuple[str, int, float]]:
        """Return (neighbour_id, depth, rel_strength) for all neighbours up to max_depth.

        Uses sequential queries (one per hop) to avoid LET. Collects unique neighbours.
        """
        if not ids:
            return []

        all_neighbours: dict[str, tuple[int, float]] = {}  # id -> (depth, strength)
        current_seeds = set(ids)
        original_ids = set(ids)

        for depth in range(1, max_depth + 1):
            if not current_seeds:
                break
            next_seeds = set()

            for table in REL_TABLES.values():
                # Outgoing
                for seed_id in current_seeds:
                    result = self._db.query(
                        f"SELECT out, strength FROM {table} WHERE in = type::thing('memory', $id)",
                        {"id": seed_id},
                    )
                    for r in _rows(result):
                        nid = _extract_id(r["out"])
                        if nid not in original_ids and nid not in all_neighbours:
                            strength = r.get("strength", 1.0)
                            all_neighbours[nid] = (depth, strength)
                            next_seeds.add(nid)
                # Incoming
                for seed_id in current_seeds:
                    result = self._db.query(
                        f"SELECT in, strength FROM {table} WHERE out = type::thing('memory', $id)",
                        {"id": seed_id},
                    )
                    for r in _rows(result):
                        nid = _extract_id(r["in"])
                        if nid not in original_ids and nid not in all_neighbours:
                            strength = r.get("strength", 1.0)
                            all_neighbours[nid] = (depth, strength)
                            next_seeds.add(nid)

            current_seeds = next_seeds

        return [
            (nid, depth, strength) for nid, (depth, strength) in all_neighbours.items()
        ]

    async def bulk_update_stability(
        self,
        updates: list[tuple[str, float, float]],  # (id, new_S, new_last_accessed_epoch)
    ) -> None:
        """Update stability for multiple memories."""
        now = datetime.now(timezone.utc)
        for memory_id, new_s, _new_la in updates:
            self._db.query(
                "UPDATE type::thing('memory', $id) SET stability = $s, last_accessed = $now",
                {"id": memory_id, "s": new_s, "now": now},
            )

    async def log_consolidation_action(self, action: dict) -> None:
        import uuid

        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        self._db.query(
            "CREATE type::thing('consolidation_log', $id) SET "
            "action = $action, source_ids = $sids, target_id = $tid, "
            "reason = $reason, created_at = $cat",
            {
                "id": log_id,
                "action": action.get("action", ""),
                "sids": action.get("source_ids", []),
                "tid": action.get("target_id"),
                "reason": action.get("reason", ""),
                "cat": now,
            },
        )

    async def get_contradictions(self, ids: list[str]) -> dict[str, list[str]]:
        result_map: dict[str, list[str]] = {mid: [] for mid in ids}
        for mid in ids:
            result = self._db.query(
                "SELECT out FROM contradicts WHERE in = type::thing('memory', $id) AND out.state = 'active'",
                {"id": mid},
            )
            for r in _rows(result):
                result_map[mid].append(_extract_id(r["out"]))
            result2 = self._db.query(
                "SELECT in FROM contradicts WHERE out = type::thing('memory', $id) AND in.state = 'active'",
                {"id": mid},
            )
            for r in _rows(result2):
                result_map[mid].append(_extract_id(r["in"]))
        return result_map

    # ── Stats helpers ─────────────────────────────────────────────────────────

    async def get_counts_by_type(self) -> dict[str, int]:
        result = self._db.query(
            "SELECT memory_type, count() AS cnt FROM memory GROUP BY memory_type"
        )
        return {r["memory_type"]: r["cnt"] for r in _rows(result)}

    async def get_counts_by_state(self) -> dict[str, int]:
        result = self._db.query(
            "SELECT state, count() AS cnt FROM memory GROUP BY state"
        )
        return {r["state"]: r["cnt"] for r in _rows(result)}

    async def get_total_count(self) -> int:
        result = self._db.query("SELECT count() AS cnt FROM memory GROUP ALL")
        rows = _rows(result)
        return rows[0].get("cnt", 0) if rows else 0

    async def get_relationship_count(self, memory_id: str) -> int:
        """Count total edges (outgoing + incoming) for a memory across all relation tables.

        B3: Used by consolidation Stage 2 to check the 'OR relationships >= 2'
        working->episodic promotion path.
        """
        total = 0
        for table in REL_TABLES.values():
            result_out = self._db.query(
                f"SELECT count() AS cnt FROM {table} WHERE in = type::thing('memory', $id) GROUP ALL",
                {"id": memory_id},
            )
            for r in _rows(result_out):
                total += r.get("cnt", 0)
            result_in = self._db.query(
                f"SELECT count() AS cnt FROM {table} WHERE out = type::thing('memory', $id) GROUP ALL",
                {"id": memory_id},
            )
            for r in _rows(result_in):
                total += r.get("cnt", 0)
        return total

    def close(self) -> None:
        try:
            self._db.close()
        except Exception:
            pass
