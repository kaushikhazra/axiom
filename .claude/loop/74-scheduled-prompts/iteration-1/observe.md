# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 74` — before the diff and before
the previous cycle's log. Attack each criterion; do not confirm it. Twelve loops have found
something real by reading the criteria cold, and nothing by re-reading the diff.

## The measurement

The number this loop moves is **criteria demonstrably met, out of 33.** Demonstrably means
a test that fails when the behaviour is removed. Not "the code appears to do this."

Time is the hard part and the place this will go wrong. **No test may sleep to wait for a
schedule.** A clock the test controls is the only way this suite stays fast and hermetic —
if a cycle finds itself adding `time.sleep`, that is the signal the clock is not injectable
yet, and that is the thing to fix before any more criteria.

Every cycle, run and record:

    uv run pytest

## Every cycle, record

- **Criteria met, out of 33**, listed by number. Three buckets: met with a test that has
  been shown to fail when broken; implemented but not proved; not started. Only the first
  bucket counts toward the number.
- How far the number moved from last cycle, and what moved it.
- `uv run pytest` — count, pass, fail, and **wall-clock time for the whole suite**. A suite
  that slows down is a test that waited on real time.
- Any assumption that changed.

## The three that will be got wrong

Watch these specifically, every cycle, because each is easy to claim and hard to hold:

- **AC 10 and AC 11 — a job never interrupts a turn.** Prove a job whose time passes
  mid-turn runs *after* the turn, not during it, and that a second job waits for the first.
- **AC 22 and AC 23 — nothing on disk, nothing survives.** Prove it by looking for files, not
  by not writing any. `.axiom/` already exists for other reasons and is where a careless fix
  would land.
- **AC 13 — a scheduled turn is distinguishable from a typed one.** #60 AC 17 and AC 18
  already govern how axiom's voice and a tool's output stay apart from the model's words.
  Whatever marks a scheduled turn has to sit inside that, not invent a fourth voice.

## Before claiming a criterion met

**Break it and watch the test go red.** #60 shipped five breaks that broke nothing and six
tests that passed for a reason other than the one they claimed. A break that turns no test
red means the test is vacuous — say so in the log and replace it.

## Goal check

- **Met** — all 33 criteria are in the first bucket, the suite is green and hermetic, and no
  test sleeps. The loop ends: delete the cron and say so.
- **Not met** — report and write the next action.
- **Did not move** — criteria met is the same as last cycle's. Report the flat result and
  stop. Do not try another variant.
