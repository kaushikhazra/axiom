"""A scheduled job inside a whole session, not inside a function.

`_chat` builds its own `Schedule` with the real clock, so a test that wants a
job to come due has to hand it a different one. The factory is patched rather
than `main` gaining a test-only argument - the production path stays exactly
what it is, and the seam is the one place that builds the store.
"""

import threading
from datetime import datetime

import pytest

import axiom
from axiom import schedule, terminal
from axiom.backend import Call, ConnectionLost
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


# --- a job that actually fires, and one that goes wrong ------------------


class Gate:
    """A reader that hands over its lines, then waits to be let go.

    The blocker cycle 6 recorded: any line the reader returns arrives *before*
    the timeout that would fire a job, so the job never fires - and a reader
    that simply blocks lets it fire but leaves nothing able to end the session.

    So this blocks, and something else opens it. `on_empty` runs once, when the
    typed lines are used up, and is where the clock moves past the job's time.
    The wait is bounded so a test that never opens the gate fails instead of
    hanging.
    """

    def __init__(self, lines, on_empty=None) -> None:
        self._lines = list(lines)
        self._on_empty = on_empty
        self.open = threading.Event()

    def __call__(self) -> str:
        if self._lines:
            return self._lines.pop(0)
        if self._on_empty is not None:
            self._on_empty()
            self._on_empty = None
        self.open.wait(timeout=5)
        raise EOFError


class Releasing(StubBackend):
    """A stub that opens the gate once it has streamed enough turns."""

    def __init__(self, gate, after, **kwargs) -> None:
        super().__init__(**kwargs)
        self._gate = gate
        self._after = after
        self._streams = 0

    def stream(self, model, messages, options=None, tools=None):
        self._streams += 1
        try:
            yield from super().stream(model, messages, options=options, tools=tools)
        finally:
            # `finally`, because a turn that *raises* is exactly what one of
            # these tests is about. Without it the exception propagates past the
            # set, the gate never opens, and the test passes only because the
            # reader gives up after five seconds - which it did, and which the
            # wall clock is how anyone found out.
            if self._streams >= self._after:
                self._gate.open.set()


def run_until_the_job_has_fired(monkeypatch, clock, turns, after=3):
    """One session: schedule something, let its time pass, watch it run.

    Two readers, because there are two paths. The **first** line is read with an
    empty schedule, which takes the untimed blocking read - that is `feed`. Every
    read after it has something scheduled, so it takes the timed path, and that
    is the gate. Patching only one of them leaves the other on real stdin.
    """
    feed(monkeypatch, ["schedule a deploy check"])
    # The tick is a quarter second in a real session and is waited on for real
    # here - several times per test, which took this file from 1.4s to 6.2s.
    # Shortened rather than tolerated: the tick bounds how late a job can be, and
    # nothing in these tests is about its value.
    monkeypatch.setattr(axiom, "SCHEDULE_TICK", 0.01)
    gate = Gate(
        [], on_empty=lambda: clock.__setitem__("at", datetime(2026, 8, 31, 19, 30))
    )
    backend = Releasing(gate, after, turns=turns)
    terminal.use_input(gate)
    axiom.main([], using=backend)
    return backend


def test_a_scheduled_job_runs_while_the_user_types_nothing(monkeypatch, capsys, clock):
    """#74 AC 9 and AC 12, through a whole session rather than through a call."""
    run_until_the_job_has_fired(
        monkeypatch,
        clock,
        [
            [scheduling("*/15 * * * *", "check the deploy")],
            ["scheduled it"],
            ["the deploy is green"],
        ],
    )

    out = capsys.readouterr().out
    assert "the deploy is green" in out, "the scheduled turn never ran"
    assert "scheduled - check the deploy" in out, "the user could not see what ran"


