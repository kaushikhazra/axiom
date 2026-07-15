from __future__ import annotations
from dataclasses import dataclass


@dataclass
class MemoryConfig:
    storage_path: str = "~/.axiom/memory/memory.surrealkv"
    n_units: int = 50
    token_budget: int = 4000
    n_recency_floor: int = 5
    k_cognitive: int = 10
    k_relevance: int = 5
    growth_factor: float = 2.0
    decay_influence: float = 0.5
    auto_link_threshold: float = 0.75
    consolidation_debounce_sessions: int = 0
