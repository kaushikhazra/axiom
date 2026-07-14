"""E2E tests — prove the two M3 milestone deliverables:
(1) Memory persists across sessions (session A stores → session B recalls).
(2) assemble_context returns both working-tier and cognitive-tier populated.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timezone

from axiom.memory.adapter import CognitiveMemoryAdapter
from axiom.memory.config import MemoryConfig
from axiom.memory.models import ConversationUnit


def _adapter(path: str) -> CognitiveMemoryAdapter:
    return CognitiveMemoryAdapter(MemoryConfig(storage_path=path))


async def _store_and_drain(
    adapter: CognitiveMemoryAdapter, content: str, **kwargs
) -> str:
    """Store in cognitive tier and wait for async insert to land."""
    mid = await adapter.store(content, **kwargs)
    await asyncio.sleep(1.2)
    return mid


class TestCrossSessionRecall:
    """MEM-DOD-9a: content stored in session A is surfaced in session B."""

    def test_cross_session_recall_cognitive(self):
        """
        (a) Init adapter A; store a cognitive memory.
        (b) Tear down A.
        (c) Init adapter B against same file.
        (d) call assemble_context with a related query.
        (e) Assert the stored content appears in cognitive_memories.
        """
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "memory.surrealkv")

            # Session A
            adapter_a = _adapter(db_path)
            content = "Kaushik prefers pair-programming reviews on complex changes"
            mid = asyncio.run(
                _store_and_drain(adapter_a, content, memory_type="semantic")
            )
            del adapter_a

            # Session B
            adapter_b = _adapter(db_path)
            ctx = asyncio.run(adapter_b.assemble_context("code review preferences"))
            stored_ids = [r.id for r in ctx.cognitive_memories]
            assert mid in stored_ids, (
                f"Memory {mid!r} not found in session B cognitive_memories. "
                f"Got: {stored_ids}"
            )

    def test_cross_session_recall_via_recall_method(self):
        """Direct recall() also finds cross-session memory."""
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "memory.surrealkv")

            adapter_a = _adapter(db_path)
            mid = asyncio.run(
                _store_and_drain(adapter_a, "The project uses Python 3.12")
            )
            del adapter_a

            adapter_b = _adapter(db_path)
            results = asyncio.run(adapter_b.recall("Python version"))
            ids = [r.id for r in results]
            assert mid in ids, f"Expected {mid} in recall results; got {ids}"


class TestTwoTierAssembly:
    """MEM-DOD-9b: assemble_context returns both tiers populated when content exists."""

    def test_both_tiers_populated(self):
        """
        Store cognitive memories AND append working-context units.
        assemble_context must return both non-empty.
        """
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "memory.surrealkv")
            adapter = _adapter(db_path)

            async def _setup_and_assemble():
                # Populate working context via append_unit
                unit = ConversationUnit(
                    user_text="What is the capital of France?",
                    agent_text="The capital of France is Paris.",
                    turn_index=0,
                    timestamp=datetime.now(timezone.utc),
                )
                await adapter.append_unit(unit)

                # Populate cognitive tier
                await _store_and_drain(adapter, "France is a country in Western Europe")

                # assemble_context
                ctx = await adapter.assemble_context("France capital")
                return ctx

            ctx = asyncio.run(_setup_and_assemble())

            # Working tier must be non-empty (we appended a unit)
            assert len(ctx.working_context) >= 1, (
                "working_context is empty; expected the appended ConversationUnit"
            )
            # Cognitive tier must be non-empty (we stored a cognitive memory)
            assert len(ctx.cognitive_memories) >= 1, (
                "cognitive_memories is empty; expected the stored semantic memory"
            )

    def test_working_context_unit_has_correct_fields(self):
        """append_unit sets embedding and token_count correctly."""
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "memory.surrealkv")
            adapter = _adapter(db_path)

            async def _run():
                unit = ConversationUnit(
                    user_text="Hello there",
                    agent_text="Hi! How can I help?",
                    turn_index=0,
                    timestamp=datetime.now(timezone.utc),
                )
                assert unit.embedding == []
                assert unit.token_count == 0

                await adapter.append_unit(unit)

                # After append_unit, embedding and token_count must be set
                assert len(unit.embedding) == 384, (
                    "Embedding must be 384-dim after append_unit"
                )
                expected_tokens = len(unit.user_text + unit.agent_text) // 4
                assert unit.token_count == expected_tokens
                return unit

            unit = asyncio.run(_run())
            assert unit.token_count > 0

    def test_assemble_context_empty_tiers_are_empty_lists(self):
        """Empty database → both tiers are [] not None/error."""
        with tempfile.TemporaryDirectory() as td:
            db_path = os.path.join(td, "memory.surrealkv")
            adapter = _adapter(db_path)
            ctx = asyncio.run(adapter.assemble_context("any query on empty db"))
            assert ctx.working_context == []
            assert ctx.cognitive_memories == []
