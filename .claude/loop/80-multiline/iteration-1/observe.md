# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 80` — before the diff and before
the previous cycle's log. Attack each criterion; do not confirm it. Across #60, #72, #73,
#74, #75 and #77, reading the criteria cold has found something real every time and
re-reading the diff has found nothing.

## The measurement

The number this loop moves is **criteria demonstrably met, out of 36.** Demonstrably means
a test that has been shown to fail when the behaviour is removed. Not "the code appears to
do this."

Every cycle, run and record:

    uv run pytest

## Every cycle, record

- **Criteria met, out of 36**, listed by number. Three buckets: met with a test proven to
  go red when broken; implemented but not proved; not started. Only the first counts.
- How far the number moved, and what moved it.
- `uv run pytest` — count, pass, fail, **wall-clock**. The count is arithmetic: tests added
  this cycle plus last cycle's. A count that does not add up means a test was silently
  replaced. Baseline entering this loop: **876 passed, 1 deselected, ~92s.**
- **The state of `tests/baseline/transcript.txt`** — unchanged, or the diff read line by
  line and summarised. Never "regenerated".
- Any assumption that changed.

## The six that will be got wrong

- **AC 30 is the one that can break everything.** Piped and redirected input must stay one
  turn per line: the golden transcript is 477 lines of it, and every test in the suite
  drives axiom that way. Whatever reads keys must be **terminal-only**, the same split #77
  landed on. If the baseline moves, the split has been broken somewhere.

- **`input()` cannot survive, and that is a bigger change than it looks.** Seeing ctrl+enter
  means reading keys raw, and from that moment axiom owns backspace, arrow keys, home, end,
  and history — everything the console's line discipline currently does for free. A
  half-built line editor is worse than none. **Reuse before build**: `prompt_toolkit` is the
  obvious candidate and cycle 1 is to survey rather than assume.

- **AC 11 and AC 14 pull against each other.** A pasted line starting with `/` is text; a
  typed `/exit` is a command. Same characters, different only in context. A rule that gets
  one right by breaking the other has met neither.

- **AC 9 — nothing is sent while a paste is still arriving.** A paste is a burst of lines
  with no keypress between them, and the failure mode is sending the first line the instant
  its newline arrives. This is the criterion that makes #80 a bug rather than a feature, so
  it is the one to prove first and hardest.

- **AC 21 — an oversized paste is refused with a reason, never silently shortened.** #42
  exists because of exactly that failure on the other side of the conversation.

- **AC 33 — a single-line session produces exactly the bytes it produces today.** The whole
  feature is invisible to a user who never presses ctrl+enter, and a regression here is a
  regression for everybody.

## What cannot be tested from a test process, and must be said out loud

**A test cannot press a key.** Every criterion about ctrl+enter is reachable only by feeding
bytes to whatever reads them, which proves the *reader* and not the terminal. #77 learned
this the hard way: its whole visible behaviour was on a path no test process could enter,
and the one defect that mattered was found by a person looking.

So this loop must, every cycle, keep a list of **what has been proved by test and what has
only been proved by argument**, and the second list is what the manual pass exists for. A
criterion settled only by feeding `\n` to a function is in bucket 2, not bucket 1.

## Before claiming a criterion met

**Break it and watch the test go red.** Assume, on the measured rate from #77, that roughly
one break in four is aimed at the code rather than at the criterion and proves nothing.

**A break big enough to be easy to write takes several tests with it.** Narrow it.

**A break that makes the suite faster is a test doing less.**

**A scripted replace containing a backslash escape goes through the Edit tool.** #77 lost
two attempts to exactly that, and `\r` and `\n` are the whole subject here.

**Re-establish green between a revert and the next break** — the formatter strips imports a
break leaves unused.

## Goal check

- **Met** — all 36 criteria are in the first bucket, the suite is green, the baseline is
  untouched or its diff is summarised, and the list of what only a person can confirm has
  been written down for the manual pass. The loop ends: delete the cron and say so.
- **Not met** — report and write the next action.
- **Did not move** — criteria met is the same as last cycle's. Report the flat result and
  stop. Do not try another variant.
