# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/40
Branch:              feature/40-plain-text-pages
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 12 hours after the first run - stop and delete the cron, converged or not,
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

**Cycle 1 writes no production code.** It measures what `trafilatura.extract` really returns,
what real servers really send, and what today's behaviour is for the four failures AC 12
protects. This issue exists because a library was assumed to be more general than it is;
assuming a second time is how the same cycle repeats.

**AC 6 is the criterion that must not be got wrong.** `page.text` decodes binary into
plausible-looking mojibake without raising, so a tool can report "not readable" and still
hand the model the bytes. It is settled by asserting on what the model received, never on
what axiom printed. A page that is not readable hands the model **none** of its content.

**No cycle ever ends with a question.** This runs unattended and the queue runs loops back
to back; a cycle that stops to ask burns every remaining cycle until the fail-safe and
strands #41, #42 and #43 behind it. Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

## Exit

Three ways out. **Every one of them ends by handing over per `queue.md`** - #41 is the next
row, and a converged run scaffolds it rather than stopping silently.

1. **Converged** - all 12 criteria met with evidence, the content-type ones against really
   served responses, suite green and hermetic, transcript cleared. Commit, push, open a PR
   referencing #40, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #40's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** delete this cron, mark #40's row done in `queue.md`, and scaffold
row 6 - #41, `41-limits-and-place` - per the handover procedure.

**The scaffold you write for #41 carries the no-questions rule forward.** Its `goal.md`,
`observe.md`, `assumption.md` and `action.md` state decisions, never open questions - if
#41's criteria contain something ambiguous, settle it in that scaffold with the reasoning
recorded, exactly as this one settles AC 6, AC 7 and AC 8. A scaffold that hands the next
loop a question halts the queue just as surely as a cycle that asks one.

**First run: 2026-08-26 01:13 IST (cron fires at :13, :28, :43, :58). Fail-safe deadline:
2026-08-26 13:13 IST.**
