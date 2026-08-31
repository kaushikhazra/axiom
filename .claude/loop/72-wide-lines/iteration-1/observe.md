# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 72` — before the diff and before
the previous cycle's log. Twelve loops for twelve issues have found something real by
reading the criteria cold and attacking each one, and nothing by re-reading the diff.

**Attack each criterion; do not confirm it.** A criterion answered by the other half of
its own sentence is the recorded failure of #60 AC 2 — it passed review twice with a
persuasive reason, and manual testing found it broken in the fourth prompt typed.

## The measurement

Run at more than one width. `COLUMNS` drives `shutil.get_terminal_size`, so the check
needs no terminal:

    COLUMNS=40 uv run python .tmp/probe.py
    COLUMNS=60 uv run python .tmp/probe.py
    COLUMNS=200 uv run python .tmp/probe.py

For each construct, compare the visible characters out against the characters in.

- **Wrapped** — every character in is present in the output, across however many lines.
- **Cropped** — the failure. Visible output shorter than input.

The number this loop moves is **characters lost across all five constructs at all three
widths. It must reach zero, and paragraphs and headings must stay at zero.**

## Every cycle, record

- The loss table: construct by width, characters in, characters visible out.
- How far that moved from the last cycle, and what moved it.
- Which criteria of #72 are now demonstrably met, which are not, and which have not been
  tested at all. Untested is not met.
- `uv run pytest` — count, pass, fail. Green and hermetic, or it did not land.
- Any assumption that changed.

## Before claiming a criterion met

**Break the feature and watch the test go red.** A test that passes when the feature does
nothing is worse than no test. #60 shipped six tests that passed for a reason other than
the one they claimed, and five breaks that broke nothing. If a break does not turn a test
red, the test is vacuous — say so in the log and replace it.

## Goal check

- **Met** — every criterion in #72 holds, characters lost is zero at every width tested,
  the suite is green and hermetic, and each new test has been shown to fail when the fix
  is reverted. The loop ends: delete the cron and say so.
- **Not met** — report and write the next action.
- **Did not move** — the loss table is identical to last cycle's. Report the flat result
  and stop. Do not try another variant.
