# Cycle 1 — 2026-08-31, started 16:08 +0530

## Where the artifact stands

**2 of 44 criteria demonstrably met.** Both are the ones the feature turns on.

The number is deliberately not eleven. Eleven criteria have tests that pass; two have
tests that have been **shown to go red when the behaviour is removed**, and observe.md
only counts the second kind.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **2** | AC 12, AC 13 |
| implemented, test passes, break not yet run | 10 | AC 1, AC 4, AC 23, AC 24, AC 26, AC 27, AC 28, AC 30, AC 33, AC 41 |
| not started | 32 | everything else |

AC 3 is half-built: the cost line now counts the catalogue, and a test derives the figure
rather than hard-coding it, but the line does not yet *name* skills separately from tools,
which is what the criterion actually asks for.

## Movement

From 0. This is the first cycle.

`src/axiom/skills.py` is new — the loader, the catalogue, and `instructions()`. The
catalogue reaches the model through `tools.system_prompt`, which gained an optional second
argument rather than a second system message, so there is still exactly one thing to weigh
when the cost of a request is reported.

## The suite

    775 -> 791 tests, all passing, 78.18s (baseline 775 / 78.56s)

Arithmetic: 775 + 16 written this cycle = 791. Holds.

Wall clock flat, which is what sixteen filesystem unit tests should look like. Nothing here
waits on anything.

## What the catalogue costs

The measurement observe.md asks for, taken against a synthetic directory:

| | characters | tokens |
|---|---|---|
| standing prompt, no skills | 616 | 154 |
| one skill | 1006 | 251 |
| three skills | 1182 | 295 |
| five skills | 1358 | 339 |

**The fixed preamble is 302 characters — about 75 tokens — and each skill line is 88
characters, about 22.** So the first skill costs 97 tokens of which only 22 is the skill
itself. The paragraph explaining what a skill is outweighs the catalogue until there are
four of them.

That is a real cost and it is the wrong shape. It is also the thing to fix next, because
every later cycle measures against it.

At zero skills the addition is exactly zero characters — not a heading with nothing under
it. There is a test for that, because "no skills" and "a skills section that is empty" cost
differently and only one of them is right.

## The break that was run

**Catalogue leaks the body.** `catalogue_text` changed to append the first 200 characters
of each skill's instructions after its line — the realistic failure, the one that looks
like a helpful feature.

Two tests went red, and the one that matters is the second:

    test_the_catalogue_carries_the_description_and_not_the_instructions
    test_a_skills_body_never_reaches_the_model_until_it_is_invoked

The second asserts on `StubBackend.streamed` — the actual payload handed to the model, not
the function that builds it. It found the leak in the real stream. Reverted, green
re-established before anything else was touched.

## The break that was not run, and why it is cycle 2's first job

**AC 33 — instructions read at invocation, not at load.** Its test edits the file after
`read()` and asserts the new text comes back, so it cannot pass under an implementation
that caches at startup. That argument is sound but it is an argument, and this loop has a
record of sound arguments about vacuous tests. The break needs three edits — a field on
`Skill`, a capture in `_one`, a return in `instructions` — and the cycle ran out before
they were worth starting badly.

Do it first next cycle. It is the criterion flagged in observe.md as most likely to be
quietly false.

## Assumptions that changed

None. One was confirmed and is worth writing down: **`python-frontmatter` was the right
call.** `frontmatter.loads` gives `.metadata` and `.content` from one parse, so the
"validate at load, read the body at invoke" split cost nothing to express. Hand-rolling the
delimiter split would have been the trap CLAUDE.md names.

## One thing that was nearly a real defect

The loader reads `.axiom/skills/` **relative to the working directory**, and the working
directory during a test run is this checkout. Without isolation, the first test to write a
skill would have left instructions in the repo that **the next real axiom session here
would load and offer to a model.**

That is precisely the exposure CLAUDE.md's #75 paragraph names, and it would have arrived
through the test suite rather than through the feature. It is now an autouse fixture in
`conftest.py`, beside the one that isolates the remembered model — structural, so a test
cannot forget it.

## Goal check

**Not met.** 2 of 44. Next action written.
