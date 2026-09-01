# Cycle 6 — abandoning, the guards, and a machine that fell over

2026-09-01, 22:26 +0530, finished 23:47 after a reboot. Branch
`feature/80-multiline`. Committed.

## The measurement

**Criteria demonstrably met: 20 of 36.** Moved by 7.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **20** | 1, 2, 3, 5, 7, 8, 9, 10, 13, 18, 22, 23, 24, 25, 26, 30, 32, 33, 34, 35 |
| 2 — implemented but not proved | 2 | 4, 12 |
| 3 — not started | 14 | 6, 11, 14, 15, 16, 17, 19, 20, 21, 27, 28, 29, 31, 36 |

## The suite

    900 passed, 1 deselected, 83.84s     entering
    909 passed, 1 deselected, 85.18s     leaving

Arithmetic: 900 + 9 = 909. **Baseline untouched**, twelve cycles across two issues.

## The machine crashed, and what that cost

The cycle died part-way through its break-proof. Kaushik's whole PC went down.

**It was not a model.** Checked against Ollama's own log rather than guessed:

    21:13:33  loading model via llama-server        gemma4
    21:16:59  system memory total=15.9 GiB free=8.6 GiB
    21:17:14  POST /api/chat  200  18.5s
    22:50:11  (housekeeping only)

Two loads, both from **this loop's own cycle-2 captures** - the real axiom runs taken to
prove the new dependency changed nothing on the piped path. Ollama unloads after about five
minutes idle, so nothing was resident from ~21:22 onward, and the crash came an hour later.
Cause unknown, and left unknown rather than invented.

**Verified afterwards that the suite loads nothing**, three ways:

| | |
|---|---|
| Ollama requests during a full run | **zero** - server.log 12 lines before, 12 after |
| python memory | 0.13-0.21 GB across 2-4 processes, flat |
| free RAM | ~7 GB throughout |

## A break-proof that dies leaves the break in

**Third time tonight**, and the first two were only harness timeouts. The pattern is now
clear enough to state:

> The harness writes a break into the real source file and relies on `finally` to put it
> back. Nothing that kills the process - a timeout, a SIGTERM, a machine going down -
> runs `finally`. The file is then left holding a break, the suite goes red for a reason
> that has nothing to do with the code, and the next person reads it as a regression.

Found this time by `git diff` rather than by a failing test: `_composer()` was missing its
`_rendering` check, which is exactly the AC 32 break the harness had applied.

**Worth fixing properly rather than being careful about.** A harness that copied the file
aside, or worked on a scratch copy of the tree, could not do this. Noted for whoever
touches it next; not done here, because it is not this issue's work.

## AC 32's test could not fail

The break said so, which is the whole reason for running breaks at all.

The first version asserted on the printed bytes of a `--no-render` run. But `conftest`
substitutes a composer that reads through `input` - so the other 900 tests keep working -
which means **both paths print identically**, and removing the `_rendering` guard changed
nothing observable. Green either way.

Rewritten to assert *which reader was reached*. The general form, and it has come up twice
in two issues now: **a guard that cannot tell the two paths apart is not guarding the thing
it names.**

## `style="class:aborting"` is the shape of a model name

`test_config` guards against a default model creeping back by looking for `family:tag` in
the source. prompt_toolkit's natural style argument for an aborted prompt is exactly that
shape, so the guard flagged it.

The guard is right and the styling is worth nothing, so the argument went rather than the
guard being widened. **Widening a real check to accommodate a cosmetic argument is a bad
trade even when the check is a false positive.**

One thing learned about that guard: its comment says it matches "inside a string literal
only, so the prose in a comment ... is not itself mistaken for the default". It does not -
the regex looks for quotes anywhere on the line, and it caught the *comment* explaining the
fix on the very next run. Not wrong, just broader than it claims.

## Assumptions changed

None.

## What only a person can confirm — one added

Criteria 2, 3, 4, 5, 7, 8, 9, **24**. Abandoning joins: a pipe input proves ctrl+c clears
the buffer, and only a person can confirm that pressing it *feels* like cancelling rather
than like something having gone wrong.

## Next

Fourteen left, and they are the ones nobody reaches for first: an oversized paste refused
rather than truncated (AC 21), trailing blank lines (AC 19, 20), a message wider than the
window (AC 22), the schedule path (AC 31), and AC 36 - leaving with a message part-composed.
