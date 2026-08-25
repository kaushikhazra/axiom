# Loop queue

Issues are worked one loop at a time, in this order. A loop never runs while another is
running - three of these write into the same code, and parallel loops would spend their
cycles resolving each other's conflicts.

| order | issue | slug | state |
|---|---|---|---|
| 1 | [#33](https://github.com/kaushikhazra/axiom/issues/33) modular OOP | `33-modular-oop` | **done** - merged in PR #36, 5 cycles |
| 2 | [#34](https://github.com/kaushikhazra/axiom/issues/34) tools | `34-tools` | **done** - merged in PR #37, 8 cycles, all 35 criteria |
| 3 | [#35](https://github.com/kaushikhazra/axiom/issues/35) web search and fetch | `35-web` | **done** - merged in PR #38, 5 cycles, all 30 criteria |
| 4 | [#32](https://github.com/kaushikhazra/axiom/issues/32) compaction overflow | `32-compaction-overflow` | **done** - merged in PR #39, 3 cycles, all 6 criteria (1, 2 and 5 amended on evidence) |
| 5 | [#40](https://github.com/kaushikhazra/axiom/issues/40) plain-text pages | `40-plain-text-pages` | **done** - merged in PR #44, 3 cycles, all 12 criteria (AC 7 found broken by the cycle-3 cold read after cycle 2 called it met) |
| 6 | [#41](https://github.com/kaushikhazra/axiom/issues/41) limits and working directory | `41-limits-and-place` | **done** - merged in PR #45, 4 cycles, all 12 criteria (AC 9 found decorative by the cycle-4 cold read after two cycles called it met) |
| 7 | [#42](https://github.com/kaushikhazra/axiom/issues/42) oversized-turn recovery | `42-oversized-turn` | **done** - merged in PR #46, 4 cycles, all 8 criteria (the cycle-3 cold read found the fix compacting away the user's own message, and AC 4 still violated) |
| 8 | [#43](https://github.com/kaushikhazra/axiom/issues/43) MCP servers | `43-mcp-servers` | **done** - merged in PR #47, 4 cycles, all 30 criteria (the cycle-4 cold read found AC 6's routing broken for a server whose name contains the separator, and AC 22 marked met with no test at all) |

**The queue is empty.** Every row is done. A new loop needs a new row here first.

Four issues ran back to back on 2026-08-26 - #40, #41, #42, #43 - and **the cold read found a
real defect in every one of them**, each time after the implementing cycle had written
`met-with-evidence` beside the criterion. That is not a run of bad luck; it is the rule
earning its place four times out of four, and the reason it sits in **Standing** rather than
in any one loop's files.

Rows 5 to 8 are ordered smallest blast radius first. #40 touches `fetch_page` alone. #41
and #42 both change what the model and the user are told, and #42 reaches into the same
compaction code #32 just settled, so it goes second of the two. #43 is last because it is
the only one that adds a dependency and a new configuration surface, and it is worth
having the tool and context work of #41 finished before a server can contribute tools.

## Handing over

**Every loop ends by starting the next one.** This happens inside the run that reaches the
exit - converged or fail-safe, either way - because nothing else is watching. A loop that
merges its work and stops without doing this leaves the queue stalled with no error and no
one to notice.

On reaching any exit in `loop.md`:

1. Finish that loop's own exit first - merge or don't, per its rules. Never start the next
   loop on top of unmerged work.
2. Delete that loop's cron. Use `CronList` to find its id if it is not to hand.
3. Mark its row **done** here, with the PR number and cycle count. If it hit its fail-safe,
   say so and link the follow-up issue it opened.
4. Take the next `queued` row. If there is none, stop and say the queue is empty.
5. Scaffold `.claude/loop/{slug}/iteration-1/` by copying
   `C:/Projects/APEX/plugins/ai-engineering/skills/auto-iterate/template`, then delete the
   `artifact/` directory it brings - the code is not the loop's artifact folder.
6. Write that iteration's `goal.md`, `observe.md`, `assumption.md`, `action.md` and
   `loop.md`, reading the issue with `gh issue view` for the criteria. Carry forward
   anything in **Standing** below that applies.
7. Create the branch `feature/{slug}` from `master`, and commit the scaffold.
8. Create the cron, 15-minute cadence on an off-minute:
   `Read C:/Projects/axiom/.claude/loop/{slug}/iteration-1/loop.md and run one iteration.`
9. Mark the new row **running** here and say, in the handover, which loop just started and
   what its first cycle will do.

## Standing

These apply to every loop in this queue and do not need rediscovering.

- **15-minute cycles, 12-hour fail-safe.** One cycle per firing. A hung run costs one cycle.
- **A loop never waits for an answer.** The queue runs unattended, one loop after another,
  and nobody is watching between firings. A cycle that stops to ask a question does not
  pause - it burns every remaining cycle until the fail-safe, and takes the loops queued
  behind it down with it. So a decision that would otherwise need Kaushik is **made by the
  loop**: pick the option that is reversible and least surprising, record it in the cycle
  log as a decision with its reasoning under a heading that says so, and carry it into the
  handover. Do not write a question into an `action.md` or an `observe.md`. Write the
  decision and the reason to revisit it.
  - **The one exception is safety, not uncertainty.** If proceeding would destroy something,
    leak something, or merge behaviour nobody has verified, that is exit 3: do not merge,
    push the branch, say plainly what is blocked. Being unsure is not that. Being unsure is
    what the log is for.
  - This is the Antenna Principle applied to something with no antenna. Find the constraint,
    break that one thing, proceed carefully, and leave a record of where you threaded.
- **The cycle that writes the code never declares it done.** A separate cycle checks, and it
  earns its keep: #40's cycle 3 found AC 7 outright broken - a typeless PNG returning its
  bytes as content and counted as a source - after cycle 2 had marked that criterion
  `met-with-evidence`. The method that caught it, in order:
  - **Read the criteria from GitHub before the diff and before the previous log.** The log
    is persuasive precisely because its author wrote both the code and the verdict.
  - **Attack each criterion instead of confirming it.** Cycle 2's AC 7 test served a *text*
    body with no type - a test that passes for an implementation doing no judging at all.
    The bug needed a hostile input, not a re-reading.
  - A genuinely fresh reader is stronger and should be used where one is available. Where
    one is not, say so in the log rather than claiming a cold read that was not cold.
  - **Four for four.** #40 AC 7 - a typeless PNG returning its bytes as content. #41 AC 9 -
    the retry block comparing whole result strings, so a pid in the output defeated it.
    #42 AC 3 - the fix compacting away the user's own message, so the model answered a
    question it had never seen. #43 AC 6 - a server whose name contained the separator
    declaring tools that could never be called. Every one found by a hostile input; not one
    by rereading code.
- **Be suspicious of a hard criterion that passes first time.** #43's lifetime tests asserted
  `surviving(spawned) == []` where `spawned` was measured *after* the servers had already been
  stopped - so the set was empty and the assertion held for any implementation at all. Ask
  whether the test could pass if the feature did nothing, then **break the feature and watch
  it go red**. A test that cannot fail proves nothing.
- **Remove a race rather than shrinking the window.** #43's call-bound test used a 1 ms
  timeout against a server that answers in about a millisecond, and the answer won. The fix
  was a tool that actually waits; a smaller timeout would have passed more often and stayed a
  coin toss.
- **A number is only as good as the function it came from.** `estimated_tokens` divides by
  four and `too_large` by three. The system prompt was reported at 56 tokens, then 163, before
  being measured at 205 - and the middle figure was carried into two loops' files before
  anyone checked.
- **The formatter is not the only thing that edits a file.** #43 added four imports in one
  edit and used them in the next; the `PostToolUse` hook ran between, saw them unused, and
  stripped them. Verify what landed, not just what was sent.
- **Cycle 1 does not write code** when the artifact already exists. It records the baseline
  that the behaviour-preservation criteria are later measured against.
- **`tests/baseline/transcript.txt` is the golden master.** Any loop that changes observable
  behaviour deliberately - #34 and #35 both add startup-line content - must regenerate it
  *on purpose*, with `AXIOM_WRITE_BASELINE=1`, and say in that cycle's log exactly which
  lines changed and why. Regenerating it to clear a failure is the one move that destroys
  its value.
- **`tests/conftest.py` clears `AXIOM_HOST`, `AXIOM_MODEL` and `AXIOM_DEBUG_MAX_CONTEXT`**
  for every test. If a suite suddenly fails on the startup line, that fixture has been lost -
  restore it rather than working around it.
- **The suite must stay green with no Ollama running**, and must not be changeable by an
  environment variable. Both are provable in one command:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **Never merge a red suite**, and never merge a behaviour change the transcript has not
  cleared.
- **The tool-testing safety rules in `CLAUDE.md` bind #34 and #35.** Live models get
  non-destructive requests only; destructive criteria are settled with a stub inside
  `tmp_path`; live-model tool tests run in `C:/Projects/.tmp/axiom-tool-sandbox`.
- **The cron is session-only.** It dies with the Claude session, and so does the chain. The
  files and commits survive; restarting means re-creating the cron for whichever loop the
  queue says is `running`.
