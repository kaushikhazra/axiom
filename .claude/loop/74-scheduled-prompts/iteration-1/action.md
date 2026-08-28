# Action

Cycle 1 found the constraint: **`terminal.read_line()` is a blocking `input()`**, so a job
whose time arrives while the user sits at an idle prompt does not run until they press
enter. AC 9 is the hard criterion of this story, and until it holds, tools that schedule
work are decoration — nothing they schedule can fire.

So the idle point comes before the tools.

1. **Build the seam in `terminal.py`**, which is the only module allowed to touch the
   console. A reader thread puts typed lines on a queue; a new function waits on that queue
   with a timeout and returns either the line the user typed or nothing, so the caller can
   look at the clock and go round again. Approach (c) in cycle 1's table — do not re-derive
   the other three, they are ruled out there with reasons.
2. **Keep `read_line`'s contract exactly.** It returns `None` for "the user is leaving", and
   Ctrl-C and Ctrl-D both mean leave at an idle prompt. A queue-based read must still make
   both reach the caller as `None`, or leaving axiom breaks — and that is a worse regression
   than the feature is a gain.
3. **Wire the dispatch into `_chat`** in `src/axiom/__init__.py`, at the top of the loop:
   a due job's prompt takes the place of a typed line and goes through the same path, which
   is AC 9 and AC 12 together. Do not add a second turn-execution path — one turn is one
   pass of that loop, and that is what makes AC 10 and AC 11 hold without any locking.
4. **Test it with a controlled clock and a fake stdin. Nothing sleeps.** If a test needs to
   wait for real time, the seam is wrong — go back to step 1 rather than adding a sleep.
   Prove three things: a due job runs while the user types nothing; a job due mid-turn runs
   *after* the turn; two jobs due at once run in order, one after the other.
5. **Break each of those three and watch them go red.** Cycle 1 nearly accepted a break that
   reddened 17 tests as proof of one guard; it proved nothing about which test guarded what.
   Break precisely.
6. `uv run pytest` — 642 was the baseline, and the wall-clock time must not climb. A suite
   that slows down is a test that waited on real time.

Leave the three tools, listing, announcing, expiry and AC 27 alone this cycle. AC 27 in
particular is now known to be harder than it looks — croniter cannot express "in the past" —
and it deserves its own cycle rather than a corner of this one.

First thing to tackle: **the reader thread, with `read_line`'s leaving contract intact.**
Everything else in the story runs through that function, and breaking how a user exits
axiom would cost more than scheduling is worth.
