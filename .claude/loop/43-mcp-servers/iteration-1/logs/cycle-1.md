# Cycle 1 — 2026-08-26, 03:58 IST

No production code. Baseline recorded, `mcp` installed, and the three structural unknowns
measured. **All three came back favourable**, and two findings change the plan.

## Criteria status

All thirty `not-started`. Nothing is built.

Suite: **272 passed**, hermetic. Transcript copied to `.tmp/transcript-baseline-43.txt`.

## The library, measured rather than trusted

`uv add mcp` installed **`mcp==2.1.1`**, negotiating protocol **2026-07-28**. The API in
`assumption.md` is correct — `Client`, `MCPServer`, `list_tools()`, `call_tool()` all as
recorded. That was the thing most likely to be stale and it is not.

**`input_schema` drops straight into an Ollama declaration.** Measured, not assumed:

```json
{"type": "function",
 "function": {"name": "add",
              "description": "Add two numbers and return the total.",
              "parameters": {"type": "object",
                             "properties": {"a": {"title": "A", "type": "integer"}, ...},
                             "required": ["a", "b"]}}}
```

No adaptation layer is needed. `declarations()` already emits exactly this shape.

**`call_tool` never raises — not even for a tool that does not exist.**

| call | result |
|---|---|
| `add(2, 3)` | `is_error=False`, `content=[TextContent(text='the total is 5')]` |
| a tool that raises | `is_error=True`, `content=[TextContent(text='Error executing tool explode')]` |
| `nope`, which the server has never heard of | `is_error=True`, `content=[TextContent(text='Unknown tool: nope')]` |

That is the same contract `tools.run()` already has: a failure comes back as text for the
model to act on, never as an exception. The two fit together without an adapter.

**Content is a list of blocks, not a string.** `tools.run()` returns `str`, so something has
to flatten it. Decided rather than left open: join the text blocks; name a non-text block by
its type rather than dropping it silently, because a model told nothing came back would
answer from memory - the failure #40 exists to prevent.

## Finding: a server writes its own traceback to your terminal

Not looked for, and it matters. When the probe's tool raised, the **server** printed a full
Python traceback to stderr:

```
Tool 'explode' raised an unexpected exception
Traceback (most recent call last):
  File "...\mcp\server\mcpserver\tools\base.py", line 176, in run
  ...
RuntimeError: deliberate failure: on purpose
```

A stdio server's stderr goes to axiom's stderr by default. So a third-party server having a
bad day writes stack traces into the middle of a user's conversation, and `terminal.py` -
which owns every print - never sees them.

It also bears directly on **AC 16**: no secret may appear "in any error". A server that
tracebacks may print its own configuration, and axiom would be the one showing it.

The SDK takes `errlog` on the stdio transport. Cycle 2 decides where it goes; the point here
is that leaving it at the default is a choice, not the absence of one.

## The sync/async bridge works

A loop on a daemon thread, the `Client` context manager entered inside it, calls from the main
thread via `run_coroutine_threadsafe(...).result()`:

| | |
|---|---|
| session opens and stays usable | yes, across 5 consecutive calls |
| latency | **1.21 ms per call** over 20 calls |
| shutdown | loop thread stops cleanly, `join` returns, thread not alive |

The cost is negligible and the shape is sound. This was the largest unknown in the issue and
it is settled.

## AC 26 and AC 27 hold by default

The one most likely to be false, and it is not.

**Clean exit** — server started through `StdioServerParameters`, three child pids appear,
`ping` answers, and on leaving the context manager **all three are gone**.

**Hard kill** — a child process holding a server open, killed with `psutil.kill()`: no
cleanup, no `atexit`, no context-manager exit, which is what a crash looks like.

```
its descendants        : [8880, 26588, 20240, 30788]
child killed           : True
*** survivors after a hard kill: [] ***
```

**No orphans.** The server exits because its stdin closes when the parent dies.

**Recorded so a later cycle does not over-build:** this is inherited behaviour, not something
axiom does. It depends on the server noticing its stdin has closed. A server that ignores that
would survive, and axiom would not currently know. AC 26 and AC 27 still need their own tests
- proving *today's* behaviour is not the same as owning it - but they do not need a kill-tree
built for them unless a test shows one is needed. `tools._kill_tree` already exists if so.

## What the fix will be

**Config.** `.axiom/mcp.json` read at startup, `${NAME}` substituted from the environment,
`--no-mcp` and `$AXIOM_MCP` to switch off. `config.py` owns resolution today and this is the
first file it has ever read; the resolved servers belong on `Settings` alongside the rest.

**The registry stops being import-time static.** `tools.REGISTRY` is a module-level dict built
at import, and it is the main structural obstacle. The smallest honest change is for
`declarations()` and `run()` to take the MCP tools as an argument rather than reaching for a
global — `main()` already holds `limits` and `instructions` that way, so the shape is
established.

**Prefixing routes as well as names.** `server__tool` gives AC 6 by construction and doubles as
the routing key: split on the separator, look up the server, call it. One mechanism, not two.

**The bridge lives beside the client.** One object owning the loop thread, the sessions, and
the shutdown, started before `terminal.announce` so the startup line can report truthfully.

**Nothing changes when no server is configured.** No config file means no bridge, no thread,
no loop — the existing path untouched, which is AC 1, AC 2, AC 29 and AC 30.

## Nothing here needs an answer from Kaushik
