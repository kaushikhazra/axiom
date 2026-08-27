# Action

**Cold-read all 9 criteria, then take the exit.** Cycle 1 wrote the fix and the tests and
declined to judge them. This cycle's whole value is in not trusting that.

## 1. Read the criteria as written

`gh issue view 57` **first** - before the diff, before `logs/cycle-1.md`. That log argues for
its own conclusions and is persuasive because its author wrote both the code and the case for
it.

Then `git diff master...HEAD -- src/ tests/`.

## 2. Attack the four that a careless fix would survive

- **AC 4 - no value carries the mark.** Cycle 1 asserts on a server's name, command, args, env
  values and a host key. **Find a path it missed.** A `tools` list entry. A nested key inside
  `env`. A second server, where the mark would land on the first only. A file whose *first*
  key is not `mcpServers`. Try each; a decoder-level fix should survive all of them, and if one
  fails the fix is not what cycle 1 claims it is.
- **AC 7, AC 8 - today's exact words.** Cycle 1's tests hard-code message text. Check them
  against the **current** strings in `config.py` and `terminal.py`, not against the log. A test
  asserting a message that was reworded elsewhere is a test asserting history.
- **AC 9 - no platform branch.** It greps for `sys.platform`, `os.name`, `platform.system`.
  Could a branch exist under another name - `platform.win32_ver`, `os.sep`, a check on
  `Path` flavour? Look at the diff rather than trusting the grep list.
- **AC 5, AC 6 - what axiom writes.** `write_choice` on a file that already has a mark is
  covered. What about `write_choice` on a file that has a mark *and* is otherwise malformed?
  It replaces the document - does the replacement carry a mark through?

## 3. The standing question

For each of the 18 tests: **could this pass if the feature did nothing?** Cycle 1 answered it
in aggregate - reverting the four reads turns 12 red - which means **6 did not**. Name those
six and say for each whether it is fine (it asserts something already true, like an unmarked
file still reading) or vacuous.

## 4. Re-run everything

- Full suite and the hermeticity command. **471 is the floor.**
- `diff .tmp/transcript-baseline-57.txt tests/baseline/transcript.txt` - **byte-identical**,
  and this row has no business changing it.
- Confirm no `.axiom/` was left behind in the repo by any probe.

## 5. Then take the exit

**All nine hold:** `loop.md` exit 1. Commit, push, PR referencing #57, merge, delete the
branch. Then in the same run: mark row 11 **done** in `queue.md` with the PR number, cycle
count and wall-clock time, scaffold `.claude/loop/55-announce-the-file/iteration-1/` per the
queue's handing-over procedure, mark row 12 **running**, and say what its first cycle will do.

**Do not touch the cron.** One cron drives the whole queue and reads `queue.md` for whichever
row is `running`. Marking row 12 running *is* the handover.

**Any criterion does not hold:** do not merge. Fix it, record what the cold read caught, and
write cycle 3's action.

## Record

Status for all 9, judged against the criteria text rather than cycle 1's table. The six tests
that survive the break, each with a verdict. Where a verdict differs from cycle 1's, say which
reading was wrong and why.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
