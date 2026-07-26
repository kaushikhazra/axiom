"""
Working-directory-scoped file tools. Every path is resolved against a
configured working_dir root; anything that resolves outside it is rejected.
Functions raise ToolError -- ToolRegistry.execute() converts that into a
ToolResult(error=...) string, never letting it propagate as a raw exception
into a caller (design.md D9).
"""

from __future__ import annotations

from pathlib import Path

MAX_READ_CHARS: int = (
    8000  # bounds prompt size the same way shell.py bounds run_shell output
)


class ToolError(Exception):
    """Raised by any tool function on a scoping violation or execution
    failure. Caught exclusively by ToolRegistry.execute()."""


def _resolve_scoped(working_dir: Path, path: str) -> Path:
    """Resolve `path` relative to working_dir; reject any escape.

    Path.resolve() collapses '..' segments and symlinks before the
    containment check, so 'a/../../etc/passwd' and an absolute path outside
    working_dir are both caught the same way.
    """
    root = working_dir.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ToolError(
            f"path {path!r} resolves outside the working directory ({root})"
        ) from exc
    return candidate


def read_file(working_dir: Path, path: str) -> str:
    target = _resolve_scoped(working_dir, path)
    if not target.is_file():
        raise ToolError(f"not a file: {path}")
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ToolError(f"failed to read {path!r}: {exc}") from exc
    if len(text) > MAX_READ_CHARS:
        return (
            text[:MAX_READ_CHARS]
            + f"\n... [truncated {len(text) - MAX_READ_CHARS} chars]"
        )
    return text


def write_file(working_dir: Path, path: str, content: str) -> str:
    target = _resolve_scoped(working_dir, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"failed to write {path!r}: {exc}") from exc
    return f"wrote {len(content)} bytes to {path}"


def list_dir(working_dir: Path, path: str = ".") -> str:
    target = _resolve_scoped(working_dir, path)
    if not target.is_dir():
        raise ToolError(f"not a directory: {path}")
    try:
        entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
    except OSError as exc:
        raise ToolError(f"failed to list {path!r}: {exc}") from exc
    return "\n".join(entries) if entries else "(empty)"
