# Cycle 1 — the defect measured, and it is not what "lines are lost" suggested

2026-09-02, 02:15–02:12 +0530. Branch `feature/76-indented-code`. Row 19 of the queue.
**No code written**, per `action.md`.

## The measurement

**Criteria demonstrably met: 1 of 13.**

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **1** | 4 |
| 2 — believed true, not proved for this issue | 6 | 5, 6, 9, 11, 12, 13 |
| 3 — not met | 6 | 1, 2, 3, 7, 8, 10 |

## What actually happens today

Measured through `tests/screen.py` at 40 columns, and then again at the byte level because
one criterion is entirely about paint and the screen model discards colour.

**An indented line longer than the window is truncated. Not wrapped — cut.**

    the model wrote:   "    def settle(host, named, installed, remembered):"      51 chars
    the screen shows:  " def settle(host, named, installed, rem"                  39 columns

Twelve characters gone, and nothing anywhere says so. That is AC 1 and AC 2, and it is the
same shape as #42: the failure is not that something looks wrong, it is that something looks
fine and is not.

**The four-space indent is collapsed to one.** `    one` is drawn as ` one`. Rich renders the
line as a code block with one column of padding, and the block's usable width is the window
less two — which is exactly where the cut falls.

**It is painted, and painted differently from a fenced block.**

    indented:   \x1b[48;5;235m ... \x1b[38;5;231m one \x1b[0m   plus a background-only row
                above and below, padded across the full width
    fenced:     \x1b[2m```python\x1b[0m   then   \x1b[49mone = \x1b[0m\x1b[94;49m1\x1b[0m
    prose:      no escape sequences at all

So an indented block gets a **hardcoded 256-colour grey background** — Rich's own
`markdown.code_block` default — while a fenced block gets **no background at all** and is set
apart by its dim fence markers. AC 3 asks for "set apart from the prose around it, **the way a
fenced block is**", and today the two are set apart in different ways. Whichever way this
lands, it is a decision about matching them, not about adding paint.

**This also puts a crack in #77 AC 20.** `_MARKDOWN_STYLES`' comment says `markdown.code_block`
"only ever reaches a block nobody has a lexer for, and AC 20 says that one carries no styling
at all". True for a *fenced* block with an unknown language — it comes out at `\x1b[49m`. False
for an indented one, which never goes through `_highlighted` and lands on Rich's default.
Nobody was wrong; the comment was written before this path was known to exist.

## What already holds

- **AC 4 — a four-space item inside a list is a list item.** #73's `_depth` stack. Pinned this
  cycle and break-proven.
- **AC 5 — a fenced block is unchanged**, highlighting included: `\x1b[94;49m` on the numeral.
- **AC 9 — an indented line of only spaces prints nothing**, and leaves no row behind.
- **AC 7's second half** — no empty line after a block exactly as wide as the window.

## AC 8 is violated, and reading it carefully matters

> An indented block one character wider than the window is shown on two, with that character
> on the second.

At 40 columns, a line of 4 spaces and 37 `x` — 41 columns as written — is drawn on **one** row,
not two. Every `x` survives, because the indent collapse bought three columns back.

So the criterion is not met, and it is also **written on an assumption that the block occupies
the full window**. Once AC 1 and AC 2 are fixed the assumption may become true, and this
resolves itself. **Do not amend the criterion to match the implementation** — that is the
failure mode #48 and #49 were caught by, criteria read too loosely by the cycle implementing
them. Fix AC 1 and AC 2 first and measure AC 8 again afterwards.

## AC 4, pinned before anything can break it

The naive rule for this issue — *four or more leading spaces is a code block*, which is what
Markdown's own spec says at the top level — placed ahead of the list check in `_styled`:

    break: "four leading spaces is code"     both pins went red
    what it also took: 4 failed, 150 passed in tests/test_rendering.py

**Four of #73's own tests go with it.** That is the argument for writing this pin in cycle 1
rather than discovering it in cycle 3 with a fix already written.

## `tests/test_indented_code.py`, and why it is a new file

`.claude/loop/cited.py` reads which criteria a file claims. `tests/test_rendering.py` holds
#60's, #72's, #73's and #77's, so "AC 7" in it could be any of four issues and the instrument
reports 30 criteria claimed with no way to say whose. **One file, one issue**, and the count
means something. Nothing moves out of `test_rendering.py` — its tests are those issues' and
stay where they are.

## The design question, named and not answered

`assumption.md` states it: AC 10 wants many lines shown as one block, and #60 AC 8 and AC 10
forbid holding lines back.

**The measurement narrows it considerably.** Today each indented line is already rendered
independently and the three lines still read as one block on screen — consecutive rows, no
separator, a shared background. So "one block rather than one block per line" may need no
holding at all: what makes them one block is that consecutive lines carry the same treatment
and the block's top and bottom rows appear once rather than between every pair.

Rich emits a background-only row **above and below each line's block**. At three consecutive
lines that is where a gap would come from, and it did not appear here — worth checking again
once the wrapping is fixed, because the fix changes what is emitted.

**Cycle 2 decides, with this in hand.** The likely shape remains state rather than a buffer:
`self._fence` already does exactly this job for fenced blocks, and an indented block is the
same thing with a different opener.

## The suite

    876 entering    master's baseline
    +2 added        the AC 4 pins
    878 leaving     878 passed, 1 deselected, 78.56s

`tests/baseline/transcript.txt` **unchanged**.

## Assumptions changed

None. `assumption.md`'s guess that the renderer's own path was the suspect is confirmed, and
its warning about AC 4 is confirmed with a number: four existing tests.

## What only a person can confirm

The grey background against a real terminal's own colours, and whether a fixed indented block
reads as one block beside a fenced one. Added to what #72, #73 and #74 already owe.

## Next

**Wrapping, which is AC 1 and AC 2 and is the bug.** An indented line must reach the screen
whole, at the window's width, and #72 already solved the same problem for a nested list item —
`_nested` wraps the text itself into the room beside the marker rather than leaving it to the
terminal. That is the pattern to reach for, not a new one.
