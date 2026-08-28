"""A scheduled job inside a whole session, not inside a function.

`_chat` builds its own `Schedule` with the real clock, so a test that wants a
job to come due has to hand it a different one. The factory is patched rather
than `main` gaining a test-only argument - the production path stays exactly
what it is, and the seam is the one place that builds the store.
"""

from datetime import datetime

import pytest

import axiom
from axiom import schedule, terminal
from axiom.backend import Call
from conftest import StubBackend, feed

MONDAY = datetime(2026, 8, 31, 18, 47)


@pytest.fixture(autouse=True)
def forget_the_reader():
    """The timed read holds a module-level reader. It must not outlive a test."""
    terminal.use_input(None)
    yield
    terminal.use_input(None)


@pytest.fixture
def clock(monkeypatch):
    """A clock the test moves, behind the store `_chat` builds for itself."""
    now = {"at": MONDAY}
    real = schedule.Schedule  # captured before patching, or the lambda calls itself
    monkeypatch.setattr(
        schedule, "Schedule", lambda clock=None: real(lambda: now["at"])
    )
    return now


def scheduling(cron: str, prompt: str, repeating: bool = True) -> Call:
    arguments = {"cron": cron, "prompt": prompt}
    if not repeating:
        arguments["repeating"] = False
    return Call("schedule_prompt", arguments)


# --- a session that never schedules anything ------------------------------


def test_a_run_with_nothing_scheduled_says_nothing_about_schedules(monkeypatch, capsys):
    """#74 AC 1.

    The guard against a later cycle adding a startup line for a feature most
    sessions never use. Nothing is scheduled here, so nothing is said.
    """
    backend = StubBackend(turns=[["a reply"]])
    feed(monkeypatch, ["hello", "/exit"])

    axiom.main([], using=backend)

    out = capsys.readouterr().out.lower()
    for word in ("schedule", "cron", " job"):
        assert word not in out, f"{word!r} was said in a session with none"


def test_a_session_that_schedules_nothing_never_starts_a_reader_thread(
    monkeypatch, capsys
):
    """The blocking read is untouched when there is nothing to wait for.

    This is what makes the tick free: a session with an empty schedule never
    reaches the timed path, so it never starts a thread and never wakes up.
    """
    backend = StubBackend(turns=[["a reply"]])
    feed(monkeypatch, ["hello", "/exit"])

    axiom.main([], using=backend)
    capsys.readouterr()

    assert terminal._typed is None, "a reader thread was started for nothing"


# --- a job that outlives the turn that made it ---------------------------


def test_the_schedule_survives_a_second_turn(monkeypatch, capsys, clock):
    """#74 AC 24's half that can be proved here.

    The store lives in `_chat`'s locals. What would break this is someone moving
    it inside the loop, which would silently forget every job on every turn - and
    nothing else in the suite would notice.
    """
    backend = StubBackend(
        turns=[
            [scheduling("0 9 * * *", "morning report")],
            ["scheduled it"],
            [Call("list_schedules", {})],
            ["here they are"],
        ]
    )
    feed(monkeypatch, ["schedule it", "what is scheduled?", "/exit"])

    axiom.main([], using=backend)

    out = capsys.readouterr().out

    # Not "morning report appears after the question": `feed` echoes the prompt
    # and not the line, so that anchor is never in the output and the split
    # returns everything. Measured - the first version of this test passed with
    # the store rebuilt on every turn, which is the whole thing it guards.
    assert "nothing is scheduled" not in out, "the schedule was forgotten"
    assert out.count("morning report") >= 2, (
        "scheduled once and listed once, so it should be said twice"
    )


def test_a_scheduled_job_is_moved_on_before_its_turn_runs(clock):
    """#74 AC 30's half that is structural.

    `_next_line` calls `mark_run` before it hands the prompt back, so the job is
    already at its next time before the turn starts. A turn that then fails
    cannot strand it - there is no path where a failed run leaves a job stuck on
    a time that has passed.
    """
    jobs = schedule.Schedule()
    jobs.add("*/15 * * * *", "check the deploy")
    clock["at"] = datetime(2026, 8, 31, 19, 30)

    terminal.use_input(lambda: (_ for _ in ()).throw(EOFError()))
    due_before = jobs.due()
    assert due_before, "the fixture did not come due"

    jobs.mark_run(due_before[0].id)

    assert jobs.due() == (), (
        "still due after being marked, so a failure would repeat it"
    )
    assert len(jobs) == 1, "a repeating job was dropped rather than moved on"
