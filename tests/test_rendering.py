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

from axiom import terminal
from axiom.terminal import Rendered


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
