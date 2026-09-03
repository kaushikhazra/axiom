# #81 — the manual pass

**All twenty-five criteria are met by test, each proved by a break.** What is owed here is not
a gap in the tests — it is that **every one of them is 127.0.0.1**, and localhost is not the
internet.

## What localhost cannot show you

| | What to do | What should happen |
|---|---|---|
| 1 | Point axiom at a real remote MCP server over `https://` | It answers, and its tools appear beside the others |
| 2 | Same server, on a slow or flaky connection | The start limit holds; the prompt appears without it |
| 3 | Pull the network mid-session and call one of its tools | Named, with a reason, and the session carries on |
| 4 | A server behind a proxy, or one presenting a certificate | Either it works or it fails with something you can act on |
| 5 | Leave axiom while a remote server is attached | Nothing is left connected at the other end |

Localhost has no latency, never drops a connection mid-call, and never presents a certificate.
**AC 11, AC 13 and AC 20 are the three most likely to look settled and not be.**

## The AC 17 decision, which is yours to overturn

> A plain-text address is refused, or the user is told the traffic is not encrypted.

Cycle 2 decided: **told, not refused, and told for every `http://` including localhost.**

Told rather than refused because the ordinary case is a server on your own machine, and refusing
`http://` would make this useless for the person most likely to want it. Localhost is *not*
carved out because loopback traffic really is unencrypted and the criterion says refused *or*
told — silence is neither.

**The thing to judge in use: is the line noise?** If every local run says
`far: http://127.0.0.1:9000/mcp is not encrypted - anything sent to it can be read in transit`,
that is a warning people learn to skip, and a warning people skip is worse than none. If it
reads that way to you, the criterion changes — and that is a change you make, not one the loop
should have made for you.

## One thing found and fixed that belongs to #43

Killing a remote server took a **stdio** server down with it: one shared `AsyncExitStack` for
every session, and a remote transport that fails by cancelling its own scope. Fixed here — one
task and one stack per server — and #43's forty-five tests pass untouched.

Worth a look by hand because it is a lifetime change to code #43 settled: start two servers of
different kinds, kill one, and check the other still answers and that nothing is left running
when you leave.

## Owed alongside this

#80, #76, #72, #73 and #74 are all waiting on a manual pass. #72, #73 and #76 are the same
renderer and are worth doing in one sitting.
