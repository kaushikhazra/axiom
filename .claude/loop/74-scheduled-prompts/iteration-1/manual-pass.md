# #74 — the manual pass

**Cycle 7 recorded 33 of 33 and ended the loop. The tests cite 31.** `cited.py`, which row 18
wrote and row 19 inherited, reads the criteria a test file actually claims on the first line of
its docstring:

    uv run --no-sync python .claude/loop/cited.py tests/test_schedule.py
    uv run --no-sync python .claude/loop/cited.py tests/test_schedule_tools.py
    uv run --no-sync python .claude/loop/cited.py tests/test_scheduled_input.py
    uv run --no-sync python .claude/loop/cited.py tests/test_scheduled_session.py
    uv run --no-sync python .claude/loop/cited.py tests/test_scheduled_turns.py

Union: 1, 3–9, 11–33. **AC 2 and AC 10 are cited by nothing, in any file.**

Neither is an oversight the loop hid. Both were reasoned, in writing, and the reasoning is
sound — which is exactly why neither got a test:

- **AC 10** — *a job never interrupts a turn in progress.* Cycle 1: "comes free." Cycle 3:
  "structural, not defended — one call site at the top of the loop." Cycle 7: "no test could
  find an interleaving to complain about." True, and `_next_line` really is called in one
  place. But `observe.md` named AC 10 as one of **the three that will be got wrong**, and it is
  the one criterion in this issue that the loop answered by argument rather than by evidence.
- **AC 2** — *available in any session, with nothing to configure first.* Recorded met in
  cycle 4 among thirteen others. Nothing tests it.

**A person settles both in about ninety seconds**, which is the cheapest evidence in this
issue.

## The thing this whole issue turns on, and no test has ever seen it

**Every test injects a fake clock.** That is the right call — `observe.md` forbade sleeping, and
a suite that waits for a minute to pass is a suite nobody runs. The consequence is that
**nothing has ever watched a real minute arrive**: not `SCHEDULE_TICK`, not the reader thread,
not `croniter` resolving against a real `datetime.now`, and not the three of them together.

A job firing on a real minute boundary is the feature. Run it as `axiom` in a normal terminal
and watch one fire.

## What a person has to look at

| AC | What to do | What should happen |
|---|---|---|
| 2 | A fresh run with nothing in `.axiom/` — ask for a repeating prompt | It schedules. Nothing had to be set up first |
| 3 | "every minute, tell me the time" | Says what was scheduled and when it next runs |
| 4 | "at 4:20pm today, say hello" | Scheduled once, with the time said back |
| 5 | Both of the above | Each came back with an identifier you can read |
| 6 | Read the confirmation against your own clock | The time is local. You were not asked to convert anything |
| 7 | The **first** job of the session | You are told schedules last only as long as the session |
| 8 | A repeating job | You are told it stops after seven days |
| 9 | Sit and wait for the minute | The prompt runs on its own, and the reply appears |
| **10** | Schedule one minute out, then ask something long enough to still be streaming when it fires | The job **waits**. It does not cut into the reply |
| 11 | Two jobs due in the same minute | One runs, then the other. Not interleaved |
| 12 | After a job has run, ask the model about what it just said | It is in the conversation, like any other turn |
| 13 | Look at the scheduled turn on screen | Marked as scheduled, in axiom's voice, and you can see the prompt you never typed |
| 14 | Ask for the list | Every job: identifier, schedule, prompt, whether it repeats, next run |
| 16 | Cancel by identifier | Confirmed, and nothing further runs from it |
| 17 | Cancel an identifier you invented | Says there is no such job. Nothing else changes |
| 22 | With a job scheduled, look in `.axiom/` | Only `mcp.json`, `model.json` and `skills/` — the three things that were already there. Nothing schedule-shaped, anywhere |
| 23 | Leave, start again, ask for the list | Nothing scheduled |
| 24 | `/model` mid-session with a job scheduled, then list | The same job. Not cancelled, not doubled |
| 25 | Ask for a schedule that is not five fields | Refused, and the refusal says what was wrong with it |
| 27 | Ask for a one-shot at a time that has gone today | Refused, and says it has passed |
| 33 | `/exit` with jobs scheduled | Exits at once. No wait, no extra prompt |

## Three things to watch that are not criteria

**Typing at a timed prompt.** With something scheduled, `read_line` is re-entered every 0.25s
and the prompt is drawn by `_next_line` rather than by the reader. Does typing feel the same as
an empty-schedule session — no dropped characters at a tick boundary, no second `>` appearing?
Nothing about this is in #74's criteria and nothing tests it.

