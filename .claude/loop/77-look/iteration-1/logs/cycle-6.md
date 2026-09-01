# Cycle 6 — the voice, and the goal met

2026-09-01, 17:27 +0530. Branch `feature/77-look`. Committed.

**The loop is over. The cron was deleted.**

## The measurement

**Criteria demonstrably met: 37 of 37.** Moved by 3.

Every one is in bucket 1 — met with a test that has been shown to go red when the
behaviour is removed. Nothing is claimed on the strength of the code looking right.

## The suite

    870 passed, 1 deselected, 89.82s     entering
    873 passed, 1 deselected, 91.00s     leaving

Arithmetic: 870 + 3 = 873.

**`tests/baseline/transcript.txt` is untouched. Six cycles, zero lines** — and this
cycle changed the one function that could have moved all 78 of them at once.

## The conversion, and the trap it was written around

`VOICE` opened 44 f-strings. **Ten of them are multi-line calls.** A regex over
lines handles the 34 single-line ones and silently skips the rest, which would
have left ten lines still reading `axiom: ...` while every test passed — AC 28 is
a claim about *every* line, and a path that happens to be tested cannot settle it.

So the conversion walked parentheses instead: find the mark, walk back to the
enclosing call, walk forward to its close, rewrite. Counted at both ends, 44 in
and 43 converted with one left by hand, and every conversion printed to be read.

Three things it caught that a line-based pass would not:

- **`say`'s own body.** Written as an f-string opening with `VOICE`, it looked
  exactly like the 44 others and was converted into a call to itself. Rewritten as
  `VOICE + " " + message`, with a comment saying why, because the next person to
  scan for that pattern will hit the same thing.
- **A comment of mine** containing the literal pattern, which stopped the walk.
- **`file=sys.stderr` on its own line.** Four multi-line calls kept the keyword
  after the conversion and failed with `say() got an unexpected keyword argument`.
  They failed loudly, which is the good case.

## Two criteria covered but cited nowhere

Found by grepping the criteria numbers out of the tests and diffing against the
issue — one command, and a habit #75 earned:

    cited: 35 of 37     missing: [5, 19]

- **AC 5** — a one-model host shows no list. The existing test asserted no
  *question* was asked, which is a **different claim**: a build that printed the
  list and then chose for you would have passed it. #77 puts that list in a
  border, which makes it much more of a thing to print at someone unasked.
- **AC 19** — a known language keeps its highlighting. Covered by a test that
  cited #60's AC 2 and nothing else.

Both now carry the citation and a break. Covered-by-accident is one step from
believed-covered, and neither would have failed if the behaviour had been dropped
on purpose.

## Breaks

Five: three for the voice, two for the criteria found uncited.

| criterion | break | verdict |
|---|---|---|
| AC 27 | axiom's own lines drawn at full strength | went red |
| AC 28 | the name goes back on every line | went red |
| AC 29 | a failure is sent to stdout with everything else | went red |
| AC 5 | a one-model host is shown the list anyway | went red |
| AC 19 | a known language is no longer highlighted | went red |

Two of the three voice breaks were wrong on the first attempt and neither was
subtle: one escaped the `·` so it never matched, and one patched the formatter
when the stream is chosen by the caller. **Fourth cycle running that a break
needed re-aiming before it proved anything**, which is now less a warning than a
measured rate: roughly one break in four is aimed at the code rather than at the
criterion.

## What the loop learned, in the order it learned it

Six cycles. The findings that generalise:

> **A green suite says nothing about global state.** Two tests added in cycle 2
> permanently rebound `terminal._width` to 24 for everything that ran after them.
> Cycle 2 was green. It surfaced in cycle 3 only because the panel is the first
> thing that reads the window width.

> **A fixture cannot force a terminal.** `monkeypatch.setattr("sys.stdout.isatty",
> ...)` in a fixture runs in the setup phase and `capsys` swaps `sys.stdout` again
> for the call phase. Five tests failed; the dangerous two **passed**, asserting
> text common to both branches while checking the wrong one.

> **An instrument can hide the thing it is pointed at.** `screen.py` read every
> `J` as "erase from the cursor down", so a screen cleared with `[2J` still showed
> what had been on it — and AC 8 was measured against that in cycle 4.

> **Ask whether the code can be shaped so the baseline is restored rather than
> updated.** 78 lines were expected to change. Zero did, because AC 33 already
> required the panel to be terminal-only. The criterion and the baseline were
> saying the same thing from two directions.

> **A break that does not violate the criterion proves nothing.** AC 3's break
> left the marker accented, AC 6's made the panel wider, AC 26's removed an erase
> that `end_turn` performed anyway. All three stayed green and all three were the
> break being wrong, not the test.

> **A boundary test that is not at the boundary is not a boundary test.** AC 6 ran
> at 30 columns, where nothing is squeezed. The real edge was 20, measured.

## Assumptions changed

None, across six cycles. The design agreed on 2026-09-01 was implemented as
written.

## What is left, and it is for a person

The goal is met and **none of it has been driven by hand.** 873 tests say the
behaviour holds; nobody has looked at it.

- **#77 itself** — run it and look. `cd C:\Projects\.tmp\axiom-manual` then
  `uv run --project C:/Projects/axiom axiom`. The mock-ups under `.tmp/` are what
  it was designed to look like; the question is whether the real thing does.
- **One divergence from the mock to judge** — the tool summary is drawn *below*
  the answer, not above it. `logs/cycle-5.md` says why.
- **The manual pass over #72, #73 and #74** was paused mid-flight for this work.
  Findings so far are at `.tmp/testing-72-73-findings.md`; #74 was never started
  and the screen model does not reach it, because scheduling is about elapsed time.
- **Two criteria in #77 were inferred rather than asked for** — AC 10, the screen
  clears once and never again, and AC 35, a bare run says no more than before.
  Both now hold and both were the agent's reading of what Kaushik wanted.
- **Nothing is merged.** `feature/77-look` is six commits ahead of `master`.
