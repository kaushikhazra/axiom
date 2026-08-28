"""The input seam a schedule needs: a read that can time out.

`input()` blocks, and that is where a session spends nearly all of its life. A
job cannot fire from inside it. These tests are about the seam only - nothing
here runs a turn or talks to a model.

Timeouts are milliseconds. Nothing waits on a schedule.
"""

import queue

import pytest

from axiom import terminal
from axiom.terminal import Typed, WAITING


def typing(*lines: str) -> Typed:
    """A reader that hands over these lines, then blocks as a real one would."""
    remaining = list(lines)
    held = queue.Queue()

    def read() -> str:
        if remaining:
            return remaining.pop(0)
        held.get()  # never arrives; stands in for a user who types nothing more
        return ""

    return Typed(read=read)


def test_a_typed_line_comes_back():
    assert typing("hello").next(timeout=1.0) == "hello"


def test_a_line_is_stripped_the_way_it_always_was():
    assert typing("  spaced  ").next(timeout=1.0) == "spaced"


def test_nothing_typed_gives_waiting_rather_than_a_line():
    """#74 AC 9's whole point: the caller gets control back to check the clock."""
    assert typing().next(timeout=0.01) is WAITING


def test_waiting_is_not_none_and_not_a_line():
    """`None` means leaving. A timeout must not be mistakable for it."""
    assert WAITING is not None
    assert not isinstance(WAITING, str)


@pytest.mark.parametrize("ending", [EOFError, KeyboardInterrupt])
def test_leaving_still_comes_back_as_none(ending):
    """The contract `read_line` has always had, carried across the queue.

    Ctrl-D and Ctrl-C at an idle prompt both mean leave. Breaking this would
    cost more than scheduling is worth - a user who cannot exit axiom.
    """

    def read():
        raise ending()

    assert Typed(read=read).next(timeout=1.0) is None


def test_lines_arrive_in_the_order_they_were_typed():
    reader = typing("first", "second", "third")

    assert [reader.next(timeout=1.0) for _ in range(3)] == ["first", "second", "third"]


def test_waiting_then_a_line_still_gives_the_line():
    """A timeout is not a lost line - the caller comes back for it."""
    remaining = ["eventually"]
    started = queue.Queue()

    def read() -> str:
        started.get()  # held until the test releases it
        return remaining.pop(0)

    reader = Typed(read=read)
    assert reader.next(timeout=0.01) is WAITING
    started.put(None)
    assert reader.next(timeout=1.0) == "eventually"


def test_no_thread_is_started_until_a_timed_read_is_asked_for():
    """A session that never schedules anything never starts a thread."""
    reader = typing("hello")

    assert reader._thread is None
    reader.next(timeout=1.0)
    assert reader._thread is not None


def test_the_untimed_read_is_unchanged(monkeypatch):
    """Every existing caller takes this path and cannot tell the other exists."""
    monkeypatch.setattr("builtins.input", lambda prompt="": "  typed  ")

    assert terminal.read_line() == "typed"


@pytest.mark.parametrize("ending", [EOFError, KeyboardInterrupt])
def test_the_untimed_read_still_returns_none_on_leaving(monkeypatch, ending):
    def raising(prompt=""):
        raise ending()

    monkeypatch.setattr("builtins.input", raising)

    assert terminal.read_line() is None
