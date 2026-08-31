# Cycle 7 — 2026-08-31, started 18:08 +0530

## Where the artifact stands

**32 of 44 criteria demonstrably met**, up from 26.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **32** | AC 1-13, 17-24, 26-28, 30, 33, 36-39, 41, 42 |
| implemented, break not run | 0 | — |
| not started | 12 | AC 14, 15, 16, 25, 29, 31, 32, 34, 35, 40, 43, 44 |

## The off switch

`--no-skills` and `$AXIOM_SKILLS`, following `--no-web` down to the `OFF_VALUES` handling.
`--no-tools` takes skills with it, for the reason it already takes the web: three of the
four skill tools are how a model reaches a skill at all, and a catalogue offered to a model
that cannot call anything is a paragraph of prompt with nothing behind it.

**Switched off, the directory is never read.** Not read and then ignored - AC 38 says
nothing about any skill reaches the model, and the cheapest way to keep that promise is for
there to be nothing to leak.

Off drops all four tools, `write_skill` included. Empty drops three and keeps it. The
difference is that a user who typed `--no-skills` is not waiting to write their first one.

## The distinction the criteria forced

AC 39 wants the startup line to say **whether** skills are on. AC 1 wants a run with no
skills to say **nothing**. Those are only in conflict if "off" and "none" are the same
state, and they are not: one was asked for.

So off is said and empty is silent. `/skills` with the feature off says "skills are off for
this run", not "no skills loaded" - the second would send a user off to write a skill into a
folder that would never be read.

## The break that produced a better answer than the code

Regenerating the golden baseline produced exactly one new line: `axiom: skills off`, on a
`--no-tools` scenario.

That is correct and it is also noise. `--no-tools` already tells the user everything is off,
and the web does not announce itself separately under it. A second line naming a feature the
user never mentioned is repeating a fact they already have.

Only a run that switched skills off *specifically* is now told so. **The baseline was
restored rather than regenerated, and the suite is green against it** - observable behaviour
for every existing scenario is byte-identical to before this cycle. That is a better outcome
than a baseline update, and it was only visible because the diff was read rather than
accepted.

## The breaks — nine, all narrow

Last cycle's lesson applied: break one thing.

| break | red | counts |
|---|---|---|
| the count dropped from the line | 3 tests | AC 2 |
| the token share dropped | 1 | AC 3 |
| startup problems not named | 1 | AC 4's startup half |
| off is silent at startup | 1 | AC 39 |
| the variable beats the flag | 4 tests | AC 37 |
| the tools still declared when off | 1 | AC 38 |
| the commands behave as though there are none | 1 | AC 38 |
| a run with no skills says "0 skills" | 1 | AC 1 |
| skills default to off | **14 tests** | AC 36 |

Six of the nine turned exactly one test red, which is what a narrow break looks like.

**AC 36's break turned fourteen red**, and that is not a failure of the break - it is what
"on by default" means. Every test of the feature runs with the default, so defaulting to
off takes all of them. Its own test is among them and its own assertion is the description
failing to reach the model.

## A test I wrote badly and fixed

`test_the_flag_turns_skills_off` carried an assertion built out of `sent.split(...)` string
gymnastics, which failed for reasons having nothing to do with the criterion. Replaced with
a direct comparison against `catalogue_text` - the thing that must not be in the payload.

## The suite

    811 -> 820 tests, all passing, 78.15s

Arithmetic: 811 + 9 = 820. Holds. Wall clock flat against last cycle's 78.34s.

## Assumptions that changed

None.

## Goal check

**Not met.** 32 of 44. Next action written.

**AC 15 and AC 16 have not been started and they need live models.** The fail-safe is at
21:30. They are the long pole and the next cycle takes them.
