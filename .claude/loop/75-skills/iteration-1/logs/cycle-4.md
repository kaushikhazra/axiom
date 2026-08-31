# Cycle 4 — 2026-08-31, started 17:08 +0530

## Where the artifact stands

**9 of 44 criteria demonstrably met**, up from 8.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **9** | AC 1, AC 4, AC 12, AC 13, AC 18, AC 19, AC 28, AC 33, AC 41 |
| implemented, test passes, break not run *for that criterion* | 10 | AC 17, AC 20, AC 21, AC 22, AC 23, AC 24, AC 26, AC 27, AC 30, AC 42 |
| not started | 25 | the two commands, configuration, compaction, exit |

Only one criterion moved for a lot of work. That is the honest count: the cycle's main
achievement was making AC 1 *true*, and one break proved it.

## The cost, fixed

| | cycle 3 | now |
|---|---|---|
| tools declared | 14 | **11** |
| cost per request | 1507 | **1250** |

`read_skill`, `delete_skill` and `invoke_skill` are no longer declared while the catalogue
is empty. `write_skill` always is - writing the first skill is how a catalogue stops being
empty, and gating it would make the feature unreachable from a fresh project, which is the
state every project starts in.

**257 tokens back on every request.** Against the history:

| | tools | cost |
|---|---|---|
| `master` before #74 | 7 | 807 |
| after #74 | 10 | 1111 |
| #75 cycle 3 | 14 | 1507 |
| #75 now | 11 | **1250** |

**The residual is 139 tokens for `write_skill` alone, on a project with no skills.** That is
not nothing, and AC 1 says a run with no skills starts as it does today. The honest position:
it cannot go lower while the feature stays reachable, and AC 37's off switch is what will
take it to zero for a user who does not want it. Recorded rather than rounded up.

## The breaks

**1. Declarations not rebuilt after a write.** `restate_skills` returns after restating the
prompt. One test red:

    test_writing_the_first_skill_brings_invoke_into_existence

This is the dead end the gating invites and the reason that test exists. A session that
starts empty is not offered `invoke_skill`; writing the first skill has to bring it into
being, or the model is told about a skill it has no way to call. **No unit test of the
library could catch it**, because the library is not what decides what is offered.

**2. No gating at all** - `_without_unusable_skill_tools` returns everything. Eight tests
red across three files, including both `test_switch` cases and five in `test_tool_cost`.
AC 1 counted.

Both reverted, green re-established.

## The suite

    801 -> 804 tests, all passing, 91.34s (last cycle 801 / 79.08s)

Arithmetic: 801 + 3 = 804. Holds.

**The wall clock went up 12 seconds for three tests, and that was chased rather than
waved through.** `--durations=8` puts the eight slowest at 5.03s, 4.92s, 4.83s, 3.55s,
3.04s, 2.78s, 2.78s, 2.77s - **all of them pre-existing MCP and command-kill tests that
wait on real bounded timeouts.** None of the three new tests appears anywhere near the top;
`test_skills.py` runs complete in about 1s.

The shift is uniform across a suite whose slowest members are real waits, which is what
machine load looks like and not what a new slow test looks like. **If it persists at ~91s
next cycle with no tests added, it wants a second look** - the point of the rule is that a
timing change is never nothing.

## Two test files had to change, and neither was weakened

`test_tool_cost.py` asserted the reported figure against `tools.declarations()` - the whole
registry. That stopped being what a run declares. The first attempt read the real payload
back from `StubBackend.tools_sent`, which would have been stronger; **it does not work here,
because these runs never take a turn** - the cost line is printed at startup, before
anything is streamed, so there is no payload. Replaced with a named `offered()` helper
derived from `SKILL_TOOLS` and `WEB_TOOLS`, so a tool added to either follows automatically.

`test_switch.py` derived `ALL_TOOLS` from `len(tools.REGISTRY)` with a comment saying a
literal count turns every new tool into a spurious failure - which #74 had already caused
once. The derivation now follows what is *offered* rather than what exists.

The golden baseline was regenerated and its diff read: 48 lines, every one of them the tool
count or the cost. Nothing else about observable behaviour moved.

## Assumptions that changed

None.

## Goal check

**Not met.** 9 of 44. Next action written.
