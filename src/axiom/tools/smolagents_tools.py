"""
smolagents Tool wrappers over ToolRegistry -- KIND-A wiring for M4.

Four small classes (design.md D8), each delegating forward() to
ToolRegistry.execute(). Denial and error results return as plain strings
(design.md D9) so the CodeAgent step observes them as normal tool output,
never as a crash.

Import boundary: smolagents only. No claude_agent_sdk. Imported lazily by
local_adapter.py, matching the existing smolagents-is-deferred rule. Not
imported by axiom/tools/__init__.py or any other module in this package, so
importing axiom.tools never pays the smolagents import cost.
"""

from __future__ import annotations

from smolagents import Tool

from axiom.tools.registry import ToolRegistry


def _dispatch(registry: ToolRegistry, name: str, arguments: dict) -> str:
    result = registry.execute(name, arguments)
    if result.denied:
        return f"DENIED: {result.error}"
    if result.error:
        return f"ERROR: {result.error}"
    return result.output


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read a UTF-8 text file's contents. Path is resolved relative to "
        "the working directory; paths outside it are rejected."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "File path, relative to the working directory.",
        }
    }
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, path: str) -> str:
        return _dispatch(self._registry, "read_file", {"path": path})


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write UTF-8 text content to a file. DESTRUCTIVE: requires approval. "
        "Path is resolved relative to the working directory; paths outside "
        "it are rejected."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "File path, relative to the working directory.",
        },
        "content": {"type": "string", "description": "Text content to write."},
    }
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, path: str, content: str) -> str:
        return _dispatch(
            self._registry, "write_file", {"path": path, "content": content}
        )


class ListDirTool(Tool):
    name = "list_dir"
    description = (
        "List entries in a directory. Path is resolved relative to the "
        "working directory; paths outside it are rejected."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "Directory path, relative to the working directory.",
            "nullable": True,
        }
    }
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, path: str = ".") -> str:
        return _dispatch(self._registry, "list_dir", {"path": path})


class RunShellTool(Tool):
    name = "run_shell"
    description = (
        "Run a shell command in the working directory (the code "
        "escape-hatch). DESTRUCTIVE: requires approval."
    )
    inputs = {"command": {"type": "string", "description": "Shell command to execute."}}
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, command: str) -> str:
        return _dispatch(self._registry, "run_shell", {"command": command})
