# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 73` — before the diff and before
the previous cycle's log. Attack each criterion; do not confirm it. A criterion answered by
the other half of its own sentence is how #60 AC 2 passed review twice while being broken.

## The measurement

`.tmp/probe_nesting.py` renders one line at a time through the real `_as_markdown` and
prints input against visible output. Extend it as the criteria demand — mixed ordered and
unordered, three levels, a return to a shallower level, an empty item at depth.

For each input line, record the **rendered indent column** and the **marker**.

Two numbers this loop moves, both to zero:

- **Levels collapsed** — inputs at different indents that render at the same column.
- **Lines that are not one line** — an input line whose rendering contains a newline or a
  blank padded line. `'    - Deepest'` currently renders as a code block with blank lines
  around it, because four spaces means code to a renderer that cannot see the list.

## Every cycle, record

- The indent table: input line, input indent, rendered column, rendered marker.
- Both numbers above, and how far they moved from last cycle, and what moved them.
- Which criteria of #73 are demonstrably met, which are not, which are untested. Untested
  is not met.
- `uv run pytest` — count, pass, fail. Green and hermetic, or it did not land.
- Any assumption that changed.

## Before claiming a criterion met

**Break the feature and watch the test go red.** Flatten the depth deliberately and confirm
the test fails. #60 shipped five breaks that broke nothing and six tests that passed for a
reason other than the one they claimed. A break that changes no test means the test is
vacuous — say so in the log and replace it.

**A flat list is the regression to guard.** Every cycle re-checks that a plain single-level
list renders exactly as it did before this loop started.

## Goal check

- **Met** — every criterion in #73 holds, levels collapsed is zero, lines that are not one
  line is zero, a flat list is byte-identical to today, the suite is green and hermetic, and
  each new test has been shown to fail when the fix is reverted. The loop ends: delete the
  cron and say so.
- **Not met** — report and write the next action.
- **Did not move** — the indent table is identical to last cycle's. Report the flat result
  and stop. Do not try another variant.
