# Cycle 1 — 2026-08-28 18:47 +0530

Designed the seam, proved the clock, built the store. No tools and no REPL wiring, as
`action.md` required.

## The constraint everything else now depends on

**`terminal.read_line()` is a blocking `input(PROMPT)`.** The chat loop in
`src/axiom/__init__.py` is:

```
while True:
    line = terminal.read_line()      # <- the session sits here, indefinitely
    ...guards and commands...
    terminal.start_turn()
    ...the whole turn...
```

Two halves of #74 fall out of that, and they fall opposite ways.

**AC 10 and AC 11 come free.** The loop body is exactly one turn and it is single-threaded.
Anything dispatched at the top of the loop runs *between* turns by construction, and a
second due job simply waits for the next pass. There is no interleaving to prevent because
there is no concurrency to begin with.

**AC 9 does not come free, and this is the problem of the story.** "When a job's time
arrives its prompt runs" cannot hold while the process is parked inside `input()`. A user
sitting at an idle prompt at 08:59 gets their 09:00 job when they next press enter - which
might be tomorrow. Checking due jobs before the read does not fix it; the read is where the
time passes.

Four ways out, recorded so cycle 2 does not rediscover them:

| | approach | why not, or why |
|---|---|---|
| a | check due jobs before `read_line` | simplest, and fails AC 9 - a job fires only after the user types |
| b | non-blocking poll of stdin | `msvcrt.kbhit` on Windows, `select` on POSIX; a platform split inside the one module allowed to touch the console |
| c | **a reader thread feeding a queue** | the main loop waits on the queue with a timeout and checks due jobs on each timeout; portable, no platform split, and turn execution stays single-threaded so AC 10 and AC 11 keep holding structurally |
| d | `signal.alarm` around the read | not on Windows, which is the primary platform here |

**(c) is the recommendation.** It is the only one that satisfies AC 9 without either a
platform split or moving turn execution off one thread.

## How a tool would reach the store - `action.md` item 3

`tools.run(name, arguments, limits)` injects `Limits`, and a tool declares `needs_limits`
to receive it. `Limits` is frozen, and its docstring is explicit that it holds settings
that *belong to the user* and are hidden from the model. **A schedule is not a limit** - it
is mutable session state, and putting it in `Limits` would make that dataclass two things.

The fitting shape is to **mirror the existing pattern rather than extend it**: a
`needs_schedule` flag alongside `needs_limits`, and a second injected argument on `run()`.
Same mechanism, same guarantee that the model cannot reach it by asking, no new concept.

## croniter - `action.md` item 4

Installed 6.2.4. `uv sync` could not run: `axiom.exe` was locked by Kaushik's open manual
testing session, so `uv pip install` was used instead, which does not rewrite console
shims. `pyproject.toml` carries `croniter>=6.0.0`. **A later cycle on a machine with no
axiom running should re-run `uv sync` to settle the lockfile.**

Three things the probe established, all of which change the design:

1. **The clock is injectable.** `croniter(expression, base)` takes a supplied datetime.
   Every criterion here is testable without sleeping, which is the whole reason this cycle
   led with it.
2. **`croniter.is_valid("*/15 * * * * *")` returns `True`.** Six fields pass - the sixth
   being seconds. So AC 25 ("a valid five-field expression") and AC 29 ("no finer than once
   a minute") are **the same guard**, and neither comes from the library. The store counts
   fields itself.
3. **croniter can never return a past time.** `0 9 28 8 *` asked at 18:47 on 28 August
   resolves to **2027**-08-28. So AC 27 cannot be answered by inspecting what croniter
   returns; a one-shot in the past looks identical to one a year out. That criterion needs
   the store to reason about the pinned fields against now, and it is **not solved in this
   cycle**.

## What was built

`src/axiom/schedule.py` - the store and nothing else. `Job` is frozen; `Schedule` holds
them in a dict, takes its clock as a constructor argument, and offers `add`, `jobs`,
`cancel`, `due` and `mark_run`. No printing, no model, no disk.

Two decisions inside it worth naming:

- **`mark_run` computes a recurring job's next time from *now*, not from when it was due.**
  A session busy through three fire times owes the user one run, not three. Computing from
  the due time queues the backlog it just missed.
- **The identifier is `uuid4`.** Nothing is authorised by holding a job id, so uniqueness is
  the whole requirement and an unguessable identifier would be the wrong kind of promise.
  The first draft imported Python's random-token module for it; the security hook blocked
  the write, and it was right to - the honest fix was to stop asking for a property this
  does not need.

`tests/test_schedule.py` - 25 tests, **0.30s**, nothing sleeps.

## The break, and what it proved

Removing only the field-count check turned **exactly three tests red** - the three
five-field cases - and nothing else. A discriminating guard, not a blanket one.

A first, blunter break (`FIELDS = 6`) turned 17 red, which proved the guard was
load-bearing but told me nothing about *which* test guards AC 25. Recorded because the
coarse break was nearly accepted as proof, and it is not proof: a break that reddens
everything reddens the vacuous tests too.

## Criteria

**Met with a test shown to fail when broken: 6 of 33** - AC 25, 26, 28, 29 (refusals),
AC 22 (proved by looking at the filesystem, not by intending not to write), AC 23.

**Implemented but not proved at the level the criterion is about: 5** - AC 5, 6, 14, 19, 20
hold in the store, but each is about what the *user* sees or what a *session* does, and
neither exists yet.

**Not started: 22** - everything about running, listing to the user, announcing, expiry,
and the seven-day rule. AC 27 is not started **and now known to be harder than it looks**.

## Suite

`uv run pytest` - **642 passed in 73.67s**. Baseline was 617 in 74.71s: 25 added, no
slowdown.

## Assumptions

One changed. The assumption said "the idle point is in the REPL in `src/axiom/__init__.py`"
and left the shape open. It is now known to be a **blocking `input()`**, which makes AC 9
the hard criterion of this story rather than an obvious one, and makes a reader thread the
likely answer. Recorded here rather than edited into `assumption.md`, per the loop's rules.
