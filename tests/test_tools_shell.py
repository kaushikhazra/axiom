"""
Unit tests for axiom.tools.shell.run_shell (design.md §6).

Covers: success (AC-05.3), timeout (AC-05.2), output truncation, cwd pinning.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import axiom.tools.shell as shell_module
from axiom.tools.filesystem import ToolError
from axiom.tools.shell import MAX_OUTPUT_CHARS, run_shell

_IS_WINDOWS = __import__("os").name == "nt"
_PY = sys.executable  # avoid PATH ambiguity between 'python'/'python3'


def test_runs_command_and_captures_stdout(tmp_path: Path) -> None:
    result = run_shell(tmp_path, "echo hello")
    assert "exit=0" in result
    assert "hello" in result


def test_nonzero_exit_code_reported(tmp_path: Path) -> None:
    result = run_shell(tmp_path, "exit 3")
    assert "exit=3" in result


def test_cwd_is_pinned_to_working_dir(tmp_path: Path) -> None:
    (tmp_path / "marker.txt").write_text("x", encoding="utf-8")
    cmd = "dir /b" if _IS_WINDOWS else "ls"
    result = run_shell(tmp_path, cmd)
    assert "marker.txt" in result


def test_timeout_raises_tool_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(shell_module, "RUN_SHELL_TIMEOUT_SECS", 0.2)
    # A pure-Python sleep avoids platform-specific quirks (e.g. Windows'
    # `timeout` command refusing to run without an interactive console).
    cmd = f'"{_PY}" -c "import time; time.sleep(60)"'
    with pytest.raises(ToolError, match="timed out"):
        run_shell(tmp_path, cmd)


def test_output_is_truncated(tmp_path: Path) -> None:
    n = MAX_OUTPUT_CHARS + 1000
    cmd = f'"{_PY}" -c "print(\'x\' * {n})"'
    result = run_shell(tmp_path, cmd)
    assert "truncated" in result
    assert len(result) < n
