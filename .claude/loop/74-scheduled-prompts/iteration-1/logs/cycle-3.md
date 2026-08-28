# Cycle 3 — 2026-08-28 20:34 +0530

The prompt question, answered by looking. Then the dispatch, wired and tested.

## The prompt, decided on a modelled screen

`action.md` said to measure rather than prefer, so all three options from cycle 2 were
rendered through `tests/screen.py`:

```
(a) the main loop owns the prompt      (b) the thread owns it, job erases first
|>                                     |axiom: scheduled - check the deploy
|axiom: scheduled - check the deploy    |
|                                      |The deploy is green.
|The deploy is green.                   |
|                                      |>
|>

what happens today, with nothing done about it
|> axiom: scheduled - check the deploy
|
|The deploy is green.
|
|>
```

The third is the mess cycle 2 predicted: the turn starts **on** the prompt row, and the user
reads their own prompt run together with axiom's line.

(b) looks best, but it needs the prompt drawn in *two* places - the thread before, the main
loop after the turn - which is worse than either. **The answer is (a)'s single ownership with
(b)'s erase**: the main loop draws the prompt, takes it back when a job fires, and draws a
fresh one after. One owner, best output.

`Typed` now reads with `input()` and no prompt string. `show_prompt` and `take_back_prompt`
are the caller's, and the untimed `read_line` still draws its own, so nothing existing moved.

## The dispatch

`_next_line(jobs)` at the top of the chat loop, and nowhere else.

**With nothing scheduled it is the blocking read it has always been** - no thread, no
timeout, no waking up. That is why all 654 tests from cycle 2 still pass untouched: a
session that never schedules anything cannot tell any of this exists. It is also why the
tick is not a cost: an empty schedule never reaches it.

AC 10 and AC 11 are **structural, not defended**. One call site at the top of the loop means
a job cannot begin mid-turn. One job returned per pass means two due at once run one after
the other, in the order `due()` gives them, with a whole turn between. Nothing is locked
because nothing was made concurrent.

`SCHEDULE_TICK` is 0.25s. The finest schedule anyone can ask for is one a minute (AC 29), so
this is two hundred times finer than it needs to be; it bounds how late a job can be, not how
often anything is computed.

## The breaks

| break | red | reads as |
|---|---|---|
| the schedule is never consulted | **6** | today's behaviour: nothing ever fires |
| `mark_run` dropped | **3** | a due job fills the session with itself, and a one-shot repeats |

The second is the interesting one. Without `mark_run` the three tests that fail are exactly
the three about a job *not* coming back - and nothing else. Precise.

No vacuous tests this cycle.

## Criteria

**Met, with a test shown to fail when broken: 12 of 33.**

New this cycle: AC 9 (a due job runs while the user types nothing), AC 10 and AC 11 (one job
per pass, at the top of the loop), AC 12 (a job's run is an ordinary turn - it goes through
the same path a typed line does), AC 13 (announced in axiom's own voice, with the prompt
echoed so the user can see what was asked), and AC 24 in part.

Carried from cycle 1: AC 22, 23, 25, 26, 28, 29.

**Not started: 21.** The three tools, listing, cancelling to the user, the seven-day expiry,
and AC 27.

## What is still not wired, and why it is honest

Nothing can *create* a job yet - there are no tools. The dispatch is live and inert, which is
not dead code: it is the mechanism, and having it in place is what made AC 9 to AC 13
testable through the real function rather than through a sketch.

**One thing cycle 4 must fix first.** `terminal._typed` is a module-level singleton, so an
end-to-end test through `main` with a schedule would leak a reader thread between tests.
These tests avoid it by patching `terminal.read_line`, which is honest for a unit test and
not enough for an end-to-end one. Make it injectable before writing the tool tests, not after.

## Suite

`uv run pytest` - **665 passed in 74.28s**. Baseline 654; 11 added. The new tests run in
**0.19s**. Nothing sleeps.

## A gotcha worth recording

`sed -i` on this repo rewrites line endings, which turns a two-line change into a 2440-line
diff - 1220 insertions, 1220 deletions, and `git diff --ignore-all-space` empty. It cost
nothing here because it was caught by a checkout refusing to switch branches, but a commit
made in that state would have been unreviewable. **Use the Edit tool for source changes.**

## Assumptions

None changed. The reader thread held up under wiring, and the prompt question - which cycle 2
raised and could not answer from reading - was answered by rendering it.
