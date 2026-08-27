"""A terminal, small enough to reason about, so a test can see the screen.

Counting escape sequences says what was *sent*. AC 7, AC 11 and AC 12 are about
what is *on the screen*, and the two stop agreeing the moment a line is longer
than the window - which, for a model writing prose, is most lines.

Cycle 4 wrote this because cycles 2 and 3 both marked AC 7 met by counting
cursor-up sequences in the byte stream, and every long paragraph was appearing
on screen twice while that count stayed at zero.

Only what the renderer actually emits is interpreted: `\\r`, `\\n`, cursor-up,
erase-to-end-of-line, erase-to-end-of-screen, and printable text with wrapping.
Colour is discarded - it is not what these criteria are about.
"""

import re

from rich.cells import cell_len

from axiom import terminal
from axiom.terminal import Rendered


_SGR = re.compile(r"\x1b\[[0-9;]*m")
_CSI = re.compile(r"\x1b\[(\d*)([A-Za-z])")

# The right-hand half of a wide character. It holds a column without holding a
# character, which is what lets a row be measured in columns and read as text.
CONTINUED = None


class Screen:
    """Rows of cells, and a cursor, and nothing else."""

    def __init__(self, width: int) -> None:
        self.width = width
        self.rows: list[list[str | None]] = [[]]
        self.row = 0
        self.column = 0

    def _room(self) -> None:
        while len(self.rows) <= self.row:
            self.rows.append([])

    def _newline(self) -> None:
        self.row += 1
        self.column = 0
        self._room()

    def _put(self, character: str) -> None:
        # A wide character takes two columns and a terminal wraps it whole
        # rather than splitting it across two rows.
        cells = max(1, cell_len(character))
        if self.column + cells > self.width:
            self._newline()
        self._room()
        row = self.rows[self.row]
        while len(row) < self.column + cells:
            row.append(" ")
        row[self.column] = character
        for extra in range(1, cells):
            row[self.column + extra] = CONTINUED
        self.column += cells
        if self.column >= self.width:
            self._newline()

    def _truncate(self, to_end_of_screen: bool) -> None:
        self._room()
        del self.rows[self.row][self.column :]
        if to_end_of_screen:
            del self.rows[self.row + 1 :]

    def feed(self, stream: str) -> None:
        stream = _SGR.sub("", stream)
        at = 0
        while at < len(stream):
            character = stream[at]
            if character == "\r":
                self.column, at = 0, at + 1
            elif character == "\n":
                self._newline()
                at += 1
            elif stream.startswith("\x1b[", at):
                found = _CSI.match(stream, at)
                if not found:
                    at += 1
                    continue
                count, letter = int(found.group(1) or 1), found.group(2)
                if letter == "A":
                    self.row = max(0, self.row - count)
                elif letter in ("K", "J"):
                    self._truncate(to_end_of_screen=letter == "J")
                at = found.end()
            else:
                self._put(character)
                at += 1

    def text(self) -> list[str]:
        """The lines a person would read off the screen."""
        drawn = [
            "".join(c for c in row if c is not CONTINUED).rstrip() for row in self.rows
        ]
        return [line for line in drawn if line.strip()]


def shown(reply: str, width: int = 80, chunk: int = 4, monkeypatch=None) -> list[str]:
    """What a terminal `width` columns wide ends up showing for `reply`.

    The renderer is told the same width as the screen. They have to agree: a
    renderer measuring one window while the terminal wraps at another leaves
    rows behind, and that is a real failure rather than a test artefact.
    """
    if monkeypatch is not None:
        monkeypatch.setattr(terminal, "_width", lambda: width)
    else:  # pragma: no cover - for scratch use outside pytest
        terminal._width = lambda: width

    out: list[str] = []
    rendered = Rendered(write=out.append)
    for start in range(0, len(reply), chunk):
        rendered.feed(reply[start : start + chunk])
    rendered.finish()

    screen = Screen(width)
    screen.feed("".join(out))
    return screen.text()
