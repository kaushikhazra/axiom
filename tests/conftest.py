"""Shared test isolation and the stubs every module needs.

AXIOM_DEBUG_MAX_CONTEXT is a debugging override that live compaction runs
export into the shell and leave there. Six tests read the effective context
out of the startup line, so an ambient value silently rewrites what they are
asserting against - the suite went red on a machine where nothing was wrong
with the code.

No test should inherit it. The ones that are actually about the override set
it themselves, which still works: this clears it before the test body runs.
"""

import builtins

import pytest

from axiom import models
from axiom.backend import Call, Piece


AXIOM_ENV_VARS = ("AXIOM_HOST", "AXIOM_MODEL", "AXIOM_DEBUG_MAX_CONTEXT")


@pytest.fixture(autouse=True)
def isolate_axiom_env(monkeypatch):
    """No test inherits an axiom setting from the shell it happens to run in.

    All three reach the startup line, and the golden transcript records that
    line verbatim - so an exported AXIOM_HOST turns the whole suite red for a
    reason that has nothing to do with the code.
    """
    for name in AXIOM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def isolate_remembered_choice(monkeypatch, tmp_path):
    """No test reads or writes the real remembered-model file.

    The path is relative to the working directory, and the working directory
    during a test run is this repository - so without this, a test that picks
    a model writes `.axiom/model.json` into the checkout, and every later test
    reads a choice a previous test made. Both are silent: one is a stray file,
    the other is order-dependent tests that pass alone and fail together.

    Tests that are *about* remembering point at their own file explicitly and
    are unaffected by this.
    """
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


class StubBackend:
    """A ModelBackend handed straight to main(). Nothing global is patched.

    `turns` is one list of actions per streamed turn: a string is yielded as a
    piece, an exception instance is raised at that point in the stream. `info`
    is what the model reports about itself, and None means it could not be
    asked - which is what a real backend returns when Ollama is unreachable.
    """

    def __init__(
        self,
        info: dict | None = None,
        turns: list | None = None,
        summary: str = "a short summary",
        usage: int = 1,
        tools_supported: bool = True,
        models: list[str] | None = None,
        listing: BaseException | None = None,
    ) -> None:
        self.info = info
        self.turns = list(turns or [])
        self.summary = summary
        self.usage = usage
        self.tools_supported = tools_supported
        # One model by default, which is the quietest host a run can meet: it
        # is settled without a question and the startup line names it. Tests
        # about the list hand in several; tests about an empty host hand in [].
        self.models = ["qwen2.5:7b"] if models is None else list(models)
        # What `installed()` raises instead of answering. Unlike `model_info`
        # and `supports_tools`, this one does not swallow - "cannot reach the
        # host" and "the host has nothing" are different things to be told.
        self.listing = listing
        # Every model name this backend was asked anything about, in order.
        self.asked_about: list[str] = []
        self.streamed: list[list[dict[str, str]]] = []
        self.completed: list[list[dict[str, str]]] = []
        self.options: list = []
        self.tools_sent: list = []
        self.index = 0

    def installed(self):
        if self.listing is not None:
            raise self.listing
        return list(self.models)

    def model_info(self, model):  # noqa: ANN001
        # Recorded, not ignored. AC 29 is that the context and tool count
        # reported at startup belong to the model actually in use - and a stub
        # that discards the name it was asked about cannot tell a correct
        # implementation from one that asks about the wrong model entirely.
        self.asked_about.append(model)
        return self.info

    def supports_tools(self, model):  # noqa: ANN001
        self.asked_about.append(model)
        return self.tools_supported

    def stream(self, model, messages, options=None, tools=None):  # noqa: ANN001, ARG002
        self.asked_about.append(model)
        self.streamed.append([dict(m) for m in messages])
        self.options.append(options)
        self.tools_sent.append(tools)
        actions = (
            self.turns[self.index] if self.index < len(self.turns) else ["a reply"]
        )
        self.index += 1
        for action in actions:
            if isinstance(action, BaseException):
                raise action
            if isinstance(action, Call):
                yield action
                continue
            yield Piece(action, self.usage)

    def complete(self, model, messages):  # noqa: ANN001, ARG002
        self.completed.append([dict(m) for m in messages])
        return self.summary


def chunk(text: str, prompt_eval_count: int = 0, eval_count: int = 0, tool_calls=None):
    """A streamed chunk shaped like the vendor client's, for tests below the seam."""
    return type(
        "Chunk",
        (),
        {
            "message": type("Msg", (), {"content": text, "tool_calls": tool_calls})(),
            "prompt_eval_count": prompt_eval_count,
            "eval_count": eval_count,
        },
    )()


def vendor_call(call: Call):
    """A Call shaped the way the vendor client hands one back.

    For tests that drive the real OllamaBackend and therefore need what Ollama
    would actually have returned, rather than what we would have made of it.
    """
    return type(
        "ToolCall",
        (),
        {
            "function": type(
                "Function", (), {"name": call.name, "arguments": call.arguments}
            )()
        },
    )()


def history(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    """One sent turn, minus the standing instructions at index 0.

    `main` prepends a system prompt to every request (#41), holding it outside
    `messages` so compaction never treats it as a carried-forward summary. A
    test about what the *conversation* contains wants everything after it.
    """
    return sent[1:]


def feed(monkeypatch, lines: list) -> None:
    """Script what the user types. An exception in the list is raised instead."""
    supply = iter(lines)

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        try:
            item = next(supply)
        except StopIteration:
            raise EOFError from None
        if isinstance(item, BaseException):
            raise item
        return item

    monkeypatch.setattr(builtins, "input", fake_input)
