# Action — cycle 2

**The wrapping. That is the bug and everything else is arrangement.**

Cycle 1 measured it: an indented line longer than the window less two is **cut**, not wrapped.
`"    def settle(host, named, installed, remembered):"` — 51 characters — comes out as 39
columns on a 40-column screen. Twelve characters gone, silently.

## Before anything else, three checks

1. **`git status`** and **`git branch --show-current`** — must be `feature/76-indented-code`.
2. **`gh issue view 76`** — the criteria, before the diff and before cycle 1's log.
3. **`uv run --no-sync python .claude/loop/cited.py tests/test_indented_code.py`** — what this
   row's tests claim so far. Should say AC 4 only.

## 1 — Build the wrapping (AC 1, AC 2)

**Reach for `_nested`, not for a new pattern.** #72 solved the identical problem for a nested
list item: a terminal wraps to column zero, so `_nested` measures the room left beside the
marker and draws the text into it, pushing every row after the first out to where the first
row's text began. An indented block is the same shape with a different lead.

Where it goes: `_styled`, **after** the fence check and **after** `self._nested(line)` — cycle
1 proved that putting it before takes four of #73's tests with it, and both AC 4 pins go red.

What the recognition rule must be, given AC 4:

- four or more leading spaces, **and**
- `self._nested(line)` returned `None`, **and**
- no list is currently open — `self._levels` is what already tracks that.

## 2 — Prove it with breaks, not with a screenshot

Two tests through `tests/screen.py`, and one break each:

- **AC 1** — a block of three lines, each longer than the window, and every character present.
  Break: restore the cut, `[: _width() - 2]`.
- **AC 2** — the same at a **narrow** window, 20 columns, where the wrap has to happen twice.
  Break: wrap at a fixed 80 rather than at `_width()`.

**Assert on the joined screen text, not on the byte stream.** The plain echo puts the
characters in the stream whatever the renderer did — that is the shape of all six of #60's
vacuous tests, and the queue's Standing names it.

## 3 — Then AC 3, which is a decision

> It is set apart from the prose around it, **the way a fenced block is**.

Cycle 1 found the two are set apart *differently*: an indented block gets Rich's hardcoded
`48;5;235` grey background across the full width; a fenced block gets no background at all and
is marked by its dim fence markers. They cannot both be right.

**Decide it in the cycle and record the reasoning** — the queue's Standing says a loop decides
rather than asking. The reversible, least-surprising reading is that AC 3 asks for the *same*
treatment a fenced block gets, since that is what it says, and `_MARKDOWN_STYLES`' comment
already records #77's position that a block with no lexer carries no styling at all. Note that
this also closes the crack cycle 1 found in #77 AC 20.

## 4 — Re-measure AC 7 and AC 8 afterwards

Both are boundaries against the window, and both were measured against a block whose indent had
been collapsed to one column. **Once the wrapping lands, measure them again from scratch.**

AC 8 is currently violated because the collapse bought three columns back. **Do not amend the
criterion to match whatever the implementation then does** — that is the failure #48 and #49
were caught by. Measure, then meet it.

## 5 — AC 10, with cycle 1's evidence

Rich emits a background-only row above and below **each line's** block. Three consecutive lines
showed no gap today, but the fix changes what is emitted. **Check it again after the wrapping
lands**, and if a gap appears, the answer is state — `self._fence` already does exactly this
job — and not a buffer. Holding lines back is barred by #60 AC 8 and AC 10.

## Do not

- Put the indent check ahead of `self._nested`. Four of #73's tests and both AC 4 pins.
- Amend a criterion to match what the code does.
- Assert that text is present in the byte stream and call it a screen check.
- Regenerate the baseline.
- Use a heredoc for anything containing a backslash escape.
- Leave a break in the file. Check `git diff` before finishing.
- Merge.

## Record

`logs/cycle-2.md`, per `observe.md`. Then write cycle 3's action from what is left.
