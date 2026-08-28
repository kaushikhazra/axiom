# Cycle 7 — 2026-08-28 20:41 +0530 — GOAL MET

The releasable reader, and the four criteria behind it. **33 of 33.**

## The seam, and it cost no production code

`action.md` said: one seam in `tests/`, no sleep, no test-only argument to `main`, and stop
if it needs production code changed. It did not.

Two pieces, both test-side:

- **`Gate`** - a reader that hands over its lines and then *blocks*, with a bounded wait so a
  test that never opens it fails rather than hangs.
- **`Releasing`** - a `StubBackend` that opens the gate once it has streamed enough turns.

That resolves the deadlock cycle 6 recorded exactly: the reader blocks so the timeout can
fire the job, and the *backend* - which is the only thing that runs while `main` has the
main thread - lets it go afterwards.

One thing the first attempt got wrong: **the first line is read with an empty schedule**, so
it takes the untimed blocking path and never touches `Gate` at all. Patching only one of the
two readers left the other on real stdin, which pytest refuses. Both are patched now, and the
helper says why.

## Three tests were wrong. The wall clock found two of them.

**One.** `test_a_failing_scheduled_job_does_not_end_the_session` took **exactly 5.00 seconds**
while every other test took 0.03. The failing turn raises through `yield from`, so the
exception propagated past the `set()` and **the gate never opened** - the test passed only
because the reader gave up after five seconds. Fixed with `finally`. **5.23s to 0.25s.**

**Two.** Shortening `SCHEDULE_TICK` from 0.25 to 0.01 moved the file from 6.20s to 5.89s -
*almost nothing*. That non-result is what said the tick was not the cost and sent me looking
for the one test that was.

**Three.** `test_switching_model_leaves_the_schedule_alone` passed with the schedule reset on
every switch. The reason took finding: **with the schedule emptied, the next read takes the
untimed path**, meets the exhausted `feed` iterator, and ends the session - so no listing is
ever produced and every assertion about its contents is vacuously true. It now asserts the
turn after the switch actually ran.

That is the third vacuous test in this loop, and the second whose cause was the session
ending earlier than the test assumed. **A test that ends the session early passes everything
it was going to assert afterwards**, and nothing about that is visible in a green run.

## Criteria — 33 of 33

Every criterion in #74 holds, each with a test shown to fail when the thing it guards is
removed - except the small number that are regression guards for properties true either way,
which are recorded as such in earlier logs.

New this cycle: **AC 19, AC 20, AC 31, AC 32**, and AC 24 completed - the earlier version
proved a job survives a second *turn*, not a *switch*, and the criterion says switch.

AC 32 was the one `action.md` singled out as the one a reasonable implementation gets
backwards, and it holds: a scheduled turn that produces no reply says nothing about failure.
It holds by absence rather than by code, which is the right way for it to hold.

## Suite

`uv run pytest` - **705 passed in 74.47s**. Baseline 699; 6 added. The session tests run in
**0.26s**.

## Goal check: MET

Every criterion in #74 holds against a running axiom. The suite is green and hermetic.
Nothing sleeps: the one wait left is a bounded gate that a correct run never reaches.

**The loop ends. The cron is deleted.**

Seven cycles: design the seam, build the store, wire the dispatch, add the tools, refuse a
time that has gone, drive it through a session, and unblock the last four.

## What a reader should know before touching this

- **The clock is injectable at two levels**, and both were discovered by needing them rather
  than by design: the store takes one, and `_chat` builds its own store, so a test patches the
  factory.
- **`SCHEDULE_TICK` is waited on for real.** It bounds how late a job can be, not how often
  anything is computed, and tests shorten it.
- **A scheduled turn is an ordinary turn.** There is one place a job enters the loop and one
  place a turn runs, which is why AC 10 and AC 11 needed no locking and no test could find an
  interleaving to complain about.
