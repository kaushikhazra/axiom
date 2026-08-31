"""The seam between axiom and whatever model it talks to.

The only module under src/ that imports a vendor client. Everything above it
sees the protocol, a Piece, and this module's own errors. That is what lets the
chat loop be exercised without patching a module global, and what turns three
near-identical failure branches into one - by the time a failure crosses this
boundary it belongs to a single family.
"""

import json
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
    # Kept apart from `usage`, which is prompt + eval and is what compaction
    # triggers on. Detecting a truncated prompt needs the prompt count alone:
    # the eval half would mask a shortfall in the half that matters.
    prompt_usage: int = 0


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


def call_from_text(
    text: str, known: set[str], skills: set[str] | None = None
) -> Call | None:
    """A call a model announced as text instead of as a structured call.

    Some models return the call as bare JSON in the reply, with no structured
    tool_calls at all - qwen2.5-coder does, and #34's cycle-7 log has the
    captured shape. Recognised by the shape of the reply, never by the name of
    the model: a per-model branch here would be the thing AC 4 and AC 5 forbid.

    Returns None when the reply is not a call, and the caller then prints it -
    so this must not claim anything it is unsure of. A reply that merely
    happens to be JSON, or that names no tool we have, is prose.

    `skills` widens that by exactly one shape: a model naming a **skill** where
    the tool belongs.

        {"name": "release-checklist", "arguments": {}}

    Measured, not guessed. Ten runs of `qwen2.5-coder:7b` against a loaded skill
    produced five well-formed calls and five of these, and every one of the five
    was the user's request being silently dropped - the model had chosen
    correctly and reached through the wrong door. It never once answered from
    memory.

    Translated rather than passed through: the returned call is `invoke_skill`
    with the skill as its argument, because `release-checklist` is not a tool
    and `tools.run` would rightly refuse it. Everything downstream then sees an
    ordinary invocation and no other code learns this happened.

    **This is a real widening and it is worth naming.** A reply that is exactly
    a JSON object naming a loaded skill now runs it, so a model *discussing* a
    skill in that precise shape would be taken as invoking one. The guards that
    make it narrow are unchanged: the whole reply must be the object, it must
    parse, and the name must match a skill actually loaded in this run. A tool
    of the same name wins, since that is the shape this function was written for.
    """
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        parsed = json.loads(stripped)
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    named = parsed.get("name")
    if named in known:
        # Arguments are passed on as they came. If they are unusable, running
        # the tool reports that - a call axiom could not make, not silence.
        return Call(named, parsed.get("arguments"))
    if skills and named in skills:
        return Call("invoke_skill", {"name": named})
    return None


class ModelBackend(Protocol):
    """What axiom needs a model to do. Implemented here, and by the test stubs."""

    def installed(self) -> list[str]: ...

    def tool_capable(self, models: list[str]) -> set[str]: ...

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

    def installed(self) -> list[str]:
        """Every model on this host, in the order the host gave them.

        Deliberately does *not* swallow the way `model_info` and `supports_tools`
        do. Those two return None/False on failure, and that is precisely why a
        missing model is silent today: the caller cannot tell "the host said no"
        from "the host is not there." Here the difference is the whole point -
        unreachable and reachable-but-empty are different messages with
        different advice - so a failure is raised and the caller decides.

        Sorting is the caller's job, not the host's. Ollama returns models
        newest-modified first, so a single `ollama pull` reorders this list;
        anything the user picks by number has to be sorted before it is shown.
        """
        try:
            # `.model`, not `.name`. The raw /api/tags JSON carries both and
            # they are equal, but the client's model object exposes only this
            # one - measured, not assumed.
            return [entry.model for entry in self._client.list().models]
        except (ollama.ResponseError, ConnectionError, httpx.HTTPError) as lost:
            raise ConnectionLost(str(lost)) from lost

    def tool_capable(self, models: list[str]) -> set[str]:
        """Which of these can call tools. Asked once, for the whole list.

        One `show()` per model, which is an N+1 against a listing that already
        knew the answer: `/api/tags` returns a `capabilities` array per model,
        and the Python client throws it away - `ListResponse.Model` declares
        only `model`, `modified_at`, `digest`, `size` and `details`, and the
        base model does not keep extras, so `model_extra` is None. Measured on
        ollama 0.6.2. There is no way to reach it through the client.

        Hand-rolling a request to `/api/tags` would avoid the N+1, and is not
        worth a second way of talking to Ollama for a field one library version
        may expose. **If a later `ollama` adds `capabilities` to the listing,
        this becomes one call and should.**

        Measured at about 75 ms per model locally - 377 ms for five - so the
        caller asks only when a choice is actually being made, never on the
        path where the user named a model that exists.

        A model that cannot be asked is simply absent from the result. It is
        not a failure worth ending a run over, and treating "unknown" as "no
        tools" is the reading that never overstates what a model can do.
        """
        capable = set()
        for model in models:
            try:
                if "tools" in (self._client.show(model).capabilities or []):
                    capable.add(model)
            except (ollama.ResponseError, ConnectionError, httpx.HTTPError):
                continue
        return capable

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
                    chunk.prompt_eval_count or 0,
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
