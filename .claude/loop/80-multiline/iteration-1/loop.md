# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Branch:              feature/80-multiline
Issue:               https://github.com/kaushikhazra/axiom/issues/80

Every 15 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     take the exit below
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-09-02 04:00 +0530, take the exit below, converged or not.
```

## This row is in the queue now

Rows 1 to 17 of [`../../queue.md`](../../queue.md) ran under it; this loop's first eight
cycles did not, because the queue was empty when it started. It is **row 18** now, and that
changes the exit and nothing else.

**On reaching either exit — converged or fail-safe — follow the queue's `Handing over`
procedure.** Mark row 18 done, scaffold row 19 (`76-indented-code`), mark it running, and
say what started. **Do not delete the cron**: one cron serves the whole queue, and deleting
it here would end the chain with two rows still waiting. It is deleted only after row 20.

**Do not merge.** #80's key presses and pastes are unverified — thirteen criteria are on
`manual-pass.md` waiting for a person at a real terminal. Commit, leave the branch, and say
in the handover that the merge is Kaushik's after that pass. That is not exit 3; nothing is
blocked. It is a row finishing with work owed to a human, which the queue expects.

## The tests that press keys are gone, and none comes back

Nineteen of them built a real `prompt_toolkit` session, and running them took Kaushik's
machine down **twice**. Deleted in `32daf51`; the reason is in `tests/test_multiline.py`'s
docstring, in `tests/conftest.py`, and in the queue's **Standing**.

**Nothing this loop does may reintroduce one.** Reach the reader through the `use_compose`
hook or through `builtins.input`. What is left to build here — AC 21 — needs no key press,
and neither do the criteria still waiting for a proof.

## What "goal met" resolves to, now that thirteen criteria are a person's

`goal.md` and `observe.md` do not change, and `observe.md` says met is all 36 in bucket 1.
**Thirteen of them can no longer enter bucket 1 from a test process** — AC 1, 2, 3, 4, 7, 8,
9, 10, 12, 18, 24, 25, 26 are key presses and pastes. Read against the prohibition above,
`observe.md`'s own section *"What cannot be tested from a test process, and must be said out
loud"* already anticipates this: those criteria belong to the manual pass, and the loop's job
is to hand them over rather than to claim them.

So this loop is **done** when:

- the **23 criteria a test can reach** are all in bucket 1 — met with a break watched going
  red — namely 5, 6, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 27, 28, 29, 30, 31, 32, 33,
  34, 35, 36;
- `uv run pytest` is green and `tests/baseline/transcript.txt` is untouched;
- `manual-pass.md` lists every one of the thirteen with what to do and what should happen.

**Say the split in the handover** — 23 by test, 13 by Kaushik — and never report it as 36.
A count that folds the manual thirteen into the tested total is the same mistake cycle 7
found eleven times over, and it would be a worse one: it would say verified about something
nobody has looked at.

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
