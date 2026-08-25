# Cycle 3 — 2026-08-26, 04:28 IST

The remaining fifteen. **All 30 criteria now have evidence.** Convergence is not declared —
cycle 4 is the cold check.

## Criteria status

All thirty `met-with-evidence`.

**Suite: 313 passed** (294 + 19), hermetic. **Transcript byte-identical** with nothing
configured.

## The vacuous test, caught by checking rather than by trusting

The AC 26 and AC 27 tests passed the first time they ran. That is when to be suspicious, and
it was right to be.

They asserted `surviving(spawned) == []`, where `spawned` was the set of child processes
measured **after `main()` returned**. By then `stop()` had already run, so `spawned` was
empty — and `surviving(set())` is `[]` for any implementation whatsoever, including one that
never started a server and one that leaked every server it started.

Checked directly rather than assumed:

```
axiom: starting 1 MCP server...
axiom: tiny: 3 tools
axiom: tools cost about 839 tokens per request
spawned during the run: []
```

The server really had started — three tools, 839 tokens. **The measurement was simply taken
too late.** This is the fourth time in five issues that a test has passed for an
implementation that did not do the thing, and the first time it was caught by suspicion of a
first-time pass rather than by a later cycle's attack.

**Fixed** with a `StubBackend` subclass that snapshots the children from inside `stream()` —
mid-session, while the servers are alive — and a guard, `assert backend.seen`, so the test
fails loudly rather than quietly if no server was ever running.

**And then proved it can fail.** With `Servers.stop` replaced by a no-op, the test goes red:

```
FAILED tests/test_mcp.py::test_every_route_out_stops_every_server[/exit]
```

A test that cannot fail proves nothing, and now this one demonstrably can.

## AC 19 and AC 20: the bounds became settings

`START_TIMEOUT` and `CALL_TIMEOUT` were module constants. They are now
`--mcp-start-timeout` and `--mcp-call-timeout`, with `$AXIOM_MCP_START_TIMEOUT` and
`$AXIOM_MCP_CALL_TIMEOUT`, the command line winning — the pattern `--command-timeout` and
`--fetch-timeout` already established.

They are resolved even under `--no-mcp`, so what `Settings` reports is what the user asked
for whether or not a server ends up using it. And a test asserts the value **reaches the
client**, because being told is not the same as being applied.

## AC 13: what the tools actually cost

Computed from the declarations that will ride in every request, and shown before any
conversation starts:

```
axiom: tools cost about 839 tokens per request
```

839 tokens for seven built-ins and three server tools. That is the figure the criterion exists
for — #42 measured the system prompt at 205 tokens for the same reason, and a server
contributing twenty tools is a fixed tax the user would otherwise never see. The percentage of
the window is shown when the window is known.

## AC 24 and AC 25 assert on the world, not the message

The dead-server test kills the subprocess with `psutil` and then checks that a **built-in tool
still works in the same session**. The criterion is that every *other* tool keeps working, not
that the dead one fails politely, and a test that only checked the error string would pass for
an implementation that had taken the whole session down with it.

## Nothing here needs an answer from Kaushik

## Why this cycle does not declare convergence

Cycles 2 and 3 wrote all of this and cycle 3 judged it. That pass has been wrong in three
consecutive issues. Cycle 4 reads #43's criteria from GitHub before the diff and before these
logs, and attacks each rather than confirming it.

The vacuous test above is the argument for it, not against it: it was found here only because
a first-time pass on a hard criterion looked wrong. The ones that look right are what the cold
read is for.
