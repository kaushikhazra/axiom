# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: C:/Projects/axiom/src/axiom/  and  C:/Projects/axiom/tests/
Design (given):      C:/Projects/axiom/.tmp/chooser-look-decision.md
Branch:              feature/77-look
Issue:               https://github.com/kaushikhazra/axiom/issues/77

Every 20 minutes, ONE iteration:
  - Action:  work on the source and tests, as action.md asks
  - Observe: check against the goal, using observe.md
  - If goal met:     stop the loop and delete the cron
  - If goal not met: write the next action.md, then exit this run

Fail-safe: at 2026-09-01 22:00 +0530, stop and delete the cron, converged or not.
```

`goal.md` and `observe.md` do not change. Everything else may, including the assumptions —
if an assumption changes, record it in that cycle's Observe.

Each cycle is written to `logs/cycle-N.md`. **These are immutable — they report the state
at that cycle and are never edited afterwards.**

**The artifact already exists.** This is a redesign of output that ships today, not new
source. `src/axiom/terminal.py` is ~1500 lines and `src/axiom/models.py` ~250, and the
suite entering this loop is **836 passed, 1 deselected, 81.9s**. Cycle 1 reads and records
where things stand before it writes anything — including which of the 37 criteria are
already true, because several are.

**The code is not this folder's artifact.** Source stays in `src/`, tests in `tests/`. This
folder holds the loop's own files and logs, nothing else.

**Work on `feature/77-look`.** Check the branch before writing; a cycle that wakes on
`master` must switch, not commit.

**The design is an input, not a question.** It is settled and recorded — see
`assumption.md`. A cycle that believes the design is wrong stops and says so rather than
changing it.

## The build order, and why it is this order

Three stages. Take them in order; each proves something the next one leans on.

1. **The reply's palette, and the unlexed fence** — AC 17 to 21. The smallest and safest:
   it changes no characters, and it cannot touch the golden baseline because rendering is
   gated on `isatty` and the transcript captures a non-tty. About 5 assertions. It settles
   where the accent constant lives and how `NO_COLOR` reaches it, before anything harder
   depends on either.

2. **The model chooser** — AC 1 to 6. Self-contained; never touches the baseline. About 30
   assertions, 11 of them the price of aligned columns.

3. **The info panel, the voice, the tool summary, the prompt** — AC 7 to 16 and 22 to 33.
   The expensive one: five functions replaced, eight test files touched, 78 baseline lines
   to read as a diff.

A stage is not finished until its criteria are in the first bucket — proved by a break that
was watched going red.

**Assume a fresh context.** Only these files exist. Read the issue from GitHub before the
diff and before the previous log.
