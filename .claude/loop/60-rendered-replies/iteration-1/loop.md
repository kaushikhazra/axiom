# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/60
Branch:              feature/60-rendered-replies
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, then say the queue is empty and hand to handoff.md
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-28 07:07 IST - four hours of wall clock from the first cycle.
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

**29 criteria, the first new dependency since #43, and the largest row in the queue.** It is last
for those reasons, and everything behind it is already merged - so a fail-safe exit here costs
this row and nothing else.

**The hard part is streaming, not markdown.** `rich.Live` re-renders its whole renderable on
every update, which on a reply longer than the window is a scrolling smear. AC 7 - *a line that
has been shown does not move again* - is written to rule that out. **Read the three references
before writing anything**: `md2term`, `richify`, and the merged `simonw/llm` PR all solve this,
and all three are applications rather than libraries, so they are prior art and not dependencies.

**AC 8 against AC 9 is the actual work.** Show every character as it arrives, and do not style a
construct until it is complete. Both, at once.

**AC 5 is blunt on purpose.** Every character reaches the screen. The failure mode of markdown
renderers is silently eating what they do not understand, and a renderer that drops content is
worse than no renderer at all.

**The transcript should not move.** Tests capture non-terminal output, and the piped path stays
plain - Kaushik settled that explicitly. **If it changes, something is wrong rather than
something is new.**

**`terminal.py` is the only module that prints**, which is why this touches one file. If
something above it needs to change, say why in the log rather than doing it quietly.

**This row has a judgement component** - Kaushik asked for it because a transcript read badly -
and that is exactly where a single flattering sample is most tempting. #62 nearly adopted a wrong
conclusion from three one-run probes. Record a real before-and-after.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than confirming
it. That pass has found something real in **eleven consecutive issues**.

## Exit

Three ways out. **This is the last row in the queue**, so a converged run says the queue is
finished rather than scaffolding nothing silently.

1. **Converged** - all 29 criteria met with evidence, suite green and hermetic, transcript
   unchanged, a real before-and-after recorded. Commit, push, open a PR referencing #60,
   **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new issue in #60's format carrying
   only the criteria that did not land. With 29 criteria and a new dependency this is a likely
   outcome and is not a failure.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and say plainly what is broken.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** mark #60's row done in `queue.md` with the PR number, cycle count and
wall-clock time, **say the queue is empty**, and update
[`../../handoff.md`](../../handoff.md) - **manual testing is still unfinished**, #41, #34, #40,
#35 and #26 were never reached, and six rows have merged since it was last written.

**Do not touch the cron.** With the queue empty there is no next row to redirect it to; say so in
the handover and leave it for Kaushik to stop.

**First run: 2026-08-28 03:07 IST (cron fires at :06, :21, :36, :51). Fail-safe deadline:
2026-08-28 07:07 IST.**
