# Handoff — #74 and #85 are both manually passed, and PR #88 is open

Rewritten 2026-09-08 at the end of a session that finished #74's manual pass, fixed the
two defects it found, and settled #85's. Nothing is scheduled and nothing is running.

## Where things stand

`master` is unchanged since PR #86. Everything from today sits on
**[PR #88](https://github.com/kaushikhazra/axiom/pull/88)**, branch
`release/74-manual-pass`, at **964 passed, 1 deselected, ~140s**.
`tests/baseline/transcript.txt` has not moved.

| | |
|---|---|
| [#74](https://github.com/kaushikhazra/axiom/issues/74) | **manual pass complete** — 21 rows, nothing in #74 found broken |
| [#85](https://github.com/kaushikhazra/axiom/issues/85) | **manual pass complete** — 29 of 30 pass, AC 19 accepted |
| [#80](https://github.com/kaushikhazra/axiom/issues/80) | complete since 2026-09-03 |
| [#81](https://github.com/kaushikhazra/axiom/issues/81) | **rows 2–5 deferred by decision** — see below |

**Merge PR #88 first.** It carries both fixes, and everything else assumes them.

## Start here tomorrow

There is no owed row. The next move is a new issue, not a continuation.

The two things closest to the surface, both already argued for in this repo and
neither filed:

**A permission gate.** `run_command` still runs whatever the model asks with no list
of allowed programs, and `outside()` is visibility only. Today gave three more live
examples: a model improvised `date` six times unasked, and reached for
`bash -c`, `/bin/date` and `date 2>&1 | head -5` when the first shapes failed. All
harmless because the working directory was a sandbox — which is the protection
CLAUDE.md's rule provides and a stranger following the README does not have.
[#82](https://github.com/kaushikhazra/axiom/issues/82) would store account access on
top of this, so the order of the two is a real decision.

**What the model is told about what it just did.** See "the pattern that is now
undeniable" below.

## What happened today

**1. #74's manual pass, finished — all 21 rows.** Twelve were owed; all twelve driven.
Full record with a transcript per row in
`.claude/loop/74-scheduled-prompts/iteration-1/manual-pass.md`.

**AC 10 was the row worth the time**, and it is why the pass existed. *A job never
interrupts a turn in progress.* Cycles 1, 3 and 7 all called it structural and free,
`observe.md` named it as one of the three that would be got wrong, and it was the one
criterion the loop settled by argument. Four minute boundaries came due inside a single
turn and not one interrupted.

Two things came free that no test asked for. **`mark_run` computing from `now` is
observable** — four missed boundaries produced one run, not a backlog of four. And
AC 11's ordering held across four consecutive boundaries with the older job in front
every time.

**Nothing in #74 was found broken.**

**2. The instrument, which is reusable.**
`.claude/loop/74-scheduled-prompts/iteration-1/drive.py` types at a real axiom over a
**held-open pipe** and stamps every line with the moment its first byte arrived.

Holding the pipe open is the whole trick: a pipe fed from a file is never empty, so
the timed read never returns `WAITING` and `due()` is never reached. Writing into it
slowly leaves the reader genuinely blocked in `input()`, and the loop consults a real
clock exactly as it does for a person sitting still.

    drive.py <steps-file> [model]

Two things it taught, both cheap to forget:

- **`uv run` will not host it.** uv does not relay piped stdin, so the first attempt
  hung with the banner printed and ollama never spawning a runner. It launches the
  project interpreter with `-c "import axiom; axiom.main()"` instead.
- **It has no tty and says so.** The drawing, the composer and `take_back_prompt` as
  an eye sees them are unreachable from a pipe, and always will be.

**3. Two defects found, fixed, and verified both ways.** Neither is #74's.

**`run_command` inherited axiom's stdin.** A command that reads a line then waits is
waiting on a console nobody is typing at. `date` on Windows prints the date and *then*
asks for a new one — ninety seconds of one turn across three calls, and the model was
told the command had been **slow** when what it had been was **blocked**. Measured both
ways in one session: **30.0s** and a timeout against **0.02s** and
`The current date is: 08-09-2026`. `stdin=subprocess.DEVNULL`.

**`take_back_prompt` was the only drawing function with no `isatty` guard.** Redirected,
its cursor escape is four bytes of rubbish — every scheduled turn read
`[Kaxiom: scheduled - ...` with the `> ` it meant to erase still there. It emits a
newline instead. **The sweep is clean**: every other escape in `terminal.py` sits behind
`_rendering and sys.stdout.isatty()` at its call site.

**One test had to be rewritten because it passed against the bug.** pytest already
points fd 0 at nothing, so a child inheriting it also saw end-of-input. It now `dup2`s a
pipe with the write end held open onto fd 0 — readable, never answered, which is what a
console with nobody typing at it is.

**4. #85's pass, settled without the checklist that was written for it.** A fifteen-row
plan was thrown away, and the reasoning generalises: **#74's pass had already left 36
captured tool calls across five tools**, gathered for a different issue and answering
most of this one, because every one of them is a call line and a result line drawn by
the code under test.

What a transcript cannot reach is the drawing, and that is one screen rather than
fifteen turns — `.claude/loop/85-tool-lines/sample.py`, no model and no waiting.

Both open judgements from the last handoff are closed. Shown the sample screen,
Kaushik: *"all the rows looks very cool to me."*

**AC 19 fails below about ninety columns and that is accepted**, with the reasoning in
`_tool_row`'s docstring so nobody re-opens it. `schedule_prompt`'s first result row
carries the prompt inside it, so its length moves with what was scheduled: whole at 100
columns, ` local` gone at 90, date cut mid-way at 80. Both fixes cost more than the
loss.

## The pattern that is now undeniable

**The model's account of a tool result is wrong often enough to be the next issue.**
Four turns today, three different models, and #85 had the truth on screen every time:

| the tool said | the model said |
|---|---|
| `next at 2026-09-08 11:16 local` | *"at 01:16 on Sept 8, 2026"* |
| `*/1 * * * *` | *"scheduled to say FAST every 30 seconds"* |
| `a repeating job stops after 7 days` | dropped it entirely, having repeated it correctly an hour earlier |
| eleven tools offered | *"I don't have direct system access to report the actual time"* |

**It is not uniform across models**, which is the useful part: qwen2.5:7b wrote *"A
repeating job will stop after 7 days, but it will continue as long as this session is
active"* — both facts, both right — where qwen3.5:9b garbled the same two an hour
earlier. So this is a system-prompt problem with a measurable target, not a fact of
small models.

#85 fixed the half where the user could not see. The half where the *model* is told
what it just did is untouched and unfiled.

## Still owed, and one thing deliberately not

**#81 rows 2–5 are deferred, not owed.** Kaushik's call, 2026-09-08: *"we pass for now,
we will see if slow connect causes issues or not."* Slow connection, dropped mid-call,
certificate or proxy, nothing left connected on exit — all wait for a real symptom
rather than a rehearsed one. **Do not pick these up as outstanding work.**

**Three notes need a real console and cannot be driven from a pipe.** Typing at a timed
prompt with something scheduled; the prompt take-back as an eye sees it; and
[#83](https://github.com/kaushikhazra/axiom/issues/83), multi-line being off while
anything is scheduled. `drive.py` has no tty.

**Google and Slack still cannot exist.** All four publish remote MCP servers and every
one is OAuth; `ServerSpec` carries `command`, `args`, `env`, `tools` and `address` — no
headers, no token, no browser flow. [#82](https://github.com/kaushikhazra/axiom/issues/82)
unblocks all four. Not started.

## Rules that must not be forgotten

**No test builds a `prompt_toolkit` session** — not a `PromptSession`, not a
`create_pipe_input`, not a key processor. Nineteen did and took this machine down twice.
`tests/whatkey.py` is allowed because it uses the key *parser* only, and its docstring
says it must not become a test.

**Break a criterion before claiming it.** Both of today's fixes were verified by removing
them and watching the right test go red — and the stdin test only became real *because*
that check showed it passing against the bug.

**Commit before you break.** A break undone with `git checkout --` takes uncommitted work
with it.

**Watch the wall clock, not just the green.** Today's suite runs at ~140s against the
last handoff's 107s. Checked with `--durations`: the slowest fifteen are all pre-existing
MCP subprocess tests and none of today's four appear, so it is machine state. Worth
re-checking on a quiet machine.
