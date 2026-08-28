# Cycle 6 — 2026-08-28 20:24 +0530

Whole-session tests. Four added, one of them vacuous until the break said so, and one
end-to-end test abandoned for a reason worth recording.

## The clock had to be injectable one level up

`_chat` builds its own `schedule.Schedule()` with the real clock, so **no end-to-end test
could make a job come due.** That is cycle 1's lesson - the clock must be injectable - applied
one level higher, and it was not visible until a test needed it.

Solved on the test side rather than by giving `main` an argument it does not need: the
factory is patched, so the production path is exactly what it was and the seam is the one
place that builds the store.

## A test that was vacuous, and the break that said so

`test_the_schedule_survives_a_second_turn` asserted that "morning report" appeared *after*
the line `what is scheduled?` in the output. Moving the store inside the loop - so every turn
forgets every job - **left all four tests green**.

The reason: `feed` prints the prompt and not the line the user typed, so `what is scheduled?`
is never in the output at all. `split` on a string that is not there returns the whole
output, and the assertion matched the first turn's echo.

Two tells, and the second was louder than the first. The break reddened nothing; and the file
went from **1.39s to 0.08s**, because an always-empty schedule never reaches the timed path
and never waits 0.25s for anything. A seventeen-fold speed-up is not a test getting faster,
it is a test doing less.

Rewritten to assert on what the second turn actually produces - `nothing is scheduled` absent,
and the prompt said twice. The break now reddens it.

That is the second time in this loop a wall-clock number found something a failing test did
not. Cycle 5 found a spinning thread the same way.

## The end-to-end fire test was abandoned, deliberately

A test that schedules a job, advances the clock, and watches it fire through `main` does not
fit the harness, and forcing it would have produced something fragile.

The session can only end when the reader returns a line or raises. But **any line the reader
returns arrives before the timeout that would fire the job** - the queue hands it over
immediately, so `_next_line` returns it rather than looking at the clock. A reader that blocks
instead lets the job fire, and then nothing can ever end the session.

Every way out of that needs either a sleep, a thread the test coordinates with the backend, or
a change to production code to make a test terminate. None of those is worth it: AC 9, 10, 11
and 13 are already proved at `_next_line`, which is the only place a job can enter the loop.

Recorded rather than left as an unexplained gap.

## What was added

- **AC 1** - a run with nothing scheduled says nothing about schedules. End-to-end.
- **A session that schedules nothing never starts a reader thread.** This is what makes the
  tick free, and it was asserted rather than assumed for the first time.
- **AC 24's provable half** - the schedule survives a second turn.
- **AC 30's structural half** - `_next_line` calls `mark_run` *before* handing the prompt
  back, so a job is at its next time before its turn starts. There is no path where a failed
  run leaves a job stuck on a time that has passed.

## Criteria — 30 of 33

**New: 2** - AC 1, AC 24. Plus AC 30 in part.

**Not started: 3** - AC 19 and AC 20 through a whole session (both hold in the store), and
AC 31/32 - a job whose run fails, and an empty reply that is not a failure. Both need a stub
backend that errors on a *scheduled* turn, which is the end-to-end shape just recorded as not
fitting the harness. They may need the harness changed rather than the test written.

## Suite

`uv run pytest` - **699 passed in 75.10s**. Baseline 695; 4 added.

## Assumptions

None changed.
