# Cycle 2 — 2026-08-28 19:12 +0530

The guard, then the fix. Both numbers reached zero.

## Where the artifact now stands

`.tmp/probe_nesting.py` now feeds whole replies through the real `Rendered`, because the fix
is state across lines and `_as_markdown` alone can no longer see it.

| in-indent | col | marker | source | drawn |
|---|---|---|---|---|
| 0 | 1 | `•` | `- Outer` | `• Outer` |
| 2 | 3 | `◦` | `- Inner` | `◦ Inner` |
| 4 | 5 | `▪` | `- Deepest` | `▪ Deepest` |
| 2 | 3 | `◦` | `- Back to two` | `◦ Back to two` |
| 0 | 1 | `•` | `- Back to the top` | `• Back to the top` |
| 0 | 1 | `1` | `1. One` | `1 One` |
| 3 | 3 | `1` | `1. One point one` | `1 One point one` |
| 2 | 3 | `◦` | `- Bullet under a number` | `◦ Bullet under a number` |
| 2 | 3 | `◦` | `-` | `◦` |
| 2 | 3 | `◦` | `- **bold** and *italic*` | `◦ bold and italic and code` |

**Levels collapsed: 0** (was 2 groups over 9 inputs).
**Lines that are not one line: 0** (was 2). Ten rows in, ten rows out.

Mode B is gone with Mode A. Four spaces never reaches Rich as four spaces, so it is never an
indented code block, so there is nothing to pad.

## What was built

`Rendered` gains `_levels`, a stack of the open levels' indents, reset in `finish()`
alongside `_fence`. `_styled` asks `_nested()` first and falls back to `_as_markdown` when
the answer is `None`.

Two decisions worth naming:

- **Depth 0 returns `None` and takes today's path untouched.** That is what makes AC 6 free
  rather than defended - the common case never enters the new code at all.
- **A stack, not arithmetic.** Markdown nests by indent relative to the parent's *content*
  column, which moves with the parent's marker: three for `1. `, two for `- `. Dividing an
  indent by a fixed width gets `- Bullet under a number` (indent 2, under a `1. `) wrong.
  The stack gets it right and needs no lookahead.

A nested item's **text** is rendered alone as prose and the marker and indent are placed
here. That keeps bold, italic, inline code and links working at depth (AC 7).

## The break, and the three tests it exposed as vacuous

Disabling nesting (`if True: return None`) turned **6 of 13** red. Four tests that should
have noticed did not, and three of those were genuinely vacuous:

- **`test_returning_to_a_shallower_level_returns_to_that_level`** — with everything
  flattened, five identical rows satisfy "returned to the same place" perfectly. It passed
  while the feature did nothing.
- **`test_a_nested_item_is_one_row_not_a_code_block`** — it filtered blank rows out before
  counting, and a code block's padding rows *are* blank. It filtered away the exact defect
  it is named for.
- **`test_a_paragraph_between_two_lists_starts_the_depths_again`** — if no list ever has a
  second level, "the second list did not inherit one" is true and means nothing.

Each got one more assertion, naming what it had been blind to. The break now turns **9**
red.

The fourth, `test_markup_inside_a_nested_item_is_still_formatted`, and
`test_a_sub_item_with_no_parent_above_it_is_shown`, still pass with nesting removed - and
**should**. They guard that this change did not break AC 7 and AC 10, not that nesting
happens. Recorded so a later cycle does not "fix" them into something they are not.

This is the standing lesson landing on my own tests within one cycle of writing them. Three
of eleven were vacuous, and the only reason it is known is that the break was run.

## The guard from cycle 1

`test_a_flat_list_item_keeps_its_layout` was written from cycle 1's recorded numbers rather
than from the renderer's current output, then proved by moving a flat bullet two columns:
**exactly 2 red, 78 green.** Nothing else in the file guards list layout, which is what
cycle 1 predicted.

## Criteria

**Met, with a test shown to fail when broken: 7 of 13** — AC 1, 2, 3, 4, 5, 6, 8.

**Holding and guarded, but not break-sensitive by design: 2** — AC 7, AC 10.

**Untested: 4** — AC 9 (a list nested deeper than the window is wide), AC 11 and AC 12
(`--no-render` and piped output byte for byte), AC 13 (the indent structure matches
`--no-render`). All four need the full output path rather than the renderer.

## A note for loop 72

A nested item now passes only its **text** to `_as_markdown`, with no marker, so it takes the
paragraph branch and does not go through a Rich container. #72's per-construct `soft_wrap`
change should therefore leave nested items alone - and AC 9 here may already hold for free
because of it. Worth measuring rather than assuming.

## Suite

`uv run pytest` — **630 passed in 73.76s**. Baseline on this branch was 617; 13 tests added.

## Assumptions

None changed. The cause and the seam were both as `assumption.md` stated.
