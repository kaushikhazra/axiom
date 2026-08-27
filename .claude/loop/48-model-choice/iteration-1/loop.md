# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/48
Branch:              feature/48-model-choice
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Cycles run BACK TO BACK - no cron, no schedule. ONE cycle is:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then hand over to row 10 (#49) and start its first cycle
  - If goal not met: write the next action.md, then begin the next cycle immediately

Fail-safe: 2026-08-27 16:27 IST - three hours of wall clock from the first cycle.
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

**The fail-safe is a clock, not a cycle count.** Cycles run back to back with nothing between
them, so a hung cycle holds the whole chain rather than costing one firing. Check the clock at
the start of every cycle. A cycle that finds 16:27 IST passed takes the fail-safe exit and
hands over - it does not start work it cannot finish.

**Cycle 1 writes no production code.** It records the baseline - 317 tests, green and
hermetic - and probes the three things that decide the shape of everything else.

**38 criteria, and the deletion of a default that eight rows have relied on.** `DEFAULT_MODEL`
is read by `parse_args`, and the golden transcript has recorded its effect on the startup line
since #26. Both change here, on purpose.

**This row is uniquely exposed to a test that needs a live Ollama**, because the whole issue is
about asking a host a question. The listing call goes on the `ModelBackend` protocol beside
`model_info` and `supports_tools`, and the stubs answer it. A test that reaches
`http://localhost:11434` has broken the one check that has held for eight rows:

```
env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q
```

**Use the local Ollama for hands-on probing** - Kaushik has asked for it, and seeing the
picker behave is worth a cycle's attention. Never let a test depend on it.

**The golden transcript changes this row, deliberately.** Regenerate with
`AXIOM_WRITE_BASELINE=1`, only once the startup line has stopped moving, and record line by
line what changed and why. Read the diff as a diff and check explicitly for removed lines -
#41 cycle 2 regenerated off pytest's summary and destroyed two compaction scenarios.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than
confirming it. That pass has found a real defect in **four consecutive issues** - #40 AC 7,
#41 AC 9, #42 AC 3, #43 AC 6 - every time after the implementing cycle marked it met, and
every time by a hostile input rather than by rereading code.

## Exit

Three ways out. **Row 10 (#49) is queued behind this one**, so every exit ends by handing over.

1. **Converged** - all 38 criteria met with evidence, suite green and hermetic with no Ollama
   running, transcript change accounted for line by line. Commit, push, open a PR referencing
   #48, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #48's format
   carrying only the criteria that did not land. State in the log why it did not converge.
   With 38 criteria in three hours this is a likely outcome and is not a failure.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first. #49 depends on this row's list and its remembered choice, so say explicitly whether
   row 10 can start on what landed.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #48's row **done** in `queue.md` with the PR number, the cycle
count and the wall-clock time it took, scaffold `.claude/loop/49-model-switch/iteration-1/`
per the queue's handing-over procedure, and **begin its first cycle immediately**. Nothing is
scheduled; if this run stops without doing that, the chain stops with it and nobody is
watching.

**First cycle: 2026-08-27 13:27 IST. Fail-safe deadline: 2026-08-27 16:27 IST.**
