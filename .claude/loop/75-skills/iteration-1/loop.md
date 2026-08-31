# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Branch:              feature/75-skills
Issue:               https://github.com/kaushikhazra/axiom/issues/75

Every 20 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-31 21:30 +0530, stop and delete the cron, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions —
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state
at that cycle and are never edited afterwards.**

The skills feature does **not** already exist — it is new source under `src/axiom/`. The
surrounding codebase does, and it is at 775 tests. Cycle 1 records that baseline before it
writes anything.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`. This
folder holds the loop's own files and logs, nothing else.

**Work on `feature/75-skills`.** It was cut from `master` after #72, #73 and #74 were
merged. Check the branch before writing; a cycle that wakes on `master` must switch, not
commit.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
diff and before the previous log.

**Run one cycle and exit.** Do not continue into a second cycle in the same run.

**This story writes instructions that outlive the run.** CLAUDE.md's "Testing tools before
security exists" section has a paragraph for #75 — read it before writing a test. Skills a
test creates go under `C:/Projects/.tmp/axiom-tool-sandbox`, never `.axiom/skills/` in this
repo, or a loop leaves a standing instruction behind for the next session to load.

**Read the clock rather than assuming it.** Several logs in #72, #73 and #74 carry times up
to an hour ahead of the real one, because a cycle guessed. Nothing was decided by a
timestamp, and that was luck.

**First run: 2026-08-31 16:07 +0530. Fail-safe deadline: 2026-08-31 21:30 +0530.**
Cycles fire at 7, 27 and 47 past the hour — 17 of them before the deadline.
