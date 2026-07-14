"""WorkingContext — in-memory VectorRingBuffer for the working-context tier."""

from __future__ import annotations
from collections import deque

from axiom.memory.config import MemoryConfig
from axiom.memory.models import ConversationUnit


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two L2-normalised vectors (dot product)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _apply_token_cap(
    units: list[ConversationUnit], budget: int
) -> list[ConversationUnit]:
    """Truncate from the front (oldest first) until within budget.

    S2 fix: use an index cursor instead of list.pop(0) to avoid O(n²) shifting.
    """
    total = sum(u.token_count for u in units)
    start = 0
    while start < len(units) and total > budget:
        total -= units[start].token_count
        start += 1
    return units[start:]


class WorkingContext:
    """In-memory ring buffer for conversation units."""

    def __init__(self, config: MemoryConfig) -> None:
        self._max_units = config.n_units
        self._token_budget = config.token_budget
        self._n_recency_floor = config.n_recency_floor
        self._k_relevance = config.k_relevance
        self._buffer: deque[ConversationUnit] = deque(maxlen=self._max_units)

    def add_unit(self, unit: ConversationUnit) -> None:
        """Add a unit to the buffer. Evicts oldest when full (deque maxlen handles this)."""
        self._buffer.append(unit)

    def assemble(
        self,
        query_embedding: list[float],
    ) -> list[ConversationUnit]:
        """Return assembled working context: recency floor + relevant older units, token-capped."""
        buf = list(self._buffer)
        if not buf:
            return []

        n_floor = min(self._n_recency_floor, len(buf))
        recency_slice = buf[-n_floor:]
        older_units = buf[:-n_floor] if n_floor < len(buf) else []

        if older_units and query_embedding:
            scored = [
                (unit, _cosine(unit.embedding, query_embedding)) for unit in older_units
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            relevance_slice = [u for u, _ in scored[: self._k_relevance]]
        else:
            relevance_slice = []

        assembled = relevance_slice + recency_slice
        return _apply_token_cap(assembled, self._token_budget)

    def __len__(self) -> int:
        return len(self._buffer)
