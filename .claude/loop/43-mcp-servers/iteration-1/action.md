# Action

**Verify cold, then take the exit.** Cycles 2 and 3 wrote all thirty implementations and
cycle 3 judged them met. This cycle's value comes entirely from not trusting that.

## 1. Read the criteria as written

`gh issue view 43` **first** — before any log, before the diff. Those logs argue for their own
conclusions.

Then `git diff master...HEAD -- src/ tests/`.

## 2. Look for more vacuous tests

Cycle 3 found one: AC 26 and AC 27 asserted `surviving(spawned) == []` where `spawned` was
measured after `stop()` had already run, so the set was empty and the assertion held for any
implementation at all. It was caught by suspicion of a first-time pass, not by an attack.

**Assume there are others.** For each criterion, ask the question that found it: *could this
test pass if the feature did nothing?* Then prove the answer by breaking the feature and
watching the test go red — the technique is in cycle 3's log and takes one command.

The likeliest candidates, because they assert on absence or on a count:

- **AC 1, 2, 29, 30** — all assert nothing changed. A test that nothing happened passes
  loudest when nothing is wired up at all.
- **AC 16** — `all(secret not in failure)` is true when `failures` is empty. Cycle 3 guards
  it with `assert attached.failures`, but check the same shape elsewhere.
- **AC 12** — asserts a name appears in `failures`; confirm the *other* tools really are still
  declared, not that the list is merely non-empty.
- **AC 9** — `surviving(first_pids) == []` has exactly the shape of the bug already found.

## 3. Attack the four hardest

- **AC 6.** The criterion is that a collision *cannot happen*. What about a server literally
  named `read_file`, or a server whose name contains `__`? Does `split()` route those
  correctly, or does a cleverly-named server reach another's tools?
- **AC 16.** Three places, and the third is the one that gets missed: **anything the model is
  told**. A tool result comes from the server. Can a server put its own configuration into a
  result the model then sees? If so, say whether that is axiom's to prevent.
- **AC 23.** `CALL_TIMEOUT` bounds a call, but the bound is enforced by
  `future.result(timeout)` — which stops *waiting*. Does the call itself stop, or does the
  server keep working while axiom moves on? #34 hit exactly this with `run_command` reporting
  "stopped it" while the command kept running.
- **AC 25.** "No server failure of any kind ends the session." Try a server that dies during
  `list_tools`, one that returns malformed content, and one whose process vanishes between
  turns.

## 4. Re-run everything

- Full suite and the hermeticity command. **313 is the floor**, and it must still pass with
  no MCP server anywhere.
- `diff .tmp/transcript-baseline-43.txt tests/baseline/transcript.txt` — **byte-identical**.
  Check for removed lines explicitly.
- Confirm no orphaned server processes are left behind by the suite itself.

## 5. Then take the exit

**All thirty hold:** `loop.md` exit 1. Commit, push, PR referencing #43, merge, delete the
branch. Then in the same run: delete the cron, mark #43 done in `queue.md` with the PR number
and cycle count, and **say the queue is empty** — #43 is the last row, so there is nothing to
scaffold and stopping silently would be wrong.

**Any criterion does not hold:** do not merge. Fix it, record what the cold read caught, and
write cycle 5's action.

## Record

Status for all 30, judged against the criteria text rather than cycle 3's table. Where a
verdict differs, say which reading was wrong and why.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
