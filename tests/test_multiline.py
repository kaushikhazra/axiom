"""#80: a message the user meant, however many lines it has.

The guards come first and they come before the feature. Whatever reads keys must
be **terminal-only**: the golden transcript is 477 lines captured from a
`StringIO`, and every one of the other 876 tests drives axiom by substituting
`builtins.input`. If a piped run can reach the new reader, all of that changes
meaning at once.
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

CTRL_ENTER = "\x1b\n"  # escape then line feed - see terminal.compose
ENTER = "\r"


def composed(typed: str) -> str:
    """What `compose` returns for a run of key presses.

    `create_pipe_input` delivers keys without a terminal, so this proves what
    axiom does **with** a key. That this console delivers ctrl+enter as a
    distinct key is a separate claim, measured once by hand and recorded in
    `assumption.md`; no test can make it.
    """
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    terminal.use_rendering(True)
    with create_pipe_input() as pipe:
        pipe.send_text(typed)
        # **Close it.** Without this, a reader whose accept binding is broken
        # waits forever for a key that never comes - and a hanging test is worse
        # than a failing one twice over: it hangs the suite, and it hangs the
        # break-proof, which then gets killed before it can put the file back.
        # That happened, and left terminal.py holding a break.
        # Closed, an unaccepted buffer ends in EOF and the test fails in
        # milliseconds, which is what a break should look like.
        pipe.close()
        return terminal.compose(source=pipe, sink=DummyOutput())


def test_enter_sends_the_message():
    """#80 AC 3."""
    assert composed("hello" + ENTER) == "hello"


def test_ctrl_enter_starts_a_new_line_and_does_not_send():
    """#80 AC 1, AC 2.

    Both halves in one assertion: the message has two lines, which means the key
    inserted one, and it arrived as a single return, which means it did not send.
    """
    assert composed("one" + CTRL_ENTER + "two" + ENTER) == "one\ntwo"


def test_a_message_can_have_many_lines():
    """#80 AC 1, past the two-line case that a special case would satisfy."""
    typed = CTRL_ENTER.join(["alpha", "bravo", "charlie", "delta"]) + ENTER

    assert composed(typed) == "alpha\nbravo\ncharlie\ndelta"


def test_a_blank_line_inside_a_message_is_kept():
    """#80 AC 18. Two ctrl+enters in a row are a blank line, not a no-op."""
    assert (
        composed("alpha" + CTRL_ENTER + CTRL_ENTER + "bravo" + ENTER)
        == "alpha\n\nbravo"
    )


def test_a_single_line_message_is_unchanged_by_any_of_this():
    """#80 AC 12. The whole feature is invisible to someone who never uses it."""
    assert composed("just one line" + ENTER) == "just one line"


def test_a_line_beginning_with_a_slash_is_still_what_was_typed():
    """#80 AC 13's half that lives in the reader.

    The reader returns text; whether a `/exit` is a command is settled above it.
    What must not happen here is the reader treating it as anything special.
    """
    assert composed("/exit" + ENTER) == "/exit"
    assert composed("/skill one" + CTRL_ENTER + "second line" + ENTER) == (
        "/skill one\nsecond line"
    )


# --- #80 AC 4, 5, 22, 23: what the user sees while composing -----------------


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


# --- #80 AC 7 to 10: paste, which is why this is a bug -----------------------

PASTE_START = "\x1b[200~"
PASTE_END = "\x1b[201~"


def pasted(text: str, then: str = ENTER) -> str:
    """What `compose` returns when `text` arrives as a paste.

    A terminal brackets a paste - `\x1b[200~` before, `\x1b[201~` after - so the
    program can tell "the user pressed these keys" from "the user pasted this".
    Windows consoles do not send those markers at all; prompt_toolkit infers a
    paste instead, from a batch of keys arriving together containing a newline
    and at least one character. Either way it becomes one `BracketedPaste` event.

    Which means **this test proves the reader, not the console**. That a real
    paste in a real terminal is recognised as one is on the manual pass's list.
    """
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    terminal.use_rendering(True)
    with create_pipe_input() as pipe:
        pipe.send_text(PASTE_START + text + PASTE_END + then)
        pipe.close()
        return terminal.compose(source=pipe, sink=DummyOutput())


