# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 77` — before the diff and before
the previous cycle's log. Attack each criterion; do not confirm it. Across #60, #72, #73,
#74 and #75, reading the criteria cold has found something real every time and re-reading
the diff has found nothing.

## The measurement

The number this loop moves is **criteria demonstrably met, out of 37.** Demonstrably means
a test that has been shown to fail when the behaviour is removed. Not "the code appears to
do this."

Every cycle, run and record:

    uv run pytest

## Every cycle, record

- **Criteria met, out of 37**, listed by number. Three buckets: met with a test proven to
  go red when broken; implemented but not proved; not started. Only the first bucket counts.
- How far the number moved from last cycle, and what moved it.
- `uv run pytest` — count, pass, fail, and **wall-clock time for the whole suite**. The
  count is arithmetic: tests added this cycle plus last cycle's. A count that does not add
  up means a test was silently replaced. Baseline entering this loop: **836 passed, 1
  deselected, 81.9s.**
- **The state of `tests/baseline/transcript.txt`** — unchanged, or changed with the diff
  read line by line and summarised. Never "regenerated".
- Any assumption that changed.

## The six that will be got wrong

Each is easy to claim and hard to hold. Watch them every cycle.

- **The four vacuous negatives.** `assert "models on" not in out.out` appears four times
  across `test_models.py` and `test_switch.py`. When the phrase moves into a panel title
  these do not fail — **they pass while testing nothing**, and the suite reports that a
  chooser which is never shown is still never shown. They must be re-pointed by hand at
  whatever the new wording is. They will not tell you themselves.

- **The baseline is not to be regenerated to make a failure go away.** 78 of its 477 lines
  are the startup lines this work rewrites. `AXIOM_WRITE_BASELINE=1` exists and using it to
  clear a red is the one thing that defeats the file. #75's own words: *regenerating it
  once produced a correct-but-noisy line; narrowing the code let the baseline be restored
  instead of updated.* Read the diff, then decide.

- **Nothing in the suite tests colour.** `show_piece` gates all rendering on
  `sys.stdout.isatty()` (terminal.py:1190) and the golden transcript captures a non-tty, so
  the baseline holds zero escape bytes and every rendering test asserts on text through the
  screen model. **The palette could be wrong in every hue and the suite would stay green.**
  AC 17, 18, 21, 27, 30 and 31 need a test that looks at the styling bytes, or they are not
  met — they are merely believed.

- **AC 34 — a reply's words are unchanged.** Prove it by rendering the same reply before
  and after through `Rendered` and comparing the screen text, not by reading the theme.
  **Normalise Rich's OSC-8 link ids first**: `tests/screen.py` strips SGR and CSI but not
  OSC-8, so a reply containing a link compares unequal to itself across two renders. That
  gap was found on 2026-09-01 and is still there.

- **AC 22 and AC 26 — nothing per call remains on screen.** The failure mode is a transient
  line that is written and never erased, which looks fine in a fast test and leaves a trail
  in a real terminal. Prove it by feeding a multi-call turn through the screen model and
  asserting on what is *on the screen at the end*, not on what was written.

- **AC 35 — a bare run says no more than it did before.** A redesign is exactly when a
  quiet path grows chatty. Compare a no-tools, no-servers, no-skills run against the
  baseline transcript's own bare-run sections.

## Two criteria that were inferred, not asked for

**AC 10** (the screen clears once, at settle, and never again) and **AC 35** were written
by the agent rather than stated by Kaushik. If either fights the implementation, raise it
rather than quietly satisfying it — they are the two cheapest to strike.

## Before claiming a criterion met

**Break it and watch the test go red.** #60 shipped five breaks that broke nothing and six
tests that passed for a reason other than the one they claimed; #74 found three vacuous
tests in one cycle of eleven; #75 lost a criterion to an over-wide break three separate
times. Assume the same rate here.

**A break big enough to be easy to write takes several tests with it and proves nothing
about the one it was aimed at.** Narrow the break to the one behaviour.

**A break that makes the suite faster is a test doing less, not a test going quicker.**

**Re-establish green between a revert and the next break** — the formatter strips imports
a break leaves unused, so a second break lands on a file that is not what the first
measured.

**A scripted break that reports nothing did not run.** Anything containing a backslash
escape goes through the Edit tool, never a scripted replace.

## Goal check

- **Met** — all 37 criteria are in the first bucket, the suite is green, and the baseline
  is either untouched or its diff is summarised line by line in a cycle log. The loop ends:
  delete the cron and say so.
- **Not met** — report and write the next action.
- **Did not move** — criteria met is the same as last cycle's. Report the flat result and
  stop. Do not try another variant.
