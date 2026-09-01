# Cycle 1 — the survey, and the import name is not the one you remember

2026-09-02, 02:50–03:08 +0530. Branch `feature/81-remote-mcp`. Row 20 of the queue.
**No source written**, per `action.md`.

## The measurement

**Criteria demonstrably met: 2 of 25.**

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **2** | 22, 23 |
| 2 — believed true, not proved for this issue | 2 | 21, 24 |
| 3 — not started | 21 | 1–20 except 3's pin, 25 |

AC 3 is **not** in bucket 1 and has a pin in bucket 3's place: the half of it that exists today
is proved, and the half the criterion is actually about needs an entry that names an address.

## The SDK, version 2.1.1, read out of the installed package

**The function is `streamable_http_client`. Not `streamablehttp_client`.** That is the name
memory gives, it is the name most of the documentation written before this release gives, and
it is an `ImportError` on this machine. Recorded first because it is the single cheapest way for
cycle 2 to lose a cycle.

    mcp.client.sse.sse_client(url, headers, timeout=5.0, sse_read_timeout=300.0, ...)
    mcp.client.streamable_http.streamable_http_client(url, *, http_client=None,
                                                      terminate_on_close=True)

**Neither carries a deprecation marker in the installed source.** The word does not appear in
either file. The SDK's own `client/session_group.py` supports both and is the working example to
copy — it is the only place in the package that chooses between three transports.

Three things about `streamable_http_client` that its signature does not make obvious:

- **`headers` and `timeout` are not parameters.** They go into an `httpx2.AsyncClient` built by
  `create_mcp_http_client(headers=..., timeout=httpx2.Timeout(...))`, which is then passed as
  `http_client`. `session_group.py` line 325 does exactly this.
- **`httpx2`, not `httpx`.** An unusual detail and easy to mistype.
- **`terminate_on_close=True`** sends a DELETE to end the session when the context exits. That is
  AC 20 — "leaving axiom leaves no connection open" — already available as a default rather than
  something to build.

`SseServerParameters` and `StreamableHttpParameters` exist in `session_group.py` as pydantic
models. A shape worth copying; not obviously worth importing, since `ServerSpec` is axiom's own
and already carries `name` and `tools`.

**Nothing here needs a new dependency.** `mcp` is already required and both transports ship
inside it.

**Neither is re-exported from `mcp/__init__.py`** — only `StdioServerParameters` and
`stdio_client` are. Axiom's `from mcp import Client, StdioServerParameters` does not extend to
these; they come from their own modules.

## The seam, written as a sentence because `action.md` asked for one

> **The one function that has to learn there are two kinds is `Servers._open`, and only its
> first eleven lines — everything from `listed = await asyncio.wait_for(client.list_tools())`
> onward is already transport-agnostic.**

Those eleven lines are `StdioServerParameters(...)`, the `errlog` file, and the
`Client(stdio_client(...))` construction. Below them: the wanted/offered tool filter, the
`_owner` routing map, `declarations`, and `connected` — none of which can tell what produced the
client.

**`errlog=quiet` is the tell.** It opens `os.devnull` to swallow a *subprocess's stderr*, and
its docstring explains that a server having a bad day would otherwise write tracebacks into the
middle of a conversation. A server reachable by address has no stderr to swallow. That line is
where AC 3 is either honoured or quietly violated.

## `tests/mcp_server.py` can already be the remote server

`MCPServer.run` takes `transport="streamable-http"` with `host` and `port` keywords. **The
script this repo already owns needs an entry point, not a rewrite** — which is the best possible
answer to `assumption.md`'s rule that a test never fetches a server.

**The open question is the port.** `assumption.md` forbids a fixed one: a hardcoded port fails on
a machine where something else is listening and, worse, *passes* by talking to whatever that
something is. `run()` wants a number. The two ways out are binding a socket to port 0 to learn
one and closing it before handing it over — a small race — or having the server print its chosen
port and the test read it. **Cycle 2 decides.**

## Three things measured that change what a later cycle would have assumed

**One stdio server is one *direct* child and three recursive ones**: the server, a
`conhost.exe`, and a second `python.exe` the Windows launcher spawns. The AC 3 pin was written
counting recursively and reported "one command spawned 3 processes". Direct children are what
"axiom started something" means; the recursive number is a platform detail and would differ
elsewhere.

**AC 23 is free.** `config.resolve` returns `mcp_servers: ()` on `--no-mcp` *before the file is
read at all*, so no entry of any kind survives it and no transport can change that. It needed a
test and no code — asserted with a populated file present, because "no servers were configured
anyway" is how that passes for the wrong reason.

**AC 20 may be free too.** `terminate_on_close=True` is the default.

## AC 22 took three breaks and two of them were no-ops

Both printed `STAYED GREEN`, which is what a genuinely surviving test prints. This is the trap
#60 named, the queue's Standing carries, and #76 hit three times last row.

1. **`--no-mcp` no longer clearing the list.** The test used `--no-mcp` too, so the run
   configured nothing either way. AC 23's break wearing AC 22's name — and the *test* was wrong,
   not the break. It now points `--mcp-file` at a path that does not exist, which is what "no MCP
   configured" means for a user who never set any of this up.
2. **`note_servers`' early return removed.** With nothing connected and no problems, every loop
   below it is over an empty collection — so it returns without the return and prints exactly
   nothing.
3. **A line drawn unconditionally.** Red. AC 22 forbids a *line*, so the break has to draw one.

## The suite

    876 entering    master's baseline
    +4 added        the AC 3 pins, AC 22, AC 23
    880 leaving     880 passed, 1 deselected, 81.17s

`tests/baseline/transcript.txt` **unchanged**. No process left running — checked.

## Assumptions changed

**One.** `assumption.md` said "the transport is a survey, not a decision" and expected the
survey to name a deprecated option. It does not: both transports are live, neither is marked,
and the SDK supports both in its own helper. **The choice is axiom's to make on other grounds** —
which one a server the user did not install is likely to speak. That is cycle 2's decision, and
it is a larger one than "use the current one".

## What only a person can confirm

Everything here is localhost. Localhost has no latency, never drops a connection mid-call, and
never presents a certificate. AC 11, AC 13 and AC 20 are the three most likely to look settled
and not be. Kept for the manual pass from this cycle on.

## Next

**AC 1, 2, 4, 5, 16, 17, 18 — the configuration half**, which needs no server at all: an entry
that names an address, both kinds in one file, and the two refusals. Then AC 17's decision, with
the survey in hand.
