"""The schedule store, on a clock the test owns.

Every criterion in #74 is about time. Not one test here waits for any, and none
ever should - the day one sleeps, the suite stops being run.
"""

from datetime import datetime, timedelta

import pytest

from axiom import schedule

MONDAY_EVENING = datetime(2026, 8, 31, 18, 47)  # a Monday, deliberately


def at(moment: datetime):
    """A clock stuck at one instant, which the test moves by making a new one."""
    return lambda: moment


def store(moment: datetime = MONDAY_EVENING) -> schedule.Schedule:
    return schedule.Schedule(clock=at(moment))


# --- taking a job ---------------------------------------------------------


def test_a_scheduled_job_gets_an_identifier():
    """AC 5. The user is given something to cancel it with."""
    job = store().add("*/15 * * * *", "check the deploy")

    assert job.id
    assert job.prompt == "check the deploy"
    assert job.recurring is True


def test_the_first_fire_time_comes_from_the_supplied_clock():
    """The clock injection this whole module exists to keep testable."""
    job = store().add("*/15 * * * *", "check the deploy")

    assert job.next_run == datetime(2026, 8, 31, 19, 0)


def test_a_nine_am_job_runs_at_nine(mocked=None):
    """AC 6. Local time, with no conversion asked of anyone."""
    job = store().add("0 9 * * *", "morning report")

    assert job.next_run == datetime(2026, 9, 1, 9, 0)
    assert job.next_run.hour == 9


def test_the_same_prompt_twice_gives_two_jobs():
    """AC 28."""
    holding = store()
    first = holding.add("0 9 * * *", "same words")
    second = holding.add("0 9 * * *", "same words")

    assert first.id != second.id
    assert len(holding) == 2


# --- refusing one ---------------------------------------------------------


@pytest.mark.parametrize(
    "cron, because",
    [
        ("*/15 * * *", "four fields"),
        ("*/15 * * * * *", "six fields - a seconds field is finer than a minute"),
        ("", "nothing at all"),
    ],
)
def test_a_schedule_that_is_not_five_fields_is_refused(cron, because):
    """AC 25 and AC 29 - one guard, because a sixth field *is* the sub-minute case."""
    with pytest.raises(schedule.Invalid) as refused:
        store().add(cron, "something", recurring=True)

    assert "five fields" in str(refused.value), because


def test_a_schedule_of_the_right_shape_but_no_meaning_is_refused():
    """AC 25. Five fields is necessary and not sufficient."""
    with pytest.raises(schedule.Invalid) as refused:
        store().add("99 44 * * *", "something")

    assert "99 44 * * *" in str(refused.value)


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t "])
def test_an_empty_prompt_is_refused(prompt):
    """AC 26."""
    with pytest.raises(schedule.Invalid) as refused:
        store().add("0 9 * * *", prompt)

    assert "empty" in str(refused.value)


def test_a_refused_job_is_not_held():
    """A refusal changes nothing, or the count is a lie."""
    holding = store()
    with pytest.raises(schedule.Invalid):
        holding.add("nonsense", "something")

    assert len(holding) == 0


# --- listing --------------------------------------------------------------


def test_jobs_are_listed_soonest_first():
    """AC 14. A listing that reads as a queue."""
    holding = store()
    later = holding.add("0 9 * * *", "morning")
    sooner = holding.add("*/15 * * * *", "quarter hourly")

    assert [job.id for job in holding.jobs()] == [sooner.id, later.id]


def test_an_empty_store_lists_nothing():
    """AC 15's half that belongs here; the wording belongs to the terminal."""
    assert store().jobs() == ()
    assert len(store()) == 0


# --- cancelling -----------------------------------------------------------


def test_cancelling_removes_the_job():
    """AC 16 and AC 18. Nothing further runs from it."""
    holding = store()
    job = holding.add("*/15 * * * *", "check the deploy")

    assert holding.cancel(job.id) == job
    assert holding.jobs() == ()
    assert holding.due(datetime(2027, 1, 1)) == ()


def test_cancelling_something_that_is_not_there_changes_nothing():
    """AC 17."""
    holding = store()
    holding.add("*/15 * * * *", "check the deploy")

    assert holding.cancel("nosuchid") is None
    assert len(holding) == 1


# --- what is due ----------------------------------------------------------


def test_nothing_is_due_before_its_time():
    holding = store()
    holding.add("*/15 * * * *", "check the deploy")

    assert holding.due(datetime(2026, 8, 31, 18, 59)) == ()


def test_a_job_is_due_once_its_time_has_passed():
    holding = store()
    job = holding.add("*/15 * * * *", "check the deploy")

    assert [due.id for due in holding.due(datetime(2026, 8, 31, 19, 0))] == [job.id]


def test_two_jobs_due_at_once_come_back_oldest_due_first():
    """AC 11. A defined order, not whichever the dictionary held first."""
    holding = store()
    quarterly = holding.add("*/15 * * * *", "sooner")  # 19:00
    hourly = holding.add("0 * * * *", "later")  # 20:00

    due = holding.due(datetime(2026, 8, 31, 20, 30))

    assert [job.id for job in due] == [quarterly.id, hourly.id]


