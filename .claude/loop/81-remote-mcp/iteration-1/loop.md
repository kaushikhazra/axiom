# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Branch:              feature/81-remote-mcp
Issue:               https://github.com/kaushikhazra/axiom/issues/81

Every 15 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     take the exit below
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-09-02 06:50 +0530, take the exit below, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions — if
an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state at
that cycle and are never edited afterwards.**

**The artifact already exists.** This adds a second transport to an MCP layer #43 built, not a
blank file. The suite entering this loop is **876 passed, 1 deselected, ~89s**, and `master` is
at `936fd1e`. Cycle 1 reads and records before it writes anything.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`. This
folder holds the loop's own files and logs, nothing else.

**Work on `feature/81-remote-mcp`.** Check the branch before writing.

## This row is the last in the queue

Row 20 of [`../../queue.md`](../../queue.md). **On reaching either exit — converged or
fail-safe — follow the queue's `Handing over` procedure.** Mark row 20 done, find there is no
next row, and **then, and only then, delete the cron**. That is the one handover where deleting
it is right: with no rows left there is no chain to end, and a cron that keeps firing wakes a
full session every fifteen minutes to read the queue and find nothing.

**Do not merge.** Rows 18 and 19 both finished unmerged, and three manual passes are owed
already. Commit, leave the branch, and say in the handover that the merge is Kaushik's.

## This is the only row that starts processes

Rows 18 and 19 never left the interpreter. This one can spawn a server, and the queue has been
running unattended for hours on a machine with 16 GB.

**Anything a test starts is killed in a fixture teardown, and every cycle checks before it
exits.** An orphaned server per cycle is a machine that stops responding around cycle twenty,
and this session has already taken Kaushik's machine down twice for a different reason.

`assumption.md` carries the rest: nothing fetched at test time, nothing hosted contacted, no
fixed ports, and a real process only from a script this repo owns.

## Why this is worth having

A server named by a command is one axiom starts, waits for, and kills. A server named by an
address is one that was already there — installed by someone else, started by someone else,
possibly shared. The user gets a capability without getting a subprocess, and the thing that
makes it work is that **nothing downstream of the transport can tell which kind it was**.

## The order to take it in

1. **Survey the SDK's transports and record the version.** More than one exists, one is
   deprecated in favour of the other, and which is which has changed. Cycle 1 does not write
   code.
2. **AC 3 first** — a remote entry reaches none of the subprocess path. It is the criterion the
   issue turns on and the easiest to satisfy accidentally.
3. **Then configuration**: AC 1, 2, 4, 5, 16, 17, 18. Most of it is `ServerSpec` and needs no
   server at all.
4. **Then using one**: AC 6, 7, 8 — where a script this repo owns starts answering.
5. **Then the failures**: AC 9 to 15, and AC 25.
6. **AC 19 to AC 24 are the unchanged half** and are checked every cycle, not once at the end.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the diff
and before the previous log.
