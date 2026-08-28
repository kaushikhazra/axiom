# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/terminal.py  and  C:/Projects/axiom/tests/
Issue:               https://github.com/kaushikhazra/axiom/issues/72

Every 15 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-28 22:20 +0530, stop and delete the cron, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions —
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state
at that cycle and are never edited afterwards.**

The artifact already existed at the start, so **cycle 1 reads it and records where it
stands. It does not write.** After that the loop edits the source; it never regenerates it.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`.
This folder holds the loop's own files and logs, nothing else.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
diff and before the previous log.

**Run one cycle and exit.** Do not continue into a second cycle in the same run — the
scheduler is the loop, and a run that keeps going is no longer measurable.

**First run: 2026-08-28 18:20 +0530. Fail-safe deadline: 2026-08-28 22:20 +0530.**
