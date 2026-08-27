# Cycle 2 — the renderer, built and measured

**Commit** `feat(#60): render a reply as it arrives, without ever moving a line`
**Suite** 539 → **567**, green and hermetic. **Golden transcript unchanged.**

---

## What was built

One class in `terminal.py`, `Rendered`, wired to the two existing seams
(`show_piece`, `end_reply`). **Nothing above `terminal.py` changed** — the action asked
for that to be stated, and it holds: `__init__.py` was not touched.

### What makes a line final

The whole design is this one decision.

A line is committed when its newline arrives. From that instant it is styled, written
once, and never addressed again. The line *still being typed* is echoed **verbatim** as
it arrives — every character appears the moment it does (AC 10) — and when its newline
lands, the same line is re-drawn in place with `\r` + erase-to-end-of-line.

`\r` is what makes AC 7 and AC 10 compatible instead of opposed. The write moves to
column zero **of the line it is already on**; it cannot travel upward, so it cannot
reach anything committed. **No cursor-up sequence is ever emitted** — a stronger and
far easier claim to test than "a line does not move".

Inside a fence, a line's *content* is fixed even though the block is not, so it is
committed as code as soon as its newline arrives rather than held until the fence
closes (AC 8). Code lines are not syntax-highlighted individually: highlighting one
line in isolation guesses at context it does not have, and guessing wrongly about
code reads worse than not colouring it. The fence is marked dim, its contents cyan.

`rich.Live` is not used, for the reasons measured in cycle 1: it emits `CURSOR_UP` once
per line of the previous render on *every* chunk, and truncates to the screen height
with an ellipsis.

---

## The measurements

| | Claim | Result |
|---|---|---|
| AC 7 | no cursor-up in a reply 3× the screen | **0 sequences**, 99 source lines → 99 committed |
| AC 5 | every non-markup character sent appears | **none missing** |
| AC 9 | `##` split across four-character chunks | emitted literally, unstyled, until complete |
| AC 8 | fence content before the fence closes | committed as cyan code |
| AC 14 | not a terminal | `"# Heading\nand **bold**\n\n"` — byte-identical, no escapes |
| AC 28 | renderer forced to raise | the line comes back as plain text |

Text is fed **four characters at a time** everywhere, because that is what a real
stream delivers — measured in cycle 1 at 77 chunks, mean 4.1 characters.

---

## Break and watch

Eight plausible-but-wrong implementations, each a shape someone would reach for who
had not measured. Harness at `.tmp/break60.py`.

| Break | Caught by |
|---|---|
| redraws with cursor-up, the way `rich.Live` does | `test_no_line_is_ever_moved` |
| no styling — markdown left as literal markup | `test_markdown_is_styled` ×5 |
| holds the incomplete line back until its newline | `test_an_incomplete_line_is_shown_but_not_styled` |
| drops a line Rich cannot draw instead of passing it through | `test_markup_rich_renders_as_nothing_is_still_shown` ×4 |
| never flushes a reply that ended without a newline | `test_a_reply_that_ends_without_a_newline_is_still_finished` |
| code and prose styled identically | `test_a_fence_is_set_apart_from_the_prose` ×3 |
| lets Rich decide the console cannot show a hyperlink | `test_a_link_keeps_its_address` |
| trims padding with `rstrip`, which cannot reach past a reset | `test_a_block_element_is_not_padded_to_the_full_width` |

**No survivors.** But three of the six tests written *before* running this survived
their break, and that is the more useful half of the record:

- **the fence test compared the wrong thing.** It asserted the code line differed from
  the prose line — but `x = 1` and `prose` differ whatever the styling. Vacuous. It now
  compares the escape sequences on each.
- **the trailing-line test asserted presence.** `"the end" in output` was already true
  from the plain echo, so a renderer that never flushed passed it. What `finish` owes is
  the *ending*: the line styled like every other, and a newline, so the next prompt does
  not land on the answer. That is what it now asserts.
- **the link test looked at the whole stream.** The raw `](https://example.com)` is in
  the bytes from the verbatim echo regardless of what the renderer does. It now looks at
  the committed line — what follows the last carriage return.

A fourth was environment-dependent: forcing `detect_legacy_windows` to `True` changed
nothing under pytest because it already returns `True` there. The forcing was dropped
rather than kept as decoration.

---

## Two real bugs, found only by breaking things

**A link lost its address.** Rich judges every Windows console unable to emit a
hyperlink and renders `see [the docs](https://example.com) for more` as `see the docs
for more`. The address — the one part a user cannot retype — was gone, silently.
`legacy_windows=False` makes Rich emit the OSC-8 sequence and the address survives.

