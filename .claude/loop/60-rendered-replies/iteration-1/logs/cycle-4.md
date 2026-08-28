# Cycle 4 — the cold read

**Four real defects**, in a row that cycle 3 ended by marking all 29 criteria met with
evidence. Twelve for twelve now, across #40 to #43, #48, #49, #57, #55, #56, #61, #62 and
this one.

**Commits** `fix(#60): every paragraph longer than the window was drawn twice`,
`fix(#60): syntax highlighting, ragged tables, and a reply leaking into the next`
**Suite** 597 → **603**, green with no Ollama running. **Transcript unchanged.**
**Breaks** 18 → **25**, no survivors.

---

## How cold this read was

**Not fully cold, and it matters.** The criteria were read from GitHub first, before the
logs and before the diff, as the method requires. But the reader was the same session that
wrote cycles 2 and 3. A separate agent was not used: this session runs under a standing
instruction not to spawn one unless Kaushik asks, so one was not available to ask.

What stood in for it was **modelling the terminal** rather than reading the code again.
Three of the four findings came from inputs run through a simulated screen; none came from
re-reading. That is the same lesson as #40 to #43 - *hostile inputs, not re-readings* - and
it is the part of the method that survives an imperfect reader.

---

## Finding 1 — AC 7 was not met at all

**Every paragraph longer than the window was drawn on screen twice.**

A model writes prose as one long line. At 80 columns that wraps to three rows. The renderer
took the line back with `\r` and erase-to-end-of-line, which returns to the start of the
**third** row and clears only that. The two rows above kept the raw echoed text; the styled
line was written below them.

```
width 40, before the fix
    'This is one very long paragraph on a sin'
    'gle line, the way a model actually write'
    's prose, and it is far wider than any te'
    'rminal window someone would have open wh'
    'This is one very long paragraph on a sin'      <- again
    'gle line, the way a model actually write'      <- again
    's prose, and it is far wider than any te'      <- again
    'rminal window someone would have open wh'      <- again
    'ile reading it.'
```

Cycles 2 and 3 both marked AC 7 `met-with-evidence`. **The evidence was true**: no cursor-up
sequence appears anywhere in the byte stream, and none did. The promise was a proxy for the
criterion, and it was the wrong proxy — it held perfectly while the screen showed the answer
twice.

The cursor now moves up by exactly the rows *the unfinished line* occupies, which cannot
reach a line already committed. That is what AC 7 asks for in its own words: nothing shown
is repositioned, nothing printed twice. Rows are counted with `cell_len`, not `len`, or a
line of Chinese wraps at half the character count and leaves a row behind.

**`tests/screen.py` is the lasting part of this cycle.** A terminal small enough to reason
about — `\r`, `\n`, cursor-up, the two erases, text with wrapping and wide characters. It is
the only honest way to assert AC 7, AC 11 and AC 12, and it would have caught this on the
day the renderer was written. Counting escape sequences says what was *sent*; these criteria
are about what is *on the screen*, and the two stop agreeing at exactly the point that
matters.

## Finding 2 — AC 2 asks for syntax highlighting, and there was none

The criterion reads *"a fenced code block is shown as a block, set apart from the prose
around it, **with syntax highlighting when the fence names a language**"*. Both earlier
cycles answered the first half and recorded a reason for skipping the second: a line lexed
alone guesses at context it does not have, and the middle of a triple-quoted string is not
code.

**The reason was sound and the conclusion did not follow.** Lex the block, not the line.
The whole fence so far is lexed and only the new line's rendering taken, so context is
kept and no committed line is ever redrawn.

This is the shape the queue already names — *a criterion read too loosely by the cycle
that implemented it* — and it is the third time in this row that a decision was recorded
persuasively enough to stop anyone checking it against the sentence it was answering.

