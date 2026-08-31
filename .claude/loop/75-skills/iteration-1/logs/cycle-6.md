# Cycle 6 — 2026-08-31, started 17:47 +0530

## Where the artifact stands

**26 of 44 criteria demonstrably met**, up from 19. The second bucket is still empty.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **26** | AC 1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 30, 33, 41, 42 |
| implemented, break not run | 0 | — |
| not started | 18 | AC 2, 3, 14, 15, 16, 25, 29, 31, 32, 34-40, 43, 44 |

## The two commands

`/skills` lists; `/skill <name> [text]` runs one. Both handled where `/model` is - before
`terminal.start_turn()`, so a command that never becomes a turn leaves no stray gap, which
is already load-bearing for #60's AC 7 and AC 8.

`/skills` is matched by equality **before** `/skill` is matched as a prefix. The other order
reads `/skills` as `/skill` with an argument of `s`, which makes listing unreachable and
looks like a missing feature rather than a bug. There is a test for the ordering itself.

A skill's instructions become the turn, with any trailing text after them - so the skill
reads as context for what was asked rather than as the thing being asked about.

AC 14 is already true and is **not counted**: a skill the model invokes goes through
`note_tool` like any other tool, which is exactly what the criterion asks for. It has no
test yet.

## The breaks — eight, and two had to be run twice

| break | red | counts |
|---|---|---|
| `/skill` loads the instructions but never asks | AC 7, AC 8 | AC 7 |
| unknown skill asks the model anyway | AC 9, AC 10 | both |
| listing shows names without descriptions | AC 5 | AC 5 |
| the skill is not announced | AC 11 | AC 11 |
| `/skills` disabled, so it falls through to `/skill` | 3 tests | ordering |
| no-skills message drops the path | AC 6 | AC 6 |
| trailing text dropped | AC 8 | AC 8 |

**AC 6 and AC 8 each went red twice, and only the second time counted.** The first was a
by-product: the ordering break stopped `/skills` working at all, and the AC 7 break stopped
any turn happening. Both are setup failures of the kind cycle 3 was caught by. Their own
breaks - drop the path from the message, drop the trailing text - were run separately and
landed on their own claims.

That is the third cycle where a break turned red for the wrong reason. It is not an
accident: **a break big enough to be easy to write is usually big enough to take several
tests with it.** The narrow break is the one that proves something.

## The scripted-break hazard, again

Cycle 5 recorded that a scripted break printing nothing must be treated as not run. This
cycle the script printed **`NO MATCH -- break not run`** for AC 8, because the search string
contained a backslash escape and did not match the file.

The guard added last cycle worked - it said so instead of staying quiet - and the break was
re-run through the Edit tool, where it turned exactly one test red. **Backslash escapes in a
scripted replace are now two-for-two at failing silently or falsely.** Anything containing
one goes through Edit.

## The test that was written and then removed

`test_invoking_a_skill_whose_file_has_gone_says_so` passed on the first run and was deleted
anyway. It removed the `SKILL.md` **before** the session started, so the catalogue was empty,
the command took the "no such skill" path, and the assertion about not asking the model
passed for a reason that had nothing to do with AC 41. It also carried dead code from an
abandoned approach.

A test that passes for the wrong reason is worse than no test, because the count says the
criterion is covered. AC 41 keeps its library-level test, which is real; the command path
needs a hook to delete the file mid-session and did not get one this cycle.

## The suite

    804 -> 811 tests, all passing, 78.34s

Arithmetic: 804 + 8 written - 1 removed = 811. Holds.

**Wall clock 78.34s, and that settles the question from cycles 4 and 5.** Four measurements
now: 79.08, 91.34, 87.28, 78.34 - on a suite that grew by seven fast tests. It has returned
to the bottom of the band it started in, which a regression does not do. Load, as recorded.

## Assumptions that changed

None.

## Goal check

**Not met.** 26 of 44. Next action written.
