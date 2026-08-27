# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/62
Branch:              feature/62-summary-facts
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then hand over to row 16 (#60) - the last
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-28 06:18 IST - four hours of wall clock from the first cycle.
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

**This row cannot be settled by the suite alone, and pretending otherwise is the failure mode.**
`StubBackend.complete` returns a fixed string; a test asserting the summary holds the right
things, against a stub that was told what to return, proves only that the stub was told. AC 4 and
AC 5 need a live probe with the real output in the log. **Say for every criterion whether its
evidence is a test or a probe.**

**The instruction is the lever.** `COMPACTION_INSTRUCTION` asks for "every distinct fact from the
conversation", and the model *said* that RPG stands for role-playing game during the
conversation - so by that instruction it belongs. What is missing is the distinction between what
the conversation established and what the model already knew.

**Do not undo the third sentence.** It forbids judging importance, and #32 put it there after
oldest-first dropping lost "my cat is called Biscuit" from turn one. "Not general knowledge" is a
different axis from "not important", and conflating them would re-open a measured bug.

**AC 3 must not become a scorer.** "The least particular to this conversation" reads like a
request to rank bullets by guessed importance. That is smarts pretending to be a guarantee - the
thing Kaushik ruled out when he chose a system prompt over axiom challenging a model. Prefer a
structural signal; if there is none, meet AC 3 by keeping general knowledge out in the first
place and say so.

**Corruption is out of scope.** "ventured" became "**Vented**" across a compaction boundary in
the same session. A fact altered rather than dropped is a different failure and belongs to its
own story.

**A criterion that cannot be met as written is an acceptable outcome here**, more than in the
four rows before it, because so much depends on a model's behaviour. Say so plainly and say why.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than confirming
it. That pass has found something real in **ten consecutive issues** - most recently #61's AC 9,
which had no test at all while the whole suite stayed green.

## Exit

Three ways out. **Row 16 (#60) is queued behind this one and is the last**, so every exit ends by
handing over.

1. **Converged** - all 12 criteria met with evidence, suite green and hermetic, transcript
   accounted for, live probe recorded. Commit, push, open a PR referencing #62, **merge it**,
   delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new issue in #62's format carrying
   only the criteria that did not land.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and say plainly what is broken.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #62's row done in `queue.md` with the PR number, cycle count and
wall-clock time, scaffold `.claude/loop/60-rendered-replies/iteration-1/` per the queue's
handing-over procedure, and mark row 16 `running`.

**Do not touch the cron.** Marking row 16 running is the entire handover.

**First run: 2026-08-28 02:18 IST (cron fires at :06, :21, :36, :51). Fail-safe deadline:
2026-08-28 06:18 IST.**
