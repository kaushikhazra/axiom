# Action

**Verify cold, then merge or fix.** Cycle 2 wrote twelve implementations and judged them
met. This cycle is the external check `observe.md` requires, and its value comes entirely
from not trusting cycle 2's reasoning.

## 1. Read the criteria as written, not as remembered

`gh issue view 40` first. Read all twelve from GitHub **before** reading `logs/cycle-2.md`,
and before reading the diff. Cycle 2's log is persuasive because its author wrote both the
code and the verdict; reading it first is how that persuasion transfers.

Then `git diff master...HEAD -- src/ tests/` and judge each criterion against the code.

## 2. Attack the four that are easiest to get wrong

For each, try to construct a case that breaks it. A criterion survives by resisting an
attack, not by having a test named after it.

- **AC 6.** The bytes must never come back. Try `text/plain` announced on a body that is
  actually binary; a type of `application/octet-stream`; a `+xml` suffix on something
  binary, since `image/svg+xml` is deliberately routed to text. Does any of them return
  bytes? If a hostile server can get a payload through by lying about the type, say so - the
  criterion says *served as*, so believing the header may be correct, but the reasoning must
  be written down rather than assumed.
- **AC 2.** Exact equality is asserted for a utf-8 body. What about a body whose charset is
  something else, or one with `\r\n` line endings? `page.text` decodes by the announced
  charset. Does "as they were served" still hold?
- **AC 9.** The cut is measured in characters against `page_characters`. Confirm the message
  is the same one HTML gets, and that a multi-byte body does not cut mid-character.
- **AC 12.** Re-run `.tmp/probe_ac12.py` and diff against the four strings quoted in
  `logs/cycle-1.md`. They are quoted there exactly for this purpose.

## 3. Re-run everything

- Full suite and the hermeticity command. 223 is the floor.
- `diff .tmp/transcript-baseline-cycle1.txt tests/baseline/transcript.txt` - must be silent.
- `.tmp/probe_types.py` for the live sweep, and `.tmp/probe_no_type.py` for AC 7.

## 4. Then take the exit

**If all twelve hold:** `loop.md` exit 1. Commit, push, open a PR referencing #40, merge it,
delete the branch. Then in the same run: delete the cron, mark #40 done in `queue.md` with
the PR number and cycle count, and scaffold row 6 - #41, `41-limits-and-place` - per the
handover procedure. **That scaffold states decisions, never questions** - if #41's criteria
contain something ambiguous, settle it there with the reasoning recorded, exactly as this
loop settled AC 6, AC 7 and AC 8.

**If any criterion does not hold:** do not merge. Fix it, record what the cold read caught
that cycle 2 missed, and write cycle 4's action. A criterion the author's own cycle called
met and a fresh read overturned is the most valuable thing this loop can produce - say so
plainly rather than quietly correcting it.

## Record

Status for all 12, judged against the criteria text rather than against cycle 2's table.
Where a verdict differs from cycle 2's, say which reading was wrong and why.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry
on. Nobody is reading between firings.
