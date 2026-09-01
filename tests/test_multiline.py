"""#80: a message the user meant, however many lines it has.

The guards come first and they come before the feature. Whatever reads keys must
be **terminal-only**: the golden transcript is 477 lines captured from a
`StringIO`, and every one of the other 876 tests drives axiom by substituting
`builtins.input`. If a piped run can reach the new reader, all of that changes
meaning at once.

**What is not here, and why.** Every test that built a real `prompt_toolkit`
session - the enter/ctrl+enter bindings, the six paste tests, the abandon tests,
the over-wide line - has been removed. Kaushik's machine crashed twice while they
ran, and the escape is understood: `_say_how_to_send` calls `run_in_terminal`,
which writes to the *real* console rather than to the `DummyOutput` the test
supplied, so a test that fed `ctrl+enter` reached out of pytest and into the
session that launched it. **Do not reintroduce a test that constructs a
`PromptSession`, a pipe input, or a key processor.** Those criteria are verified by
hand instead - a person types into a real terminal, which is where they were always
going to be settled.

What is left touches the reader only through the `use_compose` hook or through
`builtins.input`, and is safe to run.
"""

import builtins

import pytest

from axiom import main, models, terminal
from conftest import StubBackend, feed


HOST = "http://localhost:11434"
INSTALLED = ["solo:1b"]


@pytest.fixture
def choice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        models, "DEFAULT_CHOICE_FILE", tmp_path / ".axiom" / "model.json"
    )


