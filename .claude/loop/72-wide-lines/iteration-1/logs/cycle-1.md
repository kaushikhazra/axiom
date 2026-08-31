# Cycle 1 — 2026-08-28 18:52 +0530

Read and record. No source was written, as `action.md` required.

## The loss table

`.tmp/probe.py` measures **characters** rather than words - a truncated word is still one
word, so the word metric a first draft used could not see the boundary cases at all.
Payload is the line with its markers and all whitespace removed, which is what AC 4 means by
"every character the model sent": wrapping legitimately changes whitespace, and a renderer
legitimately swaps `-` for a bullet.

| case | AC | width 40 | width 60 | width 200 |
|---|---|---|---|---|
| paragraph | 10 | 0 | 0 | 0 |
| heading | 10 | 0 | 0 | 0 |
| indented-code | 4 | **41** | **25** | 0 |
| quote | 1 | **115** | **99** | 0 |
| bullet | 2 | **114** | **98** | 0 |
| numbered | 3 | **110** | **95** | 0 |
| nested-bullet | 7 | **114** | **98** | 0 |
| long-word | 14 | **44** | **64** | **204** |
| exactly-width | 12 | 0 | 0 | 0 |
| one-over | 13 | **1** | **1** | **1** |
| **total** | | **539** | **480** | **205** |

**`one-over` loses exactly one character, at every width.** That is the cleanest possible
demonstration that this is a crop at the window width and not anything subtler.

**AC 12 already passes.** A quote exactly as wide as the window survives whole, at all three
widths. Nothing to do there but keep it.

**Two constructs are lost that the issue does not name.** `indented-code` - a line indented
four spaces, which markdown reads as a code block - crops like the rest, because Rich
renders it in a container too. It is *not* the fenced path (`_code_line` and `_highlighted`,
which never touch `_as_markdown`), so AC 10's "fenced code blocks" does not cover it. It
overlaps #73's Mode B and should be settled once, not twice. And `long-word` loses at width
200 where nothing else does, because 400 unbroken characters exceed any window.

## The finding that decides the size of the fix

**`soft_wrap=False` makes Rich do almost all of this for free.** Measured at width 60:

```
quote     '▌ The quick brown fox jumps over the lazy dog. The quick'
          '▌ brown fox jumps over the lazy dog. The quick brown fox'
          '▌ jumps over the lazy dog.'

bullet    ' • The quick brown fox jumps over the lazy dog. The quick'
          '   brown fox jumps over the lazy dog. The quick brown fox'
          '   jumps over the lazy dog.'
```

The quote marker is carried onto **every** continuation row - that is AC 5, whole. The list
continuation aligns under the **text** at column 3, not under the marker and not at the left
margin - that is AC 6, in the criterion's own words. And at width 40 a single unbroken
100-character token comes back as **100 of 100 characters kept**, folded across three rows
with the marker carried - that is AC 14.

So AC 1, 2, 3, 4, 5, 6 and 14 all come from one flag. This is a small fix, not a large one.

## The constraint that stops it being one flag everywhere

**`soft_wrap` must stay on for paragraphs and headings.** Today they are emitted as one long
line and the *terminal* wraps them, which is why a resize reflows them - visible in Kaushik's
own screenshot, where dragging the window re-flowed the scrollback. Hard-wrapping them
through Rich would produce the same picture at first and then **stop reflowing on resize**,
which is AC 10 ("exactly as they do today") and touches AC 18.

So the fix is **per construct**, not global: containers wrap through Rich, bare text keeps
soft wrap and the terminal's reflow. The renderer already discriminates lines this way for
tables, with `_TABLE_ROW`, so the shape exists.

## What a fix touches — `action.md` item 4

- **`_as_markdown`** — where the crop is. Chooses `soft_wrap` per construct. The change.
- **`_unpadded`** — **must become per-line, and currently is not.** Measured:
  `_unpadded('first line   \nsecond line   ')` returns `'first line   \nsecond line'`. The
  `$` in `_PADDING` is end-of-string, not end-of-line, so the moment `_as_markdown` returns
  more than one line every intermediate line keeps Rich's padding out to the console width.
  A line padded to exactly the width plus a newline wraps to a blank line, so a wrapped quote
  would come out double-spaced.
- **`_commit`** — writes `erase + styled + "\n"`. It already handles a multi-line styled
  string correctly, because `_erase` is computed from the *echoed raw* text and not from the
  styled output. No change expected, but it is the place a wrong assumption would show.
- **`_erase` / `_rows_used`** — **no change, and deliberately none.** They take back the raw
  echo, whose row count is unrelated to how many rows the styled version occupies. These
  were earned by #60 AC 7 failing twice; leave them alone.

## The guards that already exist, and will catch this

Unlike #73, this issue's *unchanged* group is guarded today:

- `test_a_block_element_is_not_padded_to_the_full_width` — asserts a quote line equals its
  own rstrip.
- `test_nothing_is_padded_out_to_the_console_width` — the same, at widths 40, 80 and 200,
  across every committed line.

Both iterate committed lines, so both will go red the moment intermediate padding appears.
They are real guards. The `_unpadded` change is not optional and these tests are why it will
not be forgotten.

Also present: `test_a_line_that_lands_on_the_wrap_boundary_is_not_shown_twice` and
`test_a_resize_mid_reply_cannot_corrupt_what_is_on_screen`, which is #60's AC 13 and this
issue's AC 18.

## Criteria

**Met and guarded: 1 of 21** — AC 12, which passes at all three widths and has two existing
tests behind it.

**Failing: 8** — AC 1, 2, 3, 4, 5, 6, 7, 14.

**Currently holding, unchanged, guarded: 3** — AC 10, 11 in part, and 18.

**Not tested at this level: 9** — AC 8, 9 (redraw, needs the streaming path not the
function), AC 13, 15, 16, 17, 19, 20, 21 (`--no-render`, pipes, and the half-window
comparison need the full output path).

## Suite

`uv run pytest` — **642 passed in 74.25s**. Up from 617 because loop 74 added 25 tests this
hour; no source of this loop's changed.

## Assumptions

None changed. The stated cause — `soft_wrap=True` and a Rich container — is confirmed, and
now quantified at three widths. Two things were added to what it covers rather than
contradicting it: indented code blocks crop the same way, and `_unpadded` being end-of-string
only is part of the same fix.
