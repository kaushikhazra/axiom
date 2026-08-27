# Action

**The cold read.** This is the whole cycle. No feature work unless the read finds something
that needs it.

Cycle 3 ended with all 29 criteria marked met with evidence. That is the exact sentence the
implementing cycle wrote in **eleven consecutive issues** before a hostile reader found
something real in every one of them. Treat it as a claim awaiting a reader, not a result.

## 1. Read the criteria first

`gh issue view 60` — **before** the cycle logs and **before** the diff. The logs are
persuasive precisely because their author wrote both the code and the verdict.

Take each criterion as written, in the user's words, and ask what a session would have to
do to violate it. Then try to make it do that.

## 2. Attack, do not confirm

The method that has earned its place, in order:

- **A test that cannot fail proves nothing.** Five tests in this file have already been
  caught being vacuous — three in cycle 2, two in cycle 3 — and every one of them passed
  against a deliberately broken renderer. They shared a shape: they asserted that text was
  *present in the byte stream*, where the plain echo puts it regardless. **Look for more of
  that shape.** `.tmp/break60.py` has 18 breaks; the question is which criterion has no
  break at all.
- **Hostile inputs, not re-readings.** The four defects this method has found across #40 to
  #43 all needed an input nobody had tried, not a closer look at the code. Candidates the
  suite does not currently feed: a fence opened inside a table; a table whose rows arrive
  one character at a time; a reply that is a single `|`; a heading immediately followed by
  a fence with no blank line; text with a lone `\r` in it; a line longer than the console
  width; a reply of 200 blank lines.
- **Check the criteria that were never given a test of their own.** AC 17, AC 18, AC 19 and
  AC 29 are all resting on "the golden transcript did not move". Ask whether the transcript
  actually *covers* them with rendering on — it is captured with output redirected, which
  is the **plain** path. If it is, say why that is enough. If it is not, that is a finding.

## 3. The things most likely to be wrong

Named so they are checked rather than skipped, not because they are known to be broken:

- **AC 5 and the table.** Held rows are the one place content is buffered. What happens if
  the reply ends mid-row, or a fence opens while rows are held, or `_as_table` raises?
- **AC 26 and `NO_COLOR`.** Rich is honouring it inside `_as_markdown`. Is there any other
  path that emits colour — a table's own styling, for instance?
- **AC 7 during a table.** Rows are erased with `\r`. Erasing is not moving, but check that
  a **multi-line** table cannot erase a line above it.
- **AC 14 and AC 15.** The plain path is now reached two ways — not a terminal, and the
  switch. Are they identical, or merely both plain?

## 4. If it finds something

Fix it, with a test that fails first. Then run the full suite, the hermeticity command and
the break harness, and write the next action. **Do not fix quietly** — a defect found by
this pass goes in the log by name, with what it would have cost a user.

If it genuinely finds nothing, say so plainly and take exit 1: all 29 met, suite green,
transcript unchanged, before-and-after recorded. Then follow the queue's handing-over
procedure — and this is the **last row**, so that means saying the queue is empty,
updating `../../handoff.md`, and leaving the cron alone.

## 5. A fresh reader is stronger

Where one is available, use one — a reader without the author's context is the thing that
makes this pass work at all. Where one is not, **say so in the log** rather than claiming a
cold read that was not cold.

## Record

Every criterion, with the verdict and what was tried against it. Anything found, by name.
Whether the read was genuinely cold. If nothing was found, say what was attacked and came
back clean — a cold read that reports "all good" without saying what it tried is worth
nothing.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry
on.
