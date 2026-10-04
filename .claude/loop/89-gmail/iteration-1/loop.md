# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/ and C:/Projects/axiom/tests/

Every 5 minutes, ONE iteration:
  - Action:  work on src/axiom/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - If goal met:     stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-09-11 01:52 IST, stop and delete the cron, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions —
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state
at that cycle and are never edited afterwards.**

**The artifact already existed at the start, so cycle 1 reads it and records where it
stands. It does not write.** After that the loop edits `src/axiom/` and `tests/`; it never
regenerates them.

## Where the work goes

**The code is not the loop's artifact folder.** Source stays in `src/axiom/`, tests in
`tests/`, and this folder holds only the loop's own files and logs. `artifact/` stays
empty; it exists because the template ships it.

**Work on the branch `feature/89-gmail`.** Master is hook-protected — commit and push are
both blocked there, and the merge is a PR from a `release/*` branch. Create the branch on
the first cycle that writes.

## Reading the issue

`gh issue view 89` is the criteria, and it is the source of truth for what *met* means.
Do not restate them here and do not work from a copy — a copy drifts.

**First run: 2026-09-10 21:52 IST. Fail-safe deadline: 2026-09-11 01:52 IST.**
