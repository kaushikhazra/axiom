# Cycle 1 — 2026-08-28 18:42 +0530

Read and record. No source was written, as `action.md` required.

## Where the artifact stands

Nothing of #73 is implemented. Measured with `.tmp/probe_nesting.py` at 80 columns,
against the real `_as_markdown`:

| case | AC | in-indent | rendered col | marker | lines | visible |
|---|---|---|---|---|---|---|
| flat-unordered | 6 | 0 | 1 | `•` | 1 | 8 |
| flat-ordered | 6 | 0 | 1 | `1` | 1 | 6 |
| nest-2sp-unord | 1 | 2 | 1 | `•` | 1 | 8 |
| nest-4sp-unord | 2 | 4 | **80** | *(none)* | **4** | **91** |
| nest-6sp-unord | 2 | 6 | **80** | *(none)* | **4** | **98** |
| nest-3sp-ord | 3 | 3 | 1 | `1` | 1 | 16 |
| ord-in-unord | 3 | 2 | 1 | `1` | 1 | 25 |
| unord-in-ord | 3 | 3 | 1 | `•` | 1 | 24 |
| return-shallow | 5 | 0 | 1 | `•` | 1 | 24 |
| empty-at-depth | 8 | 2 | 2 | `-` | 1 | 3 |
| orphan-subitem | 10 | 2 | 1 | `•` | 1 | 21 |
| styled-at-depth | 7 | 2 | 1 | `•` | 1 | 79 |

**Levels collapsed: 2 groups, 9 inputs.**

- `col=1 marker='•'` — indents 0, 2 and 3 all land here: flat-unordered, nest-2sp-unord,
  unord-in-ord, return-shallow, orphan-subitem, styled-at-depth.
- `col=1 marker='1'` — indents 0, 2 and 3 all land here: flat-ordered, nest-3sp-ord,
  ord-in-unord.

**Lines that are not one line: 2** — nest-4sp-unord, nest-6sp-unord.

Baseline for both numbers. Nothing to move from yet.

## It is two failure modes, not one — this was `action.md` item 4

**Mode A, collapse. Indent 1 to 3 spaces.** The line is still a list item, still one line,
text intact — but the depth is gone. Rich is handed a line with no parent above it, so it
renders a top-level item. Every unordered case at every indent lands on column 1 with `•`;
every ordered case lands on column 1 with `1`, and the number restarts.

**Mode B, leaving the list. Indent 4 or more.** `'    - Deepest'` renders at **column 80
across four lines, 91 visible characters from an 18-character input**. Four spaces is an
indented code block in markdown, and that is what a renderer with no list context correctly
sees. The output is padding: a full-width blank line, the text, another blank line.

Same root cause — a single line carries no context — but the symptoms need different
handling, and a fix that only normalises the marker will leave Mode B untouched. **Mode B is
the one that shows on screen as broken**; Mode A merely looks like a flat list the model
never wrote.

## Where depth would have to be tracked — `action.md` item 5

`_as_markdown` cannot be given more context without holding lines back, and holding is
forbidden: AC 8 of #60 bars holding a fence's contents and AC 10 bars holding anything else.
A table is the only construct allowed to be held, and its comment in the source says so as a
rule rather than a habit.

So the depth must be tracked in `Rendered`, which already carries per-reply state —
`_fence`, `_lexer`, `_code`, `_table`, `_line`, `_echoed`, `_echo_width`. The seam is
`_styled`, which already branches on fence state before reaching `_as_markdown`.

The shape that fits the criteria: **a stack of seen indents.** An indent greater than the
top pushes a level, equal stays, smaller pops to the level that matches. That is what AC 2
and AC 5 describe between them, and it needs no lookahead. The line is then normalised to a
top-level item before Rich sees it, and the indent for its depth is placed by the renderer
afterwards — which also removes Mode B, since Rich never sees four leading spaces.

The stack resets per reply, alongside the other per-reply state.

## Criteria

**Met with a test shown to fail when broken: 0 of 13.**

Not started: AC 1, 2, 3, 4, 5, 8, 9, 10.
Not tested at this level: AC 11, 12, 13 — `--no-render` and piped output are above
`_as_markdown` and need the full path, not the probe.
AC 6 and AC 7 are the *unchanged* guards; both currently hold, neither is guarded.

## The regression that has no guard

**No test asserts how a list is laid out.** The only list assertion in the suite is one row
of `test_markdown_is_styled` — `("- a bullet\n", "a bullet")` — which checks that markup is
not shown literally and the text survives. It would pass whether the bullet renders at
column 1 or column 15, with `•` or with `*`. AC 6 is therefore unguarded today, and a fix
could silently change every flat list in the program without turning anything red.

That is the standing lesson's shape exactly: a test that passes for a reason other than the
one a reader would assume. It is not vacuous — it catches literal markup — but it is not the
guard AC 6 needs, and the next cycle should write that guard **before** touching the
renderer, so the before-and-after is provable.

## Suite

`uv run pytest` — **617 passed in 74.71s**. Green. This is the baseline; a fix holds it.

## Probe artifact worth not chasing

`styled-at-depth` reports 79 visible characters from a 68-character input. That is the
OSC-8 hyperlink: `_ESCAPE` matches `\x1b[...m` and does not strip `\x1b]8;;...`, so the
address is counted as visible. Not a defect. Do not spend a cycle on it.

## Assumptions

None changed. The stated cause — one line rendered in isolation — is confirmed by the table,
and the four-space case is now understood as a second mode of it rather than a separate bug.
