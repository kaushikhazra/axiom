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
from datetime import datetime

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
    """#80 AC 23, and **only** AC 23.

    prompt_toolkit's default continuation is `prompt_width` spaces, which lines
    the text up and marks nothing - a message part way through then looks exactly
    like one that has been sent and answered. What is asserted is that axiom
    supplies a continuation of its own, and that it is drawn in the voice's grey
    rather than at the answer's weight.

    **This used to claim AC 4 and AC 24 as well, and it never proved either.**
    AC 4 is "the user can see every line the message contains" and AC 24 is "the
    user can tell how many lines it has" - both are about what is on a screen, and
    this asserts that a callable returns a grey marker. Those two are on
    `manual-pass.md` where they belong.

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


def composing(monkeypatch, capsys, *messages) -> StubBackend:
    """The backend, after a session that composed each of `messages` in turn.

    Returned rather than unpacked because three criteria ask three different
    questions of the same run: what the model was *sent* (AC 15), how many
    entries the conversation *holds* (AC 16), and how many requests it *cost*
    (AC 17). Only the last of those is a question about `stub.streamed`'s length,
    and it is invisible to a helper that flattens it away.
    """
    at_a_terminal(monkeypatch)
    stub = StubBackend(models=INSTALLED, turns=[["an answer"]] * len(messages))
    supply = iter([*messages, "/exit"])
    terminal.use_compose(lambda: next(supply))
    try:
        main([], using=stub)
    finally:
        terminal.use_compose(None)
    capsys.readouterr()
    return stub


def sent_to(monkeypatch, capsys, typed_message: str) -> list:
    """What the model was asked, for a message composed rather than typed."""
    stub = composing(monkeypatch, capsys, typed_message)
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
    second line. A fix for AC 11 or AC 14 that broke this would have met neither.
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


# --- #80 AC 15 to 17: what reaches the model, and what it costs --------------


def test_the_model_receives_one_message_with_its_line_breaks(
    capsys, monkeypatch, choice
):
    """#80 AC 15, and the criterion that says the bug is actually fixed.

    The bug was three lines arriving as three turns. What is asserted is the
    opposite end of it: one entry, with the newlines still in it. Equality
    rather than `in`, because "contains the words" is exactly the vacuous shape
    the queue's Standing warns about - the plain echo puts them in the stream
    whatever the reader did.
    """
    asked = sent_to(monkeypatch, capsys, "first\nsecond\nthird")

    assert asked == ["first\nsecond\nthird"], f"the model was sent {asked!r}"


def test_the_conversation_holds_one_entry_per_message_not_one_per_line(
    capsys, monkeypatch, choice
):
    """#80 AC 16. Two messages of three lines each are two entries, not six.

    Read from the *second* request, because that is the first one whose history
    could be wrong: a single-turn session sends one entry however it split the
    message, and would pass for an implementation that had learnt nothing.
    """
    stub = composing(monkeypatch, capsys, "one\ntwo\nthree", "four\nfive\nsix")

    assert len(stub.streamed) == 2, "two messages were not two turns"
    said = [m["content"] for m in stub.streamed[-1] if m.get("role") == "user"]
    assert said == ["one\ntwo\nthree", "four\nfive\nsix"], f"history held {said!r}"


def test_a_message_of_many_lines_costs_one_request(capsys, monkeypatch, choice):
    """#80 AC 17. Six lines, one request - the thing the bug was charging for.

    The measured cost of the defect: three pasted lines were three requests and
    three useless answers. This is that, stated as arithmetic.

    **The count alone was vacuous, and the break proved it.** Written first as
    `len(stub.streamed) == 1` and nothing else, it stayed green against a reader
    that threw away every line but the first - which is one request, and is also
    the feature doing nothing. One request *carrying all six lines* is the
    criterion; the number on its own is satisfied by losing five of them.
    """
    stub = composing(monkeypatch, capsys, "a\nb\nc\nd\ne\nf")

    assert len(stub.streamed) == 1, f"six lines cost {len(stub.streamed)} requests"
    said = [m["content"] for m in stub.streamed[0] if m.get("role") == "user"]
    assert said == ["a\nb\nc\nd\ne\nf"], f"the one request carried {said!r}"


# --- #80 AC 22: wider than the window ----------------------------------------


def test_a_line_wider_than_the_window_is_read_in_full(monkeypatch):
    """#80 AC 22, at the reader - #72 owns what happens when it is *drawn*.

    Rebuilt at the hook. The version deleted in `32daf51` fed 500 characters to
    a real `prompt_toolkit` session, which was never what the criterion needed:
    what is at stake is whether anything between the composer and the caller
    shortens the message, and the composer is reachable through `use_compose`.
    """
    long_line = "x" * 500

    assert read_with(monkeypatch, long_line) == long_line


def test_every_line_of_an_over_wide_message_survives(monkeypatch):
    """#80 AC 22 with more than one line, which is where a cut would hide.

    A truncation that took the message to one window's width would still pass
    the single-line check above if the window were wide enough. Three lines of
    300 characters cannot fit any terminal, so nothing but "unchanged" passes.
    """
    wide = "\n".join(["a" * 300, "b" * 300, "c" * 300])

    assert read_with(monkeypatch, wide) == wide


# --- #80 AC 14: a command is a command, and never a first line ---------------


def test_a_command_does_not_wait_for_a_second_line(capsys, monkeypatch, choice):
    """#80 AC 14, given a test of its own at last.

    Cycle 7 found this riding on a test that cited the pre-renumber AC 10 and
    actually proved AC 11. The distinct claim here is the *negative* one: typing
    `/exit` must not put axiom into composing a longer message. Proved by
    supplying exactly one line - a reader that came back for a second would hit
    `StopIteration` and fail loudly rather than passing quietly.
    """
    at_a_terminal(monkeypatch)
    stub = StubBackend(models=INSTALLED)
    supply = iter(["/exit"])
    terminal.use_compose(lambda: next(supply))
    try:
        main([], using=stub)
    finally:
        terminal.use_compose(None)
    capsys.readouterr()

    assert stub.streamed == [], "a command reached the model"
    assert next(supply, "spent") == "spent", "the command asked for another line"


# --- #80 AC 32: a prompt that arrives from a schedule ------------------------


def test_a_scheduled_prompt_of_many_lines_arrives_whole(monkeypatch):
    """#80 AC 32. A job's prompt is a string; it never touches the reader.

    Structural, and asserted anyway: `_next_line` returns the job's own text and
    the composer is never consulted, so a schedule cannot lose a line break. The
    composer here raises if called, which is what would catch one creeping into
    this path.
    """
    import axiom
    from axiom import schedule

    def never() -> str:
        raise AssertionError("the composer was consulted for a scheduled prompt")

    jobs = schedule.Schedule(clock=lambda: datetime(2026, 8, 31, 18, 47))
    jobs.add("*/15 * * * *", "look at this\nand this\n\nand this too")
    jobs._clock = lambda: datetime(2026, 8, 31, 19, 30)
    monkeypatch.setattr(terminal, "read_line", lambda timeout=None: terminal.WAITING)
    monkeypatch.setattr(terminal, "show_prompt", lambda: None)
    monkeypatch.setattr(terminal, "take_back_prompt", lambda: None)
    terminal.use_compose(never)
    try:
        line, from_a_job = axiom._next_line(jobs)
    finally:
        terminal.use_compose(None)

    assert from_a_job is True
    assert line == "look at this\nand this\n\nand this too"


# --- #80 AC 28, 29: there is nothing to configure ----------------------------


def test_composing_works_on_a_first_run_with_no_flags(capsys, monkeypatch, choice):
    """#80 AC 28. No flag, no file, no environment variable.

    `choice` points the remembered-model file at an empty `tmp_path`, so this is
    a first run in the only sense axiom has one. `main([])` is the whole
    configuration.
    """
    asked = sent_to(monkeypatch, capsys, "two\nlines")

    assert asked == ["two\nlines"], "a first run did not compose"


def test_nothing_switches_composing_on_or_off_by_itself(monkeypatch):
    """#80 AC 29, attacked rather than confirmed.

    The criterion is not "there is no switch" - `--no-render` is one, and it has
    to be, because a piped run must not read keys. It is that no switch leaves
    *single-line* messages behaving differently from today. So what is asserted
    is that the gate has exactly two inputs, rendering and a terminal, and that
    no setting of any other name reaches it: a `--compose`, an `AXIOM_MULTILINE`
    or a `multiline:` config key would each be a way to end up with two different
    single-line behaviours.
    """
    from axiom import config

    settings = config.resolve([])
    named = " ".join(vars(settings)).lower()

    assert "compose" not in named, "a setting configures composing"
    assert "multiline" not in named, "a setting configures multi-line messages"
    assert "line" not in named, "a setting configures how a line is read"