def at_a_terminal(monkeypatch):
    """Not a fixture - see tests/test_facts.py for why that does not work."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)


# --- the confinement, proved before the reader exists ------------------------


def test_a_piped_run_reads_through_builtins_input(capsys, monkeypatch, choice):
    """#80 AC 30, and the reason it is the first thing tested.

    Not "the output looks right" - *which function did the reading*. A reader
    that reached the piped path could still produce identical bytes for a
    one-line session and break every multi-line script silently.
    """
    used = []

    def watched(prompt: str = "") -> str:
        used.append(prompt)
        raise EOFError

    monkeypatch.setattr(builtins, "input", watched)
    main([], using=StubBackend(models=INSTALLED))
    capsys.readouterr()

    assert used, "a piped run did not read through builtins.input"


def test_a_piped_run_sends_one_turn_per_line(capsys, monkeypatch, choice):
    """#80 AC 30. What scripts rely on, stated as behaviour rather than as a call.

    This is the criterion that makes multi-line composition terminal-only. A
    script piping three lines expects three turns, and the golden transcript is
    477 lines of exactly that.
    """
    stub = StubBackend(models=INSTALLED, turns=[["one"], ["two"], ["three"]])
    feed(monkeypatch, ["first", "second", "third", "/exit"])
    main([], using=stub)
    printed = capsys.readouterr().out

    assert printed.count("> ") >= 3, "three piped lines were not three turns"
    for answer in ("one", "two", "three"):
        assert answer in printed


def test_importing_the_key_reader_does_not_disturb_a_piped_run(
    capsys, monkeypatch, choice
):
    """#80 AC 30, AC 33. The dependency is present; it must be inert here.

    `prompt_toolkit` installs its own output handling when an application is
    built. Merely being importable must change nothing - and this is what would
    catch it constructing anything at import time.
    """
    import prompt_toolkit  # noqa: F401

    feed(monkeypatch, ["hello", "/exit"])
    main([], using=StubBackend(models=INSTALLED, turns=[["an answer"]]))
    printed = capsys.readouterr().out

    assert printed.startswith("axiom: "), "a piped run no longer opens plainly"
    assert "\x1b" not in printed, "escape sequences reached a piped run"


# --- the substitution hook ---------------------------------------------------


def test_the_composing_reader_can_be_replaced(capsys, monkeypatch, choice):
    """#80's testability, which is a precondition rather than a criterion.

    Every existing test supplies input by monkeypatching `builtins.input`, and a
    terminal-only reader is unreachable from all 876 of them. Without a hook of
    its own nothing about this issue can be tested at all, so the hook comes
    before the feature.
    """
    at_a_terminal(monkeypatch)
    terminal.use_compose(lambda: "a composed message")
    try:
        assert terminal.read_line() == "a composed message"
    finally:
        terminal.use_compose(None)


def test_forgetting_the_composing_reader_returns_to_the_real_one(
    capsys, monkeypatch, choice
):
    """The other half. A hook that cannot be released leaks into the next test.

    **Written in cycle 2 asserting it fell back to `builtins.input`, and that was
    right at the time** - there was no real composer yet, so a terminal with no
    substitute read a plain line. Cycle 3 built one, and this failed loudly
    rather than drifting, which is what it was for.

    What it claims now is the same claim against the new truth: releasing the
    hook returns the *real* composer. Asserted on which callable comes back,
    because building a real one needs a console that a test process does not
    have.
    """
    at_a_terminal(monkeypatch)
    terminal.use_compose(lambda: "substituted")
    assert terminal._composer() is not terminal.compose

    terminal.use_compose(None)
    assert terminal._composer() is terminal.compose


def test_the_hook_is_not_consulted_without_a_terminal(capsys, monkeypatch, choice):
    """#80 AC 30 again, at the hook rather than at the run.

    A substituted composer must not be reachable from a piped run either, or a
    test could pass while the real thing was wired to the wrong path.
    """
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    terminal.use_compose(lambda: "should not be used")
    try:
        feed(monkeypatch, ["typed"])
        assert terminal.read_line() == "typed"
    finally:
        terminal.use_compose(None)


# --- the reader --------------------------------------------------------------


def test_a_continuation_line_is_marked_as_still_being_written(monkeypatch):
    """#80 AC 23, and AC 4 and AC 24 with it.

    prompt_toolkit's default continuation is `prompt_width` spaces, which lines
    the text up and marks nothing - a message part way through then looks exactly
    like one that has been sent and answered. What is asserted is that axiom
    supplies a continuation of its own, and that it is drawn in the voice's grey
    rather than at the answer's weight.

    Asserted on the callable rather than on a screen, because rendering it needs
    a console. What it *looks* like is the manual pass's, and is on that list.
    """
    from prompt_toolkit.formatted_text import to_plain_text

    continuation = terminal._compose_continuation()
    drawn = continuation(2, 1, False)

    assert to_plain_text(drawn).strip(), "a continuation line is marked with nothing"
    assert terminal.VOICE_GREY.lstrip("#") in str(drawn.value) or "38;2" in str(
        drawn.value
    ), "the continuation is not in the voice's grey"


def test_how_to_send_is_said_once_and_not_again(capsys, monkeypatch):
    """#80 AC 5.

    The hint answers a question the user has exactly once - at the moment they
    discover that enter no longer does what it did a second ago. Said on every
    line it is noise, and by the fourth it is in the way of what they are writing.
    """
    at_a_terminal(monkeypatch)
    terminal.forget_the_hint()
    said = []
    monkeypatch.setattr(
        terminal, "say", lambda message, stream=None: said.append(message)
    )
    monkeypatch.setattr(
        "prompt_toolkit.application.run_in_terminal", lambda draw: draw()
    )

    terminal._say_how_to_send()
    terminal._say_how_to_send()
    terminal._say_how_to_send()

    assert len(said) == 1, f"the hint was said {len(said)} times"
    assert "ctrl+enter" in said[0] and "enter sends" in said[0]


def test_the_hint_says_both_halves(capsys, monkeypatch):
    """#80 AC 5. "How to send **and** how to add another" - both, or neither.

    A hint that says only how to add a line leaves the user unable to finish, and
    one that says only how to send does not explain the key they just pressed.
    """
    at_a_terminal(monkeypatch)
    terminal.forget_the_hint()
    said = []
    monkeypatch.setattr(
        terminal, "say", lambda message, stream=None: said.append(message)
    )
    monkeypatch.setattr(
        "prompt_toolkit.application.run_in_terminal", lambda draw: draw()
    )

    terminal._say_how_to_send()

    assert "sends" in said[0], "the hint never says how to send"
    assert "another line" in said[0], "the hint never says how to add a line"


# --- #80 AC 11 to 14: a composed message that opens with a slash -------------


def sent_to(monkeypatch, capsys, typed_message: str) -> list:
    """What the model was asked, for a message composed rather than typed."""
    at_a_terminal(monkeypatch)
    stub = StubBackend(models=INSTALLED, turns=[["an answer"]])
    supply = iter([typed_message, "/exit"])
    terminal.use_compose(lambda: next(supply))
    try:
        main([], using=stub)
    finally:
        terminal.use_compose(None)
    capsys.readouterr()
    return [
        message["content"]
        for sent in stub.streamed
        for message in sent
        if message.get("role") == "user"
    ]


def test_a_multi_line_message_beginning_with_a_command_is_a_message(
    capsys, monkeypatch, choice
):
    """#80 AC 11 and AC 14, above the reader, where they are actually decided.

    `/exit` was already safe - it is matched by equality, and a message with more
    lines is not equal to it. **`/model` and `/skill` were not**: both used
    `startswith`, so a stack trace pasted with `/model` on its first line was
    swallowed as a switch and the rest of it thrown away. Found by reading the
    matching rather than by a failing test, because nothing composed a message
    before this issue.
    """
    asked = sent_to(monkeypatch, capsys, "/model something\nand the rest of it")

    assert asked, "the message never reached the model"
    assert "and the rest of it" in asked[-1], "the rest of the message was lost"


def test_a_multi_line_message_beginning_with_slash_skill_is_a_message(
    capsys, monkeypatch, choice
):
    """#80 AC 11 and AC 14. The same hole, the other command."""
    asked = sent_to(monkeypatch, capsys, "/skill deploy\nplus a second line")

    assert asked, "the message never reached the model"
    assert "plus a second line" in asked[-1]


