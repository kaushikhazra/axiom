# Handoff — axiom is installable by strangers; three manual passes left

Rewritten 2026-09-02 at the end of a session that did two things: **published axiom**, and
**cleared the renderer's manual pass**. Nothing is scheduled and nothing is running.

## Where things stand

`master` is at **3b9e478 plus this commit, pushed**, and green: **892 passed, 1 deselected,
~82s**. `tests/baseline/transcript.txt` has not moved.

| branch | issue | state |
|---|---|---|
| `feature/80-multiline` | [#80](https://github.com/kaushikhazra/axiom/issues/80) | 21 by test, **15 owed by hand**, unmerged |
| `feature/81-remote-mcp` | [#81](https://github.com/kaushikhazra/axiom/issues/81) | 25/25 by test, **partly seen today**, unmerged |

Everything else that was outstanding is merged. #72, #73 and #76 are **closed**.

## What happened today

**1. axiom is public and installable.** A `README.md` is on `master` and is the repo's front
page; the description and eight topics are set. The install is three commands on a machine
with nothing on it, and uv brings its own Python:

```
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install --python 3.12 https://github.com/kaushikhazra/axiom/archive/refs/heads/master.zip
axiom
```

Every command in the README was run before it was written, and **two would have been wrong
from memory**:

- `uv tool upgrade` reports *"nothing to upgrade"* for a URL install and never re-fetches.
  Updating is `uv tool install --force`.
- `git+https://` needs a git binary a fresh machine does not have. The archive URL does not.

**2. Sitting 1 is done — #72, #73 and #76 in one pass.** Same renderer, one build, one reply
carrying an indented block, a fenced block beside it, a three-level nested list and an
over-wide quote; checked at full width, at half, and against `--no-render`. **Everything
satisfies.** The judgement a test could not make is answered: **an unpainted indented block
does read as a block**, so #76 AC 3 holds as built and #77 AC 20 stands unchanged. Record in
`.claude/loop/76-indented-code/iteration-1/manual-pass.md`.

**3. #81 was seen against a real server**, which localhost could never show. `deepwiki` at
`https://mcp.deepwiki.com/mcp` - third-party, public, no auth, streamable HTTP - attached
through axiom's own `Servers`, declared three tools, and answered correctly. That is **row 1
of #81's manual pass, genuinely satisfied**. Two incidental findings:

- A repo DeepWiki had not indexed came back **named, with the reason, session alive** - the
  closest thing yet to evidence for AC 13.
- **Three remote tools cost ~307 tokens on every request** (1250 with nothing attached, 1557
  with deepwiki). First real number behind the `"tools": [...]` filter.

## Start here tomorrow

```
cd C:\Projects\.tmp\axiom-manual
uv run --project C:/Projects/axiom axiom
```

**`--project`, not `--directory`.** `--directory` moves the working directory into the repo,
which CLAUDE.md's tool-testing rule forbids.

The deepwiki config from today is parked at `.axiom/mcp.json.bak` in that folder - rename it
back to `mcp.json`. It needs `feature/81-remote-mcp` checked out; `address` does not exist on
`master`.

**Two checks were agreed for tomorrow and not done**, both flagged in #81's file as most
likely to look settled and not be:

- **AC 13** - ask deepwiki something and kill the wifi mid-call. Named, reasoned, session
  alive.
- **AC 17's judgement** - add `"address": "http://127.0.0.1:9999/mcp"` and restart. You get
  the not-encrypted line *and* a connection failure. **Is that warning useful, or noise you
  would learn to skip?** If noise, the criterion changes, and that is Kaushik's to change.

## What is still owed

| | |
|---|---|
| **#74** | merged already, **owed a manual pass**. The scheduler, not the renderer, so sitting 1 did not touch it. Cheapest one left - no build needed. |
| **#80** | 15 by hand on a real terminal. The longest list, and the only ones a test can never reach. |
| **#81** | rows 2-5: slow connection, dropped mid-call, certificate or proxy, nothing left connected on exit. |

## Two decisions still waiting

**#80 AC 6** - *"on a terminal that cannot report ctrl+enter separately from enter…"* Real,
unimplemented, unverifiable on this console, which reports the key fine (`0a` against `0d`).
Kept unstruck because striking renumbers thirty criteria, and cycle 7 spent a whole cycle
repairing eleven citations after the last renumbering. Becomes real on Linux or macOS.

**#81 AC 17** - see above. Now testable both ways, since today produced an `https` run with no
warning to compare against.

## Two things that are not built, and are worth knowing why

**Google and Slack do not exist in `src/axiom/`, and cannot yet.** Gmail, Drive, Calendar and
Slack all publish remote MCP servers, but every one is OAuth, and `ServerSpec` carries
`command`, `args`, `env`, `tools` and `address` - **no headers, no token, no browser flow.**
That is why today's demo had to use a no-auth server. [#82](https://github.com/kaushikhazra/axiom/issues/82)
is the capability that unblocks all four; after it they are configuration, not code. Not
started.

**There is still no permission gate.** `run_command` runs whatever the model asks with no list
of allowed programs, and `outside()` is visibility only - it reports a path beyond the working
directory and does not refuse it. **This got sharper today, not softer:** the repo is public
and installs in three commands. The README says so plainly, which is honesty, not a fix.
**No issue exists for it.** #82 would store account access on top of it, so the order of those
two is a real decision.

## One rule that must not be forgotten

**No test builds a `prompt_toolkit` session** - not a `PromptSession`, not a
`create_pipe_input`, not a key processor. Nineteen did, and running them took this machine down
**twice**. `_say_how_to_send` calls `run_in_terminal`, which writes to the *real* console rather
than the `DummyOutput` a test supplies, so a test feeding `ctrl+enter` reaches out of pytest
and into the session that launched it. All nineteen were deleted in `32daf51`.

Written in `tests/test_multiline.py`'s docstring and in `tests/conftest.py`, because the next
session will not remember the crash.
