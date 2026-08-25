# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/32
Branch:              feature/32-compaction-overflow
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-25 21:37 IST, stop and delete the cron, converged or not,
state why it did not converge, and still hand over.
```

**The artifact lives outside this folder.** The code is the repo's real source at
`C:/Projects/axiom/src/`, not a copy under `iteration-1/`. No `artifact/` directory here,
deliberately - the repo rule is that the code is not the loop's artifact folder.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions - if
an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable - they report the state at
that cycle and are never edited afterwards.**

**Cycle 1 writes no production code** - it reproduces the overflow in a real session. This
issue exists because the last attempt ran out of time before proving it, and because the
original compaction bug survived a green suite and eleven mocked criteria. A fix designed
against an imagined failure would be a fix for the wrong thing.

**AC 1 deliberately reintroduces re-summarizing a summary** - the operation that lost facts in
#29. **AC 2 is therefore the criterion that matters most**, and it is settled by a planted
fact surviving a re-compaction, never by a size assertion.

## Exit

Three ways out. **Every one of them ends by handing over per `queue.md`** - and #32 is the
last row, so a converged run should say the queue is empty rather than starting nothing
silently.

1. **Converged** - all 6 criteria met with evidence, the overflow ones from a real session,
   suite green. Commit, push, open a PR referencing #32, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #32's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** delete this cron, mark #32's row done in `queue.md`, and say the
queue is finished.

**First run: 2026-08-25 09:37 IST (cron fires at :07, :22, :37, :52). Fail-safe deadline: 2026-08-25 21:37 IST.**
