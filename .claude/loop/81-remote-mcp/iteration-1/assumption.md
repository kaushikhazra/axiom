# Assumptions

## What #43 already built, and what this row adds

`src/axiom/servers.py` talks to MCP servers over **stdio only**. One event loop on its own
thread for the whole run, because the SDK is async and axiom is not, and because a stdio server
is a subprocess that has to stay alive between calls. Measured at 1.21 ms per call.

    Servers  ->  StdioServerParameters(command, args, env)  ->  stdio_client  ->  Client

`ServerSpec` in `config.py` holds `name`, `command`, `args`, `env`, `tools`. **This row adds a
second kind of entry** — one named by address — and everything downstream of the transport
should not be able to tell the difference. That is AC 6 and AC 7, and it is also the design:
one `Servers`, one routing rule, two ways in.

`SEPARATOR = "__"` is both the collision guarantee and the routing key. #43 cycle 4 found it
broken for a server whose name *contained* the separator. A remote name goes through the same
rule or AC 8 is half met.

`START_TIMEOUT = 30.0` and `CALL_TIMEOUT = 60.0` already exist and are what AC 11 and AC 15 are
about. Reuse them; a second pair of bounds that disagreed with the first would be worse than
either.

## The transport is a survey, not a decision

The MCP SDK ships more than one client transport for a server reachable over the network, and
they are not interchangeable — one of them is deprecated in favour of the other, and which is
which has changed. **Cycle 1 finds out what the installed SDK actually offers** and records the
version it read, rather than assuming a name.

**No new dependency should be needed.** If one appears to be, that is a finding for the log and
a justification in `pyproject.toml`, not a quiet addition.

## The safety rules that bind this row, and they are not general advice

`CLAUDE.md` names #43's exposure and it applies here with one more edge: an address points at
something axiom did not start and cannot see.

- **A test never fetches a server.** No `npx -y`, no `uvx`, nothing downloaded at test time.
  That is someone else's release, pulled over the network, running as whoever ran pytest.
- **No test contacts a hosted server or needs a real secret.** Everything in #81 is provable
  against localhost or against nothing at all. AC 16 and AC 17 are about addresses being
  *refused*, which needs no server whatsoever.
- **Where a criterion genuinely needs something answering** — AC 6, AC 7, AC 9, AC 13 — the
  server is a script this repo owns under `tests/`, run by the same interpreter, bound to
  **localhost on a port the operating system chose**. `tests/mcp_server.py` and
  `tests/mcp_hangs.py` already exist from #43 and are the precedent.
- **Never a fixed port.** A hardcoded port is a test that fails on a machine where something
  else is listening, and worse, a test that *passes* by talking to whatever that something is.
- **Anything a test starts is killed in a fixture teardown, and the cycle checks before it
  exits.** The queue runs unattended for hours on 16 GB. An orphaned server per cycle is a
  machine that stops responding around cycle twenty. This is in the queue's **Standing** and it
  is aimed at this row.

## AC 17 is a decision, and it is not obvious

> A plain-text address is refused, or the user is told the traffic is not encrypted.

Two acceptable outcomes, very different. **Refusing `http://` outright makes the feature useless
for the person most likely to want it** — someone running a server on their own machine. Telling
them once, plainly, is the least surprising reading, and `localhost` is arguably not even worth a
warning.

The loop decides, records the reasoning under a heading that says it was a decision, and carries
it into the handover. It does not ask.

## Constraints from the repository

- **Branch `feature/81-remote-mcp`**, from `master` at `936fd1e`. A cycle that wakes on `master`
  switches; it does not commit. The repo's hooks refuse a commit on master outright.
- **`.claude/loop/` on this branch carries the queue and rows 18 and 19's records**, brought
  across deliberately so the loop's bookkeeping travels while `src/` and `tests/` stay at
  `master`. **#80's and #76's code is not here and must not be pulled in.**
- `uv run pytest` stays green and hermetic **with nothing installed and nothing running**. That
  is the strongest single constraint on this row.
- **No compound shell commands.** One per invocation, Bash and PowerShell alike.
- **Kill before restart.** Check ports and kill zombies before starting anything.
- **Assume a fresh context.** Only these files exist. Read the issue from GitHub before the diff
  and before the previous log.

## What a test cannot do here

A test cannot prove that a real remote server, on someone else's machine, over a real network,
behaves as this expects. Everything here is localhost, and localhost never has latency, never
drops a connection mid-call, and never presents a certificate. **AC 11, AC 13 and AC 20 are the
three most likely to look settled and not be**, and they belong on the manual pass whatever the
tests say. Keep that list every cycle.
