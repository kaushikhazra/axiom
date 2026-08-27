# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/61
Branch:              feature/61-tool-cost
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then hand over to row 15 (#62)
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-28 05:43 IST - four hours of wall clock from the first cycle.
Stop then, converged or not, state why it did not converge, and still hand over.
```

**The artifact lives outside this folder.** The code is the repo's real source at
`C:/Projects/axiom/src/`, not a copy under `iteration-1/`. No `artifact/` directory here,
deliberately - the repo rule is that the code is not the loop's artifact folder.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions - if
an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable - they report the state at
that cycle and are never edited afterwards.**

**The line already exists. The bug is where it lives.** `note_servers` returns early when no
server is attached, so a figure that is a fact about the *session* is only ever shown to users
who happen to configure MCP. Moving it is most of the work; the rest is making sure the number
is right and that `note_servers` keeps everything else it says.

**The standing prompt belongs in the sum.** It rides in every request, it is held outside
`messages` so it does not look like part of the conversation, and it is 154 tokens of 807 on
this machine. A figure without it is wrong by a fifth.

**AC 9 exists because of a specific history.** `estimated_tokens` divides by four and
`too_large` by three, and #43's log records the standing prompt being quoted at 56, then 163,
before being measured at 205 - three routes, three answers, two of them carried into loop files
before anyone checked. **Take the figure from the same function the size checks use.** A more
accurate number that disagrees with the behaviour it describes is worse than no number.

**This row prints a number, and zero is a plausible number.** #56's cold read found three tests
passing because a default happened to be right. Be deliberate about what a *missing* figure
looks like, and make sure a silent path is silent by intent rather than by arithmetic.

**Pair every negative.** AC 5 and AC 6 are both "says nothing", which passes for an
implementation that never speaks. #55 built its four negatives this way.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than confirming
it. That pass has found something real in **nine consecutive issues**.

## Exit

Three ways out. **Row 15 (#62) is queued behind this one**, so every exit ends by handing over.

1. **Converged** - all 12 criteria met with evidence, suite green and hermetic, transcript change
   accounted for line by line. Commit, push, open a PR referencing #61, **merge it**, delete the
   branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new issue in #61's format carrying
   only the criteria that did not land.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and say plainly what is broken.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #61's row done in `queue.md` with the PR number, cycle count and
wall-clock time, scaffold `.claude/loop/62-summary-facts/iteration-1/` per the queue's
handing-over procedure, and mark row 15 `running`.

**Do not touch the cron.** Marking row 15 running is the entire handover. Deleting it here would
end the chain with two rows still queued.

**First run: 2026-08-28 01:43 IST (cron fires at :06, :21, :36, :51). Fail-safe deadline:
2026-08-28 05:43 IST.**
