# Handoff — manual testing

Rewritten 2026-08-28 at the end of the session that ran rows 11 to 16. **Seven more rows have
merged since the last version**, and one of them - #60 - changed what every reply looks like,
so the "start here" and "what to try" sections below are updated for it.

**The next session picks up here: manual testing.** It was the next thing before these seven
rows too, and it still is.

## Where things stand

`master` after PR #69. **617 tests, green and hermetic.** The queue is empty - sixteen rows,
all done. **A cron is still installed** and has nothing to find; see the end of this file.

| issue | PR | cycles | what it changed |
|---|---|---|---|
| [#40](https://github.com/kaushikhazra/axiom/issues/40) plain-text pages | [#44](https://github.com/kaushikhazra/axiom/pull/44) | 3 | |
| [#41](https://github.com/kaushikhazra/axiom/issues/41) limits and place | [#45](https://github.com/kaushikhazra/axiom/pull/45) | 4 | |
| [#42](https://github.com/kaushikhazra/axiom/issues/42) oversized turns | [#46](https://github.com/kaushikhazra/axiom/pull/46) | 4 | |
| [#43](https://github.com/kaushikhazra/axiom/issues/43) MCP servers | [#47](https://github.com/kaushikhazra/axiom/pull/47) | 4 | |
| [#48](https://github.com/kaushikhazra/axiom/issues/48) the model the host has | [#50](https://github.com/kaushikhazra/axiom/pull/50) | 3 | **no default model any more** |
| [#49](https://github.com/kaushikhazra/axiom/issues/49) mid-session switch | [#51](https://github.com/kaushikhazra/axiom/pull/51) | 3 | **`/model`** |
| [#52](https://github.com/kaushikhazra/axiom/issues/52) tool-capable first | [#53](https://github.com/kaushikhazra/axiom/pull/53) | 1 | **list order** |
| [#57](https://github.com/kaushikhazra/axiom/issues/57) config encoding | [#63](https://github.com/kaushikhazra/axiom/pull/63) | 2 | **a hand-written `mcp.json` is readable again** |
| [#55](https://github.com/kaushikhazra/axiom/issues/55) announce the file | [#64](https://github.com/kaushikhazra/axiom/pull/64) | 2 | |
| [#56](https://github.com/kaushikhazra/axiom/issues/56) same facts after a switch | [#65](https://github.com/kaushikhazra/axiom/pull/65) | 2 | |
| [#61](https://github.com/kaushikhazra/axiom/issues/61) what the tools cost | [#66](https://github.com/kaushikhazra/axiom/pull/66) | 2 | **the startup line says the token cost** |
| [#62](https://github.com/kaushikhazra/axiom/issues/62) what the summary keeps | [#67](https://github.com/kaushikhazra/axiom/pull/67) | 3 | **exit 2** - 6 of 12 criteria, follow-up [#68](https://github.com/kaushikhazra/axiom/issues/68) |
| [#60](https://github.com/kaushikhazra/axiom/issues/60) formatted replies | [#69](https://github.com/kaushikhazra/axiom/pull/69) | 6 | **every reply is now rendered markdown** |

**All six of #57, #55, #56, #61, #62 and #60 came out of one evening of manual testing** on
2026-08-27. That is the argument for doing more of it: the suite was 440 green and hermetic,
six loops had each survived a hostile cold read, and an evening of actually using the thing
found six more. Four were shapes no test could have produced.

**[#68](https://github.com/kaushikhazra/axiom/issues/68) is open** and is the only unfinished
loop work. #62 exited at its fail-safe with 6 of 12 criteria: the two changes it made work on
*opposite models* - showing the summariser the kept turns helps `qwen2.5:7b` and not
`gemma4:e2b`, and allowing an empty answer helps `gemma4:e2b` and not `qwen2.5:7b`.

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

## What changed about reading a reply

**Replies are rendered markdown now** (#60). Headings, bold, italic, lists, quotes, inline
code, links and tables are formatted as they stream, and fenced blocks are syntax-highlighted
when the fence names a language. Nothing is redrawn: a line is written once, when it is
complete.

```
$ axiom --no-render          # today's plain output, markup and all
$ AXIOM_RENDER=off axiom     # the same, for the session
$ NO_COLOR=1 axiom           # colour off, formatting kept
$ axiom > out.txt            # unchanged - piped output is plain, byte for byte
```

**A table is the one thing that waits.** Its rows are visible as they type, but the drawn
table only appears once the last row has arrived - measured at **4.3 to 4.5 seconds** against
`qwen2.5:7b`. That is inherent: column widths are not known until the table ends. Watch
whether it reads as work happening or as a hang.

## Why manual testing is still the next thing

**Nobody has had a long real conversation with axiom.** Thirteen issues have shipped, and the
one evening someone did use it produced six of them. Everything else is settled by tests,
stubs, and short live probes.

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

Models on this machine, in the order the list now offers them: `gemma4:e2b`, `ornith:9b`
(**see known issue 1**), `qwen2.5-coder:7b`, `qwen2.5:7b`, then `gemma2:2b` - the last being
the only one with **no tool support**, and useful for testing that path deliberately.

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

**The model list, first run in a fresh directory.** Models that can call tools come first, each
group in name order, and only a mixed host annotates the rows. Watch: is `(default)` where you
want it, is `remembering this choice in .axiom` welcome or intrusive, and does the list feel
slow on a host with many models (see known issue 2)?

**Switching mid-conversation, for real.** Ask a 2B model something it fumbles, `/model` up to
`ornith:9b`, and ask it to carry on. Watch whether the bigger model actually uses what came
before, and whether the tool-call history from before a switch confuses a model that cannot
call tools.

**MCP with something real.** Write `.axiom/mcp.json`, point it at an actual server. Watch: a
server slower than 30s to start; tool names that confuse a 7B model; and now also **what
happens when you switch models with servers attached** - they should not restart.

**A long conversation.** Talk until compaction fires. Watch what `the summary is full -
forgetting N` drops, and whether the model notices. **[#68](https://github.com/kaushikhazra/axiom/issues/68)
is open on exactly this** - what a bounded summary keeps is settled on one model and not the
other, and a real session is what would settle it.

**Reading a rendered reply, at length.** #60 is why this session existed and the least
manually tested thing here. Ask for something long with headings, a table and a code block.
Watch: does anything appear **twice** when the window is narrow - that was the row's worst
defect and it is the one to check first; does resizing mid-reply corrupt anything; does the
table's four-second pause read as a hang; and is the highlighting a help or a distraction.

## Known, recorded honestly, not bugs to re-report

1. **`ornith:9b` crashes the Ollama server on load** - `CUDA error: shared object
   initialization failed`, `llama-server process has terminated: 0xc0000409`. Not axiom's, and
   axiom reports it as a failed turn and keeps the session, but **do not lean on that model for
   manual testing** until it is looked at. It is otherwise the largest-context model here.
2. **Establishing tool support costs one request per model** on any run that shows the list or
   falls back - about 75 ms each, 377 ms for five. The Python client drops the `capabilities`
   array that `/api/tags` already returns, so there is no cheaper way through the library. If a
   host with thirty models feels slow to start, that is this, and `backend.tool_capable` says
   what to do about it.
3. **A small model will claim it accepted a limit change it cannot make.** `qwen2.5:7b`
   confirmed a 300-second timeout and then ran `sleep 120`. The limit holds structurally; axiom
   does not correct the claim. A story about that would be new scope.
4. **The MCP call bound stops axiom waiting, not the server working.**
5. **A server's stderr is discarded** - deliberate, but a misbehaving server gives you no
   diagnostic. First thing to loosen while debugging.
6. **The "conversation too large" refusal is still unreachable.** #42's last resort drops the
   summary instead. Kept deliberately.
7. **`.axiom/model.json` appears in whatever directory you run from.** Gitignored here; in
   someone else's project it is a new folder they did not ask for. axiom says so the first time.

8. **Two things belong to a system prompt story that has not been written.** A model
   **fabricated tool results** - it invented the contents of a file the tool never read - and
   compaction **corrupted** a detail rather than dropping it ("ventured" became "Vented").
   Kaushik's ruling stands that axiom must not try to detect or challenge an unsupported
   answer: that builds smarts that cannot be kept consistent. The lever is the system prompt,
   and the story is unwritten.
9. **A link's address is in the byte stream, not necessarily on the screen.** #60 emits an
   OSC-8 hyperlink so the address survives; a terminal without OSC-8 support shows the link
   text alone. Windows Terminal supports it. If a link ever looks like plain words with no way
   to reach the address, this is why.

## If manual testing turns up work

The queue is the mechanism and it is empty. A new row in `.claude/loop/queue.md` starts it
again; its **Standing** section carries what thirteen loops learned. Three worth knowing
before writing the next issue:

> **The cycle that writes the code never declares it done.** Read the criteria from GitHub
> before the diff and before the previous log, and attack each rather than confirming it.
> **Twelve for twelve** - it has found something real in every issue it has been applied to.

> **A criterion can be read too loosely by the cycle implementing it**, and the test then gets
> written from the implementation rather than from the issue. #48 AC 33, #49 AC 25 and AC 27
> were all that shape, and so was **#60 AC 2** - "with syntax highlighting when the fence names
> a language" was answered by the other half of the same sentence, twice, with a recorded
> reason persuasive enough to stop anyone checking it. Nothing in the diff looked wrong.

> **Ask what a test would do if the feature did nothing**, then break the feature and watch it
> go red. #60 turned up **six tests that passed for a reason other than the one they claimed**
> and **five breaks that broke nothing**. Both are invisible to a green suite. The break
> harness now fails loudly on a no-op break; a test suite has no equivalent guard, and finding
> the next vacuous test is still a matter of trying.

Write findings up as issues in the format `CLAUDE.md` describes. #60 is the most recent worked
example, and #26 the fullest.

**A cron is still installed and the queue is empty.** It fires, reads `queue.md`, finds no row
marked `running`, and stops - one wasted firing, nothing else. It was left alone deliberately:
the queue's own rule is that a loop never deletes the scheduler, because doing so on a bad
handover ends the chain silently with rows still queued. **Stopping it is Kaushik's call.**
A cycle that fires into an empty queue should say so and exit, not scaffold a row nobody asked
for.
