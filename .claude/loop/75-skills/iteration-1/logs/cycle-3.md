# Cycle 3 — 2026-08-31, started 16:47 +0530

## Where the artifact stands

**8 of 44 criteria demonstrably met**, up from 6.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **8** | AC 4, AC 12, AC 13, AC 18, AC 19, AC 28, AC 33, AC 41 |
| implemented, test passes, break not run *for that criterion* | 9 | AC 1, AC 17, AC 20, AC 21, AC 22, AC 23, AC 24, AC 26, AC 27, AC 30, AC 42 |
| not started | 27 | the two commands, configuration, compaction, exit |

## The four tools exist

`skills.Library` holds the directory, the catalogue and the ability to refresh it, and is
injected into tools through `needs_library` - the twin of #74's `needs_schedule`, which was
followed rather than re-invented as the action asked.

`fault_in()` is now the single rule for what a valid skill is, used by the loader to report
one that will not load and by `write` to refuse one. Written once deliberately: two sets of
rules would drift, and the first sign would be a skill that writes without complaint and
then refuses to load.

AC 42 is satisfied **by construction** - validation happens before the file is opened, so
there is no path where a refused write has already truncated a good skill.

## The suite

    791 -> 801 tests, all passing, 79.08s (last cycle 791 / 77.18s)

Arithmetic: 791 + 10 = 801. Holds.

Wall clock up 1.9s for ten filesystem tests. Proportionate.

## The break

**`write` no longer refreshes the catalogue.** Four tests went red:

    test_a_written_skill_is_catalogued_at_once                    (AC 18)
    test_writing_over_a_skill_changes_what_the_model_is_told      (AC 19)
    test_a_refused_write_leaves_the_previous_version_untouched    (AC 42)
    test_a_hand_written_skill_and_a_written_one_behave_the_same   (AC 22)

**Only the first two count, and the reason matters.**

AC 42 and AC 22 went red because their *setup* writes stopped registering, not because the
thing they assert stopped being true. A break that turns a test red for the wrong reason
proves the test is sensitive to something; it does not prove it is sensitive to its own
criterion. Counting those two here would be exactly the self-deception observe.md exists to
prevent.

AC 42 needs its own break - move validation to *after* the file is opened for writing - and
AC 22 needs one that makes a tool-written skill differ from a hand-written one. Next cycle.

## The cost, and it is now a real problem

The golden baseline caught the change, and every line of its 48-line diff is one of two
facts. Nothing else about observable behaviour moved.

| | before | after |
|---|---|---|
| tools declared | 10 | **14** |
| tools cost, per request | 1111 tokens | **1507 tokens** |

**Four skill tools cost 396 tokens on every request, with no skills configured at all.**

Set against the history this is worse than it looks:

| branch | tools | cost |
|---|---|---|
| `master` before #74 | 7 | 807 |
| after #74's scheduler | 10 | 1111 (+38%) |
| after #75's skills | 14 | **1507 (+87% on 807)** |

A project with no skills directory now pays 396 tokens per request for four tools it cannot
use. **AC 1 says axiom with no skills "starts as it does today", and paying 36% more for
nothing is not that.**

The fix is not a smaller description. `read_skill`, `delete_skill` and `invoke_skill` are
meaningless with an empty catalogue and should not be declared when it is empty;
`write_skill` must always be declared, because writing the first skill is how a catalogue
stops being empty. That is a design decision about what varies per run, and `_prepare`
already varies declarations by `--no-web`, so the seam exists.

**This wants Kaushik's eye.** It is the same trade #61's line was built to expose, and the
second time in three stories that a feature has quietly taxed every request.

## Assumptions that changed

None.

## Goal check

**Not met.** 8 of 44. Next action written.
