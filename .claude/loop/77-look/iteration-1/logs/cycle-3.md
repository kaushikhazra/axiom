# Cycle 3 — stage 2: the model chooser

2026-09-01, 16:27 +0530. Branch `feature/77-look`. Committed.

## The measurement

**Criteria demonstrably met: 13 of 37.** Moved by 6.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **13** | 1, 2, 3, 4, 6, 17, 18, 19, 20, 21, 31, 34, and 5 |
| 2 — already true, unproved | 5 | 11, 12, 13, 14, 16 |
| 3 — not started | 19 | 7, 8, 9, 10, 15, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 35, 36, 37 |

AC 5 — a host with one model shows no list — is counted because
`test_one_model_is_used_without_asking` was already asserting it and the panel
break turned it red along with the rest; it was not separately broken.

## The suite

    842 passed, 1 deselected, 79.15s     entering
    849 passed, 1 deselected, 79.51s     leaving

Arithmetic: 842 + 7 = 849. Seven new: the border, the column alignment, the
marked row's dressing, three parametrised cases of the tools annotation, and the
narrow window.

**`tests/baseline/transcript.txt` is untouched.**

## A leak I shipped in cycle 2, and the suite did not care

The three chooser test files passed on their own and **twelve tests failed in the
full suite.** That gap is the whole finding.

`tests/screen.py`'s `shown()` takes an optional `monkeypatch`:

    if monkeypatch is not None:
        monkeypatch.setattr(terminal, "_width", lambda: width)
    else:  # pragma: no cover - for scratch use outside pytest
        terminal._width = lambda: width

Every existing caller passes it. **The two AC 34 tests I added in cycle 2 did
not** — so they took the second branch and rebound `terminal._width` to 24
permanently, for every test that ran after them, for the rest of the session.

**Cycle 2's suite was green with that in place.** Nothing depended on the window
width strongly enough to notice. The panel is the first thing that does, and it
failed twelve tests the moment it existed — not because the panel is wrong, but
because it was being drawn into a 24-column window that a test file three
directories away had nailed shut.

The lesson is not "pass monkeypatch". It is that **a green suite said nothing
about global state for one whole cycle**, and what surfaced it was writing a
feature that happened to read the polluted value.

## Four parsers, one border, and a comparison of two empty lists

Four test files parsed the model list, each with its own filter, each keying on
*the line starts with a digit*. A border puts `│` first and broke all four at
once. They are now one `listed` helper in `conftest.py`.

One of the four was worse than the rest. In
`test_the_same_models_number_the_same_way_whatever_order_the_host_gives`:

    numbered = lambda text: [line for line in text.splitlines()
                             if line.strip().startswith(("1.", "2.", ...))]
    assert numbered(first.out) == numbered(second.out)

With the border it matches nothing in **either** run, so the assertion becomes
`[] == []` and passes. A test whose entire subject is "two host orders produce
one displayed order" would have gone on reporting success while looking at
nothing at all.

## Three of my own tests were hollow, and the break-proof found all three

Six breaks. Three came back green on the first attempt.

| criterion | verdict | what was actually wrong |
|---|---|---|
| AC 1 border | went red | — |
| AC 1 host | went red | — |
| AC 2 | went red | — |
| AC 3 | **stayed green** | the *break* was wrong, not the test |
| AC 4 | went red | — |
| AC 6 | **stayed green** twice | the break, then the test |

**AC 3.** The break removed the accent from the marked *name* and left it on
`(default)`, so the row was still dressed differently and the criterion still
held. A break that does not violate the criterion proves nothing about the test.
Rewritten to strip the whole row's marking; it then went red.

**AC 6, first attempt.** The break made the panel *wider* than the window, which
cannot crop anything. Rewritten to `no_wrap=True, overflow="crop"`.

**AC 6, second attempt.** Still green — and this time the test was wrong twice
over. It ran at 30 columns, where **nothing is squeezed at all**: every name fits,
so a renderer told never to wrap behaves identically. Measured the real boundary:

    width 36, 30, 24   every name intact
    width 20, 16, 12   not intact

Moved to 20. Then it failed on correct code, because a wrapped name arrives as
`qwen2.5-coder:` and `7b` on two rows **with a `│` between them**, and the check
removed whitespace and escapes but not the border glyphs. Wrapping in full is the
criterion being met; the test was reading it as a crop.

Third time it goes red on the break and green on the code.

## Two observations that are not criteria

- **The panel title truncates in a very narrow window.** At 20 columns the title
  reads `╭─ models on http:─╮`. AC 6 is about model names and holds, but a user at
  that width is not told which host. Worth knowing before stage 3, which puts the
  host in a panel too.
- **Under pytest the chooser is drawn with no colour at all**, because stdout is
  captured and `force_terminal=sys.stdout.isatty()` is False. That is correct
  behaviour — a redirected run should not be full of escapes — but it means every
  test in that file is looking at an uncoloured panel, and AC 3 had to force
  `sys.stdout.isatty` to check how anything is *dressed*.

## Assumptions changed

None.

## Next

Stage 3: the info panel, the voice, the tool summary and the prompt — AC 7 to 16
and 22 to 33. Five functions replaced, eight test files, and **78 baseline lines
read as a diff rather than regenerated**. This is the stage the loop was warned
about.
