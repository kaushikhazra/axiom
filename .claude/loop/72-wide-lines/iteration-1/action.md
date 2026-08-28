# Action

Nine of twenty-one criteria are met with tests that go red when the fix is removed. The nine
untested ones split into two groups, and only one of them can be worked here.

1. **AC 8 and AC 9 - nothing is redrawn, nothing printed twice.** These are the criteria #60
   failed twice while a byte-stream assertion said it passed, and they are now *more* at risk
   than before: a quote that used to occupy one row now occupies four, and `_erase` takes
   back the raw echo by the rows it occupied. Measure on a modelled screen - `tests/screen.py`
   exists for exactly this and is what caught #60's duplication. Sweep every length around
   the wrap boundary at widths 20, 40 and 81, as `test_no_length_at_any_width_is_shown_twice`
   already does for plain text, but for a quote and a list item.
2. **AC 15, 16, 17, 19, 20, 21 - `--no-render`, pipes, and the half-window comparison.** All
   need the full output path rather than `_as_markdown`. AC 21 is the strongest of them: the
   same prompt rendered and unrendered must differ only in styling and line breaks, never in
   words, and that is a property this cycle's change could violate without any existing test
   noticing.
3. **Leave AC 7 alone.** A nested item wrapping to its own indent needs #73's depth stack,
   which is on another branch. Record it as blocked rather than half-doing it here.
4. **Break every new test.** This cycle found one prediction wrong and one assertion wrong,
   in one hour. Assume the same rate.
5. `uv run pytest` - 642 on this branch, green.

First thing to tackle: **AC 8 and AC 9 on a modelled screen.** A construct that used to be
one row is now four, the erase arithmetic was written when it was one, and the only reason
to think it still holds is that 642 tests pass - which is exactly the evidence that was
wrong about `_unpadded` an hour ago.
