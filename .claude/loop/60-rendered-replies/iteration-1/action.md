# Action

**Close the four gaps cycle 2 named.** The renderer is built, committed and measured;
read `logs/cycle-2.md` first, particularly the status of all 29 and the two bugs that
only a break-and-watch found.

This is not a cold read. Cycle 2 said what is missing, so finding it again would be
theatre. The cold read is cycle 4, once there is a complete thing to read coldly.

## 1. Check the ground

- Full suite. **567 is the floor.**
- Golden transcript **unchanged**. If it moves, stop and find out why first.
- `python .tmp/break60.py` — all eight breaks still caught, no survivors.

## 2. Tables (AC 1)

The one place AC 1 and AC 7 genuinely pull against each other, and it is soluble.

**Hold table rows, and only table rows.** A line that looks like a table row is not
committed; it is kept. When a line arrives that is not one — or the reply ends — the
whole table is rendered at once and committed, then the line that ended it is handled
normally. Nothing already shown ever moves, because the held rows were never shown.

This is the *only* construct that gets held. It does not become a general buffering
mechanism; AC 8 forbids that for fences and AC 10 forbids it for everything else.

Two things to get right, and a test for each:
- a reply that **ends** mid-table still shows those rows — `finish()` flushes them
- a "table" that is one stray `| pipe |` line is shown, not swallowed

The held rows are echoed as they arrive, like any other incomplete line? **Decide this
and say why.** Echoing then redrawing a multi-line block would need cursor-up, which is
forbidden — so the honest answer is likely that table rows are the one thing the user
waits a line or two for. Say so in the log, and measure how long the wait actually is.

## 3. The switch (AC 25, AC 26, AC 27)

There is none. Nothing is started here.

- A flag, an environment variable, and a default — **flag beats environment beats
  default**, the same precedence every other setting in `config.py` uses. Follow what is
  there; do not invent a second mechanism.
- **`NO_COLOR`** (AC 26) is a separate, published convention: if it is set to anything at
  all, colour is off. Honour it. Decide and record whether `NO_COLOR` kills *colour* or
  kills *rendering* — they are not the same thing, and a heading can be bold without
  being coloured.
- **`--help`** (AC 27) describes the switch, in the voice the other options use.
- Rendering off must give **today's output exactly** — the same path AC 14 already takes.
  That makes it testable against the same bytes.

## 4. Scrolling, wrapping, resize (AC 11, AC 12, AC 13)

Cycle 2 called these "an argument, not a measurement" and it was right. They follow from
committing plain lines and never redrawing — so **assert the property that makes them
true**, rather than trying to simulate a terminal:

- **AC 13** is the sharp one. A resize cannot corrupt what is on screen because nothing
  on screen is ever rewritten. Test it by changing the width *mid-stream* and asserting
  no committed line is touched and no cursor-up appears.
- **AC 12** — the rendered width follows the console width, and no line is padded out to
  it. The padding bug is already fixed; pin it at more than one width.
- **AC 11** — scrollback is whatever the terminal does with ordinary writes. The testable
  half is that a reply taller than the screen emits no truncation and no ellipsis, which
  is exactly what `rich.Live` would have done.

## 5. Then

Full suite, hermeticity, transcript. **Extend `.tmp/break60.py`** with a break for each
new behaviour — a switch that ignores the environment, a table that never flushes,
`NO_COLOR` unread — and record survivors. A test written for a criterion and never seen
to fail is not evidence.

**Commit each piece as it goes green.** Cycle 2 lost the whole renderer to a stray
`git checkout --` because it sat uncommitted through a long break-and-watch; it was
recovered from a `.pyc`, and that is not a recovery to rely on twice.

## Record

Status for all 29, with what changed since cycle 2's table. The table decision and the
measured wait. What `NO_COLOR` was taken to mean, and why. The new breaks and what caught
them.

**Write no questions into anything.** Decide, record the decision and the reasoning,
carry on.