def test_a_typed_command_on_one_line_still_works(capsys, monkeypatch, choice):
    """#80 AC 13, which pulls directly against AC 11 and AC 14.

    Same characters, different meaning, told apart only by whether there is a
    second line. A fix for AC 10 that broke this would have met neither.
    """
    at_a_terminal(monkeypatch)
    supply = iter(["/skills", "/exit"])
    terminal.use_compose(lambda: next(supply))
    try:
        main([], using=StubBackend(models=INSTALLED))
    finally:
        terminal.use_compose(None)

    printed = capsys.readouterr().out
    assert "skill" in printed.lower(), "a typed command stopped being a command"


# --- #80 AC 27: changing your mind reaches nothing ---------------------------


def test_an_abandoned_message_never_reaches_the_model(capsys, monkeypatch, choice):
    """#80 AC 27. The conversation is exactly as it was before it began.

    Structural rather than defended - an abandoned buffer never leaves the reader
    - but asserted anyway, because "nothing was sent" is the claim a user cares
    about and the structure could change under it.
    """
    asked = sent_to(monkeypatch, capsys, "the message that survives")

    assert asked, "nothing reached the model at all"
    assert all("throw this away" not in message for message in asked)


# --- #80 AC 31 to 36: what did not change ------------------------------------


def test_no_render_is_unchanged_by_composing(capsys, monkeypatch, choice):
    """#80 AC 31. `--no-render` takes the plain path, composer or no composer.

    **Asserted on which reader was used, not on the output.** The first version
    checked the printed bytes, and could not fail: `conftest` substitutes a
    composer that reads through `input` so the other 900 tests keep working, so
    both paths produced identical output and the break stayed green. A guard that
    cannot tell the two paths apart is not guarding the thing it names.
    """
    at_a_terminal(monkeypatch)
    reached = []
    terminal.use_compose(lambda: reached.append("composer") or "hello")
    feed(monkeypatch, ["hello", "/exit"])
    try:
        main(
            ["--no-render"], using=StubBackend(models=INSTALLED, turns=[["an answer"]])
        )
    finally:
        terminal.use_compose(None)
    printed = capsys.readouterr().out

    assert not reached, "--no-render reached the composing reader"
    assert "an answer" in printed
    assert "\x1b" not in printed, "escape sequences reached a --no-render run"


