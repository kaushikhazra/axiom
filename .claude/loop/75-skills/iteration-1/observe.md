# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 75` — before the diff and before
the previous cycle's log. Attack each criterion; do not confirm it. Thirteen loops have
found something real by reading the criteria cold, and nothing by re-reading the diff.

## The measurement

The number this loop moves is **criteria demonstrably met, out of 44.** Demonstrably means
a test that fails when the behaviour is removed. Not "the code appears to do this."

**Progressive disclosure is the point of the feature, and it is measured in bytes.** A
skill that is catalogued costs tokens on every request forever; a skill that is invoked
costs them once. If a cycle cannot state what the catalogue adds to a request, that cycle
has not measured the thing the feature exists for.

Every cycle, run and record:

    uv run pytest

## Every cycle, record

- **Criteria met, out of 44**, listed by number. Three buckets: met with a test that has
  been shown to fail when broken; implemented but not proved; not started. Only the first
  bucket counts toward the number.
- How far the number moved from last cycle, and what moved it.
- `uv run pytest` — count, pass, fail, and **wall-clock time for the whole suite**. The
  count is arithmetic: tests added this cycle plus last cycle's count. A count that does
  not add up means a test was silently replaced.
- **What the catalogue adds to a request, in characters and in tokens**, at zero skills and
  at the number currently on disk.
- Any assumption that changed.

## The five that will be got wrong

Watch these specifically, every cycle. Each is easy to claim and hard to hold:

- **AC 12 and AC 13 — the body never rides along.** Prove by inspecting what is actually
  sent to the model, not by reading the loader. The failure mode is a catalogue that
  quietly carries the first N characters of each body "for context", which looks like a
  feature and silently doubles the cost of every request.
- **AC 15 and AC 16 — the model reaches for a skill on its own.** This cannot be stubbed
  and it cannot be asserted. It needs repeated live runs against each installed model with
  the counts written down, and a model that cannot do it reliably is a **recorded number,
  not a failed cycle**. Start this early. Left to the last cycle it will not fit, and the
  temptation will be to claim it from one lucky run.
- **AC 33 — instructions are read when invoked, not at startup.** Loading everything at
  startup is simpler and makes this criterion quietly false while every test still passes.
  Prove it by editing a skill mid-run and invoking it.
- **AC 34 — invoking twice leaves the instructions in once.** A model that re-invokes every
  turn fills the window, and nothing about it looks wrong until a long conversation dies.
- **AC 38 — with skills off, the cost is not paid.** The reporting half of AC 3 is easy.
  This half is the one that gets faked: an off switch that hides the line but still builds
  the catalogue.

## Before claiming a criterion met

**Break it and watch the test go red.** #60 shipped five breaks that broke nothing and six
tests that passed for a reason other than the one they claimed; #74 found three vacuous
tests in a single cycle of eleven. Assume the same rate.

**A break that makes the suite faster is a test doing less, not a test going quicker.**
Three separate loops found real defects this way and none found them by reading.

**Re-establish green between a revert and the next break** — the formatter strips imports
that a break leaves unused, so a second break lands on a file that is not what the first
one measured.

## Goal check

- **Met** — all 44 criteria are in the first bucket, the suite is green and hermetic, no
  live-model test runs in it, and AC 15 and AC 16 carry recorded counts per model. The loop
  ends: delete the cron and say so.
- **Not met** — report and write the next action.
- **Did not move** — criteria met is the same as last cycle's. Report the flat result and
  stop. Do not try another variant.
