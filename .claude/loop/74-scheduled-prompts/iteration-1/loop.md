# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Issue:               https://github.com/kaushikhazra/axiom/issues/74

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

This artifact does **not** already exist — it is new source under `src/axiom/`. Cycle 1
still designs before it builds, as `action.md` says, but it may write the store and its
tests.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`.
This folder holds the loop's own files and logs, nothing else.

**Loops for #72 and #73 are running against `terminal.py` at the same cadence.** Read the
current source before editing rather than assuming it matches the last log, and never revert
another loop's change.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
diff and before the previous log.

**Run one cycle and exit.** Do not continue into a second cycle in the same run.

**This is the story with no security in front of it.** CLAUDE.md's rules on testing tools
before security exists still hold: a live model is only ever asked for non-destructive work,
and anything destructive is settled with a stub. A scheduler that runs model prompts
unattended is exactly the shape those rules were written for.

**First run: 2026-08-28 18:20 +0530. Fail-safe deadline: 2026-08-28 22:20 +0530.**
