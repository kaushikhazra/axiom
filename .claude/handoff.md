# Handoff — formal testing of three finished loops

Rewritten 2026-08-28 at the end of the session that ran #72, #73 and #74. The previous
version pointed at manual testing; **that happened, it found two defects, and both are now
fixed on branches.** What is left is a formal pass over the result.

**The next session picks up here: formal testing, then merging.**

## Where things stand

`master` is untouched by all of this - **617 tests, exactly as it was.** Everything below is
on three local branches. **Nothing is pushed and no PR is open.**

| issue | what it is | branch | criteria | tests |
|---|---|---|---|---|
| [#73](https://github.com/kaushikhazra/axiom/issues/73) nested lists | a sub-item drawn as a sub-item | merged into #72's | **13 / 13** converged | — |
| [#72](https://github.com/kaushikhazra/axiom/issues/72) wide lines | a quote or list item wraps instead of cropping | `feature/72-wide-lines` | **21 / 21**, loop stopped unconverged | 687 |
| [#74](https://github.com/kaushikhazra/axiom/issues/74) scheduled prompts | run a prompt later, once or repeatedly | `feature/74-scheduled-prompts` | **33 / 33** converged | 705 |

#73 is already merged into #72's branch - AC 7 needed both, because a nested item wrapping to
its own indent needs #73's depth and #72's wrapping and neither alone satisfies it.

**#72's loop stopped deliberately rather than converging.** All 21 criteria hold; the loop's
other condition - characters lost at zero - does not, and the reason is below.

## Two decisions waiting

**1. The indented-code defect.** A line indented four spaces that is *not* a list item still
crops - 41 characters lost at width 40. It belongs to neither #72 nor #73, and #73 converged
after being handed it, which is how it slipped: two parallel loops each measured only their
own criteria.

A drafted issue with 13 criteria **and the measurement** is at `.tmp/issue-indented-code.md`
(gitignored, still on disk). The short version: a one-line change takes the loss to zero and
keeps the suite green, but renders a three-line block as three blocks over eleven rows -
because an indented code block has **no closing delimiter**, so a line-at-a-time renderer only
learns it ended afterwards. Fixing it properly needs the held-lines exemption that only tables
have. That is a design decision, not a regex.

**New story, or scope on #72?** Kaushik's call.

**2. Whether to merge before testing.** Two branches means two builds. Merging #74 into #72's
branch (or both to `master`) first would make tomorrow exercise one thing.

## What manual testing already established

**The two defects that started this were both found by using axiom, not by reading it** - a
quote losing its tail, and a nested list arriving flat. Neither was visible to 617 green tests.

**The scheduler was driven live on 2026-08-28** and works: asked to schedule `PING` every
minute, it fired twice with nothing typed, the prompt was taken back cleanly, and both
one-off notes were said once. Two things came out of that hour:

- **What gets scheduled is the model's paraphrase**, not the user's words. Asked to schedule
  "say the word PING and nothing else", qwen2.5:7b scheduled `PING`. Check the echo before
  walking away from something where the wording matters.
- **There is no way to cancel a job except by asking the model to.** No slash command. If a
  model will not call `cancel_schedule`, the only way out of a job firing every minute is to
  end the session. Not a violation of any criterion - AC 16 says cancelling by identifier
  works, and it does - but it is a real gap, found by needing it.

Still unobserved: **whether Ctrl-D exits immediately with jobs scheduled.** There is a reader
thread parked inside `input()` that cannot be interrupted, and the only thing making exit
instant is that thread being a daemon. Proved structurally, never watched.

## Start here

```
cd C:\Projects\.tmp\axiom-manual
uv run --project C:/Projects/axiom axiom
```

**`--project`, not `--directory`.** `--directory` moves the working directory into the repo,
which is what CLAUDE.md's tool-testing rule forbids, and then needs `--working-directory` to
undo. `--project` leaves cwd where you are.

**Check the startup line tells you which build you are on.** `feature/74-scheduled-prompts`
says **`10 tools`** and **`about 1111 tokens`**; `master` and `feature/72-wide-lines` say
`7 tools` and `807`. Adding three scheduling tools costs **38% more on every request**,
whether or not anything is ever scheduled. That is #61's line doing its job, and it is a trade
worth revisiting.

## What the loops learned that a reader should know

Three cycles' worth of process findings, all earned the hard way:

> **A vacuous test is normal, not exceptional.** Eleven tests written in one cycle, three of
> them passed with the feature removed. One filtered blank rows out before counting, and a
> code block's padding rows *are* blank - it filtered away the defect it was named for.
> Assume the same rate and run the break every time.

> **The wall clock finds what a green suite cannot.** Three times. A spinning thread, because
> fourteen tests at 0.04s took five seconds. A vacuous test, because a break made the file
> *seventeen times faster* - a test doing less, not going quicker. A gate that never opened,
> because one test took exactly 5.00s against its neighbours' 0.03s.

> **A test that ends the session early passes everything it was going to assert afterwards.**
> Twice. Nothing about it is visible in a green run.

> **A merge can delete a test silently.** Two branches defined the same test name; Python took
> the later one, the earlier pair vanished, and pytest reported green. Only the count caught
> it - 680 where the arithmetic said 682.

> **`sed -i` rewrites this repo's line endings**, turning a two-line change into a 2440-line
> diff. Use the Edit tool for source. And the formatter strips imports a break makes unused,
> so re-establish green *between* a revert and the next break.

## Loop records

`.claude/loop/72-wide-lines/`, `73-nested-lists/`, `74-scheduled-prompts/` - each with its
`goal.md`, `observe.md`, `assumption.md` and a `logs/cycle-N.md` per cycle. The logs carry the
measurements, the breaks and what each cycle got wrong. #72 ran 5 cycles, #73 3, #74 7.

**Note on timestamps:** several early logs carry times taken from an assumed clock rather than
a read one, running up to an hour ahead. Nothing was decided by a timestamp.

**Nothing is scheduled.** All three crons were deleted as their loops ended.
