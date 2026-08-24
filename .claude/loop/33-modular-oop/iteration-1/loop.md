# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/33
Branch:              feature/33-modular-oop

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-25 12:52 IST, stop and delete the cron, converged or not,
and state why it did not converge.
```

**The artifact lives outside this folder.** The code is the repo's real source at
`C:/Projects/axiom/src/`, not a copy under `iteration-1/`. No `artifact/` directory
here, deliberately - the repo rule is that the code is not the loop's artifact folder.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the
assumptions - if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable - they report the
state at that cycle and are never edited afterwards.**

`src/axiom/__init__.py` already exists and is the thing being restructured. This loop
**edits** it; it does not regenerate it from scratch. **Cycle 1 writes no code** - it
records the baseline that AC 1, AC 2 and AC 14 are later measured against.

## Exit

Three ways out, and every one of them leaves no branch behind unexplained:

1. **Converged** - all 20 criteria met with evidence, suite green. Commit, push, open a
   PR referencing #33, **merge it**, delete the branch, close the loop, delete the cron.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is
   proven, open a PR, **merge it**, delete the branch, then open a new GitHub issue in
   #33's format carrying only the criteria that did not land. This is the #29 - #32 move.
   State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour changed** - **do not merge.** Leave the
   branch, push it, and state plainly in the log what is broken and what the next
   iteration would have to settle first.

Never merge a red suite. Never merge a behaviour change that AC 1 has not cleared.

**First run: 2026-08-25 00:52 IST (cron fires at :07, :22, :37, :52). Fail-safe deadline: 2026-08-25 12:52 IST.**
