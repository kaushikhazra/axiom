"""What axiom can do, as the model sees it and as we run it.

One declaration per tool, sent unchanged to every model. Nothing here varies by
model: the probe in this loop's cycle-1 log found qwen2, gemma4 and qwen35 all
return the same structured call for the same declaration, so a per-model branch
would be inventing a difference that is not there.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


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


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


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


def run(name: str, arguments: dict) -> str:
    """Run a call and return what the model should be told.

    A failure is returned rather than raised: the model is the one that has to
    act on it, and a tool that cannot do its job is not a reason to end the
    turn. The session sees a result either way.
    """
    tool = REGISTRY.get(name)
    if tool is None:
        return f"error: there is no tool named {name!r}"
    try:
        return tool.run(**arguments)
    except TypeError as wrong_arguments:
        return f"error: {name} was called wrongly - {wrong_arguments}"
    except OSError as failed:
        return f"error: {failed.strerror or failed}: {failed.filename or ''}".strip()
    except Exception as failed:  # noqa: BLE001
        return f"error: {failed}"
