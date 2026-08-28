# Action

Twenty-five of thirty-three. The remaining eight split into three groups, and one of them is
the hard one this loop has been deferring since cycle 1.

1. **AC 27, and it is time.** A one-shot whose time has already passed must be refused.
   croniter cannot help: `0 9 28 8 *` asked at 18:47 on 28 August resolves to **2027**, so
   "already gone" and "a year out" are the same answer. The store has to reason about the
   *pinned fields* against now - a one-shot pins minute, hour, day-of-month and month, so if
   the resolved time is more than a year minus a day away, the user named a moment that has
   passed. **Measure that boundary before coding it**, at a leap day and at 31 December, or
   it will be right for August and wrong twice a year.
2. **AC 19, AC 20 and AC 24 through a whole session**, not through the store. A repeating job
   runs on every match; a one-shot runs once and is gone; a `/model` switch leaves jobs alone,
   neither cancelled nor duplicated. `terminal.use_input` exists now, so an end-to-end test
   through `main` is possible - that was cycle 3's blocker and it is cleared.
3. **AC 1, AC 30, AC 31, AC 32, AC 33** - a run with nothing scheduled says nothing about
   schedules; a job whose run fails says so, leaves the session usable, and still runs next
   time; a failing job never ends the session; a job that produces no reply is not a failure;
   exiting with jobs scheduled exits immediately with the same status code as exiting with
   none.
4. **Re-establish green between every revert and the next break.** This cycle lost a break's
   result to a stripped import: the formatter removed `timedelta` while a break made it
   unused, and the next break's reddening was two-thirds stale failures. Do not trust the
   previous run's baseline.
5. `uv run pytest` - 683 on this branch, green.

First thing to tackle: **AC 27's boundary, measured at a leap day and at the end of a year
before any code is written.** It is the one remaining criterion whose implementation could be
plausibly wrong and still look right, because August is the month it will be tested in.
