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

Fail-safe: at 2026-08-24 19:06 IST, stop and delete the cron, converged or not,
and state why it did not converge.
```

**The artifact lives outside this folder**, same as iteration-1: the code is the repo's real source at `C:/Projects/axiom/src/`, not a copy under `iteration-2/`. No `artifact/` directory here, deliberately.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions — if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state at that cycle and are never edited afterwards.**

`src/axiom/__init__.py` already exists and already has 11/11 of #29's original criteria met (iteration-1, converged) — this iteration edits it further, it does not regenerate it.

**First run: 2026-08-24 17:36 IST. Fail-safe deadline: 2026-08-24 19:06 IST.**
