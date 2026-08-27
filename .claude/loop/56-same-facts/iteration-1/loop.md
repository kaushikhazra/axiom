# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/56
Branch:              feature/56-same-facts
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then hand over to row 14 (#61)
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-28 05:11 IST - four hours of wall clock from the first cycle.
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

**The criterion is that two lines agree, so test them against each other.** A test that
hard-codes the expected wording on both sides passes while they drift, because it drifts with
them - and drift is exactly what produced this row. `announce()` and `note_switched()` build
their phrasings independently, which is how the web state and the override note went missing
from one and not the other. **Parse both lines from the same run and compare.**

**Two settings per fact, or the test proves nothing.** Printing the words "web off" once shows
the word can be printed. Only web-on beside web-off shows it *follows* anything. Same for the
override.

**AC 4 is deliberately open-ended** - "any fact the startup line reports that a switch does not
make stale". Read as "the two already named", it is trivially met. Enumerate everything
`announce()` says and account for each.

**AC 9 is the purpose behind AC 2.** A forced context presented as the model's own is the more
damaging of the two gaps, because it is the exact number someone debugging a compaction problem
reasons from, and it looks authoritative.

**No test would have found this**, and that is worth remembering when judging the fix: each line
was individually correct, and nothing asserted they agreed. Kaushik saw it in seconds because
the two lines sat a few rows apart in a real transcript.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than confirming
it. That pass has found something real in **eight consecutive issues**, and the last two were a
test passing for the wrong reason (#57) and two criteria that disagreed (#55).

## Exit

Three ways out. **Row 14 (#61) is queued behind this one**, so every exit ends by handing over.

1. **Converged** - all 12 criteria met with evidence, suite green and hermetic, transcript change
   accounted for line by line. Commit, push, open a PR referencing #56, **merge it**, delete the
   branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new issue in #56's format carrying
   only the criteria that did not land.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and say plainly what is broken.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #56's row done in `queue.md` with the PR number, cycle count and
wall-clock time, scaffold `.claude/loop/61-tool-cost/iteration-1/` per the queue's handing-over
procedure, and mark row 14 `running`.

**Do not touch the cron.** There is one for the whole queue and it reads `queue.md` for whichever
row says `running` - so marking row 14 running is the entire handover. Deleting it here would end
the chain with two rows still queued.

**First run: 2026-08-28 01:11 IST (cron fires at :06, :21, :36, :51). Fail-safe deadline:
2026-08-28 05:11 IST.**
