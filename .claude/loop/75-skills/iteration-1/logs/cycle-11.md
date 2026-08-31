# Cycle 11 — 2026-08-31, started 19:27 +0530

## Goal met. 44 of 44.

| bucket | count |
|---|---|
| met, break-proven | **44** |
| implemented, break not run | 0 |
| not started | 0 |

Verified rather than carried forward from the last cycle, as the action required:

    832 passed, 1 deselected in 78.93s     default suite, live excluded
    1/833 tests collected (832 deselected)  uv run pytest -m live

## AC 29 was a message, not a mechanism

The action asked first whether #42's oversized-turn path already refuses an oversized skill.
**It does** - `/skill` sets `line` to the instructions, so they become an oversized message
and `what_will_not_fit` returns `MESSAGE_TOO_LARGE`.

What it does not do is name the skill. "This message is about N tokens too large" sends a
user to look at what they typed, and they typed `/skill release-checklist` - nineteen
characters. The thing that is too large is the file behind it.

So AC 29 is a check at invocation using **the same arithmetic** as
`what_will_not_fit`'s message branch. A skill this let through and the oversized-turn check
then refused would be rejected twice, with two messages, one of them advising the user to
type less.

**The model's route needed it separately**, and that is the part #42 does not watch: an
oversized skill arrives as a *tool result*, is appended, and the turn is cut by Ollama with
the model answering from a fragment. Same failure #42 exists to prevent, reached by a door
it does not cover.

## The last five breaks

| break | its own test red |
|---|---|
| files beside `SKILL.md` loaded into the instructions | AC 25 |
| `write` puts the file where the next run will not read it | AC 31 |
| `delete` leaves the file on disk | AC 32 |
| a loaded skill changes the exit path | AC 44 |
| an oversized skill is sent anyway | AC 29 |

AC 31's break took six tests and AC 44's took twenty-six. Both are foundation breaks, like
AC 36's in cycle 7: everything that writes a skill fails when writing is broken, and
everything that runs a session fails when leaving one is. **Each landed on its own claim as
well**, which is the test that matters.

## AC 44's test was strengthened before it could be broken

It drove three exits and asserted nothing. It now asserts no `SystemExit` - every ordinary
way out of axiom is status 0 and `CANNOT_START` is the only non-zero one - and that the
skill was actually loaded, so the test cannot pass by exercising an empty catalogue.

## Two criteria were covered but not legible

A citation sweep found AC 11 and AC 39 asserted by tests whose docstrings named other
criteria: AC 11 by the `skill: one` line in AC 7's test, AC 39 by `skills off` and the
loaded count in AC 37's and AC 2's. **Both were genuinely tested**; neither could be found
by reading. The docstrings now cite them.

This is worth keeping as a habit: `grep` the criteria numbers out of the tests and diff
against 1-44. It costs one command and it is the only check that catches a criterion covered
by accident rather than on purpose - which is one step from a criterion believed covered and
not.

## The suite

    829 -> 832 tests, all passing, 78.93s, 1 deselected

Arithmetic: 829 + 3 = 832. Holds.

Wall clock across the whole loop: 78.56, 78.18, 77.18, 79.08, 91.34, 87.28, 78.34, 78.15,
79.86, 78.90, 78.54, 78.43, 78.27, 78.93. One excursion, chased twice, attributed to load,
and it came back.

## What the loop cost

Eleven cycles, 16:08 to 19:50, against a fail-safe of 21:30. 217 tests added, 44 criteria,
five behaviours that were false when a test was written for them and had to be changed
instead.

## Goal check

**Met.** All 44 criteria break-proven, the suite is green and hermetic, no live-model test
runs in it, and AC 15 and AC 16 carry recorded counts per model.

**The loop ends here. The cron is deleted.**
