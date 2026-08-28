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
| 9 | [#48](https://github.com/kaushikhazra/axiom/issues/48) model the server actually has | `48-model-choice` | **done** - merged in PR #50, 3 cycles, 25 minutes, all 38 criteria (the cycle-3 cold read found five, including AC 29 with no real test at all - the stub discarded the model name it was handed) |
| 10 | [#49](https://github.com/kaushikhazra/axiom/issues/49) mid-session model switch | `49-model-switch` | **done** - merged in PR #51, 3 cycles, 75 minutes, all 34 criteria (the cycle-3 cold read found five, three of them criteria read too loosely and two with no test at all) |
| 11 | [#57](https://github.com/kaushikhazra/axiom/issues/57) config file encoding | `57-config-encoding` | **done** - merged in PR #63, 2 cycles, 21 minutes, all 9 criteria (the cycle-2 cold read found a test passing for the wrong reason - a strict decoder rejects a rubbish file at the mark and reports 'could not be read' too) |
| 12 | [#55](https://github.com/kaushikhazra/axiom/issues/55) announce the file, not the folder | `55-announce-the-file` | **done** - merged in PR #64, 2 cycles, 29 minutes, all 11 criteria (the cycle-2 cold read found AC 1 and AC 7 conflicting over an empty file; resolved in AC 7's favour and recorded in a test) |
| 13 | [#56](https://github.com/kaushikhazra/axiom/issues/56) the same facts after a switch | `56-same-facts` | **done** - merged in PR #65, 2 cycles, 32 minutes, all 12 criteria (the cycle-2 cold read found three tests passing because a default happened to be right; the arguments are now required) |
| 14 | [#61](https://github.com/kaushikhazra/axiom/issues/61) what the tools cost | `61-tool-cost` | **done** - merged in PR #66, 2 cycles, 35 minutes, all 12 criteria (the cycle-2 cold read found AC 9 with no test at all - every test used default settings, so a figure measured from a bare Limits() matched by coincidence; also fixed a flaky lifetime test in #43) |
| 15 | [#62](https://github.com/kaushikhazra/axiom/issues/62) what the summary keeps | `62-summary-facts` | **done** - merged in PR #67 at **exit 2**, 3 cycles, 49 minutes. **6 of 12 criteria met outright**, 3 met on one model of two, 2 not met as written. Follow-up [#68](https://github.com/kaushikhazra/axiom/issues/68). The two changes work on *opposite* models - showing the kept turns fixes qwen and not gemma, allowing an empty answer fixes gemma and not qwen |
| 16 | [#60](https://github.com/kaushikhazra/axiom/issues/60) formatted replies | `60-rendered-replies` | **done** - merged in PR #69, 6 cycles, 2h40m, all 29 criteria. **Seven real defects across two cold reads**, six of them found by feeding hostile input to a modelled terminal rather than by reading code. AC 7 was not met at all - every paragraph longer than the window was drawn on screen twice, while the recorded evidence for it stayed true |

**The queue is empty.** Sixteen rows, all done. Nothing is running and there is no next row
to hand to. The cron is still installed and has nothing to find - see **Handing over** below;
it was deliberately not deleted, and stopping it is Kaushik's call.

**#60 is where the method paid for itself most plainly, and the numbers are worth keeping**:
seven real defects, **six vacuous tests**, and **five no-op breaks**. Every vacuous test
shared one shape - asserting that text was *present in the byte stream*, where the plain echo
puts it regardless of what the renderer does. Every no-op break either changed nothing (`[]
or X` is `X`, an anchored `re.match` that could never match mid-line) or had a target that
had moved under it, and each printed a line among two dozen while the run still reported "no
survivors". Both classes are invisible to a green suite. The harness now fails loudly on
both; a test suite has no equivalent guard, and that is the open problem this row leaves.

**Two cycles marked AC 7 `met-with-evidence` and the evidence was true.** No cursor-up
sequence appeared anywhere in the byte stream, and none did - while every paragraph longer
than the window was being drawn on screen twice. The promise was a *proxy* for the criterion
and it was the wrong proxy. `tests/screen.py` - a terminal small enough to reason about -
is what a criterion about the screen has to be measured against, and it is the most reusable
thing this row produced.

**All six came out of the first manual pass**, 2026-08-27, and that is the point worth keeping.
The suite was 440 green and hermetic, six loops had each survived a hostile cold read, and one
evening of a person actually using axiom found six more things. Four of them are shapes no test
could have produced:

- **#57 is a plain bug**, and the most likely of all of these to have already bitten someone:
  the one file axiom asks a user to hand-write cannot be read if Windows' own default tooling
  wrote it. Every test writes config with Python's encoding, which never emits a byte order
  mark, so the stubs and the world disagreed about what a file looks like.
- **#55 and #56 are criteria that were satisfied exactly as written and still left a hole.**
  #48 AC 30 announces a folder, so a project that already has `.axiom/mcp.json` gets a file
  written into it silently forever. #49 AC 16 promises a tool count, so the switch line drops
  the web state and the debug-override note - and a forced context then reads as the model's
  own.
- **#61 and #62 are things nobody thought to ask.** Seven built-in tools cost 653 tokens and
  the standing prompt 154, and that 807 is only ever reported when an MCP server happens to be
  attached - so a 2000-token window was 40% spent before a word was typed, invisibly. And the
  summary, which has a hard bound, spent one of its slots on "RPG stands for role-playing
  game".

Rows 11 to 15 are ordered smallest blast radius first. #57 touches only how two files are
decoded. #55, #56 and #61 all change lines in `terminal.py` and are sequenced so they do not
argue over the same output. #62 reaches into the summariser #32 settled. **#60 is last** because
it is the largest, adds the first new dependency since #43, and rewrites what every reply looks
like - and if the fail-safe takes it, the five small ones are already merged.

**Manual testing is not finished.** #52, #49, #48 and #43 passed; #42 is half done; **#41, #34,
#40, #35 and #26 were never reached** - tools doing real work, the web, and the basics. See
[`../handoff.md`](../handoff.md). Two findings are recorded there and in no issue, deliberately:
a model **fabricating tool results** (it invented the contents of a file the tool never read),
and compaction **corrupting** a detail rather than dropping it ("ventured" became "Vented").
Both belong to a **system prompt story that has not been written**, and Kaushik's ruling stands
that axiom must not try to detect or challenge an unsupported answer - that builds smarts that
cannot be kept consistent.

**Rows 9 and 10 ran back to back on 2026-08-27**, the first two under the no-cron rule, and
**the cold read found real defects in both** - six for six across #40, #41, #42, #43, #48, #49.
Two of this pair's findings were a new shape worth naming: not a bug in the code but a
**criterion read too loosely by the cycle that implemented it**, with a test written from the
implementation rather than from the issue text. #48 AC 33 and #49 AC 25 and AC 27 were all that.
Reading the criteria from GitHub *first* is what caught them; nothing in the diff looked wrong.

**#48 before #49, and the order is structural rather than a preference.** #49 AC 2 requires
the switch list to match the startup list - same contents, same order, same numbering - and
#49 AC 20 requires a switch to be remembered "the same way a startup choice is". Both of
those are #48's to build. Running #49 first would mean inventing the list and the
remembered-choice file inside the switch story, then having #48 rewrite them.

**Listing models belongs behind `ModelBackend`, like every other thing Ollama is asked.**
`backend.py` is the only module under `src/` that imports a vendor client, and both rows
need a new question - what is installed on this host. It goes on the protocol next to
`model_info` and `supports_tools`, so the test stubs can answer it and **the suite stays
green with no Ollama running**. A loop that reaches for `ollama.Client` from `__init__.py`
to get the list has broken #33 and will make every criterion here untestable. This is the
shortcut both rows will be tempted by, because the list is wanted before the backend is
otherwise built.

**The remembered choice is a new file in the user's directory, and it is not
`.axiom/mcp.json`.** `.gitignore` has no `.axiom/` entry today, and it should not gain a
blanket one - `mcp.json` is designed to be committed, which is what the `${NAME}`
substitution is for. Ignore the remembered-choice file specifically, and leave `mcp.json`
alone.

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
2. Mark its row **done** here, with the PR number, the cycle count, and the wall-clock time
   it took. If it hit its fail-safe, say so and link the follow-up issue it opened.
3. Take the next `queued` row. If there is none, stop and say the queue is empty.
4. Scaffold `.claude/loop/{slug}/iteration-1/` by copying
   `C:/Projects/APEX/plugins/ai-engineering/skills/auto-iterate/template`, then delete the
   `artifact/` directory it brings - the code is not the loop's artifact folder.
5. Write that iteration's `goal.md`, `observe.md`, `assumption.md`, `action.md` and
   `loop.md`, reading the issue with `gh issue view` for the criteria. Carry forward
   anything in **Standing** below that applies. Record the fail-safe as a **clock time** -
   four hours from now, written out - not as a number of cycles.
6. Create the branch `feature/{slug}` from `master`, and commit the scaffold.
7. Mark the new row **running** here, with the time it started and its fail-safe clock time.
8. Say in the handover which loop just started and what its first cycle will do.

**There is one cron for the whole queue, not one per row.** It reads *this file* for whichever
row says `running`, so a handover needs no cron work at all - marking the next row `running` in
step 7 is what redirects it. **Do not delete it between rows.** Deleting it on a handover would
end the chain silently with every remaining row still queued, which is the exact failure the
one-cron design removes.

**The queue is now empty, and the cron was still not deleted.** It fires, reads this file,
finds no row marked `running`, and stops - which costs one firing and nothing else. It was
left alone on purpose: the rule above is what keeps the chain alive across fifteen handovers,
and a loop deleting the queue's own scheduler on the way out is the one action that cannot be
undone by the next run. Stopping it is Kaushik's call. A cycle that fires into an empty queue
should say so and exit, not scaffold a row nobody asked for.

## Standing

These apply to every loop in this queue and do not need rediscovering.

- **15-minute cycles, four-hour fail-safe per story.** One cycle per firing, on a cron. A
  hung run costs one firing and the next fires anyway, which is the reason to prefer a
  schedule over running back to back - rows 9 and 10 ran back to back and a hung cycle there
  would have held the whole chain. The fail-safe is **wall-clock time on the row**: four
  hours from its first cycle, however many firings fit, written into that iteration's
  `loop.md` as a clock time rather than a count. A cycle that finds the clock spent takes the
  row's fail-safe exit and hands over to the next row.
- **A loop never waits for an answer.** The queue runs unattended, one loop after another,
  and nobody is watching between cycles. A cycle that stops to ask a question does not
  pause - it holds the chain against a clock that keeps running, and takes the loops queued
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
- **The chain is session-only, and now more so than under cron.** Back-to-back cycles run
  inside the session, so when it ends the chain ends with it - there is no scheduler left
  behind to fire again. The files and commits survive. Restarting means reading this queue
  for whichever row says `running`, reading that iteration's `loop.md` for the fail-safe
  clock time already written there, and carrying on from the last cycle log. Do not restart
  the fail-safe clock on resume; it is wall-clock time on the story, not on the session.