**The prompt take-back.** `take_back_prompt` erases the drawn `>` before `scheduled - ...`
prints, so a fired job does not read as `> axiom: scheduled - ...`. A test measures the bytes
axiom emits; only a person sees whether the line lands clean on a real terminal.

**Multi-line is off while anything is scheduled.** That is
[#83](https://github.com/kaushikhazra/axiom/issues/83), already filed, and it is why this pass
cannot share a session with #80's. Schedule something and #80's fifteen rows are unreachable.
**Do #80 first.**

## The one a person cannot check, and should not try

**AC 21 — a repeating job seven days old runs one final time and is then removed.** Nobody sits
for seven days. It is proved with a fake clock and that is the only way it can be proved. Leave
it to the test.

## The model has to aim, and that is part of what is being tested

Every one of AC 3, 4, 5, 14, 16 and 17 reaches the scheduler **through the model** choosing
`schedule_prompt`, `list_schedules` or `cancel_schedule` and emitting a valid five-field cron.
A test hands the tool its arguments directly; a person finds out whether a 9B model turns
"every minute" into `* * * * *`.

**When a row fails, say which half failed.** A refusal that reads
`error: a schedule has five fields ... and this has 6` is the scheduler working correctly on a
bad call — that is the model's aim, not #74's behaviour, and it belongs in a note rather than
against the criterion. A row is #74's failure only when the tool got a sane call and did the
wrong thing with it.

---

## What happened - 2026-09-03, part one

**Driven by hand by Kaushik on merged master. Nine rows settled, twelve left.**
The pass stopped for the night part way through, deliberately - not blocked.

### Four rows failed, and the cause was not the scheduler

The first attempt produced this, and nothing else:

> Set! Every minute from now, I'll tell you the time. **The job is scheduled to repeat
> indefinitely for this session.**

`schedule_prompt` had returned the identifier, the next run time, the session warning and
`a repeating job stops after 7 days`. **None of it was on screen.** `show_tool_result`
returned before printing whenever rendering is on at a terminal - #77 AC 26, which took
per-call detail off the screen and left one line counting how many tools ran.

So every #74 criterion of the form *"axiom says X"* was being satisfied by a string that
went to the model and nowhere else, and the user got the model's paraphrase. Here the
paraphrase was **the opposite of the truth**: "indefinitely" against "stops after 7 days".

**The suite could not see it.** #74's tests assert on the tool function's *return value* -
`said = call("schedule_prompt", ...)` - and that value was correct throughout. Two shipped
issues, both green, both individually right.

Filed as [#85](https://github.com/kaushikhazra/axiom/issues/85), built the same evening, and
#77 AC 22, AC 24 and AC 26 are superseded with the reason recorded on #77. The four rows were
re-run against it and all four pass.

### The rows

| AC | Verdict | |
|---|---|---|
| 2 | pass | a fresh session with nothing configured scheduled a job. **One of the two no test cites** |
| 3 | pass | after #85. What was scheduled *and* when it next runs |
| 5 | pass | after #85. `7f91449a`, on screen, where AC 16 needs it |
| 6 | pass | `next at 2026-09-04 00:24 local` - and nothing was truncated at Kaushik's width |
| 7 | pass | after #85 |
| 8 | pass | after #85. This is the one the model got backwards |
| 9 | pass | **the first time anything has watched this on a real clock.** Fired on its own, twice |
| 12 | pass | the job's turn is an ordinary turn and its reply stayed in the conversation |
| 13 | pass | `·  scheduled - What time is it now?`, in axiom's voice |

**AC 19 was seen as well**, though it is on the proved list: the repeating job ran on every
match rather than being consumed by its first run.

**The prompt take-back works on a real terminal.** `_next_line` draws the prompt and
`take_back_prompt()` erases it before the scheduled line prints, so a fired job reads as
`·  scheduled - ...` and not as `> axiom: scheduled - ...`. No test can see this; it is the
same class of thing as #80's continuation marker.

### One defect found that is not #74's

**`run_command` does not close the child's stdin**, so `subprocess.Popen` hands it axiom's
own console. The model asked for `date`, which on Windows prompts for a new date and waits.
It blocked for the full 30 second limit, three times - 90 seconds of one turn - and the model
was told "stopped at the 30 second limit", which reads as *slow* when the truth is *waiting
for input that will never arrive*.

Measured: with a non-console stdin the same command returns in **0.03s**, carrying
`The current date is: 04-09-2026` - the answer the model was after. `stdin=subprocess.DEVNULL`
is the whole fix. It also stops a command competing for the console with axiom's own reader.

Not filed yet - Kaushik's call.

### Still owed - twelve rows

| | |
|---|---|
| **10** | **the one worth the time.** No test cites it, and three cycles called it structural. Force it: schedule a job a minute out, then ask for something slow enough to still be running when it comes due |
| 4, 11 | a one-shot at a named time; two jobs due in the same minute |
| 14, 16, 17 | list; cancel `7f91449a`; cancel an identifier that does not exist |
| 22, 23 | nothing on disk; nothing survives a restart |
| 24 | `/model` mid-session, then list - same job, not duplicated |
| 25, 27 | a schedule that is not five fields; a one-shot at a time that has gone |
| 33 | `/exit` with jobs scheduled, no wait |

---

## What happened - 2026-09-08, part two

**AC 10 is settled, and it passes.** Transcript in `row-10-turn-in-progress.log`.

### The instrument, and why one was needed

AC 10 asks whether a job *waits*, which is a question about ordering, and ordering is
the one thing an eye at a terminal is bad at. `drive.py` types at a real axiom over a
pipe and stamps every line with the moment its first byte arrived.

A piped run normally cannot fire a schedule at all: `_next_line` only looks at the clock
when the timed read returns `WAITING`, and a pipe fed from a file is never empty, so
`due()` is never reached. **Holding the pipe open and writing into it slowly** is what
fixes that - between writes the reader thread is genuinely blocked in `input()`, the
queue times out after `SCHEDULE_TICK`, and the loop consults a real `datetime.now()`
exactly as it does for a person sitting still.

It cannot see the drawing. No tty means no composer and no working `take_back_prompt`,
so how a line *looks* stays a row for a person at a real console.

**`uv run` will not do.** The first run hung with the banner printed and nothing else:
uv does not relay piped stdin to the child, so axiom sat in `input()` forever and ollama
never spawned a runner. `drive.py` launches the project interpreter with
`-c "import axiom; axiom.main()"` instead, resolved from its own location.

### AC 10 - pass

qwen3.5:9b thinks for sixty to ninety seconds before it says anything, which makes this
row easy rather than hard: with `* * * * *` scheduled, **every** turn straddles a minute
boundary.

| | |
|---|---|
| 11:17:17 | a scheduled turn fires. `mark_run` moves it on - due again at 11:18 |
| 11:18:25 | the escapement question is typed |
| 11:18:36 | that turn calls `run_command`. **11:18 has come and gone.** Nothing fires |
| 11:19:06 | still in the turn, through 11:19. Nothing fires |
| 11:20:48 | the reply starts streaming, through 11:20. Nothing fires |
| 11:21:06 to 11:21:56 | five paragraphs stream, through 11:21. Nothing cuts into them |
| 11:21:56 | the reply ends, the prompt is drawn, **and the job runs** |

**Four boundaries came due while a turn was in progress. Not one interrupted.** The
criterion three cycles answered by argument now has evidence.

Two things came free with it. **`mark_run` computing from `now` is observable**: four
missed boundaries produced *one* run at 11:21:56, not a backlog of four - the behaviour
its docstring claims, seen rather than reasoned. And **AC 9 re-confirmed** on a real
clock, twice, at 11:16:00 and 11:17:17 with nothing typed.

### Three things found that are not AC 10

**1. `take_back_prompt` is the one drawing function with no tty guard.** Every scheduled
turn in the transcript reads `[Kaxiom: scheduled - What time is it?`. It prints a bare
carriage return and an erase-line escape unconditionally, while `_prompt`, `_composer`
and the rest all check `_rendering and sys.stdout.isatty()` first. So **anyone
redirecting axiom to a file gets an escape sequence glued to the front of every
scheduled turn**, and the `> ` it meant to erase stays as well. Same class as #85 -
something axiom prints landing wrong - and not filed.

**2. The `run_command` stdin defect, reproduced with both halves in one session.** Same
command, same run, differing only in whether stdin was readable:

| | | |
|---|---|---|
| 11:18:36 | pipe still open | **30.0s**, `error: stopped at the 30 second limit` |
| 11:22:27 | pipe closed | **0.02s**, `The current date is: 08-09-2026` |

`date` on Windows prints the date and then waits for a new one. With a readable stdin it
waits out the whole limit and the model is told the command was *slow*; with EOF it
answers instantly and carries the thing the model asked for. Closing the child's stdin
is still the whole fix, and this is now measured rather than argued. **Still not filed.**

**3. #85 put the truth on screen and the model still garbled it in prose.** The tool
result said `next at 2026-09-08 11:16 local`. The model wrote *"at 01:16 on Sept 8,
2026"*, dropped the seven-day warning it had repeated correctly an hour earlier, and
added *"I don't have direct system access to report the actual time"* while holding
eleven tools. The screen was right throughout - this is the system-prompt half, and it
is not #74's.

**One note on the model's aim, not on #74.** It called `schedule_prompt()` with no
arguments at 11:16:38 and got `error: schedule_prompt was called wrongly -
schedule_prompt() missing 2 required positional arguments`. The scheduler behaved, the
model recovered, and the row is unaffected.

### Both fixes, confirmed in the path they were found in

`row-10-after-the-fixes.log`, same driver, same model, same sandbox.

**The erase.** Three scheduled turns, all reading `axiom: scheduled - what time it
is` on their own row. Not one `[K` in the transcript - the only match in the file is
this checklist's own marker text.

**The stdin.** The model reached for `date` **six** times in one run, in five
different shapes, and **every one returned in under 0.05s**:

    12:42:43  run_command(command=date)
              | The current date is: 08-09-2026
              | Enter the new date: (dd-mm-yy)
              | error: exited with status 1

Not one `stopped at the 30 second limit` in the file. On the old build those six
calls were three minutes of dead turn time. The model also read the result back
correctly for the first time - it quoted the tool's output verbatim in a fenced
block - because there was finally something to quote.

Both were verified the other way too: removing `stdin=DEVNULL` fails the suite with
`error: stopped at the 5 second limit`, and removing the `isatty` guard fails it with
`assert '\x1b' not in '\r\x1b[K'`. Suite 964 passed, 1 deselected, 148s.

**The sweep is clean.** `take_back_prompt` was the only place in `terminal.py`
printing a cursor escape without a guard - `_start_working`, `_stop_working` and
every `Rendered` path sit behind `_rendering and sys.stdout.isatty()` at their call
sites.

### AC 4, AC 5 and AC 14 - pass

`row-04-one-shot.log`. qwen3.5:9b, asked for a one-off at a named time.

    axiom: schedule_prompt(cron=30 14 * * *, prompt=hello, repeating=False)
      | scheduled c1e8ac27: 'hello' on 30 14 * * * (once), next at 2026-09-08 14:30 local
      | schedules last only as long as this session

**AC 4** - once, and the time said back as a time rather than as a cron. **AC 5** -
`c1e8ac27`, on screen, where AC 16 will need it. The aim was right first try:
`30 14 * * *` with `repeating=False` from "14:30 today ... once only".

**AC 14** - the listing carries all five things it owes:

    c1e8ac27: 'hello' on 30 14 * * * (once), next at 2026-09-08 14:30 local

identifier, schedule, prompt, whether it repeats, next run.

**AC 7 came free and is sharper than it was.** The session line appears under the
*first* job of a session and not under the second - `row-11`'s BRAVO gets
`a repeating job stops after 7 days` alone. Once per session, as written.

**A note, not a failure.** The one-shot turn ended with the model saying nothing at
all - tool called, result printed, no prose. The user still learns everything,
because #85 put the three result lines on screen; before #85 this turn would have
told them nothing whatsoever.

### AC 11 - pass, after the first attempt failed to reach it

**The first attempt never tested the criterion.** On qwen3.5:9b, turns ran two to
five minutes, so the session was mid-turn at nearly every boundary and the second
job never got a gap to run in. What that run demonstrated was AC 10 for a third
time - ALPHA's turn covered 13:59:00 to 14:03:46, four boundaries, uninterrupted -
and AC 11 not at all.

Both jobs have to come due, run *and* finish inside one minute for the ordering to
be visible, and that needs seconds-long turns. Re-run on qwen2.5:7b, which has no
thinking phase. That removes a confound rather than dodging the row: what is under
test is which job `due()` hands over first, not how the model writes.

Both were genuinely due in the same minute -

    scheduled d2513b91: 'say ALPHA' on */1 * * * * (repeating), next at 2026-09-08 14:09 local
    scheduled bd2af4d4: 'say BRAVO' on */1 * * * * (repeating), next at 2026-09-08 14:09 local

\- and every boundary from 14:09 to 14:12 read exactly this, four times running:

    >
    axiom: scheduled - say ALPHA
    ALPHA
    >
    axiom: scheduled - say BRAVO
    BRAVO

One whole turn, then the other. **Never a scheduled line inside somebody else's
answer**, and the order held across all four - ALPHA first every time, which is
`due()` sorting by when a job *became* due and a stable sort keeping the older one
in front when the two are equal.

The two turns at 14:09 both landed inside the same second. Two complete turns, one
after the other, in one second - which is the shape AC 11 asks for and the thing a
slow model made unobservable.

**The erase fix is visible here too.** Every `>` sits on its own row above its
scheduled line, with no `[K` in front of it, in a transcript written to a pipe.

**And a second model reads the tool result correctly.** qwen2.5:7b wrote *"A
repeating job will stop after 7 days, but it will continue as long as this session
is active"* - both facts, both right. qwen3.5:9b garbled the same two an hour
earlier. Worth remembering when the system-prompt story is picked up: this is not a
uniform failure across models.

### Where the pass stands after 2026-09-08

**Thirteen of twenty-one rows settled. Eight owed.**

| | |
|---|---|
| settled today | 10, 4, 5, 14, 11 - plus 7 and 9 re-confirmed |
| settled 2026-09-03 | 2, 3, 5, 6, 7, 8, 9, 12, 13 |
| **owed** | **16, 17, 22, 23, 24, 25, 27, 33** |

The eight left are cheap and none of them needs a real minute to pass:

| | |
|---|---|
| 16, 17 | cancel a real identifier; cancel one you invented |
| 22, 23 | nothing schedule-shaped on disk; nothing survives a restart |
| 24 | `/model` mid-session, then list - same job, not doubled |
| 25, 27 | a schedule that is not five fields; a one-shot at a time that has gone |
| 33 | `/exit` with jobs scheduled, no wait |

**Run them on a fast model.** `drive.py <steps> qwen2.5:7b` takes ten-second turns
against qwen3.5:9b's two-to-five minutes, and none of these eight is about how the
model writes. Keep 9B for anything where the *aim* is the question.

**AC 33 needs care.** `/exit` typed mid-turn is not the criterion - the turn finishes
first, which is AC 10 working. AC 33 is `/exit` typed at an idle prompt with jobs
scheduled, and the thing to measure is that it does not wait for the next fire.

**One row cannot be driven from a pipe at all.** The three notes under "Three things
to watch that are not criteria" - typing at a timed prompt, the prompt take-back on a
real console, and #83 - all need a real terminal. `drive.py` has no tty and says so.

### The last eight rows - all on qwen2.5:7b

**Six pass outright. Two are right but cannot be reached through a model, which
is the finding.**

**AC 22 - pass.** `row-16-refuse-cancel-disk.log`. With `a30bf385` scheduled and
firing every minute, `.axiom/` held `mcp.json.bak`, `mcp.json.off`, `model.json` -
the three that were there before. Nothing schedule-shaped, anywhere. Looked at
*during* the session by a new `inspect:` step, because looked at afterwards it
proves nothing: the schedule is gone by then and so is the question.

**AC 17 - pass.** `cancel_schedule(identifier=deadbeef)` returned
`error: there is no scheduled job 'deadbeef'`, and the listing a moment later
still held both real jobs. Told, and nothing else changed.

**AC 16 - pass.** `cancelled a30bf385: 'say TICK'`. TICK had fired at 14:23:04 and
14:24:00; from 14:24:19 to 14:26:53 - **two more boundaries** - nothing fired at
all. Confirmed, and nothing further ran from it.

**AC 24 - pass, and the behaviour is better evidence than the listing.**
`row-24-switch-and-leave.log`. `6a964647` scheduled, then `/model
qwen2.5-coder:7b` mid-session. The job fired at 14:33:00 and again at 14:34:00 -
**once each minute, across the switch**. Not cancelled, and not doubled, which a
listing can only assert and a firing job demonstrates.

Worth knowing: the listing *after* the switch was the model reciting the earlier
tool output from conversation history - it never called `list_schedules` and it
repeated a stale `next at 14:32`. The row stands on the firing, not on that.

**AC 33 - pass, measured.** `/exit` typed at an idle prompt with `6a964647` still
scheduled: typed at 213.03s, exit status 0 at 213.42s. **0.39 seconds**, and that
includes this script closing the pipe and reaping the process. It did not wait for
the 14:35 fire, and there was no extra prompt.

**AC 23 - pass.** `row-23-nothing-survives.log`, a fresh child started after the
session above had left. `list_schedules()` returned `nothing is scheduled`, and
`.axiom/` still held only its three original files. The previous session had been
firing a job once a minute right up to the moment it exited.

### AC 25 and AC 27 - the strings are right, the path is unreachable

Both refusals are exactly what the criteria ask for:

    error: a schedule has five fields - minute hour day-of-month month day-of-week - and this has 6
    error: '0 9 8 9 *' names 09:00 on 08 September, which has already passed - the next one is 2027-09-08

**But three live attempts could not get a bad expression as far as the tool**, and
each failed differently:

| asked for | the model did |
|---|---|
| `0 */5 * * * *`, verbatim, unchanged | refused to relay it - *"let's correct the cron expression"* - and never called the tool |
| `0 9 8 9 *`, verbatim, one-shot | substituted `0 9 15 9 *`, *"to ensure the prompt runs at a future date"* |
| "every 30 seconds" | emitted `*/1 * * * *` - a valid five-field expression - and then said it had scheduled something *"every 30 seconds"* |
| "09:00 on 8 September 2026", told not to move it | emitted `0 9 8 9 2026`, caught by the *other* guard: `'0 9 8 9 2026' is not a schedule croniter understands` |

A model that knows cron sanitises before the tool sees anything. So the five-field
refusal and the already-passed refusal are correct, tested, and in practice reached
only by a model that is wrong in a way this one is not. That is worth knowing
before anyone spends effort improving the wording of a string a user will rarely
meet.

The boundary in `LOOKS_LIKE_A_YEAR` behaves as its comment claims, checked the same
way: `0 9 1 8 *` in September is 327 days out and refused, `0 9 1 3 *` is 174 days
out and taken - because a March date asked in September is next March, not a
mistake.

### The misreporting, a third time

`schedule_prompt(cron=*/1 * * * *, ...)` on screen, and the model's sentence
underneath: *"A repeating prompt has been scheduled to say FAST every 30 seconds."*
Axiom said `*/1 * * * *` and `next at 2026-09-08 14:29`. Both were on screen and
both were right. This is now three models, three separate turns, and the same
shape every time: the tool result is correct, visible since #85, and the sentence
below it is not.

---

## The pass is complete - 2026-09-08

**All twenty-one rows are driven. This supersedes the owed list above.**

| | |
|---|---|
| pass, 2026-09-03 | 2, 3, 5, 6, 7, 8, 9, 12, 13 |
| pass, 2026-09-08 | 4, 5, 10, 11, 14, 16, 17, 22, 23, 24, 33 - and 7, 9 re-confirmed |
| right, but unreachable through a model | 25, 27 |
| left to the fake clock, correctly | 21 |

**Nothing in #74 was found broken.** The two defects this pass turned up belong to
other code - `run_command` inheriting stdin, and `take_back_prompt` printing a
cursor escape into a file - and both are fixed, tested, and confirmed live.

### What the pass was actually for

AC 10 was the row worth the time and it says so in the record: cycles 1, 3 and 7 all
called it structural and free, `observe.md` named it as one of the three that would
be got wrong, and it was the one criterion the loop settled by argument. It is now
settled by a transcript - four minute boundaries came due inside a single turn and
not one interrupted.

The two things that came free with it are the ones no test asked for. `mark_run`
computing from `now` rather than from the due time is **observable**: four missed
boundaries produced one run, not a backlog of four. And AC 11's ordering held across
four consecutive boundaries with the older job in front every time.

### What is still owed to #74, and it is not a row

**Three of these notes are not criteria and still need a real console.** `drive.py`
has no tty and says so: typing at a timed prompt, the prompt take-back as an eye
sees it, and [#83](https://github.com/kaushikhazra/axiom/issues/83). A pipe cannot
answer any of them.

**The model's account of a tool result is wrong often enough to be a pattern.**
Three models, four turns, the same shape: `next at 11:16` read back as *"01:16"*,
`*/1 * * * *` read back as *"every 30 seconds"*, a seven-day warning dropped, and a
model claiming no system access while holding eleven tools. #85 put the truth on
screen and it stayed there every time. The remaining half is what the model is told
about what it just did, and it is not #74's.

**The refusals are effectively unreachable.** A model that knows cron corrects a bad
expression before the tool sees it, so AC 25's and AC 27's messages - both correct -
are met mainly by a model wrong in a way these are not.
