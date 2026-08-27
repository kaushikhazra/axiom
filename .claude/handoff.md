# Handoff — manual testing

Rewritten 2026-08-27 at the end of the session that ran rows 9 and 10. The previous version
(2026-08-26) is still true in outline, but **#48 and #49 both changed what starting axiom looks
like**, so its "start here" section was wrong and is replaced below.

**The next session picks up here: manual testing.**

## Where things stand

`master` after PR #51. **419 tests, green and hermetic.** No open issues, no cron running,
`.claude/loop/queue.md` says the queue is empty.

| issue | PR | cycles | what it changed |
|---|---|---|---|
| [#40](https://github.com/kaushikhazra/axiom/issues/40) plain-text pages | [#44](https://github.com/kaushikhazra/axiom/pull/44) | 3 | |
| [#41](https://github.com/kaushikhazra/axiom/issues/41) limits and place | [#45](https://github.com/kaushikhazra/axiom/pull/45) | 4 | |
| [#42](https://github.com/kaushikhazra/axiom/issues/42) oversized turns | [#46](https://github.com/kaushikhazra/axiom/pull/46) | 4 | |
| [#43](https://github.com/kaushikhazra/axiom/issues/43) MCP servers | [#47](https://github.com/kaushikhazra/axiom/pull/47) | 4 | |
| [#48](https://github.com/kaushikhazra/axiom/issues/48) the model the host has | [#50](https://github.com/kaushikhazra/axiom/pull/50) | 3 | **no default model any more** |
| [#49](https://github.com/kaushikhazra/axiom/issues/49) mid-session switch | [#51](https://github.com/kaushikhazra/axiom/pull/51) | 3 | **`/model`** |

## What changed about starting it

**axiom no longer has a default model.** `qwen2.5:7b` is gone from the code entirely. A run's
model now comes from the host:

```
$ axiom                      # lists what is installed and asks; remembers your pick
$ axiom --model ornith:9b    # uses it, no list
$ echo "hi" | axiom          # your last choice here, else the first installed - never asks
```

The pick is remembered in `.axiom/model.json`, **per host and per directory**, and only when
*you* choose it - a flag never writes it. That file is gitignored; `.axiom/mcp.json` is not,
deliberately.

**`/model` changes model mid-conversation** and keeps the conversation:

```
> /model                 # the list, with the current model marked
> /model ornith:9b       # straight there, exact name with tag
```

Ctrl-C at that list cancels; Ctrl-D ends the session.

## Why manual testing is still the next thing

**Nobody has actually used axiom.** Six issues have shipped since anyone tried to have a real
conversation with it. Everything is settled by tests, stubs, and short live probes.

Still never exercised:

- **A real MCP server.** #43 was proved against `tests/mcp_server.py`, thirty lines and ours.
  **There is no `.axiom/mcp.json` in the repo**; one has to be written by hand.
- **A long real session.** Compaction, the summary bound, #42's recovery and now #49's
  carried-conversation compaction have only been driven with stubs or a forced small context.
- **The system prompt over many turns.** Whether a model still honours its working directory on
  turn forty is unknown.
- **A switch in a real conversation.** #49's live probe switched four times and asked nothing
  in between. Whether a 2B model picks up a conversation a 9B one was having is exactly the
  question the feature exists for, and it has not been asked.

## Start here

```
uv run --directory C:/Projects/axiom axiom
```

Models on this machine: `gemma2:2b` (**no tool support** - useful for testing that path, and
what an unchosen run now lands on), `gemma4:e2b`, `ornith:9b`, `qwen2.5:7b`, `qwen2.5-coder:7b`.

**Work in the sandbox, not the repo:**

```
uv run --directory C:/Projects/axiom axiom --working-directory C:/Projects/.tmp/axiom-tool-sandbox
```

`CLAUDE.md`'s tool-testing rules still apply. Nothing between the model and the machine
inspects what a tool is about to do - the security stories have not been written, let alone
landed.

**Pointing at a different Ollama:**

```
uv run --directory C:/Projects/axiom axiom --host http://192.168.1.50:11434   # one run
$env:AXIOM_HOST = "http://192.168.1.50:11434"                                 # the session
```

Command line beats environment. The remembered model is **per host**, so pointing somewhere
else gets its own choice rather than a model that host may not have.

## What to try, and what to watch for

**The model list, first run in a fresh directory.** Watch: is the order what you expect, does
`(default)` land where you want it, and is `remembering this choice in .axiom` welcome or
intrusive?

**Switching mid-conversation, for real.** Ask a 2B model something it fumbles, `/model` up to
`ornith:9b`, and ask it to carry on. Watch whether the bigger model actually uses what came
before, and whether the tool-call history from before a switch confuses a model that cannot
call tools.

**MCP with something real.** Write `.axiom/mcp.json`, point it at an actual server. Watch: a
server slower than 30s to start; tool names that confuse a 7B model; and now also **what
happens when you switch models with servers attached** - they should not restart.

**A long conversation.** Talk until compaction fires. Watch what `the summary is full -
forgetting N` drops, and whether the model notices.

## Known, recorded honestly, not bugs to re-report

1. **An unchosen run lands on `gemma2:2b`**, which is alphabetically first here and the only
   model with no tool support. Announced, one keystroke to change, remembered after that.
   **This is the most likely thing to want changed** - Kaushik asked for it as a change request
   rather than a loop decision. Sorting tool-capable models first is the obvious fix.
2. **A small model will claim it accepted a limit change it cannot make.** `qwen2.5:7b`
   confirmed a 300-second timeout and then ran `sleep 120`. The limit holds structurally; axiom
   does not correct the claim. A story about that would be new scope.
3. **The MCP call bound stops axiom waiting, not the server working.**
4. **A server's stderr is discarded** - deliberate, but a misbehaving server gives you no
   diagnostic. First thing to loosen while debugging.
5. **The "conversation too large" refusal is still unreachable.** #42's last resort drops the
   summary instead. Kept deliberately.
6. **`.axiom/model.json` appears in whatever directory you run from.** Gitignored here; in
   someone else's project it is a new folder they did not ask for. axiom says so the first time.

## If manual testing turns up work

The queue is the mechanism and it is empty. A new row in `.claude/loop/queue.md` starts it
again; its **Standing** section carries what six loops learned. Two worth knowing before
writing the next issue:

> **The cycle that writes the code never declares it done.** Read the criteria from GitHub
> before the diff and before the previous log, and attack each rather than confirming it. Six
> for six.

> **A criterion can be read too loosely by the cycle implementing it**, and the test then gets
> written from the implementation rather than from the issue. #48 AC 33, #49 AC 25 and AC 27
> were all that shape - nothing in the diff looked wrong.

Write findings up as issues in the format `CLAUDE.md` describes. #48 and #49 are the most
recent worked examples.

**Nothing is scheduled.** Rows 9 and 10 ran back to back inside one session, with no cron at
all - the chain ends when the session does.
