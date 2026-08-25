# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/42
Branch:              feature/42-oversized-turn
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, hand over to the next loop, delete this cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-26 14:58 IST - stop and delete the cron, converged or not,
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

**Cycle 1 writes no production code.** It reproduces the refusal, measures where "too small
to continue" actually begins, and records what compaction prints when usage triggers it -
because AC 8 says a size-triggered compaction must report the same way.

**#41 made this reachable rather than theoretical.** Its system prompt is a fixed 205 tokens (measured in cycle 1)
that the user cannot shorten and compaction cannot forget, because it is held outside
`messages` on purpose. Reproduction: `AXIOM_DEBUG_MAX_CONTEXT=200`, then anything at all.

**A fix that only compacts harder cannot meet AC 4.** When the non-negotiable part alone
exceeds the context, something has to give - and AC 6, saying plainly that the session cannot
continue, is a legitimate destination where advising a shorter message is not.

**No cycle ever ends with a question.** This runs unattended and the queue runs loops back to
back; a cycle that stops to ask burns every remaining cycle until the fail-safe and strands
#43 behind it. Decide, record the decision and the reasoning in the cycle log, continue. The
exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each one rather than
confirming it. That pass has now caught a real defect twice running - #40's AC 7 and #41's
AC 9 - each after the implementing cycle had marked it met, and both by a hostile input
rather than by rereading code.

**Before regenerating the golden transcript, read the whole diff as a diff.** #41 cycle 2
regenerated off pytest's summary, which names the first differing index only, and destroyed
two compaction scenarios. It was restored; do not relearn this.

## Exit

Three ways out. **Every one of them ends by handing over per `queue.md`** - #43 is the next
row, and a converged run scaffolds it rather than stopping silently.

1. **Converged** - all 8 criteria met with evidence, the recovery ones from a real session,
   suite green and hermetic, transcript accounted for. Commit, push, open a PR referencing
   #42, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new GitHub issue in #42's format
   carrying only the criteria that did not land. State in the log why it did not converge.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and state plainly what is broken and what the next iteration must settle
   first.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** delete this cron, mark #42's row done in `queue.md`, and scaffold
row 8 - #43, `43-mcp-servers` - per the handover procedure.

**#43's scaffold carries two things forward.** The no-questions rule, stated as decisions
rather than open questions. And **the MCP clause in `CLAUDE.md`'s testing section**, which
binds that loop specifically: no test fetches a server, the in-memory transport settles
nearly everything, a real process is a script the repo owns, and no test contacts a hosted
server or needs a real secret.

**First run: 2026-08-26 02:58 IST (cron fires at :13, :28, :43, :58). Fail-safe deadline:
2026-08-26 14:58 IST.**
