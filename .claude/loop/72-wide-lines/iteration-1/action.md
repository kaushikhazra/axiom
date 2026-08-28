# Action

Twenty of twenty-one. **AC 7 - a nested item wraps to its own indent - is the only one left,
and it cannot be tested on this branch**, because it needs #73's depth stack, which lives on
`feature/73-nested-lists`. #73's loop has converged, so that branch is finished and stable.

So this cycle merges, and then tests the one criterion the merge makes reachable.

1. **Merge `feature/73-nested-lists` into `feature/72-wide-lines`.** Both changed
   `_as_markdown` and `Rendered`, in different places - #73 added `_nested`, `_depth` and
   `_levels` and hooked `_styled`; #72 changed `soft_wrap` and `_PADDING`. Expect the merge
   to be clean and **check rather than assume**: if it conflicts, resolve it by reading both
   cycle logs, not by picking a side.
2. **Run both suites before writing anything.** 664 here, 635 there. A merge that drops a
   test is the failure to look for first, and the count is how it shows.
3. **Then test AC 7.** A nested item longer than the window wraps to *its own* indent, not to
   the indent of the level above it. #73 renders a nested item's text through the paragraph
   path with the marker placed by hand, so the continuation may well land at column 0 rather
   than under the item's text - **measure before assuming it passes**. If it is wrong, the
   fix belongs here, in `_nested`, and it is this loop's to make.
4. **Re-run the sweep from this cycle with nesting present.** About 1,300 renderings proved
   nothing is shown twice for `> `, `- ` and `1. `. A nested item is a fourth marker at a
   fourth indent and the erase arithmetic has not seen it.
5. **Break AC 7's test.** Flatten the continuation indent and watch it go red.
6. `uv run pytest` - the merged count, green.

First thing to tackle: **the merge, and the two test counts either side of it.** Everything
else in this cycle is downstream of it, and a silently dropped test would make every number
after it wrong.
