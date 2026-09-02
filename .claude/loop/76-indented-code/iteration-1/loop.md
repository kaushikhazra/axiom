# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Branch:              feature/76-indented-code
Issue:               https://github.com/kaushikhazra/axiom/issues/76

Every 15 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     take the exit below
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-09-02 06:15 +0530, take the exit below, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions —
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state at
that cycle and are never edited afterwards.**

**The artifact already exists.** This changes how one branch of the markdown renderer works,
not a blank file. The suite entering this loop is **876 passed, 1 deselected, ~89s**, and
`master` is at `936fd1e`. Cycle 1 reads and records before it writes anything.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`. This
folder holds the loop's own files and logs, nothing else.

**Work on `feature/76-indented-code`.** Check the branch before writing.

## This row is in the queue

Row 19 of [`../../queue.md`](../../queue.md). **On reaching either exit — converged or
fail-safe — follow the queue's `Handing over` procedure.** Mark row 19 done, scaffold row 20
(`81-remote-mcp`), mark it running, and say what started. **Do not delete the cron**: one cron
serves the whole queue, and row 20 is still waiting.

**Do not merge.** Row 18 finished unmerged and this one does too — #72, #73 and #74 are
already owed a manual pass and this touches the same renderer. Commit, leave the branch, and
say in the handover that the merge is Kaushik's after that pass.

## Why this is a bug and not a feature

A model that writes its example indented rather than fenced is writing valid Markdown, and
axiom loses the end of every line of it. The user asked a question, got an answer with a
worked example in it, and can read all of the answer except the part that was the point.

**Nothing about the reply says anything is missing.** That is the shape this shares with #42
and with every truncation: the visible failure is not that something looks wrong, it is that
something looks fine and is not.

## The order to take it in

1. **Measure the defect before touching anything.** Capture what a real indented block does
   today, through `tests/screen.py`. Cycle 1 does not write code.
2. **AC 4 first, before any recognition rule.** #73 shipped nested lists; the obvious rule for
   this issue breaks them. Pin the existing behaviour with a test that would catch it.
3. **Then AC 1, 2, 3** — the block shown, shown in full, and set apart.
4. **Then the boundaries**: 7, 8, 9, 10 — the window's exact width, one past it, a line of only
   spaces, and many lines as one block.
5. **AC 5, 6, 11, 12, 13 are the regression half** and are checked every cycle, not once at the
   end. The renderer is shared.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the diff
and before the previous log.
