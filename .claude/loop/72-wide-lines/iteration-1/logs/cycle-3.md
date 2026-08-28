# Cycle 3 — 2026-08-28 19:40 +0530

The criteria that need the screen and the plain path rather than the function. Twenty of
twenty-one now hold; one is blocked on another branch.

**A note on the clock.** Cycles 1 and 2 of this loop, and cycles 2 and 3 of #74's, carry
timestamps taken from an assumed time rather than a read one - they run ahead of the real
clock by up to an hour. The logs are immutable so they stand as written; from here the times
are read from `date`. Nothing was decided by a timestamp, so nothing else is affected.

## AC 8 and AC 9 — the sweep

The plain-text sweep in this file exists because every boundary defect in #60 was an
off-by-one at one particular length, found by trying that length rather than by reasoning
about it. **A quote now occupies four rows where it occupied one**, and the erase arithmetic
was written when it occupied one - so the same sweep is owed to the constructs this issue
changed.

Every length from 1 to `width * 3 + 1`, at widths 20, 40 and 81, for `> `, `- ` and `1. ` -
about 1,300 renderings. Counting one repeated character catches both failures at once: too
many is a row drawn twice, too few is a row lost.

**Nothing is shown twice and nothing is lost, at any length, at any width, for any of the
three markers.** The erase arithmetic survived the constructs becoming multi-row, which was
the open question and is now closed by measurement rather than by argument.

## AC 17 — the severity argument, as a test

Halving the window loses no words and only gains rows. Before this issue, halving the window
roughly halved how much of a quote survived; that was the argument for the issue's severity
and it is now a test.

## AC 21 — the one that could find a wrong answer

Words, in order, rendered against plain. Everything else here confirms nothing was *lost*;
this would catch the change dropping or reordering a word rather than merely cropping one.

## Two tests that pass, and why — recorded rather than left implied

**AC 15 holds, but not because of the wrapping fix.** At three columns Rich produces nothing
usable and `_as_markdown` hands the line back exactly as it went in - which is #60 AC 28, a
formatting failure costing the formatting and never the answer. Measured: this test passes
with the crop reinstated too. It pins the fallback, not the wrap. That is the right thing to
pin at that width, and the docstring now says so, because a green test here is not evidence
that wrapping works at any width.

**AC 16 is a regression guard and correctly not break-sensitive.** An empty block has nothing
to crop. It is here so a later change to how a marker is drawn cannot quietly turn one empty
quote into two rows.

Both were nearly counted as break-proven on the strength of being green. They are not, and
saying which is which is the whole point of the distinction.

## The breaks

| break | red | reads as |
|---|---|---|
| `soft_wrap=True` always | **9 distinct** | the crop, back - including this cycle's sweep, halving and words-in-order |
| plain path bypassed | **5** | `--no-render` and pipes routed through the renderer |

## Criteria — 20 of 21

**Met, with a test shown to fail when the fix is reverted: 15** - AC 1, 2, 3, 4, 5, 6, 8, 9,
12, 13, 14, 17, 19, 20, 21.

**Met, guarded, correctly not break-sensitive: 5** - AC 10, 11, 15, 16, 18. AC 15's reason is
above; the rest guard properties that must hold whether or not this issue's change exists.

**Blocked: 1** - AC 7, a nested item wrapping to its own indent. It needs #73's depth stack,
which is on `feature/73-nested-lists`. `action.md` said to record it rather than half-do it
here, and that stands: the two branches have to meet before it can be tested at all.

## Suite

`uv run pytest` - **664 passed in 76.81s**. Baseline on this branch was 642; 22 added.

## Goal check: NOT met, and the only thing left is not mine to do

Twenty of twenty-one criteria hold. The twenty-first cannot be tested on this branch, because
the code it depends on is on another one.

The loop does not end here - the fail-safe is 22:20 and the goal says *every* criterion.
The next action is the merge, because that is the only move that can close AC 7.
