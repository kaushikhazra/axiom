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

import re

from axiom import terminal
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


# --- #76 AC 1, AC 2: every character reaches the screen ----------------------


BLOCK = (
    "Here is how:\n"
    "\n"
    "    def settle(host, named, installed, remembered):\n"
    "        return named or remembered or installed[0]\n"
    "        # whichever of the three answers first\n"
    "\n"
    "That is the whole rule."
)


LINE = "def settle(host, named, installed, remembered):"


def reassembled(text: str, width: int, monkeypatch, indent: str = "    ") -> str:
    """One indented line put back together from the rows it was drawn on.

    **Read from what the renderer emitted, not from `tests/screen.py`** - and
    that is a correction, not a shortcut. Two instruments were tried first:

    `row.strip()` on the modelled screen passed at 40 columns and failed at 20.
    The wrap falls inside `"host, named"`, so a row begins with a space that
    belongs to the code, and stripping it deleted a character from the very thing
    the test was checking had not lost any. **A helper that tidies its input
    cannot then assert the input was untidied.**

    Removing only the indent then failed at 12 columns, and that one is the
    instrument rather than the test. `Screen.text()` right-strips a row, because
    on a terminal a trailing space is invisible - and at width 12 a chunk
    boundary lands so that a row *ends* with the space after `"named,"`. The
    character is on the screen, occupying a column that draws the same as
    nothing. The screen model is right to drop it and cannot answer "did every
    character arrive".

    So the exactness claim is read off the committed lines - after the erase, so
    it is what was *drawn* and not what was echoed - and every claim about
    *position* stays on the modelled screen, where it belongs.
    """
    monkeypatch.setattr(terminal, "_width", lambda: width)
    out: list[str] = []
    rendered = terminal.Rendered(write=out.append)
    rendered.feed(f"before\n\n{indent}{text}\n\nafter")
    rendered.finish()

    drawn = [
        line.split("\r")[-1]
        for line in re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", "".join(out)).split("\n")
    ]
    between = [row for row in drawn if row.startswith(indent)]
    assert between, f"the block never drew: {drawn}"
    return "".join(row[len(indent) :] for row in between)


def test_an_indented_line_longer_than_the_window_is_shown_in_full(monkeypatch):
    """#76 AC 1, and the bug.

    Measured in cycle 1 before anything was written: the model wrote 51
    characters and a 40-column screen showed 39. Rich draws one of these as a
    code block with a column of padding either side and **cuts** at the window
    less two - it does not wrap, and nothing anywhere said so.

    Equality, not `in`. "The end is present" would still pass for a line that
    had lost something out of its middle.
    """
    assert reassembled(LINE, 40, monkeypatch) == LINE


def committed(reply: str, width: int, monkeypatch) -> list[str]:
    """Every row the renderer committed for `reply`, in order, blanks included.

    Not `tests/screen.py`, and the reason is the same one `reassembled` gives:
    the modelled screen *wraps*, so a row wider than the window becomes two rows
    and the overflow being asked about cannot be seen there. It also erases, so a
    blank row a block left behind can be cleared by the next line's erase and
    never appear. Both of those are questions about what was emitted.
    """
    monkeypatch.setattr(terminal, "_width", lambda: width)
    out: list[str] = []
    rendered = terminal.Rendered(write=out.append)
    rendered.feed(reply)
    rendered.finish()
    plain = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", "".join(out))
    return [line.split("\r")[-1] for line in plain.split("\n")]


def between(reply: str, width: int, monkeypatch) -> list[str]:
    """The committed rows strictly between `before` and `after`."""
    rows = committed(reply, width, monkeypatch)
    return rows[rows.index("before") + 1 : rows.index("after")]


def drawn_rows(text: str, width: int, monkeypatch, indent: str = "    ") -> list[str]:
    """The rows one indented line was drawn on."""
    rows = between(
        f"before\n\n{indent}{text}\n\nafter", width=width, monkeypatch=monkeypatch
    )
    return [row for row in rows if row.startswith(indent)]


