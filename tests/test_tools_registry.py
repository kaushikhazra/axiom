"""
Unit tests for ToolRegistry (design.md §7).

Covers: dispatch to all four tools, unknown-tool guard, denial path,
missing-required-argument path (dryrun-design-1 finding 3), list_tools().
"""

from __future__ import annotations

from pathlib import Path

from axiom.tools.guardrails import GuardrailsGate
from axiom.tools.registry import ToolRegistry


def _make_registry(tmp_path: Path, auto_approve: bool = True) -> ToolRegistry:
    gate = GuardrailsGate(auto_approve=auto_approve)
    return ToolRegistry(working_dir=tmp_path, gate=gate)


class TestOnResultCallback:
    """M10 (design.md D13, D15): on_result fires once per execute() call,
    unconditionally (every tool, every outcome) -- filtering to
    write_file/run_shell and canvas-worthiness is the interface layer's
    job, not the registry's."""

    def test_fires_with_tool_name_and_result_on_success(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
        calls: list = []
        gate = GuardrailsGate(auto_approve=True)
        registry = ToolRegistry(
            working_dir=tmp_path,
            gate=gate,
            on_result=lambda name, result: calls.append((name, result)),
        )
        registry.execute("read_file", {"path": "a.txt"})
        assert len(calls) == 1
        name, result = calls[0]
        assert name == "read_file"
        assert result.output == "hi"

    def test_fires_on_denied_calls_too(self, tmp_path: Path) -> None:
        calls: list = []
        gate = GuardrailsGate(auto_approve=False, approval_fn=lambda *_: False)
        registry = ToolRegistry(
            working_dir=tmp_path,
            gate=gate,
            on_result=lambda name, result: calls.append((name, result)),
        )
        registry.execute("write_file", {"path": "a.txt", "content": "x"})
        assert len(calls) == 1
        name, result = calls[0]
        assert name == "write_file"
        assert result.denied is True

    def test_fires_on_error_calls_too(self, tmp_path: Path) -> None:
        calls: list = []
        gate = GuardrailsGate(auto_approve=True)
        registry = ToolRegistry(
            working_dir=tmp_path,
            gate=gate,
            on_result=lambda name, result: calls.append((name, result)),
        )
        registry.execute("read_file", {"path": "does_not_exist.txt"})
        assert len(calls) == 1
        name, result = calls[0]
        assert name == "read_file"
        assert result.error is not None

    def test_fires_on_unknown_tool(self, tmp_path: Path) -> None:
        calls: list = []
        gate = GuardrailsGate(auto_approve=True)
        registry = ToolRegistry(
            working_dir=tmp_path,
            gate=gate,
            on_result=lambda name, result: calls.append((name, result)),
        )
        registry.execute("no_such_tool", {})
        assert len(calls) == 1
        assert calls[0][0] == "no_such_tool"

    def test_no_callback_by_default_does_not_raise(self, tmp_path: Path) -> None:
        """Default on_result=None -- every existing caller (LocalAdapter
        pre-M10, and any direct ToolRegistry construction without the
        param) must keep working unchanged."""
        gate = GuardrailsGate(auto_approve=True)
        registry = ToolRegistry(working_dir=tmp_path, gate=gate)
        result = registry.execute("list_dir", {})
        assert result.error is None


class TestListTools:
    def test_returns_four_specs(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        specs = registry.list_tools()
        names = {s.name for s in specs}
        assert names == {"read_file", "write_file", "list_dir", "run_shell"}

    def test_destructive_flags_match_classification(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        by_name = {s.name: s for s in registry.list_tools()}
        assert by_name["read_file"].destructive is False
        assert by_name["list_dir"].destructive is False
        assert by_name["write_file"].destructive is True
        assert by_name["run_shell"].destructive is True


class TestExecuteDispatch:
    def test_read_file_dispatch(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
        registry = _make_registry(tmp_path)
        result = registry.execute("read_file", {"path": "a.txt"})
        assert result.output == "hi"
        assert result.error is None
        assert result.denied is False

    def test_write_file_dispatch(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("write_file", {"path": "a.txt", "content": "hi"})
        assert result.error is None
        assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hi"

    def test_list_dir_dispatch_default_path(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        registry = _make_registry(tmp_path)
        result = registry.execute("list_dir", {})
        assert "a.txt" in result.output

    def test_run_shell_dispatch(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("run_shell", {"command": "echo hi"})
        assert "hi" in result.output


class TestUnknownTool:
    def test_unknown_tool_returns_error_result(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("delete_universe", {})
        assert result.error == "unknown tool: delete_universe"
        assert result.output == ""
        assert result.denied is False


class TestDenialPath:
    def test_destructive_call_denied_returns_denied_result(
        self, tmp_path: Path
    ) -> None:
        gate = GuardrailsGate(approval_fn=lambda name, args: False)
        registry = ToolRegistry(working_dir=tmp_path, gate=gate)
        result = registry.execute("write_file", {"path": "a.txt", "content": "hi"})
        assert result.denied is True
        assert result.error == "denied by user"
        assert not (tmp_path / "a.txt").exists()

    def test_safe_call_never_denied(self, tmp_path: Path) -> None:
        gate = GuardrailsGate(approval_fn=lambda name, args: False)
        registry = ToolRegistry(working_dir=tmp_path, gate=gate)
        (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
        result = registry.execute("read_file", {"path": "a.txt"})
        assert result.denied is False
        assert result.output == "hi"

    def test_approval_fn_raising_returns_error_not_raise(self, tmp_path: Path) -> None:
        """dryrun-code-1 finding B2: an approval_fn (or the default CLI
        prompt reading closed stdin) raising previously escaped execute()
        uncaught, since the gate check ran outside the try/except block."""

        def _raises(name: str, args: dict) -> bool:
            raise ValueError("I/O operation on closed file (simulated)")

        registry = ToolRegistry(
            working_dir=tmp_path, gate=GuardrailsGate(approval_fn=_raises)
        )
        result = registry.execute("write_file", {"path": "a.txt", "content": "hi"})
        assert result.denied is False
        assert result.error is not None
        assert "approval check failed" in result.error
        assert not (tmp_path / "a.txt").exists()

    def test_approval_fn_raising_never_reaches_safe_tools(self, tmp_path: Path) -> None:
        """SAFE tools never call the approval seam (AC-03.5), so a raising
        approval_fn must not affect them."""

        def _raises(name: str, args: dict) -> bool:
            raise ValueError("should never be called for a SAFE tool")

        (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
        registry = ToolRegistry(
            working_dir=tmp_path, gate=GuardrailsGate(approval_fn=_raises)
        )
        result = registry.execute("read_file", {"path": "a.txt"})
        assert result.error is None
        assert result.output == "hi"


class TestMissingArgument:
    def test_missing_path_returns_error_not_raise(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("read_file", {})
        assert result.denied is False
        assert result.error is not None
        assert "invalid arguments" in result.error

    def test_missing_content_for_write_file(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("write_file", {"path": "a.txt"})
        assert "invalid arguments" in result.error

    def test_missing_command_for_run_shell(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("run_shell", {})
        assert "invalid arguments" in result.error


class TestWrongArgumentType:
    def test_write_file_non_string_content_returns_error_not_raise(
        self, tmp_path: Path
    ) -> None:
        """dryrun-code-1 finding B1: content=123 (int) previously raised an
        uncaught TypeError from Path.write_text, violating the "never raises"
        port contract."""
        registry = _make_registry(tmp_path)
        result = registry.execute("write_file", {"path": "a.txt", "content": 12345})
        assert result.denied is False
        assert result.error is not None
        assert "invalid arguments" in result.error
        assert not (tmp_path / "a.txt").exists()

    def test_list_dir_non_string_path_returns_error_not_raise(
        self, tmp_path: Path
    ) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("list_dir", {"path": 123})
        assert result.denied is False
        assert result.error is not None
        assert "invalid arguments" in result.error


class TestPathTraversalSurfacesAsError:
    def test_read_file_traversal_returns_error_result(self, tmp_path: Path) -> None:
        registry = _make_registry(tmp_path)
        result = registry.execute("read_file", {"path": "../../etc/passwd"})
        assert result.denied is False
        assert result.error is not None
        assert "resolves outside" in result.error
