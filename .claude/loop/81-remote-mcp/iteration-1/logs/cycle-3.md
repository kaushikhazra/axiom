# Cycle 3 — connected, and two tests could not tell the servers apart

2026-09-02, 03:29–03:52 +0530. Branch `feature/81-remote-mcp`. Row 20 of the queue.
**The first cycle in this queue to start a process.**

## The measurement

**Criteria demonstrably met: 13 of 25.** It was 10 entering the cycle.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **13** | 1, 2, 3, 4, 5, 6, 7, 8, 16, 17, 18, 22, 23 |
| 2 — believed true, not proved for this issue | 2 | 21, 24 |
| 3 — not started | 10 | 9, 10, 11, 12, 13, 14, 15, 19, 20, 25 |

Three moved — 6, 7, 8 — and **AC 2 is now met whole**: cycle 2 proved a file may hold both kinds,
and this cycle proves both work in one session.

## The seam sentence held

Cycle 1 wrote it and this cycle spent it:

> The one function that has to learn there are two kinds is `Servers._open`, and only its first
> eleven lines.

Those eleven lines are now `Servers._transport`, which returns either a `stdio_client` or a
`streamable_http_client` and is the **only** place in axiom that knows the difference.
`_open` lost the `if spec.address` guard cycle 2 left as temporary and gained nothing. Everything
below - the tool filter, the `_owner` routing map, the declarations, the count at startup - is
untouched and works for both.

`terminate_on_close` is left at its default of `True`, which sends a DELETE when the context
exits. That is AC 20 arriving for free, and it is still to be proved.

## The formatter took the imports, exactly as the queue warned

`_open`'s body briefly stopped referring to `StdioServerParameters`, `stdio_client` and `os`
between the edit that moved them and the edit that created `_transport`. The `PostToolUse` hook
ran in between, saw three unused imports, and removed them. **Twenty of #43's tests went red with
`name 'StdioServerParameters' is not defined`.**

The queue's Standing says this in as many words - *"the formatter is not the only thing that
edits a file... verify what landed, not just what was sent"* - and it still happened, because the
edit that removed the last use and the edit that added the new one were two edits rather than one.

> **A refactor that moves a call is not safe to split across two edits.** The window between them
> is where a tool that tidies unused imports does its work.

Caught in one test run and cost a minute. Recorded because the next occurrence will be somewhere
the suite does not reach.

## Two tests could not tell the two servers apart

Both stayed green under breaks aimed straight at them, and both were the test's fault.

**AC 8a — the routing key.** Broken by making every tool's owner the *first* server connected, so
a remote server's tools route to the stdio one. The test asserted `from_stdio != from_remote` and
that each reply quoted its own argument - and both hold under the break, because **both servers
are the same script**. Two copies of `tests/mcp_server.py` give identical answers, so "these
came from different servers" was never actually asserted.

The script now records how it was started and says so in its answers. **A test cannot tell two
servers apart if the servers cannot.**

**AC 8b — the separator in a name.** Broken by putting the parsing back in `split`, which is
where #43 cycle 4 found the defect. It was a no-op: `split`'s own docstring says *"not used for
routing"* - #43 replaced parsing with the `_owner` map precisely because `a__b__ping` is
ambiguous and cannot be made otherwise. Breaking dead code changes nothing and prints
`STAYED GREEN`.

The break that works puts parsing back **on the routing path**, `server, tool = split(name)` in
`run`, which is #43's defect restored exactly. Red.

That is the seventh no-op break this queue has produced across three rows, and every one printed
the same words a surviving test prints.

## The port, settled without a race

`tests/mcp_server.py` gained `--http`. It **binds the socket itself**, prints the port, and hands
the already-listening socket to `uvicorn.Server.run(sockets=[...])`. There is no window in which
anything else on the machine can take the port.

The alternative `action.md` offered - bind to zero, read the number, close, hand it over - is a
race that is merely unlikely, and #43's cycle 4 rule applies: **remove a race rather than
shrinking the window.**

No new dependency: `uvicorn` 0.52.4 is already present, pulled in by `mcp`.

## Processes

Started by this cycle: one `python --http` per test that needs one, killed in the fixture's
teardown with `terminate`, then `kill` if it outlives ten seconds. **Checked three times - after
the file's own run, after the break harness, and after the full suite - and nothing was left.**

## The suite

    896 entering
    +5 added        AC 6, AC 7, AC 2's second half, AC 8 (x2)
    901 leaving     901 passed, 1 deselected, 94.51s

**Wall clock rose 80.83s to 94.51s, and that is the five new tests paying for real servers.**
About 2.7s each, which is process start plus an HTTP handshake. Worth watching rather than worth
fixing: `observe.md`'s rule is about a suite getting *faster*, and this got slower for a reason
that is visible.

`tests/baseline/transcript.txt` **unchanged**. #43's 45 tests pass untouched.

## Assumptions changed

None. `assumption.md`'s design - one `Servers`, one routing rule, two ways in - is what landed,
and `_transport` is that sentence as code.

## What only a person can confirm

Unchanged and growing. Everything here is 127.0.0.1: no latency, no dropped connection, no
certificate. **AC 11, AC 13 and AC 20 are the three most likely to look settled and not be**, and
two of them are cycle 4's.

## Next

**AC 9 to 15 - the failures**, and AC 25 with them. What the user is told at startup, a server
that cannot be reached, one that is slow, one that stops answering mid-session, and the two
bounds. **AC 11's race lives there**: a start limit tested against a server that answers in a
millisecond is a coin toss, and `tests/mcp_server.py` already has a `slow` tool for exactly that
reason.