The context is **bounded at 20 lines**, because lexing the whole block per line is
quadratic. Measured: 7.2ms a line at 10 lines, 29 at 200, **71 at 500** — 35 seconds of CPU
for one block, a visible stall and so an AC 10 failure. Held to a window the cost is flat
and linear in the window: 2.2ms at 5, **6.1 at 20**, 16.0 at 60, 28.3 at 120. Twenty is
well inside the gap between two streamed lines and more context than a chat reply's
multi-line string plausibly needs.

## Finding 3 — a ragged table came back as a paragraph of pipes

AC 23 names this case exactly: *"a table with a row of the wrong width"*. Rich cannot parse
one and does not say so — it draws the rows as a paragraph, so four rows came back run
together into a single wrapped line:

```
before:  '| a | b | c | | --- | --- | | 1 | | 2 |'
         '3 | 4 | 5 |'
after:   '| a | b | c |'
         '| --- | --- |'
         '| 1 |'
         '| 2 | 3 | 4 | 5 |'
```

Every character was present, which is why the AC 5 tests were content, and none of it was
readable. Whether Rich *drew a table* is now asked explicitly, by looking for the rule it
puts under a header; anything else goes back exactly as the model wrote it.

## Finding 4 — a failed reply leaked into the next answer

A failed turn is the only route out of the loop that does not pass `end_reply`. So the
renderer kept the dead turn's half-finished line, and the next answer was fed into it:

```
> one
partial
> two
partial a fresh answer          <- the failed reply, glued to a new one
```

Nothing on screen says the first two words are from a turn that died. A user reads them as
the model's own. Settled inside `report_failure` rather than at the call site, because that
is the function that cannot be forgotten — and settling *after* the message would erase it,
since the erase runs to the end of the screen.

**The golden transcript could not have caught this.** It is captured with output redirected,
which is the plain path, where there is no renderer to hold anything. That answers the
question cycle 4's action raised about AC 17, AC 18, AC 19 and AC 29 all resting on the
transcript: for anything that only exists when rendering is on, **it does not cover them**,
and one of those four had a real defect behind it.

---

## A fifth vacuous test

`test_no_color_set_to_nothing_still_counts` asked for the fallback colour inside a
` ```python ` fence — where the highlighter now runs and there is no fallback colour to find
whatever the code does. Found by its break surviving. That is **six** vacuous tests in this
row: three in cycle 2, two in cycle 3, one here. Every one asserted something that was true
for a reason other than the one it claimed.

---

## What was attacked and came back clean

A cold read that reports "all good" without saying what it tried is worth nothing, so:

| Input | Result |
|---|---|
| CRLF line endings throughout | clean — the `\r` is absorbed, lines commit normally |
| a lone `\r` mid-line | clean — rendered as a space, not as a cursor move |
| a fence opened while table rows are held | clean — the table settles, then the fence opens |
| a table arriving one character at a time | clean — drawn identically |
| a reply that is a single `\|` | clean — shown as itself |
| a heading immediately followed by a fence | clean |
| 200 blank lines then text | clean |
| an unclosed fence at the end of a reply | clean — content shown, no hang |
| a tab-indented line | clean — content kept |
| a 200-line reply, no truncation or ellipsis | clean |
| width changed seven times mid-reply | clean |
| a reply of 200 code lines | clean, and bounded |

Two criteria were re-examined and found sound rather than merely asserted: **AC 14 and
AC 15** — the two ways to reach the plain path (not a terminal, and the switch) are the same
branch, not two branches that happen to agree. **AC 18** now has an assertion against a
*rendered* session rather than only against the transcript.

---

## Status of all 29

**Met, with evidence, after this cycle's four fixes.** 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28.

**Met by the transcript being unchanged**, and now additionally by a rendered-session
assertion for 17 and 18: 19, 29.

---

## What cycle 5 does

**A second cold read**, because this cycle found the defects *and* fixed them, which is
exactly the arrangement the rule exists to distrust. It is a shorter pass: read the four
fixes against the criteria they claim to satisfy, and attack the new code — the erase
arithmetic, the lexing window, the table test, the settle-on-failure — the way this cycle
attacked the old.

If it comes back clean, that is exit 1 and the queue is finished.
