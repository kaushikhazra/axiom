"""
Unit tests for the smolagents Tool wrappers (design.md §8).

Exercises forward() directly against a real ToolRegistry -- not covered by
the mocked act() tests in test_local_adapter.py, which patch CodeAgent
entirely and so never construct or call these wrapper classes.

smolagents is a required dependency (pyproject.toml) and Tool subclassing
performs no I/O -- unlike test_local_adapter.py (which mocks CodeAgent /
LiteLLMModel to avoid live model calls), these tests use the real
smolagents.Tool base class directly. No mocking needed or wanted here.
"""

from __future__ import annotations

from pathlib import Path

from axiom.tools.guardrails import GuardrailsGate
from axiom.tools.registry import ToolRegistry
from axiom.tools.smolagents_tools import (
    ListDirTool,
    ReadFileTool,
    RunShellTool,
    WriteFileTool,
)


def _make_registry(tmp_path: Path, auto_approve: bool = True) -> ToolRegistry:
    return ToolRegistry(
        working_dir=tmp_path, gate=GuardrailsGate(auto_approve=auto_approve)
    )


class TestReadFileTool:
    def test_forward_reads_file(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
        tool = ReadFileTool(_make_registry(tmp_path))
        assert tool.forward("a.txt") == "hi"

    def test_forward_error_returns_error_string_not_raise(self, tmp_path: Path) -> None:
        tool = ReadFileTool(_make_registry(tmp_path))
        result = tool.forward("missing.txt")
        assert result.startswith("ERROR:")


class TestWriteFileTool:
    def test_forward_writes_file(self, tmp_path: Path) -> None:
        tool = WriteFileTool(_make_registry(tmp_path))
        result = tool.forward("a.txt", "hi")
        assert "wrote" in result
        assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hi"

    def test_forward_denied_returns_denied_string_not_raise(
        self, tmp_path: Path
    ) -> None:
        registry = ToolRegistry(
            working_dir=tmp_path, gate=GuardrailsGate(approval_fn=lambda n, a: False)
        )
        tool = WriteFileTool(registry)
        result = tool.forward("a.txt", "hi")
        assert result.startswith("DENIED:")
        assert not (tmp_path / "a.txt").exists()


class TestListDirTool:
    def test_forward_default_path(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        tool = ListDirTool(_make_registry(tmp_path))
        assert "a.txt" in tool.forward()


class TestRunShellTool:
    def test_forward_runs_command(self, tmp_path: Path) -> None:
        tool = RunShellTool(_make_registry(tmp_path))
        result = tool.forward("echo hi")
        assert "hi" in result

    def test_forward_denied_returns_denied_string_not_raise(
        self, tmp_path: Path
    ) -> None:
        registry = ToolRegistry(
            working_dir=tmp_path, gate=GuardrailsGate(approval_fn=lambda n, a: False)
        )
        tool = RunShellTool(registry)
        result = tool.forward("echo hi")
        assert result.startswith("DENIED:")