def test_every_character_arrives_however_narrow_the_window(monkeypatch):
    """#76 AC 2. Four windows, one narrow enough to wrap the line four times.

    **The row count is asserted alongside the characters**, and that is not
    belt-and-braces. Written with the characters alone, this stayed green against
    a renderer wrapping at a fixed 80 columns: the whole line fits inside 80
    however narrow the window is, so nothing was lost and nothing was right
    either. A criterion about "however narrow the window" needs the window in the
    assertion.
    """
    for width in (12, 20, 33, 80):
        rows = drawn_rows(LINE, width, monkeypatch)
        room = width - 4
        wanted = -(-len(LINE) // room)  # rows this window demands

        assert "".join(row[4:] for row in rows) == LINE, f"lost at width {width}"
        assert len(rows) == wanted, (
            f"width {width} wants {wanted} rows and drew {len(rows)}: {rows}"
        )


def test_no_row_is_wider_than_the_window(monkeypatch):
    """#76 AC 2's other half: arriving is not enough if it arrives off-screen.

    A fix that emitted the line whole and left the wrap to the terminal would put
    every character in the stream while the continuation landed at column zero,
    indistinguishable from prose. #72 settled this for a nested list item and the
    same answer applies: the renderer places the wrap.

    **Measured on the emitted rows, because the modelled screen cannot fail this
    assertion.** `Screen` wraps at its width, so `len(row) > width` is never true
    there however wide the renderer's line was - written that way first, and the
    break went straight through it.
    """
    for width in (20, 40, 80):
        rows = drawn_rows(LINE, width, monkeypatch)
        too_wide = [row for row in rows if len(row) > width]

        assert not too_wide, f"a row overflowed a {width}-column window: {too_wide}"


# --- #76 AC 3: set apart, and the way a fenced block is ----------------------


def test_the_block_keeps_its_indent(monkeypatch):
    """#76 AC 3. What sets it apart is where it sits.

    Measured in cycle 1: Rich collapses the four-space indent to one column of
    its own padding, so the block sits almost against the prose. Keeping the
    indent is what distinguishes it, and it is the model's own indent rather
    than one axiom invented.
    """
    rows = shown(BLOCK, width=40, monkeypatch=monkeypatch)
    code = [row for row in rows if "settle" in row or "installed" in row]

    assert code, f"the block never drew: {rows}"
    assert all(row.startswith("    ") for row in code), (
        f"the block lost its indent: {code}"
    )


def test_the_block_carries_no_colour_of_its_own(monkeypatch):
    """#76 AC 3, "the way a fenced block is" - which is *not* by painting.

    Cycle 1 found the two set apart in opposite ways: an indented block got
    Rich's hardcoded `48;5;235` background across the full width, and a fenced
    block with no language gets nothing at all. #77 AC 20 settled which of those
    is right - a block nobody can lex is delimited, not coloured, because a
    colour is a claim about the content that nothing supports.

    So this asserts the *absence* of styling, and the string it looks for is one
    cycle 1 actually measured in the output rather than one invented here.
    """
    monkeypatch.setattr(terminal, "_width", lambda: 40)
    out: list[str] = []
    rendered = terminal.Rendered(write=out.append)
    rendered.feed(BLOCK)
    rendered.finish()
    emitted = "".join(out)

    assert "settle" in emitted, "the block never drew at all"
    assert "48;5;235" not in emitted, "the block is painted with Rich's own grey"
    assert "\x1b[38;5;231" not in emitted, "the block is painted with Rich's own white"


# --- #76 AC 7 to 10: the boundaries ------------------------------------------


def test_a_block_exactly_as_wide_as_the_window_is_one_row(monkeypatch):
    """#76 AC 7, both halves: one row, and no empty row after it."""
    rows = shown(
        "before\n\n    " + "x" * 36 + "\n\nafter", width=40, monkeypatch=monkeypatch
    )
    drawn = [row for row in rows if "x" in row]

    assert len(drawn) == 1, f"a block that fits was drawn on {len(drawn)} rows: {rows}"
    assert len(drawn[0]) == 40, f"the row is {len(drawn[0])} columns, not 40"
    assert rows[rows.index(drawn[0]) + 1] == "after", f"a row was left behind: {rows}"


def test_a_block_one_character_wider_is_two_rows(monkeypatch):
    """#76 AC 8, and it says exactly where that character goes.

    Cycle 1 measured this violated - one row, not two - because Rich's collapse
    of the indent bought three columns back and the line still fitted. It was
    left alone rather than reworded: a criterion amended to match the
    implementation is how #48 and #49 both got caught.
    """
    rows = shown(
        "before\n\n    " + "x" * 37 + "\n\nafter", width=40, monkeypatch=monkeypatch
    )
    drawn = [row for row in rows if "x" in row]

    assert len(drawn) == 2, f"one character over did not wrap: {rows}"
    assert drawn[0] == "    " + "x" * 36
    assert drawn[1] == "    x", f"the last character is not alone on row two: {drawn}"


def test_an_indented_line_of_only_spaces_prints_nothing(monkeypatch):
    """#76 AC 9. Nothing, and no row left behind either.

    **Written first as "the non-blank rows are before and after", which filtered
    out exactly what it was looking for.** A stray blank row is blank, so a test
    that drops blanks before comparing cannot see one. Now the whole screen is
    compared, exactly.

    **On the screen and not on the committed rows**, and that is a decision. The
    renderer does commit a row of four spaces for this line - measured - and the
    erase then takes it back, so nothing reaches the screen. "Prints nothing and
    leaves no stray row" is a claim about the screen, and the committed spaces
    are what *every* whitespace-only line has always produced, indented or not.
    Not this issue's to change; recorded in `logs/cycle-2.md` rather than fixed
    here.
    """
    rows = shown("before\n\n    \n\nafter", width=40, monkeypatch=monkeypatch)

    assert rows == ["before", "after"], f"a blank indented line left a row: {rows}"


def test_many_indented_lines_are_one_block(monkeypatch):
    """#76 AC 10, measured as "no gap", which is what one block looks like.

    Rich emits a background-only row above and below *each* line's block, so the
    failure this guards is three lines drawn as three blocks with a rule between
    each pair.

    **On the committed rows rather than the modelled screen**, because the screen
    erases: a blank row one line leaves can be cleared by the next line's erase
    and never appear there. Measured on the screen first, and the break went
    through it.
    """
    rows = between(
        "before\n\n    one\n    two\n    three\n\nafter",
        width=40,
        monkeypatch=monkeypatch,
    )

    assert rows == ["", "    one", "    two", "    three", ""], (
        f"three lines were not drawn as one block: {rows}"
    )


# --- #76 AC 6: the rule's own boundary ---------------------------------------


def test_three_spaces_is_still_prose(monkeypatch):
    """#76 AC 6. Four is the number, and three has to stay what it was.

    The cheapest way to break every reply that opens with a slightly indented
    line would be an off-by-one here, and nothing else in the suite would notice
    - a paragraph drawn as a code block still contains all its words.
    """
    rows = shown(
        "before\n\n   not code at all\n\nafter", width=40, monkeypatch=monkeypatch
    )

    assert "not code at all" in "\n".join(rows)
    assert not any(row.startswith("   not code") for row in rows), (
        f"three spaces were read as a code block: {rows}"
    )


# --- #76 AC 5, 11, 12, 13: what did not change -------------------------------


FENCED = "```python\ndef settle(host):\n    return host\n```\n"
# Long enough that a 24-column window has to wrap it. Written first with short
# lines, and the cut-restored break went straight through: nothing is lost by a
# truncation that never has to truncate.
INDENTED = (
    "Here is how:\n"
    "\n"
    "    def settle(host, named, installed, remembered):\n"
    "        return named or remembered or installed[0]\n"
    "\n"
    "Done.\n"
)


def test_a_fenced_block_is_still_highlighted(monkeypatch):
    """#76 AC 5. The fence check comes first and has to stay first.

    A recognition rule placed above it would take every indented line *inside* a
    fence - which is most of them - and draw it as an indented block, losing the
    highlighting the fence's language earned. A keyword and a name coloured the
    same means nothing is being highlighted.
    """
    monkeypatch.setattr(terminal, "_width", lambda: 40)
    out: list[str] = []
    rendered = terminal.Rendered(write=out.append)
    rendered.feed(FENCED)
    rendered.finish()
    emitted = "".join(out)

    # Matched with the escapes removed: highlighting breaks `return host` into
    # separately coloured runs, so the text is not contiguous in the raw bytes.
    # Written the naive way first and it reported "the block never drew".
    inside = [
        line
        for line in emitted.split("\n")
        if "return host" in re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line)
    ]
    assert inside, "the fenced block never drew"
    assert re.findall(r"\x1b\[[0-9;]*m", inside[0]), (
        f"a line inside a fence lost its highlighting: {inside[0]!r}"
    )
    assert "    return host" in re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", inside[0]), (
        "a fenced line lost its own indent"
    )


