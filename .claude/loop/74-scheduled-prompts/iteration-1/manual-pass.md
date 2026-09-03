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
