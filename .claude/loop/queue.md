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
| 5 | [#40](https://github.com/kaushikhazra/axiom/issues/40) plain-text pages | `40-plain-text-pages` | queued |
| 6 | [#41](https://github.com/kaushikhazra/axiom/issues/41) limits and working directory | `41-limits-and-place` | queued |
| 7 | [#42](https://github.com/kaushikhazra/axiom/issues/42) oversized-turn recovery | `42-oversized-turn` | queued |
| 8 | [#43](https://github.com/kaushikhazra/axiom/issues/43) MCP servers | `43-mcp-servers` | queued |

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
