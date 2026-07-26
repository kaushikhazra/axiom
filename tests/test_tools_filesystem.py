"""
Unit tests for axiom.tools.filesystem (design.md §6).

Covers: read_file/write_file/list_dir happy paths (AC-04.1), path-traversal
rejection (AC-04.6), read_file truncation at MAX_READ_CHARS, and an OSError
path surfacing as ToolError rather than raising (dryrun-design-1 finding 4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from axiom.tools.filesystem import (
    MAX_READ_CHARS,
    ToolError,
    list_dir,
    read_file,
    write_file,
)


class TestReadFile:
    def test_reads_existing_file(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
        assert read_file(tmp_path, "a.txt") == "hello"

    def test_missing_file_raises_tool_error(self, tmp_path: Path) -> None:
        with pytest.raises(ToolError, match="not a file"):
            read_file(tmp_path, "missing.txt")

    def test_traversal_outside_working_dir_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        with pytest.raises(ToolError, match="resolves outside"):
            read_file(tmp_path, "../outside.txt")

    def test_absolute_path_outside_working_dir_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside2.txt"
        outside.write_text("secret", encoding="utf-8")
        with pytest.raises(ToolError, match="resolves outside"):
            read_file(tmp_path, str(outside))

    def test_truncates_large_file(self, tmp_path: Path) -> None:
        big = "x" * (MAX_READ_CHARS + 500)
        (tmp_path / "big.txt").write_text(big, encoding="utf-8")
        result = read_file(tmp_path, "big.txt")
        assert len(result) < len(big)
        assert "truncated" in result

    def test_os_error_surfaces_as_tool_error(self, tmp_path: Path, monkeypatch) -> None:
        target = tmp_path / "a.txt"
        target.write_text("hello", encoding="utf-8")

        def _raise_os_error(*args, **kwargs):
            raise OSError("permission denied (simulated)")

        monkeypatch.setattr(Path, "read_text", _raise_os_error)
        with pytest.raises(ToolError, match="failed to read"):
            read_file(tmp_path, "a.txt")


class TestWriteFile:
    def test_writes_new_file(self, tmp_path: Path) -> None:
        result = write_file(tmp_path, "out.txt", "content")
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "content"
        assert "wrote" in result

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        write_file(tmp_path, "nested/dir/out.txt", "content")
        assert (tmp_path / "nested" / "dir" / "out.txt").is_file()

    def test_traversal_outside_working_dir_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ToolError, match="resolves outside"):
            write_file(tmp_path, "../escape.txt", "content")

    def test_os_error_surfaces_as_tool_error(self, tmp_path: Path, monkeypatch) -> None:
        def _raise_os_error(*args, **kwargs):
            raise OSError("disk full (simulated)")

        monkeypatch.setattr(Path, "write_text", _raise_os_error)
        with pytest.raises(ToolError, match="failed to write"):
            write_file(tmp_path, "out.txt", "content")


class TestListDir:
    def test_lists_entries(self, tmp_path: Path) -> None:
        (tmp_path / "a.txt").write_text("x", encoding="utf-8")
        (tmp_path / "subdir").mkdir()
        result = list_dir(tmp_path)
        assert "a.txt" in result
        assert "subdir/" in result

    def test_empty_dir_returns_empty_marker(self, tmp_path: Path) -> None:
        assert list_dir(tmp_path) == "(empty)"

    def test_not_a_directory_raises_tool_error(self, tmp_path: Path) -> None:
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")
        with pytest.raises(ToolError, match="not a directory"):
            list_dir(tmp_path, "f.txt")

    def test_traversal_outside_working_dir_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ToolError, match="resolves outside"):
            list_dir(tmp_path, "..")
