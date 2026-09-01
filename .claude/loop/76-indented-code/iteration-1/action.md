# Action — cycle 1

**Read and record. Do not write code.**

The renderer already exists and works for twelve other constructs. A cycle that starts editing
it before anyone has looked at what an indented block actually does today is guessing, and the
guess will be "four spaces means code", which undoes #73.

## Before anything else, two checks

1. **`git status`** and **`git branch --show-current`** — this must be
   `feature/76-indented-code`. A cycle that wakes on `master` switches and does not commit.
2. **`gh issue view 76`** — the criteria, read before the code and before this file's
   assumptions.

## 1 — Capture what happens today

Through `tests/screen.py`, not by reading `_styled`. Write a throwaway under `.tmp/` that
feeds a reply through the rendering path and prints what the screen holds. Four cases at
minimum:

- a block of three lines indented four spaces, each **wider than the window**;
- the same block with each line **narrower** than the window;
- a nested list four spaces deep — **this must still be a list** (AC 4, #73's behaviour);
- a fenced block, for the comparison AC 3 and AC 5 are about.

**Record what you see, verbatim, in the log.** The issue says lines are lost; that is a report,
not a measurement. Find out whether they are truncated, wrapped to column zero, padded, or
something else, and at exactly which column it goes wrong. Every later cycle's fix is aimed at
whatever this finds.

## 2 — Pin AC 4 before anything can break it

One test, from #73's own behaviour: a list item indented four spaces is a list item at its
depth and is not code. It should pass today. **Break it anyway** — a rule that says "four
leading spaces is code" placed ahead of the list check — and watch it go red. That break is
what every later cycle is protected from.

## 3 — Establish the baseline numbers

- `uv run pytest` — count, pass, wall-clock. Expect **876 passed, 1 deselected, ~89s**.
- `tests/baseline/transcript.txt` — record that it is untouched. It has not moved in fifteen
  cycles across three issues.
- `uv run --no-sync python .claude/loop/cited.py tests/test_rendering.py` (or whichever file
  holds #60's and #73's tests) — see what is already claimed, so this row does not write a
  second test for something already covered.

## 4 — Name the design question, do not answer it

`assumption.md` states the tension: AC 10 wants many lines shown as one block, and #60 AC 8 and
AC 10 forbid holding lines back. The likely shape is **state rather than a buffer** — the
classifier remembering a block is open, exactly as `self._fence` already does. **Write down
what the measurement in step 1 implies about that**, and leave the decision to cycle 2, which
starts with the evidence in hand.

## Do not

- Write or change any code in `src/`.
- Add a rule that treats leading spaces as code without the list check ahead of it.
- Regenerate the baseline.
- Use a heredoc for anything containing a backslash escape.
- Merge.

## Record

`logs/cycle-1.md`, per `observe.md`. Then write `action.md` for cycle 2 from what the
measurement showed.
