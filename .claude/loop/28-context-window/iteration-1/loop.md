# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Code under test:     C:/Projects/axiom/src/   (+ tests in C:/Projects/axiom/tests/)

ONE cycle, every time this file is read:
  - Action:  work on C:/Projects/axiom/src/, as action.md asks
  - Observe: check it against the goal, using observe.md
  - If goal met:       report the result. Do not schedule another tick.
  - If fail-safe due:  stop, state why it did not converge. Do not schedule another tick.
  - If goal not met:   write the next action.md, THEN schedule the next tick
                       (see below), then exit this run.

Fail-safe: 2026-08-24 13:41 IST. If that time has passed when this file is
read, stop and state why it did not converge — do not run another cycle,
even if a tick fired late.
```

**Scheduling is self-relay, not a standing cron.** There is no recurring job behind this loop. A standing wall-clock cron (`*/15 * * * *` or similar) only fires on fixed minute slots — the first tick after creation can be anywhere from 1 to 15 minutes out, never a true "15 minutes from now." So instead: **the last thing a cycle does, if the loop continues, is call `CronCreate` for a single one-shot job at (now + 15 minutes), `recurring: false`, with this exact prompt:**

`Read C:/Projects/axiom/.claude/loop/28-context-window/iteration-1/loop.md and run one iteration.`

Compute the actual date/time first (a `date` call), add 15 minutes, and pin the one-shot `cron` field to that minute/hour/day/month. Each cycle relays to the next — this is the chain the IOT-style pattern relies on: genuinely spaced ticks, no wall-clock alignment, and the tool's own built-in jitter (not a hand-picked offset minute) is what keeps ticks from clustering.

If the goal is met or the fail-safe has passed, **do not create a successor** — that is how the loop stops. There is deliberately no cron left running afterward to delete.

**The artifact lives outside this folder.** The code is the repo's real source at `C:/Projects/axiom/src/`, not a copy under `iteration-1/`. There is no `artifact/` directory here, deliberately — do not create one, and do not write code anywhere but `src/` and `tests/`.

The loop's own files stay in this folder. Everything else it produces is repo source.

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions — if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state at that cycle and are never edited afterwards.**

`src/axiom/__init__.py` already exists — this iteration extends it, it does not regenerate it. Cycle 1 reads it first, records where it stands against this goal, and edits from there.

**First run: 2026-08-24 11:41 IST. Fail-safe deadline: 2026-08-24 13:41 IST.**