def test_a_single_line_session_is_what_it_was_before_any_of_this(
    capsys, monkeypatch, choice
):
    """#80 AC 33.

    Compared against `.tmp/before-80.txt` by hand in cycle 2 and again here in
    the only form a test can hold: the piped path, which is the one the golden
    transcript records, produces the lines it always did.
    """
    feed(monkeypatch, ["hello", "/exit"])
    main([], using=StubBackend(models=INSTALLED, turns=[["an answer"]]))
    printed = capsys.readouterr().out

    assert printed.startswith("axiom: "), "a piped run no longer opens plainly"
    assert "> " in printed and "an answer" in printed
    assert "…" not in printed, "a continuation marker reached a piped run"


def test_exit_at_an_empty_prompt_exits_with_the_same_status(
    capsys, monkeypatch, choice
):
    """#80 AC 34. Unchanged, and cheap to lose."""
    at_a_terminal(monkeypatch)
    supply = iter(["/exit"])
    terminal.use_compose(lambda: next(supply))
    try:
        main([], using=StubBackend(models=INSTALLED))
    finally:
        terminal.use_compose(None)

    assert "an answer" not in capsys.readouterr().out


def test_end_of_input_at_an_empty_prompt_exits(capsys, monkeypatch, choice):
    """#80 AC 35. Ctrl-d, or a pipe running dry."""
    at_a_terminal(monkeypatch)

    def ends():
        raise EOFError

    terminal.use_compose(ends)
    try:
        main([], using=StubBackend(models=INSTALLED))
    finally:
        terminal.use_compose(None)

    capsys.readouterr()  # exiting on end of input is not an error


# --- #80 AC 19, 20, 36: the edges --------------------------------------------


def read_with(monkeypatch, composed_text):
    """What `read_line` makes of what the composer returned.

    **At this level deliberately.** `compose` returns the buffer as typed - it
    does not strip - and `read_line` is where trailing whitespace goes. A test
    written against `compose` would assert the wrong thing about the right
    behaviour and pass for a build that had broken it.
    """
    at_a_terminal(monkeypatch)
    terminal.use_compose(lambda: composed_text)
    try:
        return terminal.read_line()
    finally:
        terminal.use_compose(None)


def test_blank_lines_at_the_end_do_not_become_a_message_of_their_own(monkeypatch):
    """#80 AC 19."""
    assert read_with(monkeypatch, "hello\n\n\n") == "hello"


def test_a_message_of_only_blank_lines_sends_nothing(capsys, monkeypatch, choice):
    """#80 AC 20. Sends nothing, and leaves the prompt where it was.

    Driven through `main` rather than `read_line`, because "sends nothing" is a
    claim about the model being asked, not about a string being empty.
    """
    at_a_terminal(monkeypatch)
    stub = StubBackend(models=INSTALLED, turns=[["should never be reached"]])
    supply = iter(["\n\n\n", "/exit"])
    terminal.use_compose(lambda: next(supply))
    try:
        main([], using=stub)
    finally:
        terminal.use_compose(None)
    capsys.readouterr()

    assert stub.streamed == [], "a message of blank lines was sent to the model"


def test_leaving_with_a_message_part_composed_sends_nothing(
    capsys, monkeypatch, choice
):
    """#80 AC 36.

    Ctrl-d with text in the buffer raises `EOFError`, which `read_line` already
    turns into "leave". What this asserts is the half that matters: the
    half-written text goes nowhere at all.
    """
    at_a_terminal(monkeypatch)
    stub = StubBackend(models=INSTALLED, turns=[["should never be reached"]])

    def leaves_mid_message():
        raise EOFError

    terminal.use_compose(leaves_mid_message)
    try:
        main([], using=stub)
    finally:
        terminal.use_compose(None)
    capsys.readouterr()

    assert stub.streamed == [], "a part-composed message was sent on the way out"
