"""The three tools, and what the user is told by them.

Everything here goes through `tools.run`, not through the functions directly -
the injection and the argument refusal are part of what is being tested, and
calling the function would skip both.
"""

from datetime import datetime, timedelta

import pytest

from axiom import schedule, tools

MONDAY = datetime(2026, 8, 31, 18, 47)


def store(now: datetime = MONDAY) -> schedule.Schedule:
    return schedule.Schedule(clock=lambda: now)


def call(name: str, jobs=None, **arguments) -> str:
    return tools.run(name, arguments, jobs=jobs)


# --- scheduling -----------------------------------------------------------


def test_scheduling_says_what_was_taken_and_when_it_next_runs():
    """#74 AC 3 and AC 5."""
    jobs = store()

    said = call("schedule_prompt", jobs, cron="0 9 * * *", prompt="morning report")

    assert "morning report" in said
    assert "0 9 * * *" in said
    assert "2026-09-01 09:00 local" in said, said
    assert jobs.jobs()[0].id in said, "the user was given nothing to cancel with"


def test_a_one_shot_says_it_runs_once():
    """#74 AC 4."""
    said = call(
        "schedule_prompt",
        store(),
        cron="0 9 * * *",
        prompt="just once",
        repeating=False,
    )

    assert "once" in said
    assert "repeating" not in said


def test_the_first_job_says_schedules_do_not_outlive_the_session():
    """#74 AC 7, and only the first - it is a fact about the session."""
    jobs = store()

    first = call("schedule_prompt", jobs, cron="0 9 * * *", prompt="one")
    second = call("schedule_prompt", jobs, cron="0 9 * * *", prompt="two")

    assert "last only as long as this session" in first
    assert "last only as long as this session" not in second, "said twice"


def test_a_repeating_job_says_it_stops_after_seven_days():
    """#74 AC 8."""
    said = call("schedule_prompt", store(), cron="0 9 * * *", prompt="over and over")

    assert "seven" in said or "7 days" in said, said


def test_a_one_shot_does_not_mention_seven_days():
    """It does not stop after seven days; it stops after one run."""
    said = call(
        "schedule_prompt", store(), cron="0 9 * * *", prompt="once", repeating=False
    )

    assert "7 days" not in said


@pytest.mark.parametrize(
    "cron, prompt", [("nonsense", "something"), ("* * * * * *", "x"), ("0 9 * * *", "")]
)
def test_a_job_that_cannot_be_taken_says_why(cron, prompt):
    """#74 AC 25, AC 26, AC 29, through the tool rather than the store."""
    jobs = store()

    said = call("schedule_prompt", jobs, cron=cron, prompt=prompt)

    assert said.startswith("error:")
    assert len(jobs) == 0, "a refused job was held anyway"


# --- listing --------------------------------------------------------------


def test_listing_nothing_says_so():
    """#74 AC 15. Not an empty string, which reads as a failure."""
    assert call("list_schedules", store()) == "nothing is scheduled"


def test_listing_shows_everything_the_user_needs_to_act():
    """#74 AC 14."""
    jobs = store()
    call("schedule_prompt", jobs, cron="0 9 * * *", prompt="morning")
    call("schedule_prompt", jobs, cron="*/15 * * * *", prompt="often")

    listed = call("list_schedules", jobs)

    for job in jobs.jobs():
        assert job.id in listed
        assert job.prompt in listed
        assert job.cron in listed
    assert "repeating" in listed
    assert "next at" in listed


def test_listing_puts_the_soonest_first():
    """#74 AC 14. A listing that reads as a queue."""
    jobs = store()
    call("schedule_prompt", jobs, cron="0 9 * * *", prompt="later")
    call("schedule_prompt", jobs, cron="*/15 * * * *", prompt="sooner")

    listed = call("list_schedules", jobs)

    assert listed.index("sooner") < listed.index("later")


# --- cancelling -----------------------------------------------------------


def test_cancelling_removes_the_job_and_says_so():
    """#74 AC 16 and AC 18."""
    jobs = store()
    call("schedule_prompt", jobs, cron="*/15 * * * *", prompt="check the deploy")
    identifier = jobs.jobs()[0].id

    said = call("cancel_schedule", jobs, identifier=identifier)

    assert identifier in said
    assert "cancelled" in said
    assert len(jobs) == 0
    assert jobs.due(datetime(2027, 1, 1)) == (), "it still came due after cancelling"


def test_cancelling_something_that_is_not_there_says_so_and_changes_nothing():
    """#74 AC 17."""
    jobs = store()
    call("schedule_prompt", jobs, cron="*/15 * * * *", prompt="keep me")

    said = call("cancel_schedule", jobs, identifier="nosuchid")

    assert said.startswith("error:")
    assert "nosuchid" in said
    assert len(jobs) == 1, "an unrelated job was removed"


# --- seven days -----------------------------------------------------------


def test_a_repeating_job_runs_one_final_time_after_seven_days():
    """#74 AC 21. One final run, then gone - not gone instead of running."""
    jobs = store()
    job = jobs.add("0 9 * * *", "over and over")
    week_later = MONDAY + timedelta(days=schedule.LIFETIME_DAYS)

    assert jobs.due(week_later), "it was not due for its final run"
    assert jobs.mark_run(job.id, week_later) is None
    assert len(jobs) == 0


def test_a_repeating_job_survives_six_days():
    """The bound is seven, and a test that only checks 'eventually' is no bound."""
    jobs = store()
    job = jobs.add("0 9 * * *", "over and over")

    moved = jobs.mark_run(job.id, MONDAY + timedelta(days=6))

    assert moved is not None
    assert len(jobs) == 1


# --- what the model cannot reach -----------------------------------------


def test_a_model_cannot_hand_itself_the_schedule():
    """`jobs` is the session's. `run` refuses any argument a tool did not declare."""
    jobs = store()

    said = tools.run(
        "schedule_prompt",
        {"cron": "0 9 * * *", "prompt": "x", "jobs": "mine now"},
        jobs=jobs,
    )

    assert said.startswith("error:")
    assert "does not take jobs" in said


def test_the_scheduling_tools_are_offered_to_the_model():
    """They are useless if the model is never told they exist."""
    offered = {tool["function"]["name"] for tool in tools.declarations()}

    assert {"schedule_prompt", "list_schedules", "cancel_schedule"} <= offered


def test_a_session_without_a_schedule_says_so_rather_than_failing():
    """A tool that cannot do its job returns a failure; it does not raise."""
    said = call("schedule_prompt", None, cron="0 9 * * *", prompt="x")

    assert said.startswith("error:")
