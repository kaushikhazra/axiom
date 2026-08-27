# Action

**Cold-read all 12 criteria, then take the exit.** Cycle 1 wrote the fix and the tests and
declined to judge them.

## 1. Read the criteria as written

`gh issue view 61` **first** - before the diff, before `logs/cycle-1.md`.

Then `git diff master...HEAD -- src/ tests/`.

## 2. Attack the five cycle 1 named, and any it did not

- **AC 9 - the same measurement the size checks use.** The test builds its own prompt from
  `tools.Limits()` with no arguments; `_chat` builds one from the run's actual settings via
  `_limits`. **Are they the same string?** With `--working-directory` set they are not, and the
  test would then be asserting a figure the code never produces. Check with a non-default
  setting, and if it diverges, that is a real defect in the test rather than the code.
- **AC 3 - everything that rides in every request.** Declarations and the prompt. Is there a
  third? Walk what `to_send` actually assembles and account for each part.
- **AC 2 - the share.** The guard is `if window`, so a window of `0` is treated as absent rather
  than dividing by zero. Correct, but is `0` reachable, and would silence be right if it were?
- **AC 10's negative** passes under the break. Confirm its positive genuinely discriminates by
  breaking **the switch call** specifically, not the startup one.
- **AC 4 - said once.** With a server attached *and* a switch, how many cost lines does a
  session print? Once at startup and once per switch is right; twice at startup is not.

## 3. The standing question

For each of the fifteen: **could this pass if the feature did nothing?** Cycle 1 named five
survivors of the startup break. Re-judge them independently, and additionally break the **switch**
call and name that set - the two breaks have different survivors and only doing one is half the
question.

## 4. Re-run everything

- Full suite and the hermeticity command. **520 is the floor.**
- `diff .tmp/transcript-baseline-61.txt tests/baseline/transcript.txt` - 24 added, 0 removed,
  every line a cost line. Confirm rather than assume.
- No stray `.axiom/` in the repo.

## 5. Then take the exit

**All twelve hold:** `loop.md` exit 1. Commit, push, PR referencing #61, merge, delete the
branch. Then in the same run: mark row 14 **done** in `queue.md` with the PR number, cycle count
and wall-clock time, scaffold `.claude/loop/62-summary-facts/iteration-1/` per the queue's
handing-over procedure, mark row 15 **running**, and say what its first cycle will do.

**Do not touch the cron.** Marking row 15 running *is* the handover.

**Any criterion does not hold:** do not merge. Fix it, record what the cold read caught, and
write cycle 3's action.

## Record

Status for all 12, judged against the criteria text rather than cycle 1's table. Both break sets
with verdicts. The AC 9 prompt-identity answer, with evidence.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
