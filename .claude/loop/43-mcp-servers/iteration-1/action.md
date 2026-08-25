# Action

Build the config and the client. Cycle 1 measured the library, the bridge and the process
lifetime; its findings are in `logs/cycle-1.md` and are not to be re-derived.

**30 criteria is too many for one cycle.** This cycle takes the ones that make a server's
tools reach the model at all — AC 1 to AC 9 and AC 14 to AC 16. Selection, cost, failure and
lifetime follow in cycle 3. Say in the log which are done and which are deliberately not
started; a cycle that half-finishes twenty things is worse than one that finishes ten.

## 1. Config

`.axiom/mcp.json`, read at startup, the `mcpServers` shape:

```json
{"mcpServers": {"tiny": {"command": "python", "args": ["server.py"],
                         "env": {"TOKEN": "${MY_TOKEN}"}}}}
```

- `${NAME}` substituted from the environment (**AC 14**). A referenced variable that is not
  set is reported at startup **by name**, and the literal `${NAME}` is never passed through
  (**AC 15**).
- `--no-mcp`, and `$AXIOM_MCP` off, with the flag winning (**AC 17**). `--no-tools` takes MCP
  with it, the way it already takes the web (**AC 18**).
- No file, or a file naming no servers, behaves exactly as today (**AC 1, AC 2**).
- `config.py` owns resolution and this is the first file it has read. Keep it there.

## 2. The client

A module of its own. `tools.py` is about what axiom can do; this is about talking to someone
else's process.

- The bridge from cycle 1's probe: a loop on a daemon thread, `Client` entered inside it,
  calls via `run_coroutine_threadsafe(...).result()`. Measured at 1.21 ms per call.
- **Send the server's stderr somewhere other than the user's terminal.** Cycle 1 found a
  server printing a full Python traceback into the middle of a conversation, which
  `terminal.py` never sees and AC 16 forbids being a leak path. The SDK takes `errlog` on the
  stdio transport.
- **Prefix every tool `server__tool`** (**AC 6**), and use the same prefix to route the call
  back. One mechanism, not two. AC 6 asks that a collision *cannot happen* — prove the
  impossibility, not the prefix.
- Flatten `CallToolResult.content` to a string: join the text blocks, and **name a non-text
  block by its type rather than dropping it**. A model told nothing came back answers from
  memory, which is the failure #40 exists to prevent.
- `is_error=True` becomes an `error:` string, matching `tools.run()`'s existing contract.

## 3. Wiring

- Connect **before** `terminal.announce`, so the startup line reports what actually connected
  (**AC 3, AC 5**).
- The startup line names each server and how many tools it contributed (**AC 5**).
- `declarations()` and `run()` take the MCP tools as an argument rather than reaching for a
  global. `main()` already passes `limits` and `instructions` that way.
- A server's tool is called and displayed exactly like a built-in (**AC 7**), and sessions
  stay open for the whole run (**AC 8**), with nothing carried between runs (**AC 9**).

## 4. Prove it

- **In-memory transport for nearly everything**, per `CLAUDE.md`. No test fetches a server.
- A real subprocess only where a criterion needs one — not in this cycle.
- **AC 16 is three places**: the startup line, any error, and anything the model is told. The
  third is the one that gets missed, and a server that fails to start often reports its own
  command line.
- Full suite and the hermeticity command. **272 is the floor**, and it must still pass with
  no MCP server anywhere.
- `diff .tmp/transcript-baseline-43.txt tests/baseline/transcript.txt` — with no server
  configured it must be **byte-identical**. Check for removed lines explicitly.

## Record

Status for all 30, and be explicit about which were not attempted this cycle. Then write
cycle 3's `action.md`.

**Write no questions into it.** Decide, record the decision and the reasoning, carry on.
