# Cycle 2 — 2026-08-31, started 16:27 +0530

## Where the artifact stands

**6 of 44 criteria demonstrably met**, up from 2. No new behaviour was written this cycle;
four criteria moved out of the second bucket by having their breaks run, and one moved by
being measured.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **6** | AC 4, AC 12, AC 13, AC 28, AC 33, AC 41 |
| implemented, test passes, break not yet run | 5 | AC 1, AC 23, AC 24, AC 26, AC 27, AC 30 |
| not started | 33 | everything else |

AC 3 remains half-built and is still not counted: the cost line includes the catalogue but
does not name skills apart from tools.

## Movement

From 2 to 6. Four breaks were run, three of them found what they were aimed at and one
found something extra.

## The suite

    791 tests, all passing, 77.18s (last cycle 791 / 78.18s)

Arithmetic: 791 + 0 written this cycle = 791. Holds. No test was added, and none should
have been - this cycle ran breaks and shortened a string.

Wall clock down 1.0s on an unchanged suite, which is run-to-run variance rather than a
signal. Watched because a faster suite is the shape a vacuous test makes: a single-file run
reported 0.24s where earlier runs reported 0.95s, and that was chased with `--durations`
before it was dismissed. The session-level test still does 0.02s of real work. Nothing has
gone hollow.

## The breaks

**1. Instructions cached at load** — a `body` field on `Skill`, populated in `_one`,
returned by `instructions()`. This is the implementation AC 33 exists to forbid, and it is
the one a later cycle would have drifted into because it is simpler.

Two tests went red, and the second was not expected:

    test_instructions_are_read_at_invocation_not_at_load     (AC 33)
    test_a_skill_removed_since_startup_says_so               (AC 41)

**AC 41 failed by returning `'Do the thing.'` for a file that had been deleted.** That is
not an abstract failure - it is the cached implementation literally handing back stale
instructions for a skill that no longer exists, which is the exact wording of the
criterion. Cycle 1 argued this test could not pass under a cache. It could not; but the
run also showed that one implementation choice breaks two criteria at once, which the
argument did not.

**2. Duplicate-name guard removed** — `first = None`. One test red, AC 28. Clean.

**3. Required-field check removed** — `missing = []`. One test red, AC 4. But it went red
with a `KeyError`, not an assertion.

That is worth keeping. Without the guard, `_one` **raises** rather than returning a
problem, and nothing between it and `read()` catches it - so a malformed skill would take
down startup rather than costing that one skill. It is safe today only because the guard
runs before `parsed["name"]` is ever reached. **AC 43 says no skill failure ends the
session, and that safety currently rests on ordering rather than on structure.** Put a
guard around the whole of `_one` when AC 43 is built.

All three reverted, green re-established after each.

## What the catalogue costs now

Re-measured against cycle 1's table, same synthetic directory:

| | chars before | chars now | tokens before | tokens now |
|---|---|---|---|---|
| standing prompt, no skills | 616 | 616 | 154 | 154 |
| one skill | 1006 | **857** | 251 | **214** |
| three skills | 1182 | **1033** | 295 | **258** |
| five skills | 1358 | **1209** | 339 | **302** |

**The preamble went from 302 characters to 153 - about 37 tokens off every request**,
whatever the skill count. Per-skill cost is unchanged at 88 characters, about 22 tokens.

The first skill now costs 60 tokens rather than 97, of which 22 is the skill. The
explanation outweighs the content until two skills rather than four. Still the wrong shape,
but no longer badly so.

## An assumption that changed

**The preamble is not a token-optimisation problem.** Cycle 1's action treated it as one.
It is also the only lever on AC 15 - a model reaching for a skill instead of answering from
memory - and the cheapest wording is not automatically the one that gets that right.

Shortening it further on taste is now explicitly forbidden in the docstring. The final
wording is an empirical question and it belongs to the cycle that measures AC 15, not to
this one. Recorded here because it is a change to how the loop should think about that
string, not just a change to the string.

## Goal check

**Not met.** 6 of 44. Next action written.
