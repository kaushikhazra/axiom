# Cycle 2 — stage 1: the reply's palette, and the unlexed fence

2026-09-01, 16:07 +0530. Branch `feature/77-look`. Committed.

## The measurement

**Criteria demonstrably met: 7 of 37.** Moved by 7 — the loop's first.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **7** | 17, 18, 19, 20, 21, 31, 34 |
| 2 — already true, unproved | 10 | 3, 4, 5, 6, 11, 12, 13, 14, 16, 33 |
| 3 — not started | 20 | 1, 2, 7, 8, 9, 10, 15, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 35, 36, 37 |

AC 32, 35 and 37 moved from bucket 2 to bucket 3 — not a regression, a
correction. They are guards against *this work*, and until the work that
threatens them exists they are not "already true", they are untested.

## The suite

    836 passed, 1 deselected, 83.40s     entering
    842 passed, 1 deselected, 79.15s     leaving

Arithmetic: 836 + 6 = 842. Two tests were renamed rather than added, one
assertion was removed as stale, and six are new — the probe check, the split-out
known-language case, the accent test, the foreground test, and two AC 34 guards.

**Wall clock fell 4.2s and that was checked, not shrugged at.** No test was made
to do less: the removed assertion was one comparison inside a test that still
runs, and the two AC 34 additions cost time rather than save it. Re-running the
entering suite on this machine gave 79-83s across runs, so the movement is the
machine, not the work.

**`tests/baseline/transcript.txt` is untouched** — `git status tests/baseline/`
is empty. Predicted in cycle 1 and confirmed: rendering is gated on
`sys.stdout.isatty()` and the transcript captures a non-tty, so stage 1 cannot
reach it.

## Two defects, neither introduced by this work

### The guard for AC 31 could not see the colour being added

Cycle 1 found it; this cycle fixed it *before* adding any colour, which is why
it is worth recording as a defect rather than a chore. The probe was
`\x1b\[[0-9;]*3[0-7]m` — the 16-colour range only. A truecolor accent is
`38;2;r;g;b` and a 256-colour one is `38;5;n`; neither matches. **An accent that
survived `NO_COLOR` would have left the test green.**

Widened to catch all three, and the widening is itself asserted against all three
forms plus bold, dim and reset — a regex nobody watched work is the same hole one
layer down.

### `_colourless()` claimed Rich agreed with it, and Rich does not

This one is older and worse. Its docstring said:

> Presence, not truth: `NO_COLOR=` with nothing after it counts. The published
> convention says "not an empty string", but **Rich tests for presence**.

Measured this cycle: with `NO_COLOR=""` Rich emits the accent regardless. It
follows the published wording, not presence.

**Nothing caught it because the only test of the rule went through the one colour
this module wrote by hand** — the cyan fence fallback, which obeyed `_colourless()`
and never asked Rich anything. So two rules were in force at once, and with
`NO_COLOR=` a fence lost its colour while every heading kept its own. **That is
the exact inconsistency the docstring said it was avoiding**, and it shipped for
the whole of #60.

Presence is kept — it is the recorded decision and the stricter reading of the
two — and it is now **imposed** on every Console that draws rather than assumed of
one. `_colourless()` therefore survives #77 rather than being deleted as cycle 1
expected; its job grew from one hand-written colour to the whole screen.

**This is a behaviour change and it should be seen as one:** a run with
`NO_COLOR=` set to the empty string now loses every colour, where before it lost
only a fence's cyan. It is what the recorded decision always said, made true for
the first time.

## The break-proof caught one of my own tests testing nothing

Seven breaks, each narrow, each applied to a copy and reverted:

| criterion | break | verdict |
|---|---|---|
| AC 17, 18 | the theme is never handed to the reply Console | went red |
| AC 19 | a known language is no longer lexed | went red |
| AC 20 | the unlexed fence is painted again | went red |
| AC 21 | the answer is accented too | went red |
| AC 31 | `NO_COLOR` left to Rich rather than imposed | went red |
| AC 34 narrow | #72's containment undone, containers crop | **stayed green**, then red |
| AC 34 words | a word dropped from every rendered line | went red |

`test_no_character_is_lost_in_a_window_too_narrow_to_hold_them` **stayed green
with #72's containment undone underneath it.** Its source was a heading, a short
quote and a long paragraph — and cropping happens only inside a *container*, so
there was nothing in it wide enough to crop. It asserted the boundary in its name
and tested the middle of the range. Fixed by putting a long quote and a long list
item in it; it now goes red.

That is the second time in two cycles that a first-time pass turned out to be
hollow. The rate the loop's `observe.md` assumes is holding.

## One thing the fence work exposed about the old tests

Three assertions referenced `\x1b[36m` as a *negative*. With the cyan gone, all
three would have **passed vacuously** rather than failing — they were re-pointed
at the accent, not deleted. The two positives failed honestly and were rewritten.

`test_a_fence_is_set_apart_from_the_prose` is now two tests. It used to claim the
code line is always dressed differently from prose; that is true only when a lexer
exists. The part true for every opener — the fence *marker* is dressed differently
— stays parametrised over all three, and the lexed-only half is split out. Without
the split, AC 20 would have quietly taken the highlighting of every block with it
and three parametrised cases would have gone green saying the edges were fine.

## Assumptions changed

None. The design was followed as written; `_colourless()` surviving is a
consequence of a defect found, not a design change.

## Next

Stage 2: the model chooser, AC 1 to 6. Self-contained, never touches the baseline.
Roughly 30 assertions, 11 of them the price of aligned columns. The panel title
must carry `models on <host>` **whole** — four negative assertions lean on that
phrase and go quiet rather than red if it is shortened.
