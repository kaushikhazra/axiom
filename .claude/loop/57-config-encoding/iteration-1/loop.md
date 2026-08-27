# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)
Issue:               https://github.com/kaushikhazra/axiom/issues/57
Branch:              feature/57-config-encoding
Queue:               C:/Projects/axiom/.claude/loop/queue.md

Every 15 minutes, ONE cycle:
  - Action:  work on C:/Projects/axiom/src/ and tests/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - Log:     write logs/cycle-N.md
  - If goal met:     merge, delete this cron, hand over to row 12 (#55)
  - If goal not met: write the next action.md, then exit this run

Fail-safe: 2026-08-28 04:21 IST - four hours of wall clock from the first cycle.
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

**9 criteria, and the fix is one codec name in four places.** The work is not the fix. It is
proving the fix does not quietly leave a byte order mark glued to a server's name, and proving
the decoder did not become permissive about things it should still refuse.

**This row exists because every test wrote its config the one way that cannot fail.** Python's
`write_text(encoding="utf-8")` never emits a mark; PowerShell's `Set-Content -Encoding utf8`
always does. 453 green tests and six hostile cold reads did not find it. Kaushik found it in
five minutes by writing the file the ordinary way for his platform. **Write bytes in the tests
here, not strings** - the criterion is about a file another program wrote.

**The golden transcript must not change.** This row alters how bytes are decoded and nothing a
user sees. A regeneration would be a mistake, not a decision. Copy it aside in cycle 1 and
`diff` it at the end.

**Do not touch `tools.py`.** Its two `utf-8` reads are arbitrary user files opened by a tool,
not axiom's configuration, and a mark there decodes to a character rather than raising. Out of
scope, by decision, recorded in `assumption.md`.

**No cycle ever ends with a question.** Decide, record the decision and the reasoning in the
cycle log, continue. The exception is safety, not uncertainty - see exit 3.

**The cycle that writes the code never declares it done.** A separate cycle reads the criteria
from GitHub before the diff and before the previous log, and attacks each rather than
confirming it. That pass has found a real defect in **six consecutive issues**. Two of the most
recent were criteria *read too loosely by the implementing cycle*, with the test then written
from the implementation rather than the issue - so read the issue text first, and literally.

## Exit

Three ways out. **Row 12 (#55) is queued behind this one**, so every exit ends by handing over.

1. **Converged** - all 9 criteria met with evidence, suite green and hermetic, transcript
   byte-identical, a PowerShell-written file read without complaint. Commit, push, open a PR
   referencing #57, **merge it**, delete the branch.
2. **Fail-safe reached, suite green, behaviour preserved** - commit and push what is proven,
   open a PR, **merge it**, delete the branch, then open a new issue in #57's format carrying
   only the criteria that did not land. With 9 criteria this should not happen.
3. **Fail-safe reached, suite red or behaviour unexplained** - **do not merge.** Leave the
   branch, push it, and say plainly what is broken.

Never merge a red suite. Never merge a behaviour change the transcript has not cleared.

**Then, in the same run:** delete this cron, mark #57's row done in `queue.md` with the PR
number, cycle count and wall-clock time, scaffold
`.claude/loop/55-announce-the-file/iteration-1/` per the queue's handing-over procedure, create
its cron, and say what its first cycle will do.

**First run: 2026-08-28 00:21 IST (cron fires at :06, :21, :36, :51). Fail-safe deadline:
2026-08-28 04:21 IST.**
