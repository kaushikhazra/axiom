# Action — cycle 4

**The failures: AC 9 to 15, and AC 25 with them.**

A remote server now connects and its tools are called. What is untested is every way it can go
wrong, which is where a feature like this is actually judged — a user whose server is down needs
to be told which one and carry on, not read a stack trace or lose the session.

## Before anything else, three checks

1. **`git status`** and **`git branch --show-current`** — must be `feature/81-remote-mcp`.
2. **`gh issue view 81`** — the criteria, before the diff and before the logs.
3. **No stray processes**, and check again before exiting. Cycle 3 started servers and left none;
   keep it that way.

## What cycle 3 established

- **`Servers._transport` is the only place that knows there are two kinds.** If a change to
  handle a failure has to touch anything else, say so in the log — that is the design moving.
- `tests/mcp_server.py --http` binds its own socket, prints the port, and serves. The
  `listening` fixture starts one and kills it in teardown.
- The script records **how it was started** and says so in its answers. That is what lets a test
  tell two servers apart, and it exists because a test could not.
- `terminate_on_close=True` is the default, so **AC 20 may already hold** and needs proving.

## 1 — Startup (AC 9, AC 10, AC 12, AC 25)

- **AC 9** — which remote servers answered and how many tools each offers. `note_servers`
  already draws this for stdio servers; the question is whether a remote one reaches it
  identically. **It should need no code at all** — check before writing any.
- **AC 10** — a server that cannot be reached is named, **with the reason**, and the session
  carries on. An address on a closed port is the honest case and needs no server: bind a socket,
  read the port, close it, and point at it. That address is guaranteed unreachable.
- **AC 12** — a run with no remote servers says nothing about them. AC 22's test is close but not
  the same: this one has stdio servers configured and still says nothing about remote ones.
- **AC 25** — a run that cannot reach *any* of its remote servers still starts and is usable.
  Drive it through `main` rather than through `Servers`, because "usable" is a claim about the
  session.

## 2 — The bounds (AC 11, AC 15)

> 11. A remote server that is slow to answer does not hold the session open past the start limit.
> 15. A call that exceeds the call limit is abandoned, and says so.

**AC 11 is where the race lives.** #43's cycle-4 rule: *remove a race rather than shrinking the
window.* A start limit tested against a server that answers in a millisecond is a coin toss that
usually passes. The server needs to be genuinely slow to *accept*, not slow to answer — a socket
that is bound and listening but never accepted, or a `--http` mode that sleeps before serving.
Decide, and say which in the log.

AC 15 is easier: `mcp_server.py` already has a `slow` tool built for exactly this, and #43 uses
it. Reuse rather than invent.

## 3 — Mid-session (AC 13, AC 14)

> 13. A remote server that stops answering mid-session is reported when a tool of its is called.
> 14. A failed call to a remote server does not end the turn.

Kill the server process between two calls. #43 does this for stdio and the test to copy is
`test_a_server_that_dies_fails_only_its_own_tools`. **AC 14's half that matters is that
*everything else still works*** — a built-in and another server's tool, in the same session,
after the failure.

## 4 — State (AC 19, AC 20)

> 19. Nothing about a remote server is written to disk by axiom.
> 20. Leaving axiom leaves no connection open.

AC 19 is a claim about absence: run a session with a remote server and assert nothing new
appeared. Scope it — `tmp_path` and the working directory, not the whole disk.

AC 20 needs a measurement, not an argument. `terminate_on_close` sending a DELETE is the
mechanism; the test is that the socket is gone. Counting the server's connections, or asserting
the process exits cleanly, are both better than reading the SDK's source and believing it.

## 5 — Expect a no-op break

Seven so far in this queue, two of them in cycle 3. **A failure test is especially prone**: a
break that stops the *failure* being reported looks identical to one that stops the *server*
existing. For each, ask what would still pass if the feature did nothing.

## Do not

- Fetch anything, contact a hosted server, or need a real secret.
- Start a server on a fixed port.
- Leave a process running. **Check before you exit.**
- Split a refactor that moves a call across two edits — cycle 3 lost three imports to the
  formatter that way.
- Regenerate the baseline.
- Use a heredoc for anything containing a backslash escape.
- Merge.

## Record

`logs/cycle-4.md`, per `observe.md`. If AC 9 to 15, 19, 20 and 25 all land, the row is done and
**this is the last row in the queue** — follow `loop.md`'s exit, which is the one handover where
the cron is deleted.
