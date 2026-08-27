# Cycle 2 — the cold read

2026-08-28 01:21–01:38 IST. Fail-safe 04:42 IST.

Criteria read from `gh issue view 55` **before** the diff and before cycle 1's log.
**490 tests, green and hermetic** (was 487). Transcript unchanged. No stray `.axiom/`.

Not a genuinely fresh reader - no second agent - and `observe.md` asks that this be said rather
than a cold read claimed that was not cold.

## The finding is a conflict between two criteria, not a defect in the code

**AC 1 and AC 7 disagree about a file that exists and holds nothing.**

An empty `model.json` - a `touch`, or a write interrupted half-way - is a real state.
`read_choice` returns None and `unreadable` returns True, so **no remembered choice has ever
been written there**. AC 1 says the first time axiom writes its remembered choice into a
directory, it names the file. AC 7 says the announcement is decided by *the file being there*,
and it is there.

Both readings are literal. They cannot both be satisfied.

**Decision: AC 7 wins, and the behaviour stands.** Announcing here means announcing on *every*
run for as long as the file stays unusable - noise piled on a problem rather than help. And the
user is not left unaware, which is the purpose AC 1 serves: an unusable file already produces
its own line from #48 AC 33, naming the path and saying axiom is carrying on as though nothing
had been chosen. They are told about the file, by a different sentence, and that sentence is
more useful than this one would be.

Recorded as a test, `test_an_empty_file_counts_as_the_file_being_there`, which asserts the
silence **and** asserts the other line appears - so the trade is visible rather than implied,
and a later change that removes the second line will break it.

## The attacks that found nothing

- **A route that writes without announcing** - the one that would satisfy all four of AC 10's
  negatives while violating AC 1. There is none: `models.write_choice` has exactly one call
  site, inside `_remember`, and `_remember` has exactly two, both of which announce. AC 1 is
  structurally safe rather than merely tested.
- **AC 11 with the write failing rather than the directory.** Cycle 1 patched `mkdir`, which is
  the folder failing. Patching `write_text` leaves `.axiom/` created and `model.json` absent -
  the state where an implementation deciding from the folder would be at its most wrong. It
  reports the failure and claims nothing. Now a test.
- **A directory where the file should be.** `exists()` is true, nothing is announced, the write
  fails with a permission error, the failure is reported and no file is claimed. Now a test.
- **AC 9's comparison.** The strip takes everything from `axiom: remembering` onward, so it
  cannot hide a difference in the announcement - only in the prompt that shares the line, which
  is the harness. Confirmed by reading both captured lines.
- **AC 2's assertion.** It requires `model.json` present and `mcp.json` absent from the line.
  A path naming something else that merely contained `model.json` would have to *be* the choice
  file, since it is printed from `DEFAULT_CHOICE_FILE` directly.

## The nine that survive the break, each judged

Cycle 1 reported "5 red" and did not name the nine that were not.

| test | verdict |
|---|---|
| `test_a_directory_with_nothing_in_it_is_told_too` | **fine** - AC 4 is explicitly the case that already worked; cycle 1 documented that it cannot catch the bug, which is the point |
| `test_the_second_run_says_nothing` | **fine** - AC 5 holds under both conditions, and still fails for an implementation that announces every time |
| `test_choosing_the_same_model_again_says_nothing` | **fine** - same shape, AC 6 |
| `test_a_run_that_writes_nothing_announces_nothing` ×3 | **fine** - AC 10's routes never call `_remember`, so they are unaffected by this row by construction. Weak alone, which is why the pairing positive exists |
| `test_a_run_with_no_terminal_announces_nothing` | **fine** - AC 10's fourth route, same reasoning |
| `test_the_negatives_are_not_vacuous` | **fine, and worth stating** - it survives because it uses the same empty directory the negatives use, where the old behaviour also announces. Its job is to rule out an implementation that never speaks, and it does that either way. Making it discriminate would mean a different fixture from the negatives it is pairing with, which would break the pairing |
| `test_a_failed_save_says_so_and_claims_no_file` | **fine** - AC 11's failure path is unchanged by this row |

None vacuous. Every one is a *still*-or-guard assertion that should hold on both sides.

## Status — all 11 criteria

| criteria | status |
|---|---|
| AC 1–11 | `met-with-evidence` |

AC 1 with the noted conflict resolved in AC 7's favour, recorded above and in a test.

## Exit

Converged - `loop.md` exit 1. Commit, push, PR referencing #55, merge, delete the branch. Then
mark row 12 done, scaffold row 13 (#56), mark it running. **The cron is not touched.**
