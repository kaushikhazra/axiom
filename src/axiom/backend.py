"""The seam between axiom and whatever model it talks to.

The only module under src/ that imports a vendor client. Everything above it
sees the protocol, a Piece, and this module's own errors. That is what lets the
chat loop be exercised without patching a module global, and what turns three
near-identical failure branches into one - by the time a failure crosses this
boundary it belongs to a single family.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

import httpx
import ollama


class BackendError(Exception):
    """A request to the model failed. The turn is dropped; the session lives."""


class ConnectionLost(BackendError):
    """Could not reach the backend, or the connection dropped mid-request."""


@dataclass(frozen=True)
class Piece:
    """One streamed fragment, with the usage the backend reported alongside it."""

    text: str
    usage: int = 0


@dataclass(frozen=True)
class Call:
    """A tool the model wants run, and the arguments it wants passed.

    Deliberately built from primitives rather than wrapping the vendor's own
    object: the assistant turn has to go back into history to continue a tool
    conversation, and rebuilding it from these fields is accepted.
    """

    name: str
    arguments: dict

    def as_message_part(self) -> dict:
        """This call as it goes back into history, for the model to match against."""
        return {"function": {"name": self.name, "arguments": self.arguments}}


class ModelBackend(Protocol):
    """What axiom needs a model to do. Implemented here, and by the test stubs."""

    def model_info(self, model: str) -> dict | None: ...

    def supports_tools(self, model: str) -> bool: ...

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: dict | None,
        tools: list[dict] | None,
    ) -> Iterator[Piece | Call]: ...

    def complete(self, model: str, messages: list[dict[str, str]]) -> str: ...


class OllamaBackend:
    """Talks to a local Ollama server."""

    def __init__(self, host: str) -> None:
        self._client = ollama.Client(host=host)

    def model_info(self, model: str) -> dict | None:
        """The model's raw model_info, or None if it cannot be reached or asked."""
        try:
            return self._client.show(model).modelinfo or {}
        except (ollama.ResponseError, ConnectionError, httpx.HTTPError):
            return None

    def supports_tools(self, model: str) -> bool:
        """Whether this model can be sent tools at all.

        Asked before the first turn. Ollama otherwise reports it only as a 400
        at generation time, which would spend a request to find out, and would
        tell the user after they had already asked for something.
        """
        try:
            return "tools" in (self._client.show(model).capabilities or [])
        except (ollama.ResponseError, ConnectionError, httpx.HTTPError):
            return False

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: dict | None = None,
        tools: list[dict] | None = None,
    ) -> Iterator[Piece | Call]:
        try:
            for chunk in self._client.chat(
                model=model,
                messages=messages,
                stream=True,
                options=options,
                tools=tools,
            ):
                for call in chunk.message.tool_calls or []:
                    yield Call(call.function.name, dict(call.function.arguments))
                # A Piece for every chunk, empty text included: the final chunk
                # carries the usage counts and often no text at all.
                yield Piece(
                    chunk.message.content or "",
                    (chunk.prompt_eval_count or 0) + (chunk.eval_count or 0),
                )
        except ollama.ResponseError as refused:
            raise BackendError(str(refused)) from refused
        except (ConnectionError, httpx.HTTPError) as lost:
            # ollama turns a refused *connect* into ConnectionError, but a
            # connection dropped mid-request surfaces as a raw httpx error.
            raise ConnectionLost(str(lost)) from lost

    def complete(self, model: str, messages: list[dict[str, str]]) -> str:
        """One plain, non-streamed reply. Used for summarizing."""
        reply = self._client.chat(model=model, messages=messages)
        return reply.message.content or ""
