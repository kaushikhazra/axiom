# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/55
Branch:              feature/55-announce-the-file
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then hand over to row 13 (#56)
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-28 04:42 IST - four hours of wall clock from the first cycle.
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

**The fix is one line. The eleven criteria are the work**, and most of them are about something
*not* being said - which is the easiest assertion in the world to satisfy by accident. Pair
every negative with a positive proving the announcement works at all.

**An empty directory does not test this row.** The old behaviour announces there, correctly.
The case that separates right from wrong is a directory that **already has `.axiom/mcp.json`**
and no `model.json` - a project that configures MCP, which is every project that uses it. Write
that test first and watch it fail.

**This row exists because a criterion and its implementation agreed perfectly and were both
wrong.** #48 AC 30 is worded about the folder; the code checks the folder. Nothing in the diff
looked wrong, and no test could have produced it. It surfaced because a person ran a clean
directory that turned out not to be clean and asked why the line did not appear.

**Existence decides, not memory.** A flag saying "already announced" is true within a run and
forgotten between them, so a second run would announce again. Prove the rule across two separate
`main()` calls, and prove it a third time after deleting the file.

**Both routes announce in the same words.** `_remember` is called from the startup list and from
a `/model` switch. They already share the function, so this holds by construction - but AC 9
says it, so test it.

**The golden transcript may change.** Fix every stub before regenerating - #48 cycle 2
regenerated against a broken `StubClient` and wrote a baseline in which every scenario ended in
`AttributeError`, and only the copy-aside made it recoverable. Then read the diff as a diff and
check `grep -c "^<"` for removed lines.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than confirming
it. That pass has found a real defect in **seven consecutive issues**, and three of the last four
were the same shape: an assertion a *wrong* implementation also satisfies.

## Exit

Three ways out. **Row 13 (#56) is queued behind this one**, so every exit ends by handing over.

1. **Converged** - all 11 criteria met with evidence, suite green and hermetic, transcript
   change accounted for line by line. Commit, push, open a PR referencing #55, **merge it**,
   delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new issue in #55's format carrying
   only the criteria that did not land.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and say plainly what is broken.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #55's row done in `queue.md` with the PR number, cycle count and
wall-clock time, scaffold `.claude/loop/56-same-facts/iteration-1/` per the queue's handing-over
procedure, and mark row 13 `running`.

**Do not touch the cron.** There is one for the whole queue and it reads `queue.md` for whichever
row says `running` - so marking row 13 running is the entire handover. Deleting it here would end
the chain with three rows still queued.

**First run: 2026-08-28 00:42 IST (cron fires at :06, :21, :36, :51). Fail-safe deadline:
2026-08-28 04:42 IST.**
