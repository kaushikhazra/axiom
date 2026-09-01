"""#76: a code block the model indented rather than fenced.

Its own file rather than more of `tests/test_rendering.py`, and the reason is an
instrument. `.claude/loop/cited.py` reads which criteria a test file claims, and
`test_rendering.py` already holds #60's, #72's, #73's and #77's - so "AC 7" in
that file could be any of four issues and the check cannot separate them. One
file, one issue, and the criteria a file claims mean something.

**AC 4 comes first and it comes before the feature**, because the obvious rule
for this issue undoes a shipped one. #73 draws nested list items at their own
depth, and markdown nests by indent relative to the parent's *content* column -
so a bullet four spaces in is a list item, not code. A rule that reads four
leading spaces as code turns every nested list into a code block.
"""

from screen import shown


# --- #76 AC 4: the shipped behaviour this must not break ---------------------


def test_a_list_item_four_spaces_deep_is_still_a_list_item(monkeypatch):
    """#76 AC 4, pinned before anything can break it.

    Passes today - this is #73's behaviour, and the test exists so that the
    naive recognition rule cannot land without going red. Asserted on the
    *markers*, because that is what distinguishes a list from a code block on
    screen: a nested item carries its glyph and its depth, and a code block
    carries neither.
    """
    rows = shown(
        "Steps:\n\n- first\n    - nested under first\n        - deeper still\n- second",
        width=40,
        monkeypatch=monkeypatch,
    )
    drawn = "\n".join(rows)

    assert "• first" in drawn, "the top-level item lost its marker"
    assert "◦ nested under first" in drawn, (
        f"a four-space item stopped being a list item:\n{drawn}"
    )
    assert "▪ deeper still" in drawn, f"an eight-space item was read as code:\n{drawn}"
    assert drawn.index("• first") < drawn.index("◦ nested"), "the order changed"


def test_the_deeper_item_is_indented_further_than_its_parent(monkeypatch):
    """#76 AC 4, the half a marker check alone would miss.

    A rule that kept the glyphs but flattened the depths would satisfy the test
    above. What makes a nested list readable is that each level sits further in
    than the one above it, which is #73 AC 2 and AC 5 and is what `_depth`'s
    stack of seen indents exists for.
    """
    rows = shown(
        "- first\n    - nested under first\n        - deeper still",
        width=40,
        monkeypatch=monkeypatch,
    )
    indents = [len(row) - len(row.lstrip()) for row in rows if row.strip()]

    assert len(indents) == 3, f"three items did not draw three rows: {rows}"
    assert indents[0] < indents[1] < indents[2], f"the depths were flattened: {indents}"