# --- having run -----------------------------------------------------------


def test_a_one_shot_is_gone_once_it_has_run():
    """AC 20."""
    holding = store()
    job = holding.add("0 9 * * *", "just once", recurring=False)

    assert holding.mark_run(job.id, datetime(2026, 9, 1, 9, 0)) is None
    assert holding.jobs() == ()


def test_a_repeating_job_moves_to_its_next_time():
    """AC 19."""
    holding = store()
    job = holding.add("*/15 * * * *", "over and over")

    moved = holding.mark_run(job.id, datetime(2026, 8, 31, 19, 0))

    assert moved is not None
    assert moved.next_run == datetime(2026, 8, 31, 19, 15)
    assert len(holding) == 1


def test_a_missed_backlog_owes_one_run_not_three():
    """A session busy through three fire times owes the user one run.

    Computed from now rather than from the time it was due, or the next three
    ticks each find it due again and the user gets the backlog they missed.
    """
    holding = store()
    job = holding.add("*/15 * * * *", "over and over")  # due 19:00

    moved = holding.mark_run(job.id, datetime(2026, 8, 31, 19, 44))

    assert moved.next_run == datetime(2026, 8, 31, 19, 45)
    assert holding.due(datetime(2026, 8, 31, 19, 44)) == ()


def test_marking_something_that_is_not_there_changes_nothing():
    holding = store()
    assert holding.mark_run("nosuchid") is None


# --- what it must never do ------------------------------------------------


def test_nothing_reaches_the_disk(tmp_path, monkeypatch):
    """AC 22. Proved by looking, not by having intended not to write."""
    monkeypatch.chdir(tmp_path)
    holding = store()
    job = holding.add("*/15 * * * *", "check the deploy")
    holding.mark_run(job.id, datetime(2026, 8, 31, 19, 0))
    holding.jobs()
    holding.cancel(job.id)

    assert list(tmp_path.iterdir()) == []


def test_a_new_store_starts_with_nothing():
    """AC 23. Leaving takes the schedule with it, because this is all there is."""
    holding = store()
    holding.add("*/15 * * * *", "check the deploy")

    assert len(schedule.Schedule(clock=at(MONDAY_EVENING))) == 0


# --- a one-shot that has already gone (#74 AC 27) ------------------------


AUGUST = datetime(2026, 8, 28, 18, 47)
NEW_YEARS_EVE = datetime(2026, 12, 31, 18, 47)


@pytest.mark.parametrize(
    "label, cron, now",
    [
        ("this morning", "0 9 28 8 *", AUGUST),
        ("this morning, on new year's eve", "0 9 31 12 *", NEW_YEARS_EVE),
        ("a leap day that has been and gone", "0 9 29 2 *", datetime(2024, 3, 1)),
    ],
)
def test_a_one_shot_that_has_already_passed_is_refused(label, cron, now):
    """#74 AC 27, and it is not answerable from what croniter returns.

    croniter never returns a past time - it returns the next match - so "gone"
    and "a year out" are the same answer. Measured: a genuinely-gone job resolves
    364 days out, and a *legitimate* leap-day job resolves 549 or 1460. The
    legitimate one is further away, so no distance threshold can separate them.
    """
    holding = schedule.Schedule(clock=at(now))

    with pytest.raises(schedule.Invalid) as refused:
        holding.add(cron, "too late", recurring=False)

    assert "already passed" in str(refused.value), label
    assert len(holding) == 0


@pytest.mark.parametrize(
    "label, cron, now",
    [
        ("later today", "0 21 28 8 *", AUGUST),
        ("tomorrow", "0 9 29 8 *", AUGUST),
        # The trap. Nine in the morning on 1 January, asked on 31 December, is
        # fourteen hours away - and this year's 1 January is eleven months gone.
        ("new year's day, asked on new year's eve", "0 9 1 1 *", NEW_YEARS_EVE),
        # 29 February does not exist in 2026, so it has not passed in 2026.
        ("a leap day that is still to come", "0 9 29 2 *", AUGUST),
        # Not one moment: a step names many, and the next is always soon.
        ("every fifteen minutes", "*/15 * * * *", AUGUST),
        ("every morning", "0 9 * * *", AUGUST),
    ],
)
def test_a_one_shot_still_to_come_is_taken(label, cron, now):
    """#74 AC 27's other side, which is the one a careless rule gets wrong."""
    holding = schedule.Schedule(clock=at(now))

    job = holding.add(cron, "in time", recurring=False)

    assert job.next_run > now, label
    assert len(holding) == 1


def test_a_repeating_job_named_for_a_time_today_that_has_passed_is_taken():
    """It is not a job that has been missed - it is one that starts tomorrow."""
    holding = schedule.Schedule(clock=at(AUGUST))

    job = holding.add("0 9 * * *", "every morning", recurring=True)

    assert job.next_run == datetime(2026, 8, 29, 9, 0)
