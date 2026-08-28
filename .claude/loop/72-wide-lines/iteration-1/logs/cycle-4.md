# Cycle 4 — 2026-08-28 20:12 +0530

The merge, AC 7, and a gap that neither issue owns.

## The merge dropped two tests, and the count is the only thing that noticed

`feature/73-nested-lists` merged into this branch with two conflicts, both of the
both-added kind - the two branches put different constants in the same place in
`terminal.py`, and appended different test blocks at the end of `test_rendering.py`. Both
sides were kept; nothing was chosen over anything.

Then the count came back **680**, and the arithmetic said 682: 617 shared, plus 47 from this
branch, plus 18 from #73's.

**Two tests had the same name on both branches.** `test_rendering_off_gives_the_markdown_byte_for_byte`
and `test_a_redirected_run_gives_the_markdown_byte_for_byte` were written by me on each
branch, for #72 AC 19/20 and #73 AC 11/12. Python takes the later definition, so the earlier
pair vanished - **and pytest reported green**. A silently deleted test is invisible to
everything except the count.

`action.md` said "a merge that drops a test is the failure to look for first, and the count
is how it shows." It was, and it did. #73's pair is renamed for its fixture.

## AC 7 — it did fail, and measuring first is why that was known

`action.md` said to measure rather than assume, and the assumption would have been wrong. A
nested item came back as **one 93-character line at a 40-column window**: #73 draws a nested
item's text through the paragraph path with the marker placed by hand, so nothing wrapped it
and the terminal would have wrapped it to column 0 - which is the level above's indent, and
every other level's too.

Fixed in `_nested`, where `action.md` said it would belong. The text is now drawn into the
room left beside the marker and every row after the first is pushed out to where the first
row's text began:

```
 • Outer
   ◦ The quick brown fox jumps over the
     lazy dog. The quick brown fox jumps
     over the lazy dog.
     ▪ The quick brown fox jumps over
       the lazy dog. The quick brown fox
       jumps over the lazy dog.
```

Depth 1 wraps to column 5, depth 2 to column 7. Each to its own indent.

`_as_markdown` gained `width` and `wrapped`, for a caller drawing inside its own margin.
Every other caller leaves both alone.

## The fix broke one of #73's tests, correctly

`test_a_list_nested_deeper_than_the_window_keeps_every_item` asserted `item at depth 2`
as a contiguous phrase. It was contiguous on #73's branch because the renderer did not wrap;
now it does, and the phrase straddles a row edge. **Nothing is lost** - the assertion was
written against an artifact rather than against the criterion.

Rewritten to squash whitespace before comparing. A phrase that straddles a row edge is not a
lost phrase, and asserting on the contiguous form would have called correct output broken -
the same mistake this loop made in cycle 2 with `row == row.rstrip()`.

## The sweep, extended

About 1,300 renderings in cycle 3 covered `> `, `- ` and `1. `. A nested item is a fourth
marker at a fourth indent and the erase arithmetic had not seen it. Swept at widths 20 and
40: nothing shown twice, nothing lost.

## The break

`room = 10_000` - the nested item never wraps, so the terminal wraps it to column 0. Reddens
**exactly the two AC 7 tests** and nothing else.

## Criteria — 21 of 21

All of them hold. AC 7 was the last, and it needed both branches: #73 gives an item its
depth, #72 gives it wrapping, and neither alone satisfies it.

## Goal check: NOT met — and the reason is a case no issue owns

`observe.md` asks for two things: every criterion in #72, **and characters lost at zero at
every width tested**. The first is satisfied. The second is not.

`indented-code` - a line indented four spaces that is **not** a list item - still loses **41
characters at width 40 and 25 at width 60**. Rich renders it in a container and crops it,
exactly as it did quotes and list items before this issue.

**It belongs to neither issue, and it was deferred to a loop that then converged without
it.** Cycle 2's `action.md` said: *"Leave `indented-code` alone this cycle even though it
crops the same way... Record it and let #73 own it."* #73's fix normalises the indent of a
list *item*, so a four-space line inside a list is safe. A standalone indented code block is
not, and #73 closed at 13 of 13 without ever having it as a criterion.

That is a process finding, not just a defect: **two parallel loops each measured only their
own criteria, so work handed from one to the other was dropped silently by both.** A queue
running one row at a time would have surfaced it; parallel loops did not.

An issue is drafted at `.tmp/issue-indented-code.md` - story and 13 criteria - and
**deliberately not filed**. Kaushik approved creating three specific issues; this is a
fourth, and it is his call whether it is a new story or scope added to #72.

## Suite

`uv run pytest` - **687 passed in 76.82s**. 682 after the merge, plus 5.
