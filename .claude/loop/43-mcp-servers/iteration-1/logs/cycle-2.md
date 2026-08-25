# Cycle 2 — 2026-08-26, 04:13 IST

Config and client built. **15 of 30 criteria met with evidence, 8 implemented but untested,
7 not started.** The split is deliberate — `action.md` scoped this cycle to the criteria that
get a server's tools to the model at all.

## Criteria status

**Met with evidence (15):** AC 1, 2, 3, 5, 6, 7, 8, 14, 15, 16, 17, 18, 21, 29, 30

**Attempted — implemented, not yet tested (8):**

| AC | what exists |
|---|---|
| 10 | `ServerSpec.tools` filters what is declared |
| 11 | no `tools` key means all of them |
| 12 | a named tool the server lacks becomes `no tool named X` |
| 22 | `START_TIMEOUT` bounds a slow server |
| 23 | `CALL_TIMEOUT` bounds a hung call |
| 24 | a dead server's calls fail with a reason; others untouched |
| 26 | `main()` wraps `_chat` in `try/finally` calling `stop()` |
| 27 | same, so a failure route stops servers too |

**Not started (7):** AC 4 (told while servers are starting), AC 9 (nothing carries between
runs), AC 13 (what the tools cost against the window), AC 19 and AC 20 (**the timeouts are
fixed constants and the criteria require them configurable**), AC 25 (no failure ends the
session), AC 28 (exit status unaffected).

**Suite: 294 passed** (272 + 22), hermetic. **Transcript byte-identical.**

## Two bugs caught before they ran

**`errlog` is not on `StdioServerParameters`.** It belongs to `stdio_client`, and it is typed
`TextIO` — so the obvious spelling was wrong twice over, and `subprocess.DEVNULL` (an integer)
would have been wrong even in the right place. Found by inspecting the real signature rather
than trusting cycle 1's note. The transport form is used instead, with a `devnull` text stream
held on the exit stack.

**The formatter deleted four imports.** `json`, `re`, `field` and `Path` were added to
`config.py` in one edit and used in the next; the `PostToolUse` hook ran between them, saw
them unused, and stripped them. It surfaced as `NameError: name 'Path' is not defined` at
import. Worth recording because `assumption.md` already carries "verify scripted edits landed"
and this is the same class from a different direction — the tool that edits is not the only
thing that changes the file.

## What was built

**`config.py` reads its first file.** `.axiom/mcp.json`, the `mcpServers` shape, `${NAME}`
substituted from the environment. Problems are *returned*, not raised: a bad entry costs that
server and not the session, the same reason `tools.run()` returns failures as text.

`${NAME}` deliberately, not `$NAME` — a bare dollar is ordinary in a command line and treating
it as a reference would rewrite arguments nobody meant as references. An unset variable
becomes empty rather than the literal `${NAME}`, because passing the placeholder through hands
a server the text of a reference as though it were a token, and it fails somewhere further
away with something less useful to say.

**`servers.py`** holds the loop, the sessions and the routing. One `AsyncExitStack` keeps every
session open at once, so leaving it closes them all in reverse order whatever happened in
between. `server__tool` is both the collision guarantee and the routing key — one mechanism,
not two.

**A server's stderr is discarded.** Cycle 1 found a server printing a full Python traceback
into the middle of a conversation. `terminal.py` owns every print and never sees that, and
AC 16 forbids an error being a leak path.

**AC 6 is proven by construction, not by inspection.** `tests/mcp_server.py` deliberately
offers a tool called `read_file`, and the test asserts the built-in name is untouched and the
server's is `tiny__read_file`.

## Deliberately deferred, and why

**AC 19 and AC 20 need real work, not a test.** `START_TIMEOUT` and `CALL_TIMEOUT` are module
constants. The criteria ask that both be configurable on the command line and in the
environment, and that every value in force be visible at startup. That is `config.py` work
plus a startup-line change, and doing it badly at the end of a long cycle is how #41's mistake
happened.

**AC 13 is the one to think about rather than type.** "What the declared tools cost against
the context window" — #42 measured the system prompt at 205 tokens for exactly this reason.
Tool declarations ride in every request too, and a server contributing twenty of them is a
fixed tax the user cannot see. The number is computable from the declarations; where it goes
is the question.

## Nothing here needs an answer from Kaushik
