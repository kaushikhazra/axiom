from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Memory:
    id: str
    content: str
    memory_type: str  # working/episodic/semantic/procedural/identity/person
    state: str  # active/archived/superseded
    importance: float
    stability: float  # days; S0 per type
    retrievability: (
        float  # consolidation-time snapshot only; NOT authoritative at recall
    )
    access_count: int
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime
    source: str | None = None
    conversation_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class RecallResult:
    id: str
    content: str
    memory_type: str
    importance: float
    retrievability: float  # R(t) computed on-the-fly at recall time
    score: float  # final_score after decay rerank
    found_by: list[str]  # which strategies contributed
    tags: list[str]
    created_at: datetime
    last_accessed: datetime
    contradictions: list[str] = field(
        default_factory=list
    )  # IDs of contradicting memories


@dataclass
class Relationship:
    id: str
    source_id: str
    target_id: str
    rel_type: str  # causes/follows/contradicts/supports/relates_to/supersedes/part_of/describes
    strength: float  # 0.0-1.0; auto-links < 1.0; manual = 1.0
    created_at: datetime


@dataclass
class ConversationUnit:
    user_text: str
    agent_text: str
    turn_index: int
    timestamp: datetime
    embedding: list[float] = field(
        default_factory=list
    )  # empty at construction; set by append_unit
    token_count: int = 0  # set by append_unit as len(user_text + agent_text) // 4


@dataclass
class AssembledContext:
    working_context: list[ConversationUnit]  # Last N units + older relevant units
    cognitive_memories: list[RecallResult]  # Top-K from cognitive store
