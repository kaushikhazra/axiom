# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/34
Branch:              feature/34-tools
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-25 18:07 IST, stop and delete the cron, converged or not,
state why it did not converge, and still hand over to the next loop.
```

**The artifact lives outside this folder.** The code is the repo's real source at
`C:/Projects/axiom/src/`, not a copy under `iteration-1/`. No `artifact/` directory here,
deliberately - the repo rule is that the code is not the loop's artifact folder.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions - if
an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable - they report the state at
that cycle and are never edited afterwards.**

`src/axiom/` already exists as six modules from #33. This loop **extends** it; it does not
regenerate it. **Cycle 1 writes no production code** - it probes the four models and records
what they actually do, because every design decision here depends on facts not yet in hand.

**The safety rules in `CLAUDE.md` bind every cycle.** A live model is never asked for
destructive work; destructive criteria are settled with a stub inside `tmp_path`; live-model
tool tests run in `C:/Projects/.tmp/axiom-tool-sandbox`. A cycle that breaks one of these has
failed whatever else it achieved.

## Exit

Three ways out. **Every one of them ends by handing over to the next loop in `queue.md`** -
nothing else is watching, and a loop that stops without doing that leaves the queue stalled
silently.

1. **Converged** - all 35 criteria met with evidence, the model-facing ones by live runs,
   suite green. Commit, push, open a PR referencing #34, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #34's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared - and
where this loop changes the transcript legitimately, say which lines changed and why.

**Then, in the same run:** delete this cron, mark #34's row done in `queue.md`, and start the
next queued loop by following the handover steps written there.

**First run: 2026-08-25 06:07 IST (cron fires at :07, :22, :37, :52). Fail-safe deadline: 2026-08-25 18:07 IST.**