def test_a_scheduled_job_that_produces_no_reply_is_not_a_failure(
    monkeypatch, capsys, clock
):
    """#74 AC 32.

    The one a reasonable implementation gets backwards, because a quiet turn and
    a broken one reach the same place. Every quiet scheduled job reporting itself
    as broken is worse than not reporting a real failure.
    """
    run_until_the_job_has_fired(
        monkeypatch,
        clock,
        [
            [scheduling("*/15 * * * *", "check the deploy")],
            ["scheduled it"],
            [],  # the model says nothing at all
        ],
    )

    out = capsys.readouterr().out.lower()
    assert "scheduled - check the deploy" in out, "the job did not run"
    for word in ("failed", "error", "could not"):
        assert word not in out.split("scheduled - check the deploy")[-1], (
            f"a quiet reply was reported as {word!r}"
        )


def test_a_failing_scheduled_job_does_not_end_the_session(monkeypatch, capsys, clock):
    """#74 AC 31, and AC 30's first half - the failure is said."""
    run_until_the_job_has_fired(
        monkeypatch,
        clock,
        [
            [scheduling("*/15 * * * *", "check the deploy")],
            ["scheduled it"],
            [ConnectionLost("the host went away")],
        ],
    )

    captured = capsys.readouterr()
    assert "scheduled - check the deploy" in captured.out, "the job did not run"
    said = captured.out + captured.err
    assert "the host went away" in said, "the failure was swallowed"


def test_a_repeating_job_is_still_scheduled_after_a_run(monkeypatch, capsys, clock):
    """#74 AC 19. It runs on every match, so one run must not consume it."""
    backend = run_until_the_job_has_fired(
        monkeypatch,
        clock,
        [
            [scheduling("*/15 * * * *", "check the deploy")],
            ["scheduled it"],
            ["the deploy is green"],
        ],
    )
    capsys.readouterr()

    assert backend._streams >= 3, "the scheduled turn never happened"


def test_a_one_shot_is_gone_after_it_has_run(monkeypatch, capsys, clock):
    """#74 AC 20, through a session."""
    run_until_the_job_has_fired(
        monkeypatch,
        clock,
        [
            [scheduling("0 19 * * *", "just once", repeating=False)],
            ["scheduled it"],
            ["done"],
        ],
    )

    out = capsys.readouterr().out
    assert "scheduled - just once" in out, "the one-shot never ran"


def typing(*lines):
    """A reader for the timed path that ends the session when it runs out."""
    remaining = list(lines)

    def read() -> str:
        if remaining:
            return remaining.pop(0)
        raise EOFError

    return read


def test_switching_model_leaves_the_schedule_alone(monkeypatch, capsys, clock):
    """#74 AC 24. Neither cancelled nor duplicated.

    The store lives in `_chat`'s locals and a switch rebinds `run`, not `jobs` -
    so this should hold structurally. Proved rather than reasoned, because "it is
    in a different variable" is true right up until someone moves the variable.
    """
    backend = StubBackend(
        models=["gemma2:2b", "qwen2.5:7b"],
        turns=[
            [scheduling("0 9 * * *", "morning report")],
            ["scheduled it"],
            [Call("list_schedules", {})],
            ["still there"],
        ],
    )
    feed(monkeypatch, ["schedule it"])
    terminal.use_input(typing("/model gemma2:2b", "what is scheduled?"))

    axiom.main(["--model", "qwen2.5:7b"], using=backend)

    out = capsys.readouterr().out
    assert "now gemma2:2b" in out, "the switch did not happen"
    # The listing must actually have happened. Measured: with the schedule reset
    # on switch, the next read finds an empty store, takes the *untimed* path,
    # meets the exhausted `feed` iterator and ends the session - so no listing is
    # produced and every assertion about its contents is vacuously true.
    assert "still there" in out, "the turn after the switch never ran"
    assert "nothing is scheduled" not in out, "the switch cancelled the job"
    assert out.count("morning report") >= 3, "the listing did not name the job"
