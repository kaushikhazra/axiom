# Cycle 4 — 2026-08-26, 04:43 IST

The external check. **It found a real bug and a criterion with no test at all**, both marked
`met-with-evidence` by cycle 3. Fixed, re-attacked, and converged.

## Criteria status

All thirty `met-with-evidence`, two of them only after this cycle's work.

**Suite: 317 passed**, hermetic. **Transcript byte-identical.** No orphaned server processes
left behind by the suite.

## Defect: a server whose name contains the separator

AC 6 says every tool carries its server's name *"so it can never take the name of a built-in
tool or of another server's tool."* Cycle 3 tested the prefix. It did not test what the prefix
does to routing.

A server called `a__b` declares `a__b__ping`. Routing partitioned at the **first** separator:

```
declared            : ['a__b__ping', 'a__b__shout', 'a__b__read_file']
split('a__b__ping') -> ('a', 'b__ping')
owns('a__b__ping')  -> False
call                -> "error: there is no tool named 'a__b__ping'"
```

**Three tools declared to the model and permanently uncallable**, with nothing saying so. The
model would keep trying and keep being told the tool does not exist, about a tool axiom itself
had just offered it.

**The fix is not a better separator.** Splitting a qualified name cannot be made unambiguous:
`a__b__ping` is server `a` with tool `b__ping` exactly as legitimately as server `a__b` with
tool `ping`, and both are legal. Routing is now a lookup in a map built when the tools are
declared, so no parsing happens and no name can be misrouted. `split()` survives with a
docstring saying it is a guess and is not used for routing.

## Gap: AC 22 had no test

*"A server still not ready at the startup bound is given up on, and axiom says so rather than
waiting indefinitely."* Cycle 3 marked it met. Searching the suite for it found nothing — the
implementation existed and had never been exercised.

`tests/mcp_hangs.py` now starts and says nothing. Against a 3-second bound:

```
start() returned after : 5.0s
connected              : {}
failures               : ['hangs: TimeoutError']
child processes left   : []
```

It gives up, says which server, and leaves nothing behind.

## A racy test, caught on its first red

The AC 23 test used a 1 ms call bound against a local server that answers in about a
millisecond, and the answer won:

```
AssertionError: assert 'did not answer' in 'pong'
```

**Fixed by removing the race, not by shrinking the bound.** `tests/mcp_server.py` gained a
`slow` tool that actually waits, so the bound decides the outcome every time. Shrinking the
timeout would have made it pass more often and stayed a coin toss.

## What was attacked and held

| attack | result |
|---|---|
| a server literally named `read_file` | no collision with the built-in; `read_file__ping` answers |
| AC 23 — does the turn carry on after a bound is hit? | reports the timeout, and the session answers normally afterwards |
| the suite's own leavings | no orphaned server processes, checked by name across the machine |

**On AC 23, honestly:** the bound stops axiom *waiting*; it does not reach into the server and
stop the work. The criterion says the call "is stopped, the model is told so, and the turn
carries on" — the model is told and the turn carries on, both proven. Whether the server is
still computing is not observable from axiom's side, and the session recovers regardless.
Recorded rather than claimed as more than it is, because #34 shipped exactly that confusion
once, reporting "stopped it" while a command kept running.

## An honesty note

This ran in the same session that wrote cycles 2 and 3, so it was not context-free. What
worked was method: reading the criteria off GitHub before the diff, then writing an attack per
criterion rather than re-reading code. The AC 6 bug came from asking what a *server name*
containing the separator would do — a question no amount of rereading the prefix logic would
have raised.

## Verdict

All thirty criteria met with evidence. Taking `loop.md` exit 1. **#43 is the last row**, so the
handover says the queue is empty.
