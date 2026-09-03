# Handoff — every branch is merged, #80 is verified, #74 is half done

Rewritten 2026-09-04 at the end of a session that consolidated the repo, drove #80's manual
pass to completion, and got half way through #74's before stopping for the night. Nothing is
scheduled and nothing is running.

## Where things stand

`master` is green and **pushed through PR #84**, plus two merges made after it: **960 passed,
1 deselected, ~107s**. `tests/baseline/transcript.txt` has not moved.

**There are no unmerged branches.** That is new. The five that were outstanding yesterday are
all in.

| | |
|---|---|
| [#80](https://github.com/kaushikhazra/axiom/issues/80) | merged, **manual pass complete** — 14 rows, one real defect found and fixed |
| [#81](https://github.com/kaushikhazra/axiom/issues/81) | merged, row 1 of its pass taken; **rows 2–5 owed** |
| [#74](https://github.com/kaushikhazra/axiom/issues/74) | merged, **9 rows of 21 done**, 12 owed |
| [#85](https://github.com/kaushikhazra/axiom/issues/85) | new today, built and merged, **not yet manually passed** |

## Start here tomorrow

```
cd C:\Projects\.tmp\axiom-manual
uv run --project C:/Projects/axiom axiom
```

**`--project`, not `--directory`.** `--directory` moves the working directory into the repo,
which CLAUDE.md's tool-testing rule forbids.

`.axiom/mcp.json` is parked as `mcp.json.off` so nothing attaches at startup and the model is
not juggling three remote tools during a pass. Rename it back for #81's rows.

**The next row is #74 AC 10**, and it is the one worth the time. *A job never interrupts a turn
in progress.* No test cites it; cycles 1, 3 and 7 all called it structural and free. There is
now a clean way to force it — schedule a job a minute out, then ask for something slow enough
to still be running when it comes due. The full list of the twelve remaining is at the bottom
of `.claude/loop/74-scheduled-prompts/iteration-1/manual-pass.md`.

## What happened today

**1. Everything merged, in order, each branch tested before it went the other way.** Master
took #80 then #81, each merged *into* its branch first and the suite run there, so a broken
master never existed. No code conflicted — `terminal.py` took #76 in the renderer half and #80
in the reader half; #81 is `config.py` and `servers.py`. Every conflict was the loop's own
bookkeeping meeting itself at three different ages.

| | tests | wall clock |
|---|---|---|
| master, before | 892 | 94.3s |
| \+ #80 | 923 | 95.1s |
| \+ #81 | 959 | 154.7s |
| \+ #80's fix | 960 | 126.6s |
| \+ #85 | 960 | 107.3s |

**2. #80's manual pass found the criterion it was written for.** Ctrl+enter **sent the
message** — AC 2, on the first row that needed a second line.

prompt_toolkit has two Windows readers and `Win32Input.__init__` picks between them on
`_is_win_vt100_input_enabled()`, which asks only whether the console *accepts*
`ENABLE_VIRTUAL_TERMINAL_INPUT` — true on every modern console, conhost included.
`ConsoleInputReader` delivers ctrl+enter as `escape, c-j`; `Vt100ConsoleInputReader` delivers a
bare `c-j`. Only the pair was bound, so the bare key fell through to prompt_toolkit's own `c-j`
default — `feed(KeyPress(ControlM, "\r"))` — and hit the send binding.

**No test could have caught it, and `compose`'s docstring said so before it shipped**: tests
feed keys through `create_pipe_input`, which proves what axiom does *given* a key. `tests/whatkey.py`
is the instrument that found it — it names the reader in use and prints what each key produces.
**AC 6 is untouched**: this console reports `ControlJ` against `ControlM`, so it separates them
perfectly well.

All fourteen rows now pass, and four criteria on the *proved* list — AC 5, 11, 19, 23 — were
seen on a screen for the first time. **AC 27's vacuous test is answered.**

**3. #74's pass found a collision between two shipped issues.** A model scheduled a repeating
job and said it would *"repeat indefinitely"*. The tool result in front of it said `a repeating
job stops after 7 days`. #77 AC 26 had taken tool output off the screen, so that string went to
the model and nowhere else.

Every #74 criterion of the form *"axiom says X"* — AC 3, 5, 7, 8 — was being satisfied by a
string the user never sees. **Both issues were green.** #74's tests assert on the tool
function's return value, which was correct throughout.

**4. #85 was written, built and merged the same evening**, and the four rows re-run against it
all pass. It draws the call and its result:

```
·  schedule_prompt(cron=*/1 * * * *, prompt=What time is it now?, repeating=True)
·  scheduled 7f91449a: 'What time is it now?' on */1 * * * * (repeating), next at …
·  schedules last only as long as this session
·  a repeating job stops after 7 days
```

Three rows of a result, not one — one was the obvious reading and it was wrong, because
`schedule_prompt` answers in three lines and flattening them cuts off exactly the two the model
got wrong. **#77 AC 22, AC 24 and AC 26 are superseded**, recorded as a comment on #77, and
five tests were rewritten in place carrying why. One now asserts the exact inverse of what it
used to.

## One defect found and not yet filed

**`run_command` never closes the child's stdin.** `subprocess.Popen` is called without a
`stdin=` argument, so the child inherits axiom's console. The model asked for `date`, which on
Windows prompts for a new date and waits — it blocked for the full 30 second limit, three
times, 90 seconds of one turn. The model was told "stopped at the 30 second limit", which reads
as *slow* when the truth is *waiting for input that will never arrive*.

Measured: with a non-console stdin the same command returns in **0.03s** carrying `The current
date is: 04-09-2026`, which is the answer it wanted. `stdin=subprocess.DEVNULL` is the whole
fix, and it also stops a command competing for the console with axiom's own reader.

**No issue exists for it.** Kaushik's call.

## Still owed

| | |
|---|---|
| **#74** | 12 rows. AC 10 first — see above |
| **#85** | its own manual pass. Two open judgements: is `×` distinct enough from `·` at a glance, and is four rows per tool too dense? |
| **#81** | rows 2–5: slow connection, dropped mid-call, certificate or proxy, nothing left connected on exit |

## Two things that are not built, and are worth knowing why

**Google and Slack cannot exist yet.** All four publish remote MCP servers and every one is
OAuth; `ServerSpec` carries `command`, `args`, `env`, `tools` and `address` — no headers, no
token, no browser flow. [#82](https://github.com/kaushikhazra/axiom/issues/82) unblocks all
four. Not started.

**There is still no permission gate.** `run_command` runs whatever the model asks with no list
of allowed programs, and `outside()` is visibility only. Today gave a live example of why it
matters: asked to paste a traceback, the model improvised two `read_file` calls nobody
requested. Harmless because the working directory was the sandbox — which is the protection
CLAUDE.md's rule provides and a stranger following the README does not have. **No issue exists
for it.** #82 would store account access on top of it, so the order of those two is a real
decision.

## Rules that must not be forgotten

**No test builds a `prompt_toolkit` session** — not a `PromptSession`, not a
`create_pipe_input`, not a key processor. Nineteen did and took this machine down twice.
`tests/whatkey.py` is allowed because it uses the key *parser* only, and its docstring says it
must not become a test.

**Break a criterion before claiming it.** Both defects today were found by a person looking at
a screen; both suites were green through the whole thing. Today's fix was verified by removing
the bare `c-j` binding and watching one test go red while the other thirty-one stayed green —
which is precisely how it shipped.

**Commit before you break.** A break undone with `git checkout --` takes uncommitted work with
it, which happened once today and cost a re-apply.
