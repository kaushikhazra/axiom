# Cycle 1 — where things stand before anything is written

2026-09-01, 15:47 +0530. Read-only by instruction. `src/` untouched.

## The measurement

**Criteria demonstrably met: 0 of 37.**

Not a claim that nothing works — a claim that nothing has been *proved* this cycle.
Bucket 1 requires a break watched going red, and cycle 1 ran no breaks. Seventeen
criteria describe behaviour that already ships and have tests around them; each needs one
break to be promoted, and that is cycle 2's cheapest work.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **0** | — |
| 2 — already true, unproved | 17 | 3, 4, 5, 6, 11, 12, 13, 14, 16, 19, 21, 31, 32, 33, 34, 35, 37 |
| 3 — not started | 20 | 1, 2, 7, 8, 9, 10, 15, 17, 18, 20, 22, 23, 24, 25, 26, 27, 28, 29, 30, 36 |

Two in bucket 2 are regression guards rather than features — **34** (a reply's words are
unchanged) and **35** (a bare run says no more than before) are trivially true right now
and can only be proved against the change that threatens them. They are the last two to
close, not the first.

**15 is in bucket 3 and looks like bucket 2.** "The reason this model was settled on is
shown *with the model*, not as a separate statement." Today it is a separate line -
`axiom: using qwen3.5:9b - your last choice here`. The fact is shown; the criterion is
about where.

## The suite

    836 passed, 1 deselected, 83.40s

Matches the figure `loop.md` recorded on entry. Nothing to investigate.

## The accent constant, and how NO_COLOR reaches it

**No new mechanism is needed, and one existing one is about to die.**

`_colourless()` has **exactly one caller** — terminal.py:918, the hand-written cyan on an
unlexed fence. AC 20 makes that line return `line` unchanged, so `_colourless()` becomes
dead code the moment stage 1 lands. It should be deleted, not kept warm.

Everything else already gets `NO_COLOR` from Rich, which its own docstring says out loud:
*"Rich tests for presence, and Rich draws most of what reaches the screen here."*

**Verified rather than assumed** — the gold theme rendered with `NO_COLOR=1` through the
real pipeline:

    gold bytes present under NO_COLOR: False
    any SGR at all:                    True

Colour gone, attributes kept. That is AC 31's behaviour, for free.

**So the accent is a module-level constant in `terminal.py`, applied through a Rich
`Theme`.** Do not add a third path.

## Two holes found by reading, both about things that will look fine

### The NO_COLOR guard cannot see the colour we are about to add

`test_no_color_drops_colour_and_keeps_formatting` (test_rendering.py:679) is the guard for
AC 31. It looks for colour with:

    re.search(r"\x1b\[[0-9;]*3[0-7]m", emitted)

Measured against the three forms:

| | caught |
|---|---|
| cyan, 16-colour `\x1b[36m` | **yes** |
| gold, truecolor `\x1b[38;2;218;169;0m` | **no** |
| gold, 256-colour `\x1b[38;5;178m` | **no** |

The regex matches only the 16-colour range. **A gold that survived `NO_COLOR` would leave
this test green.** The behaviour happens to be correct today, so this hole ships a working
feature with a guard that is not guarding it — the worst kind, because it will read as
covered. AC 31 is bucket 2 for exactly this reason and cannot move to bucket 1 until the
regex covers `38;2` and `38;5`.

### Removing the cyan deletes the only expression of a recorded decision

Three tests reference `\x1b[36m` as a *negative*: lines 693 and 718, plus 287's set
comparison. Once the unlexed fence is plain, **all three pass vacuously** - there is no
cyan to find whatever the renderer does.

Line 718 is the one that matters. It records a deliberate decision:

> The convention says "not an empty string"; Rich tests for presence. Rich draws most of
> what reaches the screen here, so presence it is.

`NO_COLOR=` with nothing after it counts. That decision is expressed in exactly one place -
`_colourless()` - and checked in exactly one place - line 718. Stage 1 removes both. The
decision does not become wrong; it becomes **Rich's**, untested here and unstated anywhere
except a docstring that is being deleted with the function.

That is a defensible hand-off and it must be a deliberate one. Either keep a test that
asserts Rich's presence-semantics directly, or record in the commit that axiom no longer
holds an opinion and defers to the renderer.

## The vacuous negatives — corrected

I said "four" while planning. **It is eleven**, and the split matters:

| pattern | count | where | at risk? |
|---|---|---|---|
| `"which model?" not in` | 7 | test_models 249, 258, 267, 623, 637; test_switch 121, 542 | **no** — the prompt keeps that wording |
| `"models on" not in` | 4 | test_models 250, 622; test_switch 120, 160 | **only if the title is shortened** |

The design already defuses these: the panel title carries `models on <host>` **whole**, so
all eleven keep meaning. The risk is not the change as designed — it is someone later
shortening the title to `models`, at which point four assertions go quiet without failing.
Whoever writes that title should know four tests are leaning on it.

## The `_as_markdown` seam

`_as_markdown` builds its own `Console` inline and takes no theme. `.tmp/mock_reply.py`
proved a themed Console renders correctly through the real pipeline; it did not settle how
the theme arrives.

**It needs no signature change.** A module-level `Theme` referenced inside the function,
the same way `_CONTAINED` is referenced inside it today. Every call site is untouched, and
the two callers that pass `width`/`wrapped` for a nested item stay as they are.

`_highlighted` keeps `theme="ansi_dark"` — that is Syntax's own palette for a known
language and AC 19 requires it to stay.

## Assumptions changed

None.

## Next

Stage 1 of the build order: the reply's palette and the unlexed fence, AC 17 to 21, plus
widening the AC 31 guard so the colour being added is a colour the suite can see.
