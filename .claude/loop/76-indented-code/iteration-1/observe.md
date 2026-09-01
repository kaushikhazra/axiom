# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 76` — before the diff and before the
previous cycle's log. Attack each criterion; do not confirm it. Across #60, #72, #73, #74,
#75, #77 and #80, reading the criteria cold has found something real every time and re-reading
the diff has found nothing.

## The measurement

The number this loop moves is **criteria demonstrably met, out of 13.** Demonstrably means a
test that has been shown to fail when the behaviour is removed. Not "the code appears to do
this."

Every cycle, run and record:

    uv run pytest

## Every cycle, record

- **Criteria met, out of 13**, listed by number. Three buckets: met with a test proven to go
  red when broken; implemented but not proved; not started. Only the first counts.
- How far the number moved, and what moved it.
- `uv run pytest` — count, pass, fail, **wall-clock**. The count is arithmetic: tests added
  this cycle plus last cycle's. A count that does not add up means a test was silently
  replaced. Baseline entering this loop: **876 passed, 1 deselected, ~89s** on `master`.
- **The state of `tests/baseline/transcript.txt`** — unchanged, or the diff read line by line
  and summarised. Never "regenerated".
- **`.claude/loop/cited.py tests/<file>`** — which criteria the tests actually claim, against
  the issue. Two greps were wrong about this in opposite directions before it existed.
- Any assumption that changed.

## The five that will be got wrong

- **AC 4 is the trap, and it is the whole reason this issue exists.** A line indented four
  spaces *inside a list* is a list item at its own depth, not code. Markdown's own rule is
  relative to the list's content indent, not to column zero, and the naive test — "four or
  more spaces means code" — turns every nested bullet into a code block. #73 is the story that
  found this; do not undo it.

- **AC 2 against AC 7 and AC 8.** "Every character reaches the screen, however narrow the
  window" and "exactly as wide as the window is one line, one wider is two". These are the
  same boundary from two sides, and an off-by-one satisfies one while breaking the other.
  `tests/screen.py` — a terminal small enough to reason about — is what a criterion about the
  screen is measured against. #60 learned this after two cycles marked a criterion met against
  a byte stream that was true and irrelevant.

- **AC 5 and AC 6 are the regression half and they are most of the risk.** The renderer is
  shared. A change to how an indented line is recognised reaches fenced blocks, paragraphs,
  headings, quotes, list items and table cells. Every one of them has tests already; a cycle
  that only adds tests for the new behaviour has not looked at the old.

- **AC 11 and AC 12 — `--no-render` and a piped run are byte-for-byte unchanged.** The golden
  transcript is 477 lines and has not moved in fifteen cycles across three issues. If it
  moves, the terminal-only split has been broken.

- **AC 9 — an indented line of only spaces prints nothing and leaves no stray row.** The
  cheapest criterion to get subtly wrong: an empty block that emits a blank line looks
  harmless and is a visible gap in every reply that contains one.

## Before claiming a criterion met

**Break it and watch the test go red.** Assume, on the measured rate from #77 and #80, that
roughly one break in four is aimed at the code rather than at the criterion and proves nothing.

**A break big enough to be easy to write takes several tests with it.** Narrow it.

**A break that makes the suite faster is a test doing less.**

**Ask what typed the string you are asserting about.** #80 cycle 10 found a test asserting the
absence of a string nothing had ever produced. It passed for every implementation there is.

**A count is not a criterion.** #80 cycle 9 found "one request" satisfied by an implementation
that threw the message away. Every number in an assertion needs the thing it is a number *of*
asserted beside it.

**Asserting that text is present in the byte stream proves nothing about the screen.** The
plain echo puts it there whatever the renderer did. This is the shape of every one of #60's
six vacuous tests.

**A scripted replace containing a backslash escape goes through the Edit tool.**

**Re-establish green between a revert and the next break** — the formatter strips imports a
break leaves unused.

## Goal check

- **Met** — all 13 criteria are in the first bucket, the suite is green, the baseline is
  untouched or its diff is summarised, and the list of what only a person can confirm has been
  written down for the manual pass. Take the queue's handing-over exit.
- **Not met** — report and write the next action.
- **Did not move** — criteria met is the same as last cycle's. Report the flat result and stop.
  Do not try another variant.
