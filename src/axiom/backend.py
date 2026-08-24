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


class ModelRefused(BackendError):
    """Reached the service, and it rejected the request."""


class ConnectionLost(BackendError):
    """Could not reach the backend, or the connection dropped mid-request."""


@dataclass(frozen=True)
class Piece:
    """One streamed fragment, with the usage the backend reported alongside it."""

    text: str
    usage: int = 0


class ModelBackend(Protocol):
    """What axiom needs a model to do.

    Two implementations earn this: OllamaBackend below, and the stubs the tests
    hand to the session directly. Without the second one it would be an
    abstraction over a single thing, which is what AC 13 forbids.
    """

    def model_info(self, model: str) -> dict | None: ...

    def stream(
        self, model: str, messages: list[dict[str, str]], options: dict | None
    ) -> Iterator[Piece]: ...

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

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        options: dict | None = None,
    ) -> Iterator[Piece]:
        try:
            for chunk in self._client.chat(
                model=model, messages=messages, stream=True, options=options
            ):
                yield Piece(
                    chunk.message.content or "",
                    (chunk.prompt_eval_count or 0) + (chunk.eval_count or 0),
                )
        except ollama.ResponseError as refused:
            raise ModelRefused(str(refused)) from refused
        except (ConnectionError, httpx.HTTPError) as lost:
            # ollama turns a refused *connect* into ConnectionError, but a
            # connection dropped mid-request surfaces as a raw httpx error.
            raise ConnectionLost(str(lost)) from lost

    def complete(self, model: str, messages: list[dict[str, str]]) -> str:
        """One plain, non-streamed reply. Used for summarizing."""
        reply = self._client.chat(model=model, messages=messages)
        return reply.message.content or ""