def test_rendering_off_gives_the_block_byte_for_byte(capsys, monkeypatch):
    """#76 AC 11. `--no-render` takes the plain path, which never sees any of this.

    **At a terminal, deliberately.** Written without forcing `isatty`, this proved
    nothing: a test process is not a terminal, so the plain path was taken because
    of *that* and the `--no-render` half of the gate was never consulted. Removing
    it from the gate left the test green. `--no-render` is a promise about a run
    that *is* at a terminal and asked for plain output.
    """
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    terminal.use_rendering(False)
    try:
        for start in range(0, len(INDENTED), 4):
            terminal.show_piece(INDENTED[start : start + 4])
    finally:
        terminal.use_rendering(True)

    assert capsys.readouterr().out == INDENTED


def test_a_redirected_run_gives_the_block_byte_for_byte(capsys):
    """#76 AC 12. Not a terminal, so the plain path - the same one a pipe takes."""
    for start in range(0, len(INDENTED), 4):
        terminal.show_piece(INDENTED[start : start + 4])

    assert capsys.readouterr().out == INDENTED


def closed_up(rows: list[str], width: int) -> list[str]:
    """The rows with the wrap points closed, so the source lines come back.

    **AC 8 and AC 13 pull against each other and this is where they meet.** AC 8
    says a block one character wider than the window is drawn on two rows *with
    that character on the second*, which forces a hard wrap by column - and a
    hard wrap splits `named,` into `nam` and `ed,`. Read literally against the
    drawn rows, AC 13's "the same words" is then false for any block that wraps
    mid-word, and no implementation can satisfy both.

    The same shape as #80's AC 11 against AC 14: two criteria, one behaviour, and
    the resolution is to read them at the level each is about. AC 8 is about rows.
    AC 13 is about the reply, so the rows are put back into lines first.

    A row that filled the window exactly, followed by a row at the same indent, is
    a wrap point - that is what the renderer emits and nothing else produces it.
    """
    lines: list[str] = []
    # The *previous row* being full is the wrap signal, not the line built so
    # far. Written as `len(lines[-1]) == width` first, which closed the first
    # wrap of a line and then never matched again: joining two rows makes the
    # line longer than the window by construction.
    last_full = False
    for row in rows:
        held = lines[-1] if lines else ""
        # The continued line's own indent, which is what the continuation row
        # repeats. Hardcoded as four first, and the eight-space line then came
        # back with four stray spaces in the middle of it - enough to split one
        # word into two and fail the very comparison this is preparing.
        lead = held[: len(held) - len(held.lstrip(" "))]
        if last_full and lead and row.startswith(lead):
            lines[-1] += row[len(lead) :]
        else:
            lines.append(row)
        last_full = len(row) == width
    return lines


def test_rendered_and_unrendered_hold_the_same_words_in_the_same_order(monkeypatch):
    """#76 AC 13, and it is the criterion that would catch a silent cut.

    The styling changes the bytes and the wrapping changes where the breaks fall,
    so the two can only be compared on their words - and only once the wrap
    points are closed, for the reason `closed_up` gives.

    What must not differ is which words there are and what order they come in. A
    truncation shortens that list, which is exactly the defect this issue was
    filed for; a reordering would mean the block had been put back wrongly.

    Run at 24 columns, where the block has to wrap. **Written first at a width
    where it did not, and the cut-restored break went straight through** - a
    truncation that never has to truncate loses nothing.
    """
    monkeypatch.setattr(terminal, "_width", lambda: 24)
    out: list[str] = []
    rendered = terminal.Rendered(write=out.append)
    for start in range(0, len(INDENTED), 4):
        rendered.feed(INDENTED[start : start + 4])
    rendered.finish()
    plain = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", "".join(out))
    rows = [line.split("\r")[-1] for line in plain.split("\n")]
    drawn = " ".join(closed_up(rows, 24))

    assert drawn.split() == INDENTED.split(), (
        f"the words changed:\n  drawn:  {drawn.split()}\n  source: {INDENTED.split()}"
    )
