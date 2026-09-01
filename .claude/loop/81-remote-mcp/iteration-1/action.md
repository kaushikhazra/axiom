# Action — cycle 3

**A remote server answering. This is the cycle with a process in it.**

Cycle 2 made an address configurable and proved it reaches none of the subprocess path. Cycle 3
connects it, which means `tests/mcp_server.py` gains an HTTP entry point and the port question
has to be settled.

## Before anything else, three checks

1. **`git status`** and **`git branch --show-current`** — must be `feature/81-remote-mcp`.
2. **`gh issue view 81`** — the criteria, before the diff and before the logs.
3. **No stray processes**, and check again before exiting. This is the cycle where that stops
   being a formality.

## What the earlier cycles established

- **`streamable_http_client`, not `streamablehttp_client`.** SDK 2.1.1.
- `headers` and `timeout` are not its parameters — they go into an `httpx2.AsyncClient` from
  `create_mcp_http_client`. `session_group.py` line 325 is the working example.
- `terminate_on_close=True` is the default, which may make **AC 20 free**.
- **The seam is `Servers._open`'s first eleven lines.** Everything from `listed = await ...
  list_tools()` down already works for both.
- `Servers._open` currently returns early for an address with *"reached by address, not connected
  yet"*. **That line is this cycle's to delete.**
- `tests/mcp_server.py` can serve over `streamable-http` with `host` and `port`.

## 1 — Settle the port, first

`assumption.md` forbids a fixed one: it fails where something else is listening and, worse,
*passes* by talking to whatever that is. Two ways out:

- bind a socket to port 0, read the port, close it, hand it over — a small race;
- have the server print its chosen port on stdout and the test read the line.

**The second has no race and is barely more code.** Prefer it unless it does not work, and say in
the log which was used and why.

Whatever is chosen: **the fixture kills the process in teardown, and the cycle checks before it
exits.**

## 2 — Connect (AC 6, AC 7, and AC 2's second half)

Replace the early return with the transport. The whole change should be inside those eleven
lines — if it is not, cycle 1's seam sentence was wrong and that is the finding.

- **AC 6** — the tools appear alongside every other tool, indistinguishable in use.
- **AC 7** — a tool is called and its result shown exactly as a local one is.
- **AC 2's second half** — both kinds working in one session. One stdio server and one remote in
  the same `Servers`, both answering.

## 3 — AC 8, and it has a known trap

> Two servers offering a tool of the same name stay distinguishable.

#43 cycle 4 found this broken for a server whose **name contained the separator**. `SEPARATOR`
is `__` and is both the collision guarantee and the routing key. A remote name goes through the
same rule or the guarantee is half a guarantee. Test with a remote server named `odd__name`.

## 4 — Do not claim what you have not broken

Cycle 2's AC 3 test passed for the wrong reason and only the break found it: an address entry
has an empty command, `stdio_client` failed to exec, no process appeared, and the test was green
while axiom had attempted a subprocess and waited out its timeout. **"Nothing happened" is not
"nothing was tried".**

Expect the same shape here. A remote tool that returns nothing and a remote server that was never
reached look identical from the outside unless the test says which.

## Do not

- Fetch anything. No `npx -y`, no `uvx`, nothing downloaded at test time.
- Contact a hosted server, or need a real secret.
- Start a server on a fixed port.
- Leave a process running. **Check before you exit.**
- Give `Servers` a second class of server.
- Regenerate the baseline.
- Use a heredoc for anything containing a backslash escape.
- Merge.

## Record

`logs/cycle-3.md`, per `observe.md`. Then write cycle 4's action, which is AC 9 to 15 — the
failures, and where AC 11's race lives.
