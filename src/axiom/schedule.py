"""Prompts waiting for their time to come.

The store and nothing else: what is scheduled, what is due, what to forget. It
does not run anything, does not print, and does not know a model exists - the
chat loop asks it what is due and decides what to do about that.

**The clock is supplied, never taken.** Every criterion in #74 is about time, and
a store that can only ask the real clock makes all of them untestable without
sleeping. A suite that sleeps is a suite nobody runs, so the clock arrives as a
callable and the tests hand it a fake one.

Nothing here reaches a disk. A schedule lives as long as the session does, which
is #74 AC 22 and AC 23, and is a property of this module holding the only copy.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Callable

from croniter import croniter

# Five fields, because that is what the user is promised and what a minute is
# the floor of. `croniter.is_valid` accepts six - the sixth being seconds - so
# it cannot be the whole check: a six-field expression is both "not a five-field
# expression" (AC 25) and a schedule finer than once a minute (AC 29). One guard
# answers both criteria, which is why they are not separate code.
FIELDS = 5

# How long a repeating job lives before it is retired (#74 AC 21). It runs one
# final time at the end of this and is then removed.
#
# A bound rather than forever, because a schedule nobody remembers making is a
# session that never settles - and because the user is told this number when
# they schedule one, so it has to be a number rather than a policy.
LIFETIME_DAYS = 7


# How far away a resolved time has to be before it reads as "you named a moment
# that has gone" rather than "you named one that is nearly here".
#
# Measured, not picked. A cron expression has no year field, so `0 9 28 8 *`
# asked at 18:47 on 28 August names 09:00 on 28 August *next year* - 364 days
# out - and that is croniter being right rather than wrong. The only case where a
# past-looking one-shot is genuinely imminent is across a year boundary: `0 9 1 1 *`
# asked on 31 December resolves **one day** out. 300 separates the two with room
# either side, and no value can separate them on distance alone - a legitimate
# leap-day job asked in August resolves 549 days out, and one asked on 1 March
# 2024 resolves 1460.
LOOKS_LIKE_A_YEAR = 300


def _already_gone(expression: str, next_run: datetime, now: datetime) -> bool:
    """Whether a one-shot names a moment that has already passed (#74 AC 27).

    Not answerable from what croniter returns, which is why this exists. croniter
    never returns a past time - it returns the next match - so "gone" and "a year
    out" are the same answer, and a leap-day job is further away than either.

    So the *pinned fields* are read instead. A one-shot that names a minute, an
    hour, a day and a month names one moment in a year; if that moment exists in
    this year, has passed, and the next match is a year away, the user named a
    time that is gone.

    All three conditions are needed. Without the first, 29 February in a
    non-leap year looks past when it simply does not exist. Without the third,
    `0 9 1 1 *` asked on 31 December is refused for naming a time eight hours
    from now.
    """
    fields = expression.split()
    if len(fields) != FIELDS:
        return False
    minute, hour, day, month, _weekday = fields
    if not all(field.isdigit() for field in (minute, hour, day, month)):
        return False  # not one moment: a range or a step names many
    try:
        named = now.replace(
            month=int(month),
            day=int(day),
            hour=int(hour),
            minute=int(minute),
            second=0,
            microsecond=0,
        )
    except ValueError:
        return False  # 29 February in a year that has none
    return named < now and (next_run - now).days > LOOKS_LIKE_A_YEAR


class Invalid(ValueError):
    """A schedule or prompt that will not do, with the reason the user needs."""


@dataclass(frozen=True)
class Job:
    """One prompt and the times it will run at."""

    id: str
    cron: str
    prompt: str
    recurring: bool
    created: datetime
    next_run: datetime


def _checked(cron: str, prompt: str) -> str:
    """The schedule, if it is one, and the prompt, if there is one.

    Refusals name what was wrong rather than that something was: the user is
    about to retype it, and "invalid" tells them nothing they did not know.
    """
    if not prompt or not prompt.strip():
        raise Invalid("a scheduled prompt cannot be empty")
    expression = cron.strip()
    count = len(expression.split())
    if count != FIELDS:
        raise Invalid(
            "a schedule has five fields - minute hour day-of-month month "
            f"day-of-week - and this has {count}"
        )
    if not croniter.is_valid(expression):
        raise Invalid(f"{expression!r} is not a schedule croniter understands")
    return expression


class Schedule:
    """Every job this session is holding.

    In memory, and only here. Nothing is written anywhere, so leaving takes the
    schedule with it - which is the promise, not an omission.
    """

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or datetime.now
        self._jobs: dict[str, Job] = {}

    # --- what is scheduled -------------------------------------------------

    def add(self, cron: str, prompt: str, recurring: bool = True) -> Job:
        """Take a job, or say why it cannot be taken.

        The first fire time is computed from the supplied clock rather than from
        the real one, so a test can schedule the past, the future, or a leap day
        without waiting for any of them.

        The identifier only has to be unique, not unguessable - nothing is
        authorised by holding one - so `uuid4` is the right amount of machinery
        and a random-secret generator would be the wrong kind of promise.
        """
        expression = _checked(cron, prompt)
        now = self._clock()
        next_run = croniter(expression, now).get_next(datetime)
        # AC 27, and only for a one-shot: a repeating job named for a time that
        # has passed today is simply a job that starts tomorrow, which is what
        # the user asked for.
        if not recurring and _already_gone(expression, next_run, now):
            raise Invalid(
                f"{expression!r} names {next_run:%H:%M on %d %B}, which has "
                f"already passed - the next one is {next_run:%Y-%m-%d}"
            )
        job = Job(
            id=uuid.uuid4().hex[:8],
            cron=expression,
            prompt=prompt.strip(),
            recurring=recurring,
            created=now,
            next_run=next_run,
        )
        self._jobs[job.id] = job
        return job

    def jobs(self) -> tuple[Job, ...]:
        """Everything scheduled, soonest first, so a listing reads as a queue."""
        return tuple(sorted(self._jobs.values(), key=lambda job: job.next_run))

    def cancel(self, job_id: str) -> Job | None:
        """Forget a job, or `None` if there was no such job to forget.

        `None` rather than an exception: AC 17 wants the user told and nothing
        changed, and a caller that has to catch an error to print a sentence is
        the harder thing to get right.
        """
        return self._jobs.pop(job_id, None)

    # --- what is due -------------------------------------------------------

    def due(self, now: datetime | None = None) -> tuple[Job, ...]:
        """Jobs whose time has come, oldest due first.

        Ordered by when they *became* due rather than by when they were made, so
        a job that has been waiting goes before one that just came up. Which
        matters for AC 11: two jobs due at once run in a defined order rather
        than whichever the dictionary happened to hold first.
        """
        moment = now if now is not None else self._clock()
        return tuple(
            sorted(
                (job for job in self._jobs.values() if job.next_run <= moment),
                key=lambda job: job.next_run,
            )
        )

    def mark_run(self, job_id: str, now: datetime | None = None) -> Job | None:
        """Record that a job has run: move it on, or drop it.

        A one-shot is gone the moment it has run, which is AC 20. A recurring
        job gets its next time computed from **now** rather than from the time
        it was due - a session that was busy through three fire times owes the
        user one run, not three, and computing from the due time would queue the
        backlog it just missed.

        Returns the job as it now stands, or `None` if it has been dropped or
        was never here.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if not job.recurring:
            del self._jobs[job_id]
            return None
        moment = now if now is not None else self._clock()
        # AC 21: seven days old, so this run was its last. Checked *after* the
        # run rather than before it, because the criterion is that it runs one
        # final time and is then removed - not that it is removed instead.
        if moment - job.created >= timedelta(days=LIFETIME_DAYS):
            del self._jobs[job_id]
            return None
        moved = replace(job, next_run=croniter(job.cron, moment).get_next(datetime))
        self._jobs[job_id] = moved
        return moved

    # --- housekeeping ------------------------------------------------------

    def __len__(self) -> int:
        return len(self._jobs)
