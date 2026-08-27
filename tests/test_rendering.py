"""A reply read as formatted text while it is still arriving.

The measurements here are on the **byte stream**, not on how the output looks.
AC 7 and AC 9 are claims about escape sequences and about when a line is
written, and neither can be settled by reading the result and deciding it seems
fine.

Text is fed **four characters at a time** throughout, because that is what a
real stream delivers - measured at 77 chunks, mean 4.1 characters, 13 of them a
single character, in `logs/cycle-1.md`.
"""

import re

import pytest

from axiom import config, main, terminal
from axiom.terminal import Rendered
from conftest import StubBackend, feed, history


REPLY = (
    "# Factorial\n\nHere is a **short** function with *notes*.\n\n"
    "- it uses recursion\n- it handles only non-negative integers\n\n"
    "```python\ndef factorial(n):\n    if n == 0:\n        return 1\n"
    "    return n * factorial(n - 1)\n```\n\nThat is `factorial` done.\n"
)


def stream(text: str, chunk: int = 4, finish: bool = True) -> str:
    """The bytes a reply produces, fed the way a model delivers it."""
    out: list[str] = []
    rendered = Rendered(write=out.append)
    for start in range(0, len(text), chunk):
        rendered.feed(text[start : start + chunk])
    if finish:
        rendered.finish()
    return "".join(out)


