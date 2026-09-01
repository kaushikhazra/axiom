# Action — cycle 2

**The configuration half. None of it needs a server.**

AC 1, 2, 4, 5, 16, 17 and 18 are all about `ServerSpec` and the file that fills it. Seven
criteria reachable without anything listening, which is the cheapest and safest ground on this
row — and it settles the shape everything else is built on.

## Before anything else, three checks

1. **`git status`** and **`git branch --show-current`** — must be `feature/81-remote-mcp`.
2. **`gh issue view 81`** — the criteria, before the diff and before cycle 1's log.
3. **No stray processes.** Cycle 1 left none; check anyway, and check again before exiting.

## What cycle 1 established, so it is not rediscovered

- **`streamable_http_client`, not `streamablehttp_client`.** SDK 2.1.1. The second is what
  memory gives and it is an `ImportError` here.
- Both network transports are live; **neither is deprecated**, so the choice is axiom's on other
  grounds rather than "use the current one".
- `headers` and `timeout` are not parameters of `streamable_http_client` — they go into an
  `httpx2.AsyncClient` from `create_mcp_http_client`. `session_group.py` line 325 is the working
  example.
- **The seam is `Servers._open`'s first eleven lines.** Everything from `listed = await ...
  list_tools()` down is already transport-agnostic.
- `tests/mcp_server.py` can serve over `streamable-http` with `host` and `port`. It needs an
  entry point, not a rewrite.

## 1 — `ServerSpec` gains an address (AC 1, AC 2)

`command` and `args` become optional beside an `address`. Both kinds in one file, both working
in one session — AC 2 is about the *file*, so it is a `config` test with two entries.

**Do not give `Servers` a second class.** Cycle 1's seam sentence is the design: one `Servers`,
one routing rule, two ways in.

## 2 — The two refusals (AC 4, AC 5)

> 4. An entry that names neither a command nor an address is refused, and the refusal says which
>    is missing.
> 5. An entry that names both is refused, and the refusal says so.

`config.read_servers` already returns `(servers, problems)` and #43 built the vocabulary for a
refused entry. Reuse it. **The refusal has to name the entry** — a user with six servers
configured needs to know which one, and #55 exists because a message named a folder instead of a
file.

## 3 — Addresses (AC 16, AC 18)

> 16. An address that is not a valid URL is refused before anything is attempted.
> 18. An address may carry a port, a path, and a query.

AC 16's "before anything is attempted" is the half with teeth: refused at *configuration* time,
not by a transport failing later. The break is a rubbish address reaching `Servers` at all.

AC 18 is three cases and they are cheap: `:8080`, `/mcp`, `?key=value`. Watch for a validator
that accepts a port and quietly drops a query.

## 4 — AC 17, decided this cycle

> A plain-text address is refused, or the user is told the traffic is not encrypted.

**Two acceptable outcomes and they are different features.** `assumption.md` records the leaning:
refusing `http://` outright makes this useless for someone running a server on their own
machine, which is the ordinary case. Telling them once, plainly, is the least surprising reading,
and `localhost` is arguably not worth a word.

**Decide it, record the reasoning under a heading that says it was a decision, and carry it into
the handover.** Do not ask, and do not leave it for cycle 3.

## 5 — Prove each one, and expect a no-op

`observe.md`'s rate, and cycle 1's own: **AC 22 took three breaks and two of them were no-ops
that printed `STAYED GREEN`.** A refusal test is especially prone to it — a break that stops the
refusal firing looks identical to one that stops the *entry* existing.

For each criterion, ask what would still pass if the feature did nothing, then break exactly
that.

## Do not

- Fetch anything. No `npx -y`, no `uvx`, nothing downloaded at test time.
- Contact a hosted server, or need a real secret.
- Start a server on a fixed port. That question is cycle 3's and it is open.
- Leave a process running. Check before you exit.
- Give `Servers` a second class of server.
- Regenerate the baseline.
- Use a heredoc for anything containing a backslash escape.
- Merge.

## Record

`logs/cycle-2.md`, per `observe.md`. Then write cycle 3's action — which is where a server
starts answering, and where the port question has to be settled.
