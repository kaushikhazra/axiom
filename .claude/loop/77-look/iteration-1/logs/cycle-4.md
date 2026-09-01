# Cycle 4 — stage 3, first half: the facts panel and the clear

2026-09-01, 16:47 +0530. Branch `feature/77-look`. Committed.

## The measurement

**Criteria demonstrably met: 24 of 37.** Moved by 11.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **24** | 1–21 except 5 and 10 are all in, plus 31, 33, 34 — full list below |
| 2 — already true, unproved | 0 | — |
| 3 — not started | 13 | 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 35, 36, 37 |

Bucket 1: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
21, 31, 33, 34.

## The suite

    849 passed, 1 deselected, 79.51s     entering
    861 passed, 1 deselected, 80.12s     leaving

Arithmetic: 849 + 12 = 861, all twelve in the new `tests/test_facts.py`.

## The baseline did not move, and that is the result

`git status tests/baseline/` is empty. **78 of 477 lines were expected to change
and 0 did.**

The action for this cycle said to ask, before regenerating anything, whether the
code could be narrowed so the baseline is *restored* rather than updated. It can,
and the answer was already written into the issue:

> **AC 33** — Redirected and piped output are unchanged, byte for byte.

The golden transcript is captured from an `io.StringIO`, which is not a terminal.
So AC 33 does not merely permit a terminal-only panel, it **requires** one. The
criterion and the baseline were saying the same thing from two directions and
neither had to be traded against the other.

The shape is the one `use_rendering` already chose for replies: one plain path,
which is the path the transcript records, and a rendered path on top of it. Two
renderers read **one set of arguments** rather than keeping two sets of sentences,
so the panel and the plain lines cannot drift.

Zero of the 78 lines regenerated means zero chance of a real change hiding in a
diff nobody could read. That was the whole risk this stage carried.

## A green suite that proved nothing, for five tests

Worth writing down carefully because it will happen again to anyone testing a
terminal.

    @pytest.fixture
    def at_a_terminal(monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)

**This does not work.** A fixture runs in pytest's *setup* phase; `capsys` swaps
`sys.stdout` again for the *call* phase. The patch lands on an object that no
longer exists by the time the test body runs, `isatty()` reads False, and
`show_facts` takes the plain path.

Five tests failed outright, which was lucky. The dangerous ones were the two that
**passed** — they asserted text that appears on *both* paths, so they were green
while checking the branch they were not written for.

`tests/test_rendering.py` already had `at_a_terminal` as a plain function called
inside the test body. It was written that way for this reason and the reason was
not recorded, so it was rediscovered from scratch. It is recorded now, in the
function's own docstring.

The general shape: **a test that forces an environment in a fixture and asserts on
behaviour that differs by environment can be green about the wrong branch.**

## Breaks

Eleven, all narrow, all red on the first attempt — the first cycle where that has
happened.

| criterion | break |
|---|---|
| AC 7 | the screen is never cleared |
| AC 8 | something is printed between the clear and the facts |
| AC 9 | the clear takes the scrollback with it |
| AC 10 | the screen is cleared more than once |
| AC 11 | the cost is left off the panel entirely |
| AC 12 | an unknown cost is reported as zero rather than left out |
| AC 13 | servers are listed without their tool counts |
| AC 14 | a run with no skills is told about them anyway |
| AC 15 | the reason goes back to a statement of its own |
| AC 16 | what failed to load is not shown at all |
| AC 33 | the panel is drawn whether or not there is a terminal |

AC 9's break is the one worth keeping: `\x1b[3J` alongside `\x1b[2J`. The two are
indistinguishable the moment they run and differ only in whether the user can
scroll back to what was there. Asserting on Rich's promise rather than on the
bytes would not have caught it.

## A design decision taken this cycle, and it should be seen

**The clear happens immediately before the panel, not immediately after the
choice.** AC 7 says choosing a model clears the screen and AC 8 says the facts are
what follows *immediately*. Between the two, MCP servers start, and that can take
seconds and prints `starting N MCP servers...`. Clearing at the moment of choice
would leave that line sitting between the clear and the panel, which AC 8 forbids
on a literal reading.

Clearing just before the panel satisfies both: the clear is still caused by
choosing, and nothing comes between it and the facts. The transient server line is
wiped, which is what a transient line is for.

## Assumptions changed

None.

## Next

Stage 3, second half: the voice, the tool summary and the prompt — AC 22 to 30,
32, 35, 36, 37. `note_tool` is the one to be careful with: AC 22 and AC 26 say
nothing per call stays on screen, and the failure mode is a transient line written
and never erased, which looks fine in a fast test and leaves a trail in a real
terminal.
