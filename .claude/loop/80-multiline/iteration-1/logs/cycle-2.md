# Cycle 2 — the confinement, and the hook that makes any of this testable

2026-09-01, 21:06 +0530. Branch `feature/80-multiline`. Committed.

## The measurement

**Criteria demonstrably met: 1 of 36.** Moved by 1.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **1** | 30 |
| 2 — already true, unproved | 7 | 12, 13, 14, 31, 32, 34, 35 |
| 3 — not started | 28 | 1–11, 15–29, 33, 36 |

One criterion in a cycle looks thin and is not: AC 30 is the one that can break
everything else, and the cycle also built the thing without which **no criterion in
this issue could ever have been proved**.

## The suite

    876 passed, 1 deselected, 83.75s     entering
    882 passed, 1 deselected, 86.95s     leaving

Arithmetic: 876 + 6 = 882. **`tests/baseline/transcript.txt` is untouched** — with a
new dependency installed and the reader hook wired into `read_line`.

## An obstruction worth recording, and how it was gone round rather than through

`uv add prompt_toolkit` failed:

    error: failed to remove file `.venv/Scripts/axiom.exe`:
    The process cannot access the file because it is being used by another process.

A live axiom session, started 20:45, was holding the console shim — Kaushik's, from the
manual pass. **Not killed.** `~/.claude/CLAUDE.md` says kill zombies before starting a
service; a session someone is using is not a zombie.

Worse, it left `uv run` failing outright, because every invocation tries to sync first. So
for a few minutes the loop could not run its own tests.

The precise constraint was narrow: `uv add` rewrites the project's console scripts, and one
of them was locked. `uv pip install` does not touch them. So the package went in that way,
`pyproject.toml` was edited by hand, and the suite runs with `--no-sync`.

**What that leaves owed, and it must not be forgotten:** `uv.lock` does not list
`prompt_toolkit`. A clean checkout would not install it. `uv lock` is owed the moment no
session is running, and it is in the commit message as well as here because a lockfile that
silently disagrees with `pyproject.toml` is exactly the kind of thing that surfaces on
someone else's machine.

## What was proved, and why it is asserted this way

**AC 30 — piped and redirected input unchanged.** Two tests, and the distinction between
them is the point:

- one asserts a piped run **sends one turn per line**, which is the behaviour
- one asserts a piped run **read through `builtins.input`**, which is the mechanism

The second exists because the first is not enough. A reader that reached the piped path
could produce byte-identical output for a one-line session and still break every script that
pipes more than one line. Asserting the behaviour alone would have passed.

A third checks that merely importing `prompt_toolkit` disturbs nothing — it installs its own
output handling when an application is built, and "it only does that when constructed" is an
argument until something measures it.

## The hook, which is a precondition rather than a criterion

Cycle 1's finding: **every one of the 876 existing tests supplies input by monkeypatching
`builtins.input`**, and a terminal-only reader is unreachable from all of them, because no
test process is a terminal.

So `use_compose` was built before the feature, not after. Without it #80 could have been
implemented and never checked — which is how #77 nearly shipped a panel that nothing had
looked at, and it was only caught because a person ran the program.

`_composer()` returns the substituted reader **only** when rendering is on and stdout is a
terminal. That is the same gate #77 uses, and it is why the baseline did not move.

## Breaks

| what was broken | verdict |
|---|---|
| the composer is reachable without a terminal | went red |
| the composer is never consulted at all | went red |
| forgetting the composer does not release it | went red |

The third is worth keeping: a hook that cannot be released leaks a fake reader into every
test that runs after it, and the failure appears somewhere unrelated. `use_input`'s docstring
already says this happened once with the timed reader.

## Assumptions changed

None. `prompt_toolkit` is promoted from recommendation to dependency, which cycle 1 named as
this cycle's job.

## What only a person can confirm — unchanged from cycle 1

Criteria 2, 3, 4, 5, 7, 8, 9, 22, 23, 24. Nothing was added to that list this cycle,
because nothing that only a person can see was built yet.

## Next

The reader itself. Bindings are `c-m` to accept and `escape, c-j` to insert a newline —
read out of `prompt_toolkit/input/win32.py` in cycle 1, and **not** `"c-enter"`, which does
not exist as a key.
