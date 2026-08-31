# Cycle 2 — 2026-08-28 19:52 +0530

The fix landed. Characters lost went to zero at every width, for every construct this issue
owns.

## The number

| width | before | after | what is left |
|---|---|---|---|
| 40 | 539 | **41** | `indented-code` only |
| 60 | 480 | **25** | `indented-code` only |
| 200 | 205 | **0** | nothing |

Every remaining character is the four-space indented code block, which `action.md` assigns
to #73 and which is deliberately untouched.

Continuations land where the criteria ask: a quote's marker at column 0 on every row (AC 5),
a list item's continuation at column 3 - under the text, not the marker (AC 6). `one-over`
now comes back as two rows with all 57 characters (AC 13). A 400-character unbroken token at
width 200 comes back whole, folded across three rows (AC 14).

## What was changed

Two lines, and one of them is a flag.

- **`_PADDING` gained `re.MULTILINE`.** `$` was end-of-*string*, so only the last line of a
  rendering was ever unpadded. Harmless while every rendering was one line.
- **`soft_wrap` is chosen per construct**: off for anything Rich draws in a container - a
  quote, a list item, matched by `_CONTAINED` - and on for everything else.

`_erase` and `_rows_used` were not touched, as `action.md` required. They take back the raw
echo, whose row count is unrelated to the styled output's.

## Cycle 1 was wrong about the existing guards, and the break found it

Cycle 1 recorded that `test_a_block_element_is_not_padded_to_the_full_width` and
`test_nothing_is_padded_out_to_the_console_width` "will go red the moment intermediate
padding appears", and called them real guards that would stop `_unpadded` being forgotten.

**They do not.** With `re.MULTILINE` removed and the wrapping fix in place, all **78** tests
in the file still passed. Their inputs are short lines that render on a single row, so
reaching only the last line is enough for them. The prediction was made by reading the tests
rather than by running them against the change.

That is the same failure this repo has one recorded example of, and it would have shipped a
double-spaced quote with a green suite. It was caught only because `action.md` step 2 said to
prove the break rather than assume it.

## A test of mine that was wrong in the other direction

The replacement guard first asserted `row == row.rstrip()` and **failed on correct output**.
Rich keeps the word-separator space at a wrap point, so a 37-column row in a 40-column window
legitimately ends in a space. That is harmless: it is a row reaching the *width* that costs a
blank row, and nothing else does.

Rewritten to assert `len(row) < width`, which is the thing AC 12 is actually about. Worth
recording because a green-looking assertion was, for twenty minutes, calling correct output
broken - the mirror image of the vacuous-test problem and just as expensive.

## The breaks

Three, each precise:

| break | red | reads as |
|---|---|---|
| `_PADDING` without `MULTILINE` | 6 | wrapped bullets and numbered items padded to the width |
| `soft_wrap=True` always | 21 across 6 tests | the original crop, back |
| `soft_wrap=False` always | **1** | paragraphs pre-wrapped |

The third is the one worth naming. `test_a_paragraph_is_still_one_long_line` is the **only**
test in 642 that stands between this codebase and silently losing resize-reflow: pre-wrapped
prose looks identical until someone drags their window. One test, and it is the guard for
AC 10 and AC 18 both.

## Criteria

**Met, with a test shown to fail when broken: 9 of 21** - AC 1, 2, 3, 4, 5, 6, 12, 13, 14.

**Holding and guarded: 3** - AC 10, AC 11, AC 18.

**Not tested at this level: 9** - AC 7 (a nested item's own indent, which needs #73's depth
stack and is not on this branch), AC 8 and AC 9 (redraw, needs the streaming path measured on
a modelled screen), AC 15, 16, 17, 19, 20, 21 (`--no-render`, pipes, and the half-window
comparison, all of which need the full output path).

## Suite

`uv run pytest` - **642 passed in 73.85s**. Baseline on this branch was 617; 25 tests added.

## Assumptions

None changed. The stated cause held exactly, and the fix is the one cycle 1 predicted. What
cycle 1 got wrong was not the cause but the *coverage* - see above.
