# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Branch:              feature/80-multiline
Issue:               https://github.com/kaushikhazra/axiom/issues/80

Every 20 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-09-02 01:00 +0530, stop and delete the cron, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions —
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state
at that cycle and are never edited afterwards.**

**The artifact already exists.** This replaces how axiom reads a line, not a blank file.
The suite entering this loop is **876 passed, 1 deselected, ~92s**, and `master` is at
`936fd1e` with #77 merged. Cycle 1 reads and records before it writes anything.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`. This
folder holds the loop's own files and logs, nothing else.

**Work on `feature/80-multiline`.** Check the branch before writing.

## Why this is a bug and not a feature

Measured on 2026-09-01, three lines pasted into a running axiom:

    >
    Please provide the rest of your request.

    >
    Please provide the full text or instructions you would like me to work with.

    >
    Please provide the full text or instructions you would like me to work with.

Three turns, three requests paid for, three useless answers, and the message the user meant
was never assembled. The history now holds three fragments that will confuse every turn
after them. **That is the thing being fixed** - "you cannot type two lines" is the smaller
half of it.

## The order to take it in

1. **Survey, then decide the reader.** `prompt_toolkit` is a candidate, not a conclusion.
   Whatever is chosen owns backspace, arrows, home, end and history from that moment on.
2. **The terminal-only split first**, before any key handling. If a piped run can reach the
   new reader, the golden transcript moves and several hundred tests change meaning.
3. **Paste before typing.** AC 9 - nothing sent while a paste is still arriving - is what
   makes this a bug, and it is the hardest to get right.
4. **Then the binding**, ctrl+enter and enter.
5. **Then the edges**: commands, blank lines, oversized pastes, abandoning a compose.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
diff and before the previous log.
