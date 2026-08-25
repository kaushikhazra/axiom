"""What axiom can do, as the model sees it and as we run it.

One declaration per tool, sent unchanged to every model. Nothing here varies by
model: the probe in this loop's cycle-1 log found qwen2, gemma4 and qwen35 all
return the same structured call for the same declaration, so a per-model branch
would be inventing a difference that is not there.
"""

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass(frozen=True)
class Tool:
    """One thing axiom can do.

    `parameters` is JSON Schema, because that is what the model is given.
    `run` takes the arguments as keywords and returns what the model sees.
    """

    name: str
    description: str
    parameters: dict
    run: Callable[..., str]
    needs_limits: bool = False


@dataclass(frozen=True)
class Limits:
    """Operational settings a tool may need.

    Never model-visible: these belong to the user, and run() refuses any
    argument a tool did not declare in its schema, so a model cannot set them
    by asking.
    """

    working_directory: str | None = None  # None means where axiom was started
    command_timeout: float = 30.0


DEFAULT_LIMITS = Limits()


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} characters to {target}"


def edit_file(path: str, old: str, new: str) -> str:
    """Replace one stretch of a file and leave every other byte alone.

    Refuses when the text appears more than once: the model asked to change
    one thing, and silently changing three would be a different edit than the
    one it described to the user.
    """
    target = Path(path)
    original = target.read_text(encoding="utf-8")
    found = original.count(old)
    if found == 0:
        return f"error: that text does not appear in {target}"
    if found > 1:
        return f"error: that text appears {found} times in {target} - narrow it down"
    target.write_text(original.replace(old, new, 1), encoding="utf-8")
    return f"replaced one occurrence in {target}"


def delete_file(path: str) -> str:
    target = Path(path)
    target.unlink()
    return f"deleted {target}"


def _report(stdout: str, stderr: str, status: int) -> str:
    """What the model is told about a finished command.

    Both streams, and the exit status whenever it is not success - a command
    that failed must never read as one that worked.
    """
    parts = []
    if stdout:
        parts.append(stdout.rstrip("\n"))
    if stderr:
        parts.append("stderr:\n" + stderr.rstrip("\n"))
    if status != 0:
        parts.append(f"error: exited with status {status}")
    elif not parts:
        parts.append("(finished with no output)")
    return "\n".join(parts)


def _kill_tree(pid: int) -> None:
    """Kill a process and everything it started.

    Killing only the process is not enough: with shell=True the child is a
    shell, and the program the user actually asked about is its grandchild.
    Killing the shell alone leaves that program running - and holding the
    output pipe open, so waiting on it blocks for as long as it wants to live.
    """
    try:
        parent = psutil.Process(pid)
        doomed = [*parent.children(recursive=True), parent]
    except psutil.Error:
        return
    for process in doomed:
        try:
            process.kill()
        except psutil.Error:
            pass  # already gone, which is the outcome we wanted


def run_command(command: str, limits: "Limits" = DEFAULT_LIMITS) -> str:
    process = subprocess.Popen(  # noqa: S602
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=limits.working_directory,
    )
    try:
        stdout, stderr = process.communicate(timeout=limits.command_timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process.pid)
        process.communicate()  # returns now that nothing holds the pipes open
        return (
            f"error: still running after {limits.command_timeout:g} seconds "
            f"- stopped it"
        )
    except KeyboardInterrupt:
        # The user cancelled while this was running. Kill it before unwinding:
        # letting the turn end with the process still going would leave work
        # happening that nobody is waiting for and nobody can see.
        _kill_tree(process.pid)
        process.communicate()
        raise
    return _report(stdout, stderr, process.returncode)


REGISTRY: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="read_file",
            description="Read a text file and return its contents.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path of the file to read.",
                    }
                },
                "required": ["path"],
            },
            run=read_file,
        ),
        Tool(
            name="write_file",
            description="Create a file, or replace one entirely, with given content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to write to."},
                    "content": {"type": "string", "description": "What to write."},
                },
                "required": ["path", "content"],
            },
            run=write_file,
        ),
        Tool(
            name="edit_file",
            description=(
                "Replace one exact stretch of text in a file, leaving the rest "
                "unchanged. The text to replace must appear exactly once."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file."},
                    "old": {
                        "type": "string",
                        "description": "Exact text to replace. Must be unique in the file.",
                    },
                    "new": {
                        "type": "string",
                        "description": "What to put in its place.",
                    },
                },
                "required": ["path", "old", "new"],
            },
            run=edit_file,
        ),
        Tool(
            name="delete_file",
            description="Delete a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the file."}
                },
                "required": ["path"],
            },
            run=delete_file,
        ),
        Tool(
            name="run_command",
            description=(
                "Run a shell command and return its output. Any program on the "
                "machine can be run this way."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command line to run.",
                    }
                },
                "required": ["command"],
            },
            run=run_command,
            needs_limits=True,
        ),
    )
}


def declarations() -> list[dict]:
    """The tools as they are sent to a model."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in REGISTRY.values()
    ]


def run(name: str, arguments: dict, limits: Limits = DEFAULT_LIMITS) -> str:
    """Run a call and return what the model should be told.

    A failure is returned rather than raised: the model is the one that has to
    act on it, and a tool that cannot do its job is not a reason to end the
    turn. The session sees a result either way.
    """
    tool = REGISTRY.get(name)
    if tool is None:
        return f"error: there is no tool named {name!r}"

    # Only what the tool declared. A model inventing an argument gets told so,
    # and cannot reach a keyword the schema does not offer it - the time limit,
    # for instance, which belongs to the user rather than to the model.
    declared = set(tool.parameters.get("properties", {}))
    unexpected = sorted(set(arguments) - declared)
    if unexpected:
        return f"error: {name} does not take {', '.join(unexpected)}"

    try:
        if tool.needs_limits:
            return tool.run(**arguments, limits=limits)
        return tool.run(**arguments)
    except TypeError as wrong_arguments:
        return f"error: {name} was called wrongly - {wrong_arguments}"
    except OSError as failed:
        return f"error: {failed.strerror or failed}: {failed.filename or ''}".strip()
    except Exception as failed:  # noqa: BLE001
        return f"error: {failed}"
