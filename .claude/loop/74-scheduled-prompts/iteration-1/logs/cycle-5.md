# Cycle 5 — 2026-08-28 20:31 +0530

AC 27, which this loop has deferred since cycle 1. It was worth deferring: the obvious rule
is wrong, and the measurement says so before any code did.

## AC 27 — no distance threshold can work, and that is measured

A cron expression has no year field, so a fully-pinned one-shot names a moment *in a year*,
not a moment. croniter always returns the next match, so "already gone" and "a year out" are
the same answer.

| case | resolves to | days away |
|---|---|---|
| this morning, already gone | 2027-08-28 | 364 |
| a leap day, asked in August | 2028-02-29 | **549** |
| a leap day, asked 1 March 2024 | 2028-02-29 | **1460** |
| new year's day, asked on new year's eve | 2027-01-01 | **1** |

**The legitimate leap-day job is further away than the genuinely-gone one.** Any threshold
below 1460 refuses a valid leap day; any threshold at or above it lets a gone job through.
The ranges overlap, so distance alone cannot separate them - which is why cycle 1 recorded
this as "harder than it looks" and did not guess.

## What it took: three conditions, and each one has a trap behind it

A one-shot is refused when **all three** hold:

1. the pinned minute, hour, day and month name a moment that **exists in this year**
2. that moment has **passed**
3. the next match is **more than 300 days away**

Drop the first and 29 February in a non-leap year looks past when it simply does not exist.
Drop the second and nothing is being asked at all. **Drop the third and `0 9 1 1 *` asked on
new year's eve is refused for naming a time fourteen hours away** - this year's 1 January is
eleven months gone, and the user meant tomorrow.

The 300 is not arbitrary. The only case where a past-looking one-shot is genuinely imminent
is across a year boundary, where the next match is a day or two out. 300 sits in the gap with
room either side.

## The breaks proved each half separately

- **Distance alone** (skip the pinned-moment construction): reddens **exactly** the
  leap-day-still-to-come case.
- **Pinned moment alone** (drop the distance check): reddens **exactly** new year's day asked
  on new year's eve.

Each break hits the one trap its half exists for, and nothing else.

**A first attempt at the second break reddened nothing**, and that was informative rather
than a waste: removing only the `named < now` comparison left the construction and its
`ValueError` guard in place, so the leap-day case still short-circuited. The break has to
remove the *whole* condition, not the part of it that reads like the condition.

## A spin found by the wall clock, not by a failing test

Fourteen tests, none slower than 0.04s, and the file took **5.43 seconds**. The time was
outside the tests entirely.

`_pump` is `while True: read(); put()`. A real `input()` blocks, so the loop reads exactly as
fast as the user types. **A reader that returns without blocking - which every fake one does -
fills an unbounded queue as fast as the interpreter allows.** My own injected reader in this
cycle's test did precisely that.

The queue is now bounded to one, so `put` blocks until the caller has taken the last line.
Nothing is lost by it: a line typed but not yet read is still in the terminal's own buffer.
**5.43s to 0.84s.**

`observe.md` says a suite that slows down is a test that waited on real time. It was not a
test - it was the code - and watching the number is what found it either way.

## Criteria — 28 of 33

**New this cycle: 3** - AC 27, AC 33 (the reader thread is a daemon, which is the only thing
making exit immediate - a non-daemon one would hold the process open until the user pressed
enter, which is a hang rather than an exit), and the injection housekeeping behind it.

**Not started: 5** - AC 1, 19, 20, 24, 30, 31, 32. AC 19 and AC 20 hold in the store and have
not been driven through a whole session; AC 30 to AC 32 are about a job whose *run* fails,
which needs a stub backend that errors on a scheduled turn.

## Suite

`uv run pytest` - **695 passed in 74.62s**. Baseline 683; 12 added.

## Assumptions

None changed. Cycle 1's judgement that AC 27 "needs the store to reason about the pinned
fields rather than the resolved time" was right, and this cycle is what it looks like carried
out.
