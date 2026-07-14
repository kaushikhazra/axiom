"""Verify CognitiveMemoryAdapter satisfies MemoryPort structurally."""

from __future__ import annotations

import asyncio
import os
import tempfile

from axiom.memory.adapter import CognitiveMemoryAdapter
from axiom.memory.config import MemoryConfig
from axiom.memory.port import MemoryPort


def _adapter() -> tuple[CognitiveMemoryAdapter, str]:
    td = tempfile.mkdtemp()
    config = MemoryConfig(storage_path=os.path.join(td, "test.surrealkv"))
    return CognitiveMemoryAdapter(config), td


class TestMemoryPortContract:
    def setup_method(self):
        self.adapter, self._td = _adapter()

    def test_isinstance_memory_port(self):
        assert isinstance(self.adapter, MemoryPort)

    def test_has_assemble_context(self):
        assert hasattr(self.adapter, "assemble_context")
        assert callable(self.adapter.assemble_context)

    def test_has_recall(self):
        assert hasattr(self.adapter, "recall")
        assert callable(self.adapter.recall)

    def test_has_append_unit(self):
        assert hasattr(self.adapter, "append_unit")
        assert callable(self.adapter.append_unit)

    def test_has_store(self):
        assert hasattr(self.adapter, "store")
        assert callable(self.adapter.store)

    def test_has_reinforce(self):
        assert hasattr(self.adapter, "reinforce")
        assert callable(self.adapter.reinforce)

    def test_has_update(self):
        assert hasattr(self.adapter, "update")
        assert callable(self.adapter.update)

    def test_has_relate(self):
        assert hasattr(self.adapter, "relate")
        assert callable(self.adapter.relate)

    def test_has_consolidate(self):
        assert hasattr(self.adapter, "consolidate")
        assert callable(self.adapter.consolidate)

    def test_has_stats(self):
        assert hasattr(self.adapter, "stats")
        assert callable(self.adapter.stats)

    def test_has_health(self):
        assert hasattr(self.adapter, "health")
        assert callable(self.adapter.health)

    def test_store_returns_string_id(self):
        mid = asyncio.run(self.adapter.store("test content"))
        assert isinstance(mid, str)
        assert len(mid) == 36  # UUID4 format

    def test_health_returns_dict(self):
        result = asyncio.run(self.adapter.health())
        assert isinstance(result, dict)
        assert "status" in result

    def test_stats_returns_dict(self):
        result = asyncio.run(self.adapter.stats())
        assert isinstance(result, dict)
        assert "total" in result

    def test_assemble_context_returns_assembled_context(self):
        from axiom.memory.models import AssembledContext

        result = asyncio.run(self.adapter.assemble_context("test query"))
        assert isinstance(result, AssembledContext)
        assert isinstance(result.working_context, list)
        assert isinstance(result.cognitive_memories, list)
