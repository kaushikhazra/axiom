# Cycle 1 — the survey, and where the seam is

2026-09-01, 20:46 +0530. Read-only by instruction. `src/` untouched.

## The measurement

**Criteria demonstrably met: 0 of 36.** Nothing was proved this cycle; nothing was
meant to be.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **0** | — |
| 2 — already true, unproved | 8 | 12, 13, 14, 30, 31, 32, 34, 35 |
| 3 — not started | 28 | 1–11, 15–29, 33, 36 |

Bucket 2 is entirely the guards - single lines, commands, piped input, `--no-render`,
scheduled prompts, and the two exits. They describe behaviour that ships today and they
are what this work must not break. **AC 33 is deliberately not among them**: "a single-line
session produces exactly the bytes it produces today" cannot be true-but-unproved before
there is a change to compare against.

## The suite

    876 passed, 1 deselected, 84.09s

Matches what `loop.md` recorded on entry. `master` is at `936fd1e`.

## The library survey

Four candidates. The rule is `~/.claude/CLAUDE.md`'s: search before building, and present
alternatives rather than a single name.

### prompt_toolkit — **recommended**

3.0.53, BSD, Python >= 3.10. **One dependency: `wcwidth`.** A pure-Python package of a few
hundred lines. That is a smaller footprint than most of what axiom already carries.

It answers the hard question, and it answers it in a way worth writing down exactly, because
the obvious guess is wrong. From `src/prompt_toolkit/input/win32.py` on main:

    b"\x0d": Keys.ControlM,   # enter
    b"\x0a": Keys.ControlJ,

    if ((control_key_state & self.LEFT_CTRL_PRESSED
         or control_key_state & self.RIGHT_CTRL_PRESSED)
        and result and result.key == Keys.ControlJ):
        return [KeyPress(Keys.Escape, ""), result]

So on Windows **ctrl+enter does not arrive as a key called "ctrl+enter"**. It arrives as
`\x0a` with the control state set, and prompt_toolkit turns that into **escape followed by
ControlJ** - the VT100 convention for a meta-modified key. The bindings are therefore:

    enter        c-m               accept the message
    ctrl+enter   escape, c-j       insert a newline

That is a real finding and not a detail: a cycle that binds `"c-enter"` will find no such
key, and one that binds a bare `c-j` will also catch a plain ctrl+J.

**Consequence to hold on to:** ctrl+enter and ctrl+J are indistinguishable to it, because
they are indistinguishable to the console. Nothing can recover that. Ctrl+J is not otherwise
used here, so the collision costs nothing - but it should be a decision rather than a
surprise.

What it brings that would otherwise be hand-written: multi-line buffers, backspace, arrow
keys, home, end, word-delete, kill-line, history, and bracketed paste. That last one is what
AC 9 needs.

### pyreadline3 — rejected

3.5.6, released 2026-05-14, no runtime dependencies. It exists to give Windows a GNU
readline so `input()` keeps working, which is attractive: the seam would not move.

Rejected because readline is **line-oriented by construction**. Its editing buffer is one
line; multi-line composition is not something it exposes, and its documented multi-line
support is a paste helper that *strips empty lines* - the opposite of AC 18. Custom key
bindings exist but bind to readline's own commands, and there is no command for "insert a
newline into a buffer that does not have more than one line".

### A hand-rolled reader on `msvcrt` — rejected

Stdlib only, no dependency, and the probe already proved it can see the key. Rejected on
what comes with it: the moment axiom reads raw it owns backspace, arrows, home, end,
word-delete and history. **A half-built line editor is worse than none**, and axiom has
`input()`'s behaviour today for free. It is also Windows-only, which makes AC 6 unreachable
rather than merely unimplemented.

### textual / urwid — rejected

Full-screen TUI frameworks. Both take the alternate screen buffer and own the whole
terminal, which puts them directly against `Rendered` - the thing that streams a reply line
by line into the *normal* buffer and has seven cycles of #72, #73 and #77 invested in how it
does that. Replacing the reader must not mean replacing the renderer.

### What would have to be true for the recommendation to be wrong

- **If `prompt_toolkit` cannot be confined to the terminal path.** It installs its own
  output handling, and if importing or constructing it disturbs `sys.stdout` for a piped
  run, AC 30 fails and the golden transcript moves. **Cycle 2 must prove the confinement
  before anything else.**
- **If it fights `Rendered`.** Both write to the same terminal. The reader is only alive
  while the user types and the renderer only while a reply streams, so they should never
  overlap - but "should" is an argument, and this one is measurable.
- **If bracketed paste is not on by default on this console.** AC 9 leans on it.

## Where the seam is

`terminal.read_line(timeout=None)` is the only reader of a typed line, and it has two paths
already:

    timeout is None    input(_prompt()).strip()      every existing caller
    timeout given      Typed(...).next(timeout)      only when something is scheduled

`Typed` wraps a second reader on a thread so a scheduled job can fire while the user sits
idle. **Both call `builtins.input`.**

`use_input(read=...)` exists to substitute the reader behind the *timed* path, and its
docstring says why: a module-level singleton is wrong for a test suite.

### And this is the finding that matters

**Every test in the suite supplies input by monkeypatching `builtins.input`** -
`conftest.feed` does exactly that, and 876 tests depend on it.

A terminal-only reader is therefore **unreachable from any existing test**, because no test
runs at a terminal. That is not a problem to solve later; it decides the shape of cycle 2:

- the plain path must keep calling `builtins.input`, so `feed` keeps working and the
  baseline does not move
- the composing path needs its own substitution hook, the way `use_input` is one for the
  timed path, or **nothing about #80 is testable at all**

## What a test will never be able to prove

The manual pass's brief, started now rather than at the end. A test can feed bytes to a
reader; it cannot press a key, and it cannot be a terminal.

| criterion | why only a person can settle it |
|---|---|
| 2, 3 | that the console really delivers ctrl+enter and enter differently, through the library, on his machine |
| 4, 22, 23 | that a part-composed message *looks* unsent, and that its lines are visible |
| 5 | that the hint appears at the moment a second line starts, and reads as help rather than noise |
| 7, 8, 9 | that a real paste - the terminal's own bracketed-paste burst - arrives whole |
| 24 | that abandoning feels like abandoning |

Everything else is reachable by driving the reader directly.

**#77's lesson applies without modification**: its entire visible behaviour was on a path no
test process could enter, 876 tests said it held, and the one defect that mattered was found
by a person looking. This loop starts with that list instead of discovering it at the end.

## Assumptions changed

None. `assumption.md` named `prompt_toolkit` a candidate rather than a conclusion; this
cycle promotes it to a recommendation, with the confinement question named as the thing that
could still overturn it.

## Next

Cycle 2: prove the confinement, then add the dependency. Not the other way round.