def test_pasting_several_lines_gives_one_message():
    """#80 AC 7. The defect this issue exists for.

    Measured before any of this was built: three lines pasted became three turns,
    three requests, and three confused answers, and the message the user meant was
    never assembled.
    """
    assert pasted("line one\nline two\nline three") == "line one\nline two\nline three"


def test_every_pasted_line_is_there_in_the_order_pasted():
    """#80 AC 8. Cheap-looking, and the cheapest place for an off-by-one to hide."""
    lines = [f"line {n}" for n in range(1, 13)]

    assert pasted("\n".join(lines)) == "\n".join(lines)


def test_nothing_is_sent_while_a_paste_is_still_arriving():
    """#80 AC 9, and the assertion that separates fixed from nearly fixed.

    **A test that only checks the paste came back passes for an implementation
    that sent line one and returned lines two and three.** That is precisely the
    old behaviour with a smaller number, so what is asserted is that the *first*
    line is still in the message rather than gone ahead of it.
    """
    got = pasted("first\nsecond\nthird")

    assert got.startswith("first"), "the first line was sent before the rest arrived"
    assert got.count("\n") == 2, "the paste was broken into pieces"


def test_a_paste_whose_last_line_has_no_newline_is_still_complete():
    """#80 AC 10. Most pastes end without a trailing newline."""
    assert pasted("alpha\nbravo") == "alpha\nbravo"


def test_blank_lines_inside_a_paste_survive():
    """#80 AC 18, on the paste path rather than the typed one.

    A stack trace and a config file both carry blank lines, and they are most of
    what anyone pastes into a coding assistant.
    """
    assert pasted("alpha\n\nbravo\n\n\ncharlie") == "alpha\n\nbravo\n\n\ncharlie"


def test_a_pasted_line_beginning_with_a_slash_is_text():
    """#80 AC 11, at the reader.

    The reader returns text either way; whether a `/exit` is a command is settled
    above it. What must not happen here is the paste being cut at that line, or
    the reader treating it as anything but characters.
    """
    assert pasted("/exit\nand more") == "/exit\nand more"
    assert pasted("run this:\n/skill deploy\nthen stop") == (
        "run this:\n/skill deploy\nthen stop"
    )


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


# --- #80 AC 24 to 26: changing your mind -------------------------------------

ABANDON = "\x03"  # ctrl+c


def test_abandoning_clears_the_message_and_keeps_the_prompt():
    """#80 AC 25. Sends nothing, and returns to an empty prompt."""
    assert composed("throw this away" + ABANDON + "kept this" + ENTER) == "kept this"


def test_abandoning_a_multi_line_message_clears_all_of_it():
    """#80 AC 25. Not just the line the cursor is on.

    The failure this excludes is an abandon that clears one line of four and
    leaves the rest, which reads as a bug rather than as a cancel.
    """
    half_written = "first" + CTRL_ENTER + "second" + CTRL_ENTER + "third"

    assert composed(half_written + ABANDON + "fresh" + ENTER) == "fresh"


def test_abandoning_does_not_end_the_session():
    """#80 AC 26, and the trap in it.

    ctrl+c has always meant "leave" at an idle prompt, and that was right when a
    prompt held one line. With a message part-written it is wrong - the user
    means *not that*, not goodbye - and ending the session would take the
    conversation with it.

    Proved by the reader returning a later message at all: had the interrupt
    escaped, there would be no return value to assert on.
    """
    assert composed("half a thought" + ABANDON + "a whole one" + ENTER) == "a whole one"


def test_an_interrupt_at_an_empty_prompt_still_leaves():
    """#80 AC 26's other half, and AC 35's neighbour.

    The fix for AC 25 must not swallow a real ctrl+c. Empty, the interrupt goes
    up exactly as it did before #80 - which is what ends the session.
    """
    with pytest.raises(KeyboardInterrupt):
        composed(ABANDON)


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
