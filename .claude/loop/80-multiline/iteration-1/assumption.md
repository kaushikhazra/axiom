# Assumptions

## The binding is decided, and it was measured rather than chosen

Kaushik, 2026-09-01, at his own console. **Do not re-derive this by asking him to press
keys again.**

    Enter        0d   \r
    ctrl+enter   0a   \n      distinct - this is what makes the binding possible
    shift+enter  0d   \r      identical to enter; unusable
    alt+enter    taken by the window manager; unusable

**ctrl+enter starts a new line, enter sends.** Shift+enter - what most chat clients bind -
cannot be seen on this console, and alt+enter never reaches the program at all.

**This is one console's answer.** On most Linux and macOS terminals ctrl+enter sends a plain
`\r`, indistinguishable from enter. That is why AC 6 exists: somewhere that cannot report
the key, a user must still be able to send more than one line, and must be told how. AC 6
was written by the agent rather than asked for, and is the cheapest criterion to strike if
it fights the implementation.

## What that costs, and it is the real work

`input()` is line-buffered: the console's line discipline consumes the newline and hands
over a finished string, so **the keypress never reaches axiom at all**. Telling `\n` from
`\r` means reading keys in raw mode, and from that moment axiom owns backspace, arrow keys,
home, end, word-delete and history - everything it currently gets for free.

**A half-built line editor is worse than none.** `~/.claude/CLAUDE.md`: *reuse before build -
search for existing libraries first; if multiple exist, present with recommendations.*

`prompt_toolkit` is the obvious candidate - multi-line buffers, custom key bindings, Windows
console support, and on Windows it reads through the console API rather than a byte stream.
Enter arrives as `ControlM` and ctrl+enter as `ControlJ`, which are separate keys to it.
**It is a candidate and not a decision**: it is not currently a dependency, and cycle 1 is
to survey rather than to assume.

## The split that keeps the suite alive

#77 landed on it and #80 needs the same one: **anything that reads keys is terminal-only.**

    piped or redirected   one turn per line, exactly as today
    at a terminal         ctrl+enter composes, enter sends

The golden transcript is 477 lines captured from a `StringIO`, and every test in the suite
drives axiom by feeding it lines. If reading keys reaches that path, the baseline moves and
several hundred tests change meaning. It has not moved in seven cycles across two issues.

## Constraints from the repository

- **Branch `feature/80-multiline`.** A cycle that wakes on `master` switches; it does not
  commit. The repo's hooks refuse a commit on master outright, and a push while standing on
  master - whatever it targets.
- `uv run pytest` stays green and hermetic. The live lane stays deselected by default.
- **No compound shell commands.** One per invocation, Bash and PowerShell alike.
- A new dependency goes in `pyproject.toml` and is justified in the cycle log.
- **Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
  diff and before the previous log.

## What a test cannot do here

A test cannot press a key. Everything about ctrl+enter is reachable only by feeding bytes to
whatever reads them, which proves the reader and not the terminal. #77's whole visible
behaviour sat on a path no test process could enter, and the one defect that mattered was
found by a person. **Keep the list of what only a person can confirm**, every cycle, and
hand it to the manual pass at the end.
