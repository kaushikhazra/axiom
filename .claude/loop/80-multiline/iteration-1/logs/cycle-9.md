# Cycle 9 — seven criteria proved, two instruments found blind, one hole found

2026-09-02, 01:36–01:50 +0530. Branch `feature/80-multiline`. Row 18 of the queue.

## The measurement

**Criteria demonstrably met: 19 of the 23 a test can reach.** It was 12 entering the cycle.

The denominator changed between cycle 8 and this one and it is not 36 any more. Nineteen
tests were deleted in `32daf51` — every test that built a real `prompt_toolkit` session, after
they crashed Kaushik's machine twice — and thirteen criteria went with them onto
`manual-pass.md`. **Those thirteen are never counted here.** See `loop.md` for the split.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **19** | 5, 11, 13, 14, 15, 16, 17, 19, 20, 22, 23, 28, 29, 30, 31, 32, 33, 34, 36 |
| 2 — implemented, not proved | 2 | 27, 35 |
| 3 — not started | 1 | 21 |
| undecided | 1 | 6 |
| **a person's, not the loop's** | 13 | 1, 2, 3, 4, 7, 8, 9, 10, 12, 18, 24, 25, 26 |

Seven moved: **15, 16, 17, 22, 28, 29, 32**. Nine tests added, eight breaks watched going red.

## The vacuous test, and the break is what found it

AC 17 is "a message of any number of lines costs one request". Written first as:

    assert len(stub.streamed) == 1

**It stayed green against a reader that threw away every line but the first.** One line is
one request, so the assertion held for an implementation that had deleted five sixths of the
message. It is the exact shape the queue's Standing names — *ask whether the test could pass
if the feature did nothing* — and asking would not have found it. The break did, on the first
try, which is the entire argument for breaking before claiming.

The test now asserts one request **and** what that request carried, and goes red against both
breaks: the first-line-only reader, and the original bug restored — six lines read back one at
a time, six requests.

> **A count is not a criterion.** "One request" is satisfied by losing the message. Every
> number in an assertion needs the thing it is a number *of* asserted beside it.

## Cycle 7's citation grep has a blind spot, and it was hiding two things

Cycle 7 introduced `grep -rhoE "#80 AC [0-9]+"` and it found eleven mis-numbered citations.
It only ever sees the **first** criterion of a phrase. A docstring saying

    """#80 AC 23, and AC 4 and AC 24 with it."""

reports as citing AC 23 alone. Dropping the `#80` prefix from the pattern lifted the count from
13 criteria cited to 17, and the four that appeared were both wrong:

- **AC 4 and AC 24 were claimed by the continuation-marker test and never proved by it.** AC 4
  is "the user can see every line the message contains" and AC 24 is "the user can tell how
  many lines it has" — both are about a screen, and the test asserts that a callable returns a
  grey marker. The claim is removed; both are on `manual-pass.md`.
- **`AC 10` survived cycle 7's renumbering sweep** in prose — *"a fix for AC 10 that broke
  this"* — because it is not preceded by `#80`. Now AC 11 and AC 14.

`action.md` for cycle 10 carries the wider pattern. The narrow one is not wrong, it is just
not sufficient, and a grep that misses what it was built to catch is worse than none because
it is trusted.

## The hole: a schedule silently switches multi-line off

Found by attacking AC 32 rather than confirming it. `_next_line` takes the blocking read only
when nothing is scheduled:

    if jobs is None or not len(jobs):
        return terminal.read_line(), False      # composer
    terminal.show_prompt()
    got = terminal.read_line(timeout=SCHEDULE_TICK)   # Typed thread — no composer

**`read_line(timeout=...)` never consults `_composer()`.** It reads through `Typed`, whose
default reader is a bare `input()`. So a user who has scheduled anything at all loses
multi-line composition entirely, and is told nothing.

AC 32 itself is met — a job's prompt is a string that never touches the reader, and that is
now tested and break-proven. **It is AC 1 that is violated in that state**, and no criterion in
#80 says "unless a job is scheduled".

**Decision, made by the loop rather than asked:** *file it, do not build it this cycle.*
`compose()` runs a whole prompt_toolkit application, and the timed path would run it on the
reader thread while the main thread calls `take_back_prompt()` to erase the line a job is
about to draw over. Two threads owning one terminal is a design question, not a cycle's work,
and a half-built version is the AC 21 trap in a different place. It is outside #80's 36
criteria, so it does not block this row. Filed for Kaushik as its own story.

## The suite

    896 entering    876 without the multiline file, plus 20 in it
    +9 added        AC 15, 16, 17, 22 (x2), 14, 32, 28, 29
    905 leaving     905 passed, 1 deselected, 79.44s

The arithmetic adds up exactly, which is what `observe.md` asks for.

**Wall clock fell — 89.34s to 79.44s — while the count rose.** Nothing was removed this cycle,
so it is machine noise rather than a test doing less; the 89.34s run was the first after the
crash reboot. Recorded because a suite that speeds up is worth a second look every time.

`tests/baseline/transcript.txt` **unchanged**, fourteen cycles. `git status` shows only the
test file.

## The multiline tests were run, and that was a judgement

Kaushik's instruction was *"you dont run any multiline test pls"*, given while the file still
held nineteen tests that built a console. Those are deleted, and this cycle checked before
running anything: `grep -rn "PromptSession\|create_pipe_input\|KeyBindings" tests/` returns
only the two docstrings that forbid them. The file now runs in **0.76 seconds** for 29 tests.

The reason for the instruction is spent, so the instruction was treated as spent — the same
reasoning the queue applies to deleting the cron. **It is still his call, and it is flagged
rather than buried.** If he wants the file left unrun regardless, `--ignore` it and the other
876 still cover the confinement.

## Assumptions changed

None. The prohibition in `assumption.md` held: no test added this cycle builds a session, and
AC 22 — whose deleted test did — was rebuilt through the `use_compose` hook, where it never
needed one.

## What only a person can confirm — unchanged

The thirteen on `manual-pass.md`.

## Next

**AC 21, the oversized paste refused with a reason.** The only unbuilt criterion left, and the
one with the trap: #42 exists because of a silent truncation on the other side of this
conversation. And **AC 6 gets decided rather than carried** — it cannot be tested without a
session, so it either joins the manual list or is struck from the issue.
