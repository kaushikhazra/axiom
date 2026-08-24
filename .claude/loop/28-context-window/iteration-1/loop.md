# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - If goal met:     stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-24 13:41 IST, stop and delete the cron, converged or not,
and state why it did not converge.
```

**The artifact lives outside this folder.** The code is the repo's real source at `C:/Projects/axiom/src/`, not a copy under `iteration-1/`. There is no `artifact/` directory here, deliberately — do not create one, and do not write code anywhere but `src/` and `tests/`.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions — if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state at that cycle and are never edited afterwards.**

`src/axiom/__init__.py` already exists — this iteration extends it, it does not regenerate it. Cycle 1 reads it first, records where it stands against this goal, and edits from there.

**First run: 2026-08-24 11:41 IST. Fail-safe deadline: 2026-08-24 13:41 IST.**
