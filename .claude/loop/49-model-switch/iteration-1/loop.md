# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/49
Branch:              feature/49-model-switch
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Cycles run BACK TO BACK - no cron, no schedule. ONE cycle is:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then say the queue is finished and hand to manual testing
  - If goal not met: write the next action.md, then begin the next cycle immediately

Fail-safe: 2026-08-27 16:52 IST - three hours of wall clock from the first cycle.
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
the start of every cycle. A cycle that finds 16:52 IST passed takes the fail-safe exit - it
does not start work it cannot finish.

**Cycle 1 writes no production code.** It records the baseline - 377 tests, green and hermetic
- and settles the two shape questions that decide everything after them.

**34 criteria, and this row edits the middle of the chat loop rather than the front of it.**
#48 added a step before the conversation began. This one changes six locals *while* a
conversation is running, and the criteria are mostly about what must **not** change alongside
them: the history, the servers, the limits, the working directory.

**The hardest two criteria are AC 11 and AC 16**, and they pull in opposite directions.
AC 16 says tool availability becomes the new model's; AC 11 says tool calls already in the
history stay exactly as they are, even when the new model cannot call tools. Kaushik settled
that deliberately - do not resolve the tension by cleaning history.

**Reuse #48's list, do not rebuild it.** AC 2 requires the switch list to match the startup
list in contents, order and numbering. `models.sorted_models`, `models.picked` and
`terminal.show_models` already exist and are the reason that criterion is cheap. A second
sorting implementation is how the two lists drift apart.

**`StubBackend.asked_about` is the instrument for AC 15 and AC 16.** #48 AC 29 was the same
class of claim and had no real test at all until the cold read found the stub was discarding
the model name it was handed. A printed startup line cannot tell a correct implementation from
one asking about the wrong model.

**Use the local Ollama for hands-on probing** - `gemma2:2b` has no tool support and the other
four do, which makes a real tool-availability switch observable by hand. Never let a test
depend on it:

```
env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q
```

**Before regenerating the golden transcript, fix every stub first.** #48 cycle 2 regenerated
against a `StubClient` with no `list` and wrote a baseline in which every scenario ended
`escaped AttributeError`. A transcript regenerated against a broken stub is still a green
suite, and only the copy-aside made it recoverable. Then read the diff as a diff and check
`grep -c "^<"` for removed lines.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than
confirming it. That pass has found a real defect in **five consecutive issues** - #40 AC 7,
#41 AC 9, #42 AC 3, #43 AC 6, #48 AC 33 - every time after the implementing cycle marked it
met, and every time by a hostile input rather than by rereading code.

## Exit

Three ways out. **This is the last row in the queue**, so a converged run says the queue is
finished rather than scaffolding nothing silently.

1. **Converged** - all 34 criteria met with evidence, suite green and hermetic with no Ollama
   running, transcript accounted for. Commit, push, open a PR referencing #49, **merge it**,
   delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #49's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #49's row **done** in `queue.md` with the PR number, the cycle
count and the wall-clock time, **say the queue is empty**, and hand to
[`../../handoff.md`](../../handoff.md) - **manual testing is what comes next, not another
loop.** Nobody has used axiom yet, and #48 and #49 have both now changed what starting it
looks like, so that handoff needs updating rather than merely citing.

**First cycle: 2026-08-27 13:52 IST. Fail-safe deadline: 2026-08-27 16:52 IST.**
