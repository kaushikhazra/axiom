# Observe

## Order matters

**Read the criteria from GitHub first** — `gh issue view 81` — before the diff and before the
previous cycle's log. Attack each criterion; do not confirm it. Across #40, #41, #42, #43, #48,
#49, #60, #72, #75, #77, #80 and #76, reading the criteria cold has found something real every
time and re-reading the diff has found nothing.

## The measurement

The number this loop moves is **criteria demonstrably met, out of 25.** Demonstrably means a
test that has been shown to fail when the behaviour is removed. Not "the code appears to do
this."

Every cycle, run and record:

    uv run pytest

## Every cycle, record

- **Criteria met, out of 25**, listed by number. Three buckets: met with a test proven to go red
  when broken; implemented but not proved; not started. Only the first counts.
- How far the number moved, and what moved it.
- `uv run pytest` — count, pass, fail, **wall-clock**. The count is arithmetic: tests added this
  cycle plus last cycle's. A count that does not add up means a test was silently replaced.
  Baseline entering this loop: **876 passed, 1 deselected, ~89s** on `master`.
- **The state of `tests/baseline/transcript.txt`** — unchanged, or the diff read line by line
  and summarised. Never "regenerated".
- **`.claude/loop/cited.py tests/<file>`** — which criteria the tests actually claim, against the
  issue.
- **Any process this cycle started, and that it is gone.** Row 20 is the only one in this queue
  that starts things.
- Any assumption that changed.

## The five that will be got wrong

- **AC 3 is the criterion the whole issue turns on.** A server named by address *is not a
  subprocess*: not started, not stopped, not waited for. `Servers` today builds a
  `StdioServerParameters` and spawns one, and its lifetime code — #43 AC 26 and AC 27 — is about
  processes outliving axiom. A remote entry must not reach any of it, and "it happens to work"
  is not the test. Prove that nothing was spawned.

- **AC 22 — a session with no MCP configured is unchanged, byte for byte.** The golden
  transcript is 477 lines and has not moved in sixteen cycles across four issues. If it moves,
  something is being paid for by every run that configured nothing.

- **AC 8 — two servers offering a tool of the same name stay distinguishable.** #43's cycle 4
  found this broken for a server whose *name contained the separator*. The routing key is the
  `server__tool` prefix, and it is both the collision guarantee and the route — one mechanism.
  A remote server's name goes through exactly the same rule or the guarantee is half a
  guarantee.

- **AC 10 and AC 25 against AC 11.** A server that cannot be reached is named and the session
  carries on; a slow one must not hold the session past the start limit. Both are about a
  failure that costs nothing, and the second is the one with a race in it. #43's cycle 4 note
  stands: **remove a race rather than shrinking the window.** A 1 ms timeout against a server
  that answers in about a millisecond is a coin toss, not a test.

- **AC 17 — a plain-text address is refused, or the user is told the traffic is not
  encrypted.** Two acceptable outcomes and they are very different. **Decide which, and record
  the decision with its reasoning**, rather than implementing whichever falls out. A localhost
  server over `http://` is the ordinary case and refusing it outright would make the feature
  useless for the person most likely to want it.

## Before claiming a criterion met

**Break it and watch the test go red.** Assume, on the measured rate from #77, #80 and #76,
that roughly one break in four is aimed at the code rather than at the criterion and proves
nothing. #76 cycle 2 had three of fourteen, and **a no-op break reads exactly like a passing
test** — say so in the log when one is found.

**A break big enough to be easy to write takes several tests with it.** Narrow it.

**A break that makes the suite faster is a test doing less.**

**Ask what typed the string you are asserting about.** #80 cycle 10 found a test asserting the
absence of a string nothing had ever produced.

**A count is not a criterion.** #80 cycle 9 found "one request" satisfied by an implementation
that threw the message away.

**A helper that tidies its input cannot then assert the input was untidied.** #76 cycle 2.

**Be suspicious of a hard criterion that passes first time.** #43's lifetime tests asserted
`surviving(spawned) == []` where `spawned` was measured *after* the servers had been stopped —
so the set was empty and the assertion held for any implementation at all. Ask whether the test
could pass if the feature did nothing.

**A scripted replace containing a backslash escape goes through the Edit tool.**

**Re-establish green between a revert and the next break** — the formatter strips imports a
break leaves unused.

## Goal check

- **Met** — all 25 criteria are in the first bucket, the suite is green, the baseline is
  untouched or its diff is summarised, no process this loop started is still running, and the
  list of what only a person can confirm has been written down for the manual pass. Take the
  queue's handing-over exit.
- **Not met** — report and write the next action.
- **Did not move** — criteria met is the same as last cycle's. Report the flat result and stop.
  Do not try another variant.
