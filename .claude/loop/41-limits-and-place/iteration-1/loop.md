# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/41
Branch:              feature/41-limits-and-place
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-26 13:58 IST - stop and delete the cron, converged or not,
state why it did not converge, and still hand over.
```

**The artifact lives outside this folder.** The code is the repo's real source at
`C:/Projects/axiom/src/`, not a copy under `iteration-1/`. No `artifact/` directory here,
deliberately - the repo rule is that the code is not the loop's artifact folder.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions -
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable - they report the state at
that cycle and are never edited afterwards.**

**Cycle 1 writes no production code.** It records the baseline AC 12 is measured against,
probes the system prompt against compaction, and finds out whether a real local model does
anything at all with being told its limits.

**This issue introduces axiom's first system prompt**, and `compaction.py` already treats a
leading system message as a carried-forward summary. That collision is the sharpest edge
here and cycle 1 measures it before anything is built on top of it.

**Most of these criteria are about what a model is told**, which is unusually easy to fake.
A test asserting the prompt contains "30 seconds" proves a sentence was assembled, not that
anything acted on it. AC 1, 3, 4 and 5 need a live model.

**No cycle ever ends with a question.** This runs unattended and the queue runs loops back to
back; a cycle that stops to ask burns every remaining cycle until the fail-safe and strands
#42 and #43 behind it. Decide, record the decision and the reasoning in the cycle log,
continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the
criteria from GitHub before the diff and before the previous log, and attacks each one
rather than confirming it. In #40 that pass found a criterion outright broken after the
implementing cycle had marked it met.

## Exit

Three ways out. **Every one of them ends by handing over per `queue.md`** - #42 is the next
row, and a converged run scaffolds it rather than stopping silently.

1. **Converged** - all 12 criteria met with evidence, the behavioural ones from a live model,
   suite green and hermetic, transcript accounted for. Commit, push, open a PR referencing
   #41, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #41's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** delete this cron, mark #41's row done in `queue.md`, and scaffold
row 7 - #42, `42-oversized-turn` - per the handover procedure.

**The scaffold you write for #42 carries the no-questions rule forward.** Its files state
decisions, never open questions - if #42's criteria contain something ambiguous, settle it
there with the reasoning recorded. A scaffold that hands the next loop a question halts the
queue just as surely as a cycle that asks one.

**First run: 2026-08-26 01:58 IST (cron fires at :13, :28, :43, :58). Fail-safe deadline:
2026-08-26 13:58 IST.**
