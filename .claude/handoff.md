# Handoff — three features built and unmerged, five manual passes owed

Rewritten 2026-09-02 at 04:40, before a restart, at the end of an unattended queue run that
took rows 18 to 20 between 01:35 and 04:30.

**The next session's job is a manual pass, not more building.** Everything below is green,
break-proven and committed. None of it has been watched running by a person, and that is the
only thing standing between it and `master`.

## Where things stand

`master` is at `936fd1e` and has not moved. **Six branches are committed and unpushed** — a
reboot does not lose them, they are local commits, but nothing off this machine has a copy.

| branch | issue | state |
|---|---|---|
| `feature/81-remote-mcp` | [#81](https://github.com/kaushikhazra/axiom/issues/81) MCP server by address | 25/25 break-proven, 4 cycles |
| `feature/76-indented-code` | [#76](https://github.com/kaushikhazra/axiom/issues/76) indented code block | 13/13 break-proven, 2 cycles |
| `feature/80-multiline` | [#80](https://github.com/kaushikhazra/axiom/issues/80) multi-line message | **21 by test, 15 by a person** |
| `feature/74-scheduled-prompts` | [#74](https://github.com/kaushikhazra/axiom/issues/74) | merged to master already; branch left behind |
| `feature/73-nested-lists` | [#73](https://github.com/kaushikhazra/axiom/issues/73) | merged already; branch left behind |
| `feature/72-wide-lines` | [#72](https://github.com/kaushikhazra/axiom/issues/72) | merged already; branch left behind |

The suite on `feature/81-remote-mcp` is **912 passed, 1 deselected, ~128s**. On `master` it is
876. `tests/baseline/transcript.txt` has not moved in seventeen cycles across five issues.

**Nothing is scheduled and nothing is running.** The queue's cron was deleted at its last
handover, which is the one place that is right — `.claude/loop/queue.md` explains why.

## Start here

```
cd C:\Projects\.tmp\axiom-manual
uv run --project C:/Projects/axiom axiom
```

**`--project`, not `--directory`.** `--directory` moves the working directory into the repo,
which CLAUDE.md's tool-testing rule forbids, and then needs `--working-directory` to undo.

Each branch carries its own checklist, written by the loop that built it:

- `.claude/loop/80-multiline/iteration-1/manual-pass.md` — **fifteen criteria**, all key
  presses and pastes
- `.claude/loop/76-indented-code/iteration-1/manual-pass.md` — one judgement: does an
  unpainted indented block still read as a block
- `.claude/loop/81-remote-mcp/iteration-1/manual-pass.md` — everything tested is 127.0.0.1;
  what is owed is a real server over a real network

**#72, #73 and #74 are still owed a pass from before**, and #72, #73 and #76 are all the same
renderer. Worth one sitting.

## The order that costs least

1. **#76 and #72/#73 together** — one build, one renderer, one look.
2. **#80** — the key presses. Its fifteen are the longest list and the only ones a test can
   never reach.
3. **#81** — needs a real remote MCP server, so it is the one that needs something you do not
   have on the machine.

Merge each as it passes. Nothing was merged by the loop, deliberately.

## Two decisions waiting

**#80 AC 6** — *"on a terminal that cannot report ctrl+enter separately from enter…"* Real,
unimplemented, and unverifiable on your console, which reports the key fine. Kept in the issue
rather than struck, because striking means renumbering thirty criteria and cycle 7 spent a whole
cycle repairing eleven citations after the last renumbering. It becomes real the first time
axiom runs on Linux or macOS.

**#81 AC 17** — the loop decided *told, not refused*, and *told for every `http://` including
localhost*. The thing to judge in use is whether the line is noise. If every local run says
`far: http://127.0.0.1:9000/mcp is not encrypted`, that is a warning people learn to skip. If it
reads that way to you, the criterion changes — and that is yours to change.

## Two issues this run opened

- **[#83](https://github.com/kaushikhazra/axiom/issues/83)** — scheduling anything silently
  switches multi-line input off. `read_line`'s timed path never consults the composer, so a user
  with a job set gets the old single-line reader and is told nothing. Seventeen criteria; the
  four that matter are about a job firing while a message is half-written.
- **[#82](https://github.com/kaushikhazra/axiom/issues/82)** — browser auth, from the earlier
  conversation about Gmail, Drive, Calendar and Slack. Not started.

## One rule that must not be forgotten

**No test builds a `prompt_toolkit` session** — not a `PromptSession`, not a
`create_pipe_input`, not a key processor. Nineteen did, and running them took this machine down
**twice**. `_say_how_to_send` calls `run_in_terminal`, which writes to the *real* console rather
than the `DummyOutput` a test supplies, so a test feeding `ctrl+enter` reaches out of pytest and
into the session that launched it. All nineteen were deleted in `32daf51`.

It is written in `tests/test_multiline.py`'s docstring, in `tests/conftest.py`, and in the
queue's **Standing**, because the next session will not remember the crash.

## What the run is actually evidence for

Not the loop — **the break**. Across three rows it found five tests that could not have failed,
thirteen no-op breaks, and two real defects in shipped code. Not one came from reading a diff.
The details are in `.claude/loop/queue.md` under the empty-queue note, and in each row's cycle
logs.

The open problem it leaves: **a break that applies cleanly and changes no behaviour prints
exactly what a surviving test prints.** The only thing that has ever caught one is asking why it
stayed green.
