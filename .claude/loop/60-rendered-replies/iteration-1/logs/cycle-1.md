# Cycle 1 — read the prior art, and found it does not solve AC 7

2026-08-28 03:07–03:35 IST. Fail-safe 07:07 IST.

**539 tests, green and hermetic** - unchanged by adding the dependency. **Transcript unchanged**,
as this row requires. No production rendering written.

## The dependency

`rich>=14.2.0` in `pyproject.toml`; `uv sync` installed **rich 15.0.0** with `markdown-it-py
4.2.0` and `mdurl 0.1.2`. Three packages, 6 → 7 direct dependencies, first since `mcp` in #43.
The full suite ran again after installing and **not a single test moved**.

## The prior art, and the finding

`action.md` asked what each reference does to avoid redrawing what is already on screen. The
answer is that **none of them avoids it.**

| reference | approach |
|---|---|
| `simonw/llm` PR #571 | `with Live(Markdown("")) as live:` then `live.update(Markdown(md))` on every chunk - the whole reply reconstructed each time |
| `md2term` | explicit full redraw: *"clears previous output using `\033[1A\033[2K` (move up, clear line) for each rendered line"* |
| `richify` | "Live Display: updates the rendered content in real-time" - the same shape, undocumented in detail |

So **AC 7 asks for something no reference implements.** That is worth knowing before cycle 2
starts, because the obvious move - copy the merged PR from a well-known project - produces
exactly the behaviour the criterion forbids.

## I measured the naive approach wrongly, and the disagreement caught it

First measurement: 4.6x byte amplification, 11 cursor-up sequences. Second, on the same
approach: **0 cursor-ups**, all content present, identical byte counts across three different
terminal heights and both overflow modes.

Three settings that should differ producing identical numbers is not a result, it is a broken
instrument. **A `StringIO` with `force_terminal=True` does not reproduce `Live`** - it checks for
a real terminal and behaves differently without one. I was measuring the harness.

Windows has no pty here, so there is no sound way to capture real `Live` output from this
session. **Recorded as a limitation rather than worked around**, and the question answered from
Rich's source instead - which is evidence, where the capture was not.

This is the same fault the cold reads keep finding, committed by me: a measurement that cannot
tell the thing under test from the scaffolding around it. #62's cycle 1 nearly published a
conclusion from one; here the numbers disagreed loudly enough to expose it.

## What Rich actually does, from its source

**`LiveRender.position_cursor`** emits, on every refresh:

```
CARRIAGE_RETURN, ERASE_IN_LINE, then (CURSOR_UP, ERASE_IN_LINE) * (height - 1)
```

where `height` is the previous render's height. **Every line already on screen is erased and
rewritten on every chunk.** That is AC 7 violated by construction, not by accident.

**`LiveRender.__rich_console__`** handles content taller than the screen:

```python
if height > options.size.height:
    if self.vertical_overflow == "crop":      lines = lines[: options.size.height]
    elif self.vertical_overflow == "ellipsis": lines = lines[: height - 1] + ["..."]
```

`"ellipsis"` is the default. So on a reply longer than the terminal - which is every reply this
row exists for - **the naive approach shows only the last screenful with an ellipsis while it
streams.** That is not one criterion failing but three: AC 5 (every character reaches the
screen), AC 7 (a shown line does not move), and AC 11 (everything above stays in scrollback).

## Decision — commit finished lines, re-render only the tail

Settled by the above rather than by preference. Completed lines are printed normally, so they
enter the terminal's own scrollback and can never be moved again. Only the unfinished tail is
subject to re-render, and it is by definition shorter than the screen.

`Live` is therefore **not** the mechanism for the committed part. Rich remains the right
dependency - it does the markdown parsing, the syntax highlighting and the layout, which is all
of the work that is not this. Cycle 2 uses `Console.render_lines` or equivalent to get formatted
lines out of Rich without letting it own the cursor.

## The real stream, measured

`qwen2.5:7b`, a reply with a heading, bullets and a fenced Python block:

```
chunks           : 77
sizes            : min 1 max 10 mean 4.1
chunks of 1 char : 13 of 77
total chars      : 318
```

**Four characters a chunk.** A fence opener ` ```python ` arrives across two or three chunks, so
a renderer sees ` `` `, then ` ```pyt `, then the rest. AC 9 - never showing an incomplete
construct as complete - is a per-character problem, not a per-line one, and AC 8 forbids holding
the characters back while it resolves.

## Status — all 29 criteria

| criteria | status |
|---|---|
| AC 1–29 | `not-started` |

Nothing implemented; this cycle was research, the dependency, and two measurements, by design.

## Cycle 2 will

Implement, at the `terminal.show_piece` / `end_reply` seam:

1. A renderer that accumulates text, decides which lines are **final** - safely past any
   construct that could still change - prints those once, and re-renders only what follows.
2. Plain text when output is not a terminal, checked first and cheaply.
3. AC 20's hold-back left alone: `_could_still_be_a_call` still governs whether anything is
   shown at all, and the renderer only sees what it releases.

The measurements to take: no line emitted twice, no cursor-up above the committed region, and
every character present in the stripped output.