def stripped(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def displayed(text: str) -> list[str]:
    """What a terminal ends up showing: after the last carriage return."""
    return [line.split("\r")[-1] for line in stripped(text).split("\n")]


# --- While it is still arriving -----------------------------------------


def test_no_line_is_ever_moved(*_):
    """AC 7, as the strongest measurable form of it.

    Not "does not move" but **no cursor-up is emitted at all**. Every
    published streaming-markdown implementation fails this - Rich's `Live`
    emits `CURSOR_UP` once per line of the previous render on every chunk.
    """
    assert re.findall(r"\x1b\[\d*A", stream(REPLY * 3)) == []


def test_each_line_is_written_once():
    """AC 7. A committed line belongs to the scrollback and is not touched."""
    emitted = stream(REPLY * 3)
    source = [line for line in (REPLY * 3).split("\n") if line.strip()]
    shown = [line for line in displayed(emitted) if line.strip()]

    assert len(shown) == len(source), "a line was written more or fewer times than once"


def test_formatting_appears_before_the_reply_ends():
    """AC 6. The user does not wait for the whole reply to see any of it."""
    partial = stream(REPLY[: len(REPLY) // 2], finish=False)

    assert "\x1b[" in partial, "nothing was styled until the reply finished"


def test_an_incomplete_line_is_shown_but_not_styled():
    """AC 8, AC 9, and the tension between them.

    Every character appears as it arrives - nothing waits for the newline -
    and a half-arrived `##` is not a heading until it is one.
    """
    out: list[str] = []
    rendered = Rendered(write=out.append)
    for chunk in ("##", " He", "ad", "ing"):
        rendered.feed(chunk)

    assert "".join(out) == "## Heading"


def test_a_line_inside_an_unclosed_fence_is_shown():
    """AC 8. Content is not held back until the fence closes."""
    out: list[str] = []
    rendered = Rendered(write=out.append)
    for chunk in ("```py", "thon", "\n", "x =", " 1", "\n"):
        rendered.feed(chunk)

    assert "x = 1" in stripped("".join(out))


def test_a_reply_that_ends_without_a_newline_is_still_finished():
    """AC 5, AC 21.

    Asserting the text is *present* proves nothing - it was echoed plainly as
    it arrived, so it is there whether or not the last line is ever finished.
    What `finish` owes is the ending: the line styled like every other, and a
    newline, so the next prompt does not land on top of the answer. The first
    version of this test asserted presence, and a renderer that never flushed
    passed it.
    """
    emitted = stream("a line\n**the end**")

    assert emitted.endswith("\n"), "the prompt would land on the reply"
    assert "\x1b[" in emitted.rsplit("\r", 1)[-1], "the last line was left unstyled"
    assert "the end" in stripped(emitted)


# --- Formatted ----------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("# Heading\n", "Heading"),
        ("**bold**\n", "bold"),
        ("*italic*\n", "italic"),
        ("- a bullet\n", "a bullet"),
        ("`code`\n", "code"),
    ],
)
def test_markdown_is_styled(source, expected):
    """AC 1. The markup is turned into formatting rather than shown literally."""
    emitted = stream(source)

    assert "\x1b[" in emitted
    assert expected in stripped(emitted)
    assert source.strip() not in displayed(emitted), "shown as literal markup"


def styling(text: str, containing: str) -> list[str]:
    """The escape sequences on the line that holds `containing`."""
    line = next(part for part in text.split("\n") if containing in part)
    return re.findall(r"\x1b\[[0-9;]*m", line)


@pytest.mark.parametrize("opener", ["```python", "```", "```nosuchlanguage"])
def test_a_fence_is_set_apart_from_the_prose(opener):
    """AC 2, AC 3. A block reads as a block, named language or not.

    Comparing the two lines' *text* is vacuous - `x = 1` and `prose` differ
    whatever the styling. The claim is about how they are dressed, so that is
    what is compared. The first version made the vacuous comparison and a
    renderer that styled code exactly like prose passed it.
    """
    emitted = stream(f"prose\n{opener}\nx = 1\n```\nmore\n")

    assert styling(emitted, "x = 1"), "code carried no styling at all"
    assert styling(emitted, "x = 1") != styling(emitted, "prose")
    assert styling(emitted, opener), "the fence marker was not set apart"


def test_a_link_keeps_its_address():
    """AC 1, AC 5, and a bug this file was written blind to.

    Rich shows `[the docs](https://example.com)` as the words `the docs` alone
    when it believes the console cannot emit a hyperlink - and it believes that
    of every Windows console. The address, the one part the user cannot retype,
    was being thrown away silently.

    Asserting the address is somewhere in the stream proves nothing: the line
    is echoed *verbatim* while it arrives, so the raw `](https://...)` is in
    the bytes whatever the renderer does with it. The claim is about the line
    that stays on screen - what follows the last carriage return - and the
    first version of this test, which looked at the whole stream, passed with
    the fix removed.
    """
    committed = displayed(stream("see [the docs](https://example.com) for more\n"))

    assert any("https://example.com" in line for line in committed), "address dropped"
    assert any("the docs" in line for line in committed)


def test_a_block_element_is_not_padded_to_the_full_width():
    """AC 12. Rich pads a quote out to the console width.

    A line padded to exactly the width, plus the newline written after it,
    wraps to an empty line on most terminals - so a quoted paragraph would
    come out double-spaced.
    """
    emitted = stream("> quoted words\n")
    line = next(part for part in stripped(emitted).split("\n") if "quoted" in part)

    assert line == line.rstrip(), "padded out to the console width"


def test_a_reply_with_no_markdown_reads_as_written():
    """AC 4."""
    plain = "Just a sentence with nothing special in it.\n"

    assert plain.strip() in " ".join(displayed(stream(plain)))


def test_every_character_reaches_the_screen():
    """AC 5, blunt on purpose.

    The failure mode of markdown renderers is silently eating what they do not
    understand. A renderer that drops content is worse than no renderer.
    """
    seen = re.sub(r"\s+", "", re.sub(r"[*_`#>-]", "", stripped(stream(REPLY))))
    sent = re.sub(r"\s+", "", re.sub(r"[*_`#>-]", "", REPLY))

    assert set(sent) - set(seen) == set()


def test_odd_markdown_is_shown_rather_than_swallowed():
    """AC 23. An unclosed fence, a stray backtick, a ragged table."""
    odd = "a ` stray backtick\n| one | two |\n| --- |\n```never closed\nstill here\n"
    shown = " ".join(displayed(stream(odd)))

    for fragment in ("stray backtick", "still here"):
        assert fragment in shown


@pytest.mark.parametrize("line", ["<div>", "<br/>", "<!-- a note -->", "<span>"])
def test_markup_rich_renders_as_nothing_is_still_shown(line):
    """AC 5, AC 23, and the one real content-loss bug this file exists for.

    Rich renders an HTML tag to the empty string - it is markdown's escape
    hatch into HTML and there is nothing to draw. A model explaining HTML, or
    quoting a template, therefore loses the line entirely unless the renderer
    notices it produced nothing and hands back what it was given.

    Found by breaking that fall-back and watching the whole file stay green:
    no earlier test fed it anything Rich could not draw.
    """
    assert line in stripped(stream(line + "\n"))


# --- Not a terminal -----------------------------------------------------


def test_output_is_plain_when_it_is_not_a_terminal(capsys, monkeypatch):
    """AC 14, AC 15. Byte for byte what a redirected run produced before."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    terminal.show_piece("# Heading\nand **bold**\n")
    terminal.end_reply()

    printed = capsys.readouterr().out
    assert printed == "# Heading\nand **bold**\n\n"
    assert "\x1b[" not in printed


def test_the_renderer_is_not_even_built_without_a_terminal(monkeypatch, capsys):
    """AC 14. The plain path is the old path, not a rendered path that hides."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr(terminal, "_reply", None)

    terminal.show_piece("text")

    assert terminal._reply is None


# --- Failure ------------------------------------------------------------


def test_a_rendering_failure_costs_the_formatting_not_the_answer(monkeypatch):
    """AC 28."""

    def explode(*_args, **_kwargs):
        raise RuntimeError("rendering fell over")

    monkeypatch.setattr(terminal, "_as_markdown", explode)
    out: list[str] = []
    rendered = Rendered(write=out.append)
    rendered.feed("a **bold** line\n")
    rendered.finish()

    assert "a **bold** line" in stripped("".join(out))


def test_an_empty_reply_prints_nothing(capsys, monkeypatch):
    """AC 21, and #58's spacing is not disturbed."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(terminal, "_reply", None)

    terminal.show_piece("")
    terminal.end_reply()

    assert capsys.readouterr().out == "\n"


def test_a_single_character_reply_is_shown():
    """AC 22."""
    assert "x" in stripped(stream("x"))


# --- Tables, the one construct that is held --------------------------------


TABLE = (
    "Here are the results.\n\n"
    "| language | year |\n| --- | --- |\n| Python | 1991 |\n| Rust | 2010 |\n"
    "\nThat is all of them.\n"
)


def test_a_table_is_drawn_as_a_table():
    """AC 1. The last construct a line-at-a-time renderer can reach.

    Column widths are not known until the last row has arrived, so a row drawn
    alone is only its own text. Rows are held - the one construct that is -
    and the whole table is written when it ends.
    """
    shown = [line for line in displayed(stream(TABLE)) if line.strip()]

    assert not any(line.startswith("|") for line in shown), "rows drawn as raw pipes"
    assert any("─" in line for line in shown), "no rule between header and body"
    for word in ("language", "Python", "1991", "Rust"):
        assert any(word in line for line in shown), f"{word} was lost"


def test_a_table_gains_no_blank_lines_of_its_own():
    """Rich's box style for markdown draws an empty top and bottom border.

    They arrive as lines that are empty apart from their escape sequences, so
    a table came out with a blank line either side of it. `strip()` does not
    see them as empty, because an escape sequence is not whitespace - found by
    reading a real reply, not by a test.
    """
    emitted = stream(TABLE)
    blanks = [line for line in emitted.split("\n") if not stripped(line).strip()]

    assert len(blanks) == 3, f"expected the reply's own two blanks, got {len(blanks)}"


def test_holding_a_table_still_moves_no_committed_line():
    """AC 7 against AC 1. Held rows were never shown, so nothing moves."""
    assert re.findall(r"\x1b\[\d*A", stream(TABLE * 3)) == []


def test_a_reply_that_ends_inside_a_table_still_shows_it():
    """The held rows are not lost when there is no line after them."""
    shown = displayed(stream("| a | b |\n| --- | --- |\n| 1 | 2 |\n"))

    assert any("1" in line and "2" in line for line in shown)


def test_a_stray_pipe_row_is_shown_not_swallowed():
    """AC 23. One `| pipe |` line is not a table - markdown needs the rule."""
    shown = " ".join(displayed(stream("| a stray pipe row |\nand on we go\n")))

    assert "a stray pipe row" in shown
    assert "and on we go" in shown


def test_prose_containing_a_pipe_is_not_held():
    """The reason a row is tested by its *leading* pipe and nothing looser.

    Treating any line containing `|` as a table row would swallow a shell
    pipeline or a regex alternation into a table that never closes - eating a
    paragraph to avoid missing a table.

    Measured on the *committed* line, and **before the reply ends**. Both
    matter, and each was found by a break that survived without it:

    - a held row is echoed verbatim before it is taken back, so the text is in
      the byte stream either way
    - a held row is drawn when the reply finishes, so it reaches the screen
      eventually even when it was wrongly held - `finish()` hides the bug

    What a wrongly-held line actually costs is AC 10: it appears at the end of
    the reply instead of when it was written. So the assertion is that the line
    is on screen *while the reply is still arriving*.
    """
    committed = displayed(stream("run `ls | wc -l` to count them\n", finish=False))

    assert any("wc -l" in line for line in committed), "held as though a table"


# --- The switch ------------------------------------------------------------


def test_rendering_can_be_switched_off(capsys, monkeypatch):
    """AC 25. Off is today's output, not a quieter rendering."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr(terminal, "_reply", None)
    monkeypatch.setattr(terminal, "_rendering", False)

    terminal.show_piece("# Heading\nand **bold**\n")
    terminal.end_reply()
    printed = capsys.readouterr().out

    assert printed == "# Heading\nand **bold**\n\n"
    assert "\x1b[" not in printed


@pytest.mark.parametrize(
    ("argv", "environment", "expected"),
    [
        ([], {}, True),
        ([], {"AXIOM_RENDER": "off"}, False),
        ([], {"AXIOM_RENDER": "0"}, False),
        (["--no-render"], {}, False),
        (["--no-render"], {"AXIOM_RENDER": "on"}, False),
    ],
)
def test_the_switch_follows_the_usual_precedence(
    argv, environment, expected, monkeypatch
):
    """AC 25. Flag beats environment beats default, as every setting does."""
    monkeypatch.delenv("AXIOM_RENDER", raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    assert config.resolve(argv).render_enabled is expected


def test_switching_off_tools_says_nothing_about_rendering(monkeypatch):
    """A decision, recorded: --no-tools takes the web and MCP, not this.

    Those are things the model may *do*. Rendering is about reading the answer,
    and someone who wants a session without tools has said nothing about how
    they want to read it.
    """
    monkeypatch.delenv("AXIOM_RENDER", raising=False)

    assert config.resolve(["--no-tools"]).render_enabled is True


def test_help_names_the_flag_and_its_variable(capsys):
    """AC 27."""
    with pytest.raises(SystemExit):
        config.parse_args(["--help"])
    text = capsys.readouterr().out

    assert "--no-render" in text
    assert "$AXIOM_RENDER" in text
    assert "NO_COLOR" in text


# --- NO_COLOR --------------------------------------------------------------


def test_no_color_drops_colour_and_keeps_formatting(monkeypatch):
    """AC 26.

    A decision, recorded: `NO_COLOR` means no *colour*, not no formatting. A
    heading stays bold and underlined; inline code loses its cyan. That is the
    published convention's own wording, and it is what Rich does natively - so
    the two agree instead of arguing.
    """
    monkeypatch.setenv("NO_COLOR", "1")
    emitted = stream("# Heading\nwith `inline code`\n")

    assert "\x1b[1" in emitted, "formatting was dropped along with the colour"
    assert not re.search(r"\x1b\[[0-9;]*3[0-7]m", emitted), "colour survived"


def test_no_color_reaches_the_colour_this_module_writes_itself(monkeypatch):
    """AC 26. Rich honours it for free; the fence styling is hand-written."""
    monkeypatch.setenv("NO_COLOR", "1")
    emitted = stream("```python\nx = 1\n```\n")

    assert "\x1b[36m" not in emitted, "fenced code kept its cyan"
    assert "x = 1" in stripped(emitted)


def test_colour_is_there_without_no_color(monkeypatch):
    """The other half - otherwise the test above passes on a broken renderer."""
    monkeypatch.delenv("NO_COLOR", raising=False)

    assert "\x1b[36m" in stream("```python\nx = 1\n```\n")


def test_no_color_set_to_nothing_still_counts(monkeypatch):
    """A decision, recorded.

    The convention says "not an empty string"; Rich tests for presence. Rich
    draws most of what reaches the screen here, so presence it is - a session
    where headings lose their colour and fenced code keeps it is worse than
    either rule applied consistently.
    """
    monkeypatch.setenv("NO_COLOR", "")

    assert "\x1b[36m" not in stream("```python\nx = 1\n```\n")


# --- What the model and the history see ------------------------------------


def at_a_terminal(monkeypatch):
    """Run the chat loop with rendering on, as a person would see it."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr(terminal, "_reply", None)
    monkeypatch.setattr(terminal, "_rendering", True)


def test_history_holds_the_reply_as_written_not_as_rendered(monkeypatch):
    """AC 16.

    Cycle 2 called this met because "the renderer sits below `show_piece`".
    That is an argument about where the code is, and the criterion is about
    what the model is sent - so here it is measured. A reply full of markdown
    goes back to the model with its markup intact and no escape sequence in it.
    """
    written = "# Heading\n\nsome **bold** words and a `snippet`.\n"
    backend = StubBackend(models=["a:1b"], turns=[[written], ["and again"]])
    at_a_terminal(monkeypatch)
    feed(monkeypatch, ["first", "second", "/exit"])

    main([], using=backend)

    carried = history(backend.streamed[-1])
    assistant = [m for m in carried if m.get("role") == "assistant"]
    assert any(m.get("content") == written for m in assistant), "history was rendered"
    assert not any("\x1b[" in (m.get("content") or "") for m in carried)


def test_a_reply_that_turns_out_to_be_a_call_never_reaches_the_renderer(
    monkeypatch, capsys
):
    """AC 20, with rendering on.

    The hold-back sits above `show_piece`, so a withheld reply is never fed to
    the renderer at all. Measured rather than argued: the text of the call must
    not appear on screen, styled or otherwise.
    """
    announced = '{"name": "read_file", "arguments": {"path": "x"}}'
    backend = StubBackend(models=["a:1b"], turns=[[announced], ["the answer"]])
    at_a_terminal(monkeypatch)
    feed(monkeypatch, ["do it", "/exit"])

    main([], using=backend)

    printed = capsys.readouterr().out
    assert announced not in printed, "the call was shown as though it were an answer"
    assert '{"name"' not in printed
    assert "read_file(path=x)" in printed, "the call was not made"
    assert "the answer" in printed, "the reply after the call never arrived"


def test_characters_the_console_cannot_spell_survive_rendering():
    """AC 24. Rendering must not become a second place a reply can die."""
    emitted = stream("a snowman ☃ and an emoji 🎉 in **bold**\n")

    assert "☃" in stripped(emitted)
    assert "🎉" in stripped(emitted)


# --- Scrolling, wrapping, resize -------------------------------------------


def test_a_reply_taller_than_the_screen_is_not_truncated(monkeypatch):
    """AC 11. `rich.Live` would have cut this to the screen height."""
    monkeypatch.setattr(terminal, "_width", lambda: 80)
    tall = "".join(f"line number {n}\n" for n in range(200))
    shown = [line for line in displayed(stream(tall)) if line.strip()]

    assert len(shown) == 200
    assert "…" not in " ".join(shown), "truncated with an ellipsis"


@pytest.mark.parametrize("width", [40, 80, 200])
def test_nothing_is_padded_out_to_the_console_width(width, monkeypatch):
    """AC 12."""
    monkeypatch.setattr(terminal, "_width", lambda: width)
    for line in displayed(stream("> a quoted line\n# a heading\nplain words\n")):
        assert line == line.rstrip(), f"padded out at width {width}"


def test_a_resize_mid_reply_cannot_corrupt_what_is_on_screen(monkeypatch):
    """AC 13, and it is a consequence rather than a feature.

    A resize corrupts a stream that redraws. Nothing here is redrawn, so the
    property to assert is that the committed lines survive a width moving
    under them - and that no cursor-up appears when it does.
    """
    widths = iter([80, 80, 40, 200, 30, 120, 60])
    monkeypatch.setattr(terminal, "_width", lambda: next(widths, 100))

    out: list[str] = []
    rendered = Rendered(write=out.append)
    for chunk in ("# One\n", "two **words**\n", "- three\n", "`four`\n", "five\n"):
        rendered.feed(chunk)
    rendered.finish()
    emitted = "".join(out)

    assert re.findall(r"\x1b\[\d*A", emitted) == []
    shown = [line for line in displayed(emitted) if line.strip()]
    assert len(shown) == 5, "a line was rewritten when the width moved"
    assert "five" in shown[-1]
