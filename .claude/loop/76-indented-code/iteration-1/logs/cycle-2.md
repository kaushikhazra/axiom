# Cycle 2 — converged, and five tests could not have failed

2026-09-02, 02:21–02:47 +0530. Branch `feature/76-indented-code`. Row 19 of the queue.

## The measurement

**Criteria demonstrably met: 13 of 13**, each proved by a break watched going red.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **13** | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 |
| 2 — implemented, not proved | 0 | — |
| 3 — not started | 0 | — |

Twelve moved. `.claude/loop/cited.py` reports 13 claimed against 13 in the issue.

## The fix, and it is twenty lines

`Rendered._indented`, called from `_styled` **after** the fence check and **after** `_nested`:

- four or more leading spaces, no list open (`self._levels` empty), and something after
  the indent;
- the indent is **kept** — the model's own, not one axiom invented;
- the text is sliced at `_width() - len(lead)` and every row after the first is written at
  the same indent, so the block stays a rectangle;
- the text is **not** run through `_as_markdown`. It is code: `**bold**` inside it is two
  asterisks and a word.

**Nothing is painted, and that is AC 3's answer.** Cycle 1 found an indented block getting
Rich's hardcoded `48;5;235` background across the full width while a fenced block gets none at
all. `_MARKDOWN_STYLES` already records #77 AC 20's position — a block nobody can lex is
delimited, not coloured, because a colour is a claim about the content that nothing supports.
Applying it here makes the two consistent and closes the crack cycle 1 found in that comment.

Placement is the whole of AC 4, and cycle 1 had already proved what happens if it moves.

## Five things that could not have failed, and every one was found by a break

Not one of these was visible by reading. This is the cycle's real content.

**1 — `test_no_row_is_wider_than_the_window` was impossible.** It asked the modelled screen for
rows wider than the window. `Screen` *wraps* at its width, so `len(row) > width` is never true
there, for any renderer. The break — the wrap left to the terminal, exactly what the test was
written to catch — went straight through it.

**2 — AC 2 measured characters and not the window.** `reassembled(...) == LINE` at four widths
stayed green against a renderer wrapping at a fixed 80 columns: the whole line fits inside 80
however narrow the window is, so nothing was lost and nothing was right either. A criterion
about "however narrow the window" needs the window in the assertion. It now asserts the row
count the window demands.

**3 — AC 9 filtered out the thing it was looking for.** *"The non-blank rows are `before` and
`after`"* — and a stray row left by a blank line is blank. It survived a break that drew the
empty line as a block.

**4 — AC 11 never consulted `--no-render`.** A test process is not a terminal, so the plain
path was taken because of `isatty` and the rendering flag was never reached. Removing
`not _rendering` from the gate left the test green. It now forces a terminal, which is the only
state where `--no-render` means anything.

**5 — a helper tidied the input it was asserting was untidy.** `reassembled` used
`row.strip()`. At 20 columns the wrap falls inside `"host, named"`, so a row begins with a space
that belongs to the code — and stripping it deleted a character from the very thing the test
was checking had not lost any.

> **A helper that tidies its input cannot then assert the input was untidied.**

## Three breaks were no-ops, and they read exactly like a passing test

`observe.md` warns that roughly one break in four is aimed at the code rather than the
criterion. Three of fourteen here, and the harness reports them identically to a real survival —
which is the trap #60 named and has not been solved.

- **AC 7 broken with "the cut restored".** The cut cannot change a line that already fits. Nothing
  happened, and it printed `STAYED GREEN`. Replaced with an off-by-one in the room.
- **AC 13 broken with the fence-first placement.** That costs highlighting and not one word, and
  the sample had no fence in it. Replaced with the cut — and then the *sample* had to grow,
  because a truncation that never has to truncate loses nothing either.
- **AC 9 broken twice with blank rows.** Returning `""`, and returning two rows of spaces, are
  both absorbed by #60's erase: `\x1b[J` goes out before every committed line, so a row of
  whitespace is cleared before anything sees it. **That is a real structural property** and it
  is why AC 9 held before this cycle began. The break that worked draws *content* for an empty
  line, which is what "prints nothing" actually forbids.

## Which instrument answers which criterion

The two disagree, and each is right about a different thing.

- **`tests/screen.py` for position** — how many rows, where the indent sits, what a block that
  fits looks like. It erases and it wraps, exactly as a terminal does.
- **The committed rows for exactness** — did every character arrive, did the renderer place the
  wrap. `Screen.text()` right-strips a row, because on a terminal a trailing space is invisible;
  at 12 columns a chunk boundary lands so that a row *ends* with the space after `"named,"`. The
  character is on the screen, occupying a column that draws the same as nothing. **The screen
  model is right to drop it and cannot answer "did every character arrive".**

## AC 8 and AC 13 pull against each other

AC 8 says a block one character wider than the window is drawn on two rows **with that character
on the second**, which forces a hard wrap by column — and a hard wrap splits `named,` into `nam`
and `ed,`. Read literally against the drawn rows, AC 13's "the same words" is then false for any
block that wraps mid-word, and **no implementation can satisfy both**.

The same shape as #80's AC 11 against AC 14. Resolved the same way: read each at the level it is
about. AC 8 is about rows; AC 13 is about the reply, so the rows are put back into lines first.
`closed_up` does that, and its own first two versions were wrong — a fixed four-space lead put
four stray spaces into the middle of an eight-space line, which split one word into two.

**Neither criterion was amended.** That is the failure #48 and #49 were caught by.

## One thing observed and left alone

A whitespace-only line commits a row containing its spaces — measured, `['', '    ', '']`
between `before` and `after`. The erase takes it back, so nothing reaches the screen and AC 9
holds. It is what *every* whitespace-only line has always produced, indented or not, so it is
not this issue's to change. Recorded rather than fixed.

## The suite

    878 entering
    +14 added       AC 1, 2, 2b, 3, 3b, 5, 6, 7, 8, 9, 10, 11, 12, 13
    892 leaving     892 passed, 1 deselected, 78.63s

The arithmetic adds up. Wall clock flat against cycle 1's 78.56s with fourteen more tests.

`tests/baseline/transcript.txt` **unchanged** — sixteen cycles across four issues.

## Assumptions changed

**One.** `assumption.md` said AC 10 pulls against #60's ban on holding lines back, and that the
answer would probably be state rather than a buffer. **Neither was needed.** Consecutive lines
each drawn with the same treatment already read as one block, because what made Rich's version
look like separate blocks was the background rows it painted around each one — and dropping the
paint dropped them. AC 10 came free with AC 3.

## What only a person can confirm

Written to `manual-pass.md`. Added to what #72, #73 and #74 already owe.

## Goal check

**Met.** 13 of 13 in bucket 1, suite green, baseline untouched, manual list written.

**Not merged**, per `loop.md` — this touches the renderer #72, #73 and #74 are all still owed a
manual pass on.

## Handing over

Row 19 done. Row 20 — `81-remote-mcp` — scaffolded and running.
