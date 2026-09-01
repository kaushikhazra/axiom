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
    """The other half. A hook that cannot be released leaks into the next test."""
    at_a_terminal(monkeypatch)
    terminal.use_compose(lambda: "substituted")
    terminal.use_compose(None)

    feed(monkeypatch, ["typed"])
    assert terminal.read_line() == "typed"


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
