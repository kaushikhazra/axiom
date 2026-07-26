"""
ToolRegistry -- the concrete ToolsPort. Owns the working_dir root and the
GuardrailsGate; dispatches by name to filesystem.py / shell.py functions.
"""

from __future__ import annotations

from pathlib import Path

from axiom.tools.filesystem import ToolError, list_dir, read_file, write_file
from axiom.tools.guardrails import Classification, GuardrailsGate
from axiom.tools.port import ToolResult, ToolSpec
from axiom.tools.shell import run_shell

_SPECS: dict[str, str] = {
    "read_file": "Read a UTF-8 text file. Path is resolved relative to the working directory.",
    "write_file": "Write UTF-8 text to a file. DESTRUCTIVE: requires approval. Path is resolved relative to the working directory.",
    "list_dir": "List entries in a directory. Path is resolved relative to the working directory.",
    "run_shell": "Run a shell command in the working directory (the code escape-hatch). DESTRUCTIVE: requires approval.",
}


class ToolRegistry:
    """Implements ToolsPort (structurally -- Protocol, no explicit inheritance)."""

    def __init__(self, working_dir: Path, gate: GuardrailsGate) -> None:
        self._working_dir = working_dir
        self._gate = gate

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=name,
                description=desc,
                destructive=self._gate.classify(name) is Classification.DESTRUCTIVE,
            )
            for name, desc in _SPECS.items()
        ]

    def execute(self, name: str, arguments: dict) -> ToolResult:
        if name not in _SPECS:
            return ToolResult(output="", error=f"unknown tool: {name}")

        try:
            approved = self._gate.check(name, arguments)
        except Exception as exc:
            # The approval step itself failed (e.g. a custom approval_fn
            # raised, or stdin was closed for the default CLI prompt) --
            # covered by the same "never raises" contract as _dispatch below
            # (dryrun-code-1 finding B2). Fails closed: treated as an error,
            # not silently approved.
            return ToolResult(output="", error=f"approval check failed: {exc}")

        if not approved:
            return ToolResult(output="", denied=True, error="denied by user")

        try:
            output = self._dispatch(name, arguments)
            return ToolResult(output=output)
        except ToolError as exc:
            return ToolResult(output="", error=str(exc))
        except (KeyError, TypeError) as exc:
            # A required argument was missing (KeyError) or had the wrong
            # type (TypeError, e.g. content=123 instead of a string, which
            # Path.write_text raises as a bare TypeError) -- e.g. a direct
            # execute() call bypassing smolagents' own argument validation.
            # Converted to a ToolResult, not left to propagate, so the
            # "never raises" port contract (ToolsPort.execute docstring,
            # AC-01.1) holds for every caller, not just ones that happen to
            # go through a smolagents Tool (dryrun-code-1 finding B1).
            return ToolResult(output="", error=f"invalid arguments: {exc}")

    def _dispatch(self, name: str, arguments: dict) -> str:
        if name == "read_file":
            return read_file(self._working_dir, arguments["path"])
        if name == "write_file":
            return write_file(
                self._working_dir, arguments["path"], arguments["content"]
            )
        if name == "list_dir":
            return list_dir(self._working_dir, arguments.get("path", "."))
        if name == "run_shell":
            return run_shell(self._working_dir, arguments["command"])
        raise AssertionError(f"unreachable: {name!r} passed the _SPECS guard")
