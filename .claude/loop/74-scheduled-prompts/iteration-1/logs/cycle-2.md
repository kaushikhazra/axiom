# Cycle 2 — 2026-08-28 19:28 +0530

Built the input seam and proved it. **Did not wire it into `_chat`** - the reason is below
and it is the constraint cycle 3 starts from.

## What was built

`terminal.Typed` - the user's lines read on a thread and handed over a queue - and
`read_line(timeout=None)`.

**The extension is backward compatible by construction.** With no timeout, `read_line` is
byte for byte what it was: a blocking `input()` on the calling thread. Every existing caller
and all 642 existing tests take that path and cannot tell the other one exists. Only a
caller that asks for a timeout gets the thread, and the thread is not started until the
first timed read - so a session that never schedules anything never starts one.

Three return values, which is the whole design:

| | meaning |
|---|---|
| a string | the user typed a line |
| `None` | the user is leaving - Ctrl-C or Ctrl-D, exactly as before |
| `WAITING` | the timeout ran out; the caller may look at the clock and come back |

**`WAITING` exists because `None` was already taken.** A timeout that returned `None` would
mean a quiet moment ends the session. That is not hypothetical - it is one of the two breaks
run below, and it reddens exactly the tests that name it.

## Why AC 10 and AC 11 still hold for free

The thread only ever *reads*. Turn execution stays on the main thread, so there is still one
place that runs a turn and it still runs one at a time. Nothing was made concurrent that was
not concurrent before, which is why neither criterion needs a lock to defend it.

## The breaks

Two, each precise, each reddening a different pair:

- **`put("")` instead of `put(None)` on EOF** - leaving no longer says so. Reddens both
  `test_leaving_still_comes_back_as_none` cases and nothing else. This is the regression
  `action.md` named as costing more than the feature is worth: a user who cannot exit axiom.
- **`return None` instead of `WAITING` on timeout** - a quiet moment looks like leaving.
  Reddens `test_nothing_typed_gives_waiting_rather_than_a_line` and
  `test_waiting_then_a_line_still_gives_the_line`, and nothing else.

Ten of twelve pass under each break, and the two that fail are the two that should. No
vacuous tests found this cycle - unlike loop 73's cycle 2, where three of eleven were.

## Why `_chat` was not wired — the constraint for cycle 3

Building the seam surfaced a problem that reading the loop did not.

**The prompt is printed by whoever performs the read**, and that is now the thread. It
prints `> ` and blocks. When a job fires, the thread is still sitting in `input()` with the
prompt already on the screen - so the job's turn would be drawn *underneath a prompt that is
still waiting for input*, and the user would be looking at their own live prompt above a
reply they did not ask for.

That is not a corruption and nothing is lost, but it is #60 AC 17 and AC 29 territory: what
axiom prints that is not the model's reply must say what it says today, and a scheduled turn
must be distinguishable from a typed one (#74 AC 13). Wiring the dispatch before deciding
how the prompt is drawn would put a visible mess in the main loop and make AC 13 harder to
satisfy afterwards, not easier.

Three ways it could go, none chosen yet - cycle 3 decides with a measurement rather than a
preference:

| | approach |
|---|---|
| a | the main loop prints the prompt, the thread only reads - needs the loop to know when a prompt is already on screen |
| b | the thread prints it, and a firing job erases the prompt line first and re-prints it after the turn |
| c | the prompt moves to after the timeout loop entirely, so it is drawn once per idle period rather than once per read |

## Criteria

**Met, with a test shown to fail when broken: 6 of 33** - unchanged. AC 25, 26, 28, 29, 22,
23. The seam is not itself a criterion; it is what AC 9, 10 and 11 need in order to be
testable at all.

**Not started: 22.** AC 27 still not started and still known to be harder than it looks.

## Suite

`uv run pytest` - **654 passed in 74.97s**. Baseline on this branch was 642; 12 added. The
seam's own tests run in **0.23s** and use millisecond timeouts. Nothing waits on a schedule.

## Assumptions

None changed. The reader-thread approach recorded in cycle 1 held up; what cycle 1 could not
see from reading was that the *prompt* travels with the read, which is now the open question.
