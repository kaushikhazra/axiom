# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/35
Branch:              feature/35-web
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-08-25 20:07 IST, stop and delete the cron, converged or not,
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

`src/axiom/` already has a working tool mechanism from #34. This loop **adds two tools to
it**; it does not build a second mechanism. **Cycle 1 writes no production code** - it probes
the libraries and records which criteria existing work already satisfies.

**The safety rules in `CLAUDE.md` bind every cycle**, and `observe.md` adds the one this loop
introduces: an arbitrary-URL fetcher can reach the local network. This loop does not fix that
and must not quietly patch around it - record it for the security stories.

## Exit

Three ways out. **Every one of them ends by handing over to the next loop in `queue.md`** -
nothing else is watching, and a loop that stops without doing that leaves the queue stalled
silently.

1. **Converged** - all 30 criteria met with evidence, the network-facing ones from real runs,
   suite green. Commit, push, open a PR referencing #35, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #35's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared - and
where this loop changes the transcript legitimately, diff it and say which lines changed.

**Then, in the same run:** delete this cron, mark #35's row done in `queue.md`, and start the
next queued loop by following the handover steps written there.

**First run: 2026-08-25 08:22 IST (cron fires at :07, :22, :37, :52). Fail-safe deadline: 2026-08-25 20:07 IST.**
