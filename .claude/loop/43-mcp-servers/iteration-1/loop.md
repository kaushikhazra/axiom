# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/43
Branch:              feature/43-mcp-servers
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-26 15:58 IST - stop and delete the cron, converged or not,
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

**Cycle 1 writes no production code.** It records the baseline, installs `mcp`, and probes the
three things that decide the shape of everything else: what `list_tools` and `call_tool`
really return, whether a background event-loop thread bridges async to sync cleanly, and
whether a stdio server's process is actually gone when the client closes.

**30 criteria. This is the largest issue in the queue** and the only one adding a dependency,
a config file, and a source of tools axiom did not write.

**`CLAUDE.md`'s testing clause binds this loop specifically.** No test fetches a server - no
`npx -y`, no `uvx`, nothing downloaded at test time. The in-memory transport settles nearly
everything. Where a real process is genuinely needed - **AC 26 and AC 27, about processes
outliving axiom** - the server is a script this repo owns, run by the same interpreter, in the
sandbox. No test contacts a hosted server or needs a real secret.

**AC 26 and AC 27 are where the shortcut will be tempting**, because pointing at a real server
is the fastest way to get a process to kill. That is the moment to write the script.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than
confirming it. That pass has found a real defect in **three consecutive issues** - #40 AC 7,
#41 AC 9, #42 AC 3 - every time after the implementing cycle marked it met, and every time by
a hostile input rather than by rereading code.

**Before regenerating the golden transcript, read the whole diff as a diff** and check
explicitly for removed lines. #41 cycle 2 regenerated off pytest's summary and destroyed two
compaction scenarios.

## Exit

Three ways out. **#43 is the last row in the queue**, so a converged run says the queue is
finished rather than scaffolding nothing silently.

1. **Converged** - all 30 criteria met with evidence, the lifetime ones against a real
   subprocess, suite green and hermetic, transcript accounted for. Commit, push, open a PR
   referencing #43, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #43's format
   carrying only the criteria that did not land. State in the log why it did not converge.
   With 30 criteria this is a likely outcome and is not a failure.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** delete this cron, mark #43's row done in `queue.md`, and say the
queue is empty.

**First run: 2026-08-26 03:58 IST (cron fires at :13, :28, :43, :58). Fail-safe deadline:
2026-08-26 15:58 IST.**
