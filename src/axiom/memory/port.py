"""MemoryPort Protocol — the ONLY memory import that loop.py touches."""

from __future__ import annotations
from typing import Protocol, runtime_checkable
from axiom.memory.models import RecallResult, AssembledContext, ConversationUnit


@runtime_checkable
class MemoryPort(Protocol):
    async def assemble_context(
        self,
        query: str,
        conversation_id: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> AssembledContext: ...

    async def recall(
        self,
        query: str,
        context: dict | None = None,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[RecallResult]: ...

    async def consolidate(self) -> list[dict]: ...
    async def stats(self) -> dict: ...
    async def health(self) -> dict: ...

    async def append_unit(self, unit: ConversationUnit) -> None: ...

    # Working-context write path: AWAITED; embeds unit and appends to ring buffer.
    # Does NOT write to cognitive store.

    async def store(
        self,
        content: str,
        memory_type: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> str: ...

    # Cognitive store ONLY. Fire-and-forget. Returns UUID4 id synchronously.

    async def reinforce(self, ids: list[str]) -> None: ...
    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
    ) -> None: ...
    async def relate(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float = 1.0,
    ) -> None: ...
