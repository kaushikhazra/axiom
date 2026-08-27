# Action

**Cold-read all 12 criteria, then take the exit.** Cycle 1 wrote the fix and the tests and
declined to judge them.

## 1. Read the criteria as written

`gh issue view 56` **first** - before the diff, before `logs/cycle-1.md`.

Then `git diff master...HEAD -- src/ tests/`.

## 2. Attack the four cycle 1 named, and any it did not

- **AC 4 - "any fact the startup line reports".** Cycle 1's enumeration claims `announce` says
  six things and no more. **Verify against the source, not against that table.** Then widen the
  question: `note_servers` also speaks at startup - server names, tool counts, the cost line,
  the timeout bounds. Are any of those facts about the *session* that a switch leaves true and
  unrepeated? Decide whether AC 4 reaches them, and say why either way.
- **The `facts()` parser.** It removes `debug override` by string replacement before splitting
  on `", "`. Feed it every line shape the code can now produce and confirm it never returns
  equal dicts for two genuinely different lines - a parser that flattens a difference would make
  the agreement tests pass on a broken implementation.
- **AC 3.** `test_the_window_still_follows_the_model` hard-codes 32768 and 4096, which come from
  the fixture. Is it asserting the fix, or restating the stub? If the latter, make it derive the
  expectation rather than name it.
- **AC 12 - nothing else changes.** `note_switched` gained two parameters with defaults. Confirm
  no other caller exists that now silently gets `overridden=False, web=False`.

## 3. The standing question

For each of the fifteen: **could this pass if the feature did nothing?** The break turns 6 red,
so **nine survive**. Name all nine, each with a verdict - fine (a *still*-or-guard assertion) or
vacuous.

This is where #57's cold read found its defect, and #55's. Do not skip it.

## 4. Re-run everything

- Full suite and the hermeticity command. **505 is the floor.**
- `diff .tmp/transcript-baseline-56.txt tests/baseline/transcript.txt` - expect **no change**.
- No stray `.axiom/` in the repo.

## 5. Then take the exit

**All twelve hold:** `loop.md` exit 1. Commit, push, PR referencing #56, merge, delete the
branch. Then in the same run: mark row 13 **done** in `queue.md` with the PR number, cycle count
and wall-clock time, scaffold `.claude/loop/61-tool-cost/iteration-1/` per the queue's
handing-over procedure, mark row 14 **running**, and say what its first cycle will do.

**Do not touch the cron.** Marking row 14 running *is* the handover.

**Any criterion does not hold:** do not merge. Fix it, record what the cold read caught, and
write cycle 3's action.

## Record

Status for all 12, judged against the criteria text rather than cycle 1's table. The nine
survivors, each with a verdict. The AC 4 decision about `note_servers`, with reasoning.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
