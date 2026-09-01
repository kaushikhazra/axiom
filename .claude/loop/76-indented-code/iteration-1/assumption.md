# Assumptions

## The renderer is a streaming line classifier, and that is the constraint

`_Rendered` in `terminal.py` sees one line at a time as it arrives and commits it before the
next one exists. It holds exactly one construct — a table — and #60 AC 8 and AC 10 forbid
holding anything else: a fence's contents must appear as they stream, and nothing else may be
buffered at all.

**AC 10 pulls straight against that.** *"An indented block of many lines is shown as one block
rather than as one block per line"* is a statement about several lines together, and the only
tool that has ever produced one is holding. The table is the precedent and it is a narrow one:
a table is held because its column widths are unknowable until the last row, and that
justification does not transfer.

This tension is the story. Do not resolve it by quietly buffering — that reopens #60, whose
whole point was that a held line is a line the user watched being taken back. The likely shape
is **state, not a buffer**: the classifier remembers that a block is open and styles each line
as part of it, exactly as `self._fence` already does for a fenced block. Cycle 1 measures
before deciding.

## AC 4 is #73's, and #73 already settled it

> A line indented four spaces *inside* a list is still a list item at its own depth, and is not
> treated as code.

`_depth` keeps a **stack of indents seen**, not arithmetic, because Markdown nests relative to
the parent's content column — three for `1. `, two for `- `. Dividing an indent by four gets
mixed lists wrong, and that is written into `_depth`'s docstring as AC 2 and AC 5 of #73.

**The naive rule for this issue — "four or more leading spaces is code" — turns every nested
bullet into a code block.** It is the first thing anyone would write and it undoes a shipped
story. Whatever recognises an indented block has to run *after* the list check and only when no
list is open.

## What is already known about the bug

Filed from an observation, not from reading code: a model that indents its example rather than
fencing it produces a block whose lines are cut. The renderer's own path is the suspect —
`_as_markdown` is handed one line, and Rich rendering `    foo` alone has no way to know it is
part of a block.

**Cycle 1 measures this rather than assuming it.** Capture the real thing with `tests/screen.py`
before changing a line.

## The instrument, and it is not the byte stream

`tests/screen.py` is a terminal small enough to reason about. #60 spent two cycles marking a
criterion met against a byte stream where the promise was true and the screen was wrong — every
long paragraph drawn twice while no cursor-up sequence was ever emitted.

**Every criterion in this issue about what the user sees is measured on a modelled screen.**
Asserting that text is present in the output proves nothing: the plain echo puts it there
whatever the renderer did.

`tests/screen.py` had its own defect once — it read every `J` as "erase from cursor down",
so a cleared screen still showed prior content, and #77 AC 8 had been measured against it.
The instrument gets attacked too.

## Constraints from the repository

- **Branch `feature/76-indented-code`**, from `master` at `936fd1e`. A cycle that wakes on
  `master` switches; it does not commit. The repo's hooks refuse a commit on master outright.
- **`.claude/loop/` on this branch carries the queue and #80's records.** They were brought
  across from `feature/80-multiline` deliberately so the loop's own bookkeeping travels while
  `src/` and `tests/` stay at `master`. #80's code is **not** here and must not be pulled in.
- `uv run pytest` stays green and hermetic. The live lane stays deselected by default.
- **No test builds a `prompt_toolkit` session** — the queue's Standing, earned by two machine
  crashes on #80. This row should never come near it; the rule binds anyway.
- **No compound shell commands.** One per invocation, Bash and PowerShell alike.
- **Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
  diff and before the previous log.

## What a test cannot do here

A test process is not a terminal, and every rendering path is gated on `_rendering` and
`sys.stdout.isatty()`. The tests force both and measure through `tests/screen.py`, which proves
what axiom *emits* and not what a console *draws*. **Keep the list of what only a person can
confirm**, every cycle, and hand it to the manual pass at the end — #72, #73 and #74 are
already waiting on one.
