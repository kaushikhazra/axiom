"""A job's prompt reaching the chat loop, and never reaching it mid-turn.

`_next_line` is the whole seam: it is called at the top of the loop and nowhere
else, so AC 10 and AC 11 are structural rather than defended. These tests pin
that structure.

The clock is supplied and `terminal.read_line` is patched, so nothing here waits
on real time and no reader thread is ever started.
"""

from datetime import datetime

import pytest

import axiom
from axiom import schedule, terminal

MONDAY = datetime(2026, 8, 31, 18, 47)
LATER = datetime(2026, 8, 31, 19, 30)


def store(now: datetime = MONDAY) -> schedule.Schedule:
    return schedule.Schedule(clock=lambda: now)


def reading(monkeypatch, *answers):
    """Script what `read_line` returns, and record how it was called."""
    supply = iter(answers)
    calls: list = []

    def fake(timeout=None):
        calls.append(timeout)
        try:
            return next(supply)
        except StopIteration:
            return terminal.WAITING

    monkeypatch.setattr(terminal, "read_line", fake)
    return calls


def quiet(monkeypatch) -> list[str]:
    """Swallow the prompt drawing, and record it."""
    drawn: list[str] = []
    monkeypatch.setattr(terminal, "show_prompt", lambda: drawn.append("prompt"))
    monkeypatch.setattr(terminal, "take_back_prompt", lambda: drawn.append("erase"))
    return drawn


# --- nothing scheduled ----------------------------------------------------


def test_an_empty_schedule_takes_the_blocking_read(monkeypatch):
    """A session that never schedules anything cannot tell any of this exists."""
    calls = reading(monkeypatch, "hello")
    quiet(monkeypatch)

    assert axiom._next_line(store()) == ("hello", False)
    assert calls == [None], "a timeout was used with nothing scheduled"


def test_no_schedule_at_all_takes_the_blocking_read(monkeypatch):
    calls = reading(monkeypatch, "hello")

    assert axiom._next_line(None) == ("hello", False)
    assert calls == [None]


# --- a job firing ---------------------------------------------------------


def test_a_due_job_runs_while_the_user_types_nothing(monkeypatch):
    """#74 AC 9. The criterion the whole seam exists for."""
    jobs = store()
    jobs.add("*/15 * * * *", "check the deploy")
    jobs._clock = lambda: LATER  # the wait outlasts the job's time
    reading(monkeypatch)  # the user types nothing at all
    quiet(monkeypatch)

    assert axiom._next_line(jobs) == ("check the deploy", True)


def test_a_typed_line_is_still_a_typed_line(monkeypatch):
    """A schedule existing does not make what the user types into a job."""
    jobs = store()
    jobs.add("0 9 * * *", "much later")
    reading(monkeypatch, "hello")
    quiet(monkeypatch)

    assert axiom._next_line(jobs) == ("hello", False)


def test_leaving_still_reaches_the_caller_through_the_timed_read(monkeypatch):
    """Ctrl-D with a schedule running must still end the session."""
    jobs = store()
    jobs.add("0 9 * * *", "much later")
    reading(monkeypatch, None)
    quiet(monkeypatch)

    assert axiom._next_line(jobs) == (None, False)


# --- one at a time --------------------------------------------------------


def test_two_jobs_due_at_once_come_back_one_per_call(monkeypatch):
    """#74 AC 11. One job per pass of the loop, so a turn separates them."""
    jobs = store()
    jobs.add("*/15 * * * *", "sooner")  # 19:00
    jobs.add("0 * * * *", "later")  # 20:00
    jobs._clock = lambda: datetime(2026, 8, 31, 20, 30)
    reading(monkeypatch)
    quiet(monkeypatch)

    assert axiom._next_line(jobs)[0] == "sooner"
    assert axiom._next_line(jobs)[0] == "later"


def test_a_one_shot_does_not_come_back_twice(monkeypatch):
    """#74 AC 20, through the seam rather than in the store."""
    jobs = store()
    jobs.add("0 19 * * *", "just once", recurring=False)
    jobs._clock = lambda: LATER
    reading(monkeypatch)
    quiet(monkeypatch)

    assert axiom._next_line(jobs)[0] == "just once"
    assert len(jobs) == 0


def test_a_repeating_job_does_not_come_back_immediately(monkeypatch):
    """Or one due job would fill the session with itself."""
    jobs = store()
    jobs.add("*/15 * * * *", "over and over")
    jobs._clock = lambda: LATER
    reading(monkeypatch)
    quiet(monkeypatch)

    assert axiom._next_line(jobs)[0] == "over and over"
    assert jobs.due(LATER) == (), "still due immediately after running"


# --- what the user sees ---------------------------------------------------


def test_the_prompt_is_drawn_once_and_taken_back_when_a_job_fires(monkeypatch):
    """Measured on the modelled screen in cycle 3's log.

    Without the erase the turn starts on the prompt row and the user reads
    `> axiom: scheduled - ...`, their own prompt run together with axiom's line.
    """
    jobs = store()
    jobs.add("*/15 * * * *", "check the deploy")
    jobs._clock = lambda: LATER
    reading(monkeypatch)
    drawn = quiet(monkeypatch)

    axiom._next_line(jobs)

    assert drawn == ["prompt", "erase"]


def test_the_prompt_is_not_taken_back_when_the_user_types(monkeypatch):
    """Nothing is drawn over, so nothing is erased."""
    jobs = store()
    jobs.add("0 9 * * *", "much later")
    reading(monkeypatch, "hello")
    drawn = quiet(monkeypatch)

    axiom._next_line(jobs)

    assert drawn == ["prompt"]


def test_a_scheduled_turn_says_so_in_axioms_own_voice(capsys):
    """#74 AC 13, and #60 AC 17 - axiom's voice, not a fourth one."""
    terminal.note_scheduled("check the deploy")

    out = capsys.readouterr().out
    assert out.startswith(terminal.VOICE)
    assert "check the deploy" in out, "the user cannot see what was asked"