> Residual risk, recorded rather than hidden: on a terminal with no OSC-8 support the
> address is in the byte stream but not visible. Windows Terminal supports it, and
> printing every URL twice would undo the point of rendering. The cold read may
> disagree; this is a decision, not an oversight.

**A quoted paragraph came out double-spaced.** Rich pads a block element to the console
width. A line padded to exactly the width, plus the newline this module writes, wraps to
a blank line. `rstrip` does not reach that padding — it sits *before* the closing reset
sequence.

---

## The judgement — one real reply, before and after

`qwen2.5:7b`, local Ollama, asked for a heading, bold and italic, two bullets and a
fenced function. **BEFORE** is what a terminal showed until today; **AFTER** is what it
shows now.

```
=== BEFORE ===
# Quick Example

This is a **bold and*italic* sentence**.

- Item 1
- Item 2

```python
def hello_world():
    print("Hello, World!")
```

=== AFTER (escapes shown) ===
^[[1;4mQuick Example^[[0m

This is a ^[[1mbold and^[[0m^[[1;3mitalic^[[0m^[[1m sentence^[[0m.

^[[1m • ^[[0mItem 1
^[[1m • ^[[0mItem 2

^[[2m```python^[[0m
^[[36mdef hello_world():^[[0m
^[[36m    print("Hello, World!")^[[0m
^[[2m```^[[0m
```

The heading is bold and underlined rather than a `#`; `**` and `*` are gone and the
words carry the weight instead; `-` became `•`; the fence is dim and its code cyan. Note
the model wrote *nested* emphasis — `**bold and*italic* sentence**` — and it survives as
bold → bold-italic → bold.

**One sample shows this; it does not claim it.** Kaushik asked for this story because a
real transcript read badly, so the log has to show the difference — but a single reply
from one model is an illustration, not evidence about markdown in general. The evidence
for the criteria is the table above and the break-and-watch.

---

## Status of all 29

**Met, with the evidence named.**

| | |
|---|---|
| 2, 3 | fence set apart, named language or not — `test_a_fence_is_set_apart_from_the_prose` |
| 4 | plain prose reads as written |
| 5 | nothing dropped — including HTML tags, which Rich draws as nothing |
| 6 | formatting appears mid-reply |
| 7 | **0 cursor-up sequences**, each line written once |
| 8 | unclosed fence content shown as it arrives |
| 9 | a half-arrived construct is never styled as a complete one |
| 10 | every character echoed on arrival; no character waits for another |
| 14, 15 | not a terminal → the old path exactly, byte for byte |
| 16 | the renderer sits below `show_piece`; history never sees it |
| 17, 18, 19, 29 | untouched — golden transcript unchanged |
| 20 | `_could_still_be_a_call` still gates what reaches the renderer |
| 21, 22 | empty prints nothing; one character is shown |
| 23 | malformed markdown shown as text |
| 24 | unchanged — `_accept_any_character` still owns this |
| 28 | guarded at the call site, not only inside the renderer |

**Partly met.**

- **AC 1** — headings, bold, italic, ordered and unordered lists, block quotes, inline
  code and links are all formatted. **Tables are not.** A table needs every row before it
  can be drawn, and a line-at-a-time renderer commits each row as prose. This is the one
  place where AC 1 and AC 7 genuinely pull against each other, and it is soluble: hold
  table rows *only*, emit the whole table when the block ends. Nothing shown ever moves,
  because the rows were never shown.

**Not met.**

- **AC 11, 12, 13** — scrolling, wrapping and resize follow from committing plain lines
  and never redrawing, but that is an argument, not a measurement. No test asserts them.
- **AC 25, 26, 27** — there is **no switch**. Rendering cannot be turned off, `NO_COLOR`
  is not read, and `--help` says nothing. Not started.

---

## What cycle 3 does

Close the four named gaps. They are known, so a cold read to *find* them would be
theatre — the cold read is cycle 4, once there is a complete thing to read coldly.

---

## The near-miss worth recording

`git checkout -- src/axiom/terminal.py`, run to undo a hand-applied break, **destroyed
the entire uncommitted renderer** — `checkout --` restores from HEAD, and cycle 2's work
had not been committed. Recovered in full: `show_piece` and `end_reply` were
reconstructed by disassembling `__pycache__/terminal.cpython-314.pyc`, and the rest from
this session's own `sed` output. The suite confirms the reconstruction.

Two things follow, and both are cheap:

1. **Commit when a unit is green, not when the cycle ends.** The renderer was green and
   uncommitted for the whole of the break-and-watch.
2. **A break harness must restore from its own saved copy, never from git.** `break60.py`
   does exactly that in a `finally`; the mistake was reaching for git *outside* it.
