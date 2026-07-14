"""SurrealKV schema for Axiom memory — applied idempotently at StorageSeam init."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

_EDGE_TABLES = (
    "causes",
    "follows",
    "contradicts",
    "supports",
    "relates_to",
    "supersedes",
    "part_of",
    "describes",
)


def _edge_stmts(t: str) -> list[str]:
    return [
        f"DEFINE TABLE OVERWRITE {t} SCHEMAFULL TYPE RELATION FROM memory TO memory",
        f"DEFINE FIELD OVERWRITE strength ON {t} TYPE float DEFAULT 1.0",
        f"DEFINE FIELD OVERWRITE created_at ON {t} TYPE datetime",
    ]


SCHEMA_STATEMENTS: list[str] = [
    "DEFINE TABLE OVERWRITE memory SCHEMAFULL",
    "DEFINE FIELD OVERWRITE content         ON memory TYPE string",
    "DEFINE FIELD OVERWRITE memory_type     ON memory TYPE string ASSERT $value IN ['working', 'episodic', 'semantic', 'procedural', 'identity', 'person']",
    "DEFINE FIELD OVERWRITE state           ON memory TYPE string DEFAULT 'active' ASSERT $value IN ['active', 'archived', 'superseded']",
    "DEFINE FIELD OVERWRITE importance      ON memory TYPE float",
    "DEFINE FIELD OVERWRITE stability       ON memory TYPE float",
    "DEFINE FIELD OVERWRITE retrievability  ON memory TYPE float",
    "DEFINE FIELD OVERWRITE access_count    ON memory TYPE int DEFAULT 0",
    "DEFINE FIELD OVERWRITE created_at      ON memory TYPE datetime",
    "DEFINE FIELD OVERWRITE updated_at      ON memory TYPE datetime",
    "DEFINE FIELD OVERWRITE last_accessed   ON memory TYPE datetime",
    "DEFINE FIELD OVERWRITE source          ON memory TYPE option<string>",
    "DEFINE FIELD OVERWRITE conversation_id ON memory TYPE option<string>",
    "DEFINE FIELD OVERWRITE tags            ON memory TYPE array<string> DEFAULT []",
    "DEFINE FIELD OVERWRITE embedding       ON memory TYPE option<array<float>>",
    "DEFINE INDEX OVERWRITE idx_memory_embedding ON memory FIELDS embedding HNSW DIMENSION 384 DIST COSINE",
    "DEFINE ANALYZER OVERWRITE memory_analyzer TOKENIZERS blank, class FILTERS lowercase, snowball(english)",
    "DEFINE INDEX OVERWRITE idx_memory_fts ON memory FIELDS content SEARCH ANALYZER memory_analyzer BM25",
    "DEFINE INDEX OVERWRITE idx_memory_state ON memory FIELDS state",
    "DEFINE INDEX OVERWRITE idx_memory_type ON memory FIELDS memory_type",
    *[s for t in _EDGE_TABLES for s in _edge_stmts(t)],
    "DEFINE TABLE OVERWRITE memory_version SCHEMAFULL",
    "DEFINE FIELD OVERWRITE memory_id  ON memory_version TYPE record<memory>",
    "DEFINE FIELD OVERWRITE content    ON memory_version TYPE string",
    "DEFINE FIELD OVERWRITE metadata   ON memory_version TYPE option<object>",
    "DEFINE FIELD OVERWRITE created_at ON memory_version TYPE datetime",
    "DEFINE INDEX OVERWRITE idx_version_memory ON memory_version FIELDS memory_id",
    "DEFINE TABLE OVERWRITE consolidation_log SCHEMAFULL",
    "DEFINE FIELD OVERWRITE action     ON consolidation_log TYPE string ASSERT $value IN ['promote', 'merge', 'archive', 'flag_contradiction']",
    "DEFINE FIELD OVERWRITE source_ids ON consolidation_log TYPE array<string>",
    "DEFINE FIELD OVERWRITE target_id  ON consolidation_log TYPE option<string>",
    "DEFINE FIELD OVERWRITE reason     ON consolidation_log TYPE string",
    "DEFINE FIELD OVERWRITE created_at ON consolidation_log TYPE datetime",
    "DEFINE TABLE OVERWRITE config SCHEMAFULL",
    "DEFINE FIELD OVERWRITE val        ON config TYPE any",
    "DEFINE FIELD OVERWRITE updated_at ON config TYPE datetime",
]


def init_schema(db) -> None:
    """Apply each schema statement. DEFINE OVERWRITE = idempotent."""
    for stmt in SCHEMA_STATEMENTS:
        try:
            db.query(stmt)
        except Exception as e:
            logger.warning("Schema stmt warning (non-fatal): %s — %s", stmt[:60], e)
