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

from axiom import models, skills
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


@pytest.fixture(autouse=True)
def compose_reads_a_line(monkeypatch):
    """In tests, composing a message reads one line through `input` (#80).

    A test process is not a console. The real composer reads keys, and
    prompt_toolkit refuses to build against anything that is not a real Windows
    console - so every test that forces `sys.stdout.isatty` in order to exercise
    the *renderer* would otherwise die on a reader it is not testing. Fourteen
    did the moment the composer was wired.

    So the default here is the behaviour those tests were written against: one
    line, from `builtins.input`, which is what `feed` substitutes.

    **This is now the only path any test takes.** It used to say that #80's own
    tests reached the real composer through a `create_pipe_input`; they did, and
    those tests are gone - see `test_multiline.py` for why, and do not write
    another one. The wiring between `read_line` and the composer is still
    asserted there; what a key press does is settled by hand at a real terminal.
    """
    from axiom import terminal

    # `_prompt()`, not `PROMPT`: the accented one, which is what the real path
    # draws at a terminal. Using the plain string here made #77's AC 30 test
    # report that the prompt had lost its accent, when what it had lost was this
    # fixture's attention.
    terminal.use_compose(lambda: input(terminal._prompt()))
    yield
    terminal.use_compose(None)


@pytest.fixture(autouse=True)
def isolate_skills(monkeypatch, tmp_path):
    """No test reads or writes this repository's own `.axiom/skills/`.

    The same hazard as the remembered choice above, and a worse one. The path
    is relative to the working directory, and the working directory during a
    test run is this checkout - so without this, a test that writes a skill
    leaves instructions behind that the *next session axiom runs here* would
    load and offer to a model.

    That is the exposure CLAUDE.md names for #75: a skill outlives the run that
    wrote it. Every other tool axiom has is bounded by its turn. This one is
    not, so the isolation is structural rather than remembered - autouse, so a
    test cannot forget it.

    Tests that are *about* loading point at their own directory explicitly and
    are unaffected.
    """
    monkeypatch.setattr(skills, "DEFAULT_SKILLS_DIRECTORY", tmp_path / "no-skills")


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
        infos: dict[str, dict | None] | None = None,
        capable: dict[str, bool] | None = None,
    ) -> None:
        self.info = info
        # Per-model overrides, for tests where a switch must be shown to have
        # adopted the new model's window or its tool support rather than
        # keeping the old one's.
        self.infos = infos
        self.capable = capable
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
        # Every call to `tool_capable`, with what it was asked about.
        self.capability_asks: list[list[str]] = []
        self.streamed: list[list[dict[str, str]]] = []
        self.completed: list[list[dict[str, str]]] = []
        self.options: list = []
        self.tools_sent: list = []
        self.index = 0

    def installed(self):
        if self.listing is not None:
            raise self.listing
        return list(self.models)

    def tool_capable(self, models):  # noqa: ANN001
        # Recorded, because #52 AC 10 is that a run which never shows a list
        # and never falls back does not pay for this at all - and the only way
        # to see that it was not paid is to see it was not called.
        self.capability_asks.append(list(models))
        if self.capable is not None:
            return {m for m in models if self.capable.get(m, self.tools_supported)}
        return set(models) if self.tools_supported else set()

    def model_info(self, model):  # noqa: ANN001
        # Recorded, not ignored. AC 29 is that the context and tool count
        # reported at startup belong to the model actually in use - and a stub
        # that discards the name it was asked about cannot tell a correct
        # implementation from one that asks about the wrong model entirely.
        self.asked_about.append(model)
        # Per-model when a test says so. One `info` for every model cannot show
        # that a mid-session switch adopted the *new* model's window - the
        # number printed would be identical either way (#49 AC 15).
        if self.infos is not None and model in self.infos:
            return self.infos[model]
        return self.info

    def supports_tools(self, model):  # noqa: ANN001
        self.asked_about.append(model)
        if self.capable is not None and model in self.capable:
            return self.capable[model]
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


def listed(text: str) -> list[str]:
    """The model names, in the order the chooser printed them.

    One helper because there were four, in three files, each keying on "the line
    starts with a digit" - which #77 broke all at once by putting the list inside
    a border, where every row starts with `|`. Four copies of a parse is four
    places to miss next time the frame changes.

    The border and the padding are chrome; the numbering, the order and the names
    are the behaviour. Only the second group is returned.
    """
    names = []
    for line in text.splitlines():
        bare = line.strip().strip("│").strip()
        if not bare[:1].isdigit() or ". " not in bare:
            continue
        names.append(bare.split(". ", 1)[1].split("  ")[0].strip())
    return names


def row_for(text: str, model: str) -> str:
    """The chooser's row for one model, without the frame around it.

    So an assertion can say what follows the name - `tools`, `(default)`,
    `(current)` - without also asserting how many spaces the padding put there.
    #77 aligns the annotations into a column, so the gap is now the length of the
    longest name and pinning it would make every test a test of the widest model
    on the stub's list.

    Returns "" when the model has no row, so a test can assert absence too.
    """
    for line in text.splitlines():
        bare = line.strip().strip("│").strip()
        if not bare[:1].isdigit() or ". " not in bare:
            continue
        if bare.split(". ", 1)[1].split("  ")[0].strip() == model:
            return bare
    return ""
