# Action

**Cold-read all 11 criteria, then take the exit.** Cycle 1 wrote the fix and the tests and
declined to judge them.

## 1. Read the criteria as written

`gh issue view 55` **first** - before the diff, before `logs/cycle-1.md`. That log argues for
its own conclusions and its author wrote both the code and the case for it.

Then `git diff master...HEAD -- src/ tests/`.

## 2. Attack the five cycle 1 named, and any it did not

- **AC 10's four negatives.** The paired positive rules out "never announces at all". It does
  **not** rule out a route that *writes without announcing*. Is there one? Walk every call site
  of `models.write_choice` and confirm each either goes through `_remember` or is deliberately
  silent. A write that skips `_remember` would satisfy all four negatives and violate AC 1.
- **AC 7 - existence decides.** Three runs cover absent, present, deleted. Two states are
  untested: the file present but **empty**, and the path present but a **directory**. What does
  `_remember` do with each, and is that right? An empty file is not a remembered choice.
- **AC 11 - a failed save.** Cycle 1 patches `Path.mkdir`. That is the *directory* failing.
  Patch the **write** instead - `Path.write_text` - so the folder is created and the file is
  not. Does it still avoid claiming a file was written?
- **AC 9 - the two routes.** The comparison strips everything before `axiom: remembering`.
  Confirm that strip is not hiding a difference - print both captured lines and read them.
- **AC 2 - the path named.** It asserts `model.json` present and `mcp.json` absent. Would it
  pass if the path named were something else entirely that happened to contain `model.json`?

## 3. The standing question

For each of the fourteen: **could this pass if the feature did nothing?** Cycle 1 answered in
aggregate - the break turns 5 red - which means **nine survive**. Name all nine and give each a
verdict: fine (a *still*-or-guard assertion that should hold either way) or vacuous.

This is where #57's cold read found its defect, and it is the third time in four issues. Do not
skip it.

## 4. Re-run everything

- Full suite and the hermeticity command. **487 is the floor.**
- `diff .tmp/transcript-baseline-55.txt tests/baseline/transcript.txt` - expect **no change**,
  and if there is one, something is wrong rather than something is new.
- No stray `.axiom/` in the repo.

## 5. Then take the exit

**All eleven hold:** `loop.md` exit 1. Commit, push, PR referencing #55, merge, delete the
branch. Then in the same run: mark row 12 **done** in `queue.md` with the PR number, cycle count
and wall-clock time, scaffold `.claude/loop/56-same-facts/iteration-1/` per the queue's
handing-over procedure, mark row 13 **running**, and say what its first cycle will do.

**Do not touch the cron.** One cron drives the whole queue and reads `queue.md` for whichever
row is `running`. Marking row 13 running *is* the handover.

**Any criterion does not hold:** do not merge. Fix it, record what the cold read caught, and
write cycle 3's action.

## Record

Status for all 11, judged against the criteria text rather than cycle 1's table. The nine
survivors, each with a verdict. Where a verdict differs from cycle 1's, say which reading was
wrong and why.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
