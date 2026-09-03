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
