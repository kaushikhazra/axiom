# Action

**Verify cold, then merge or fix.** Cycles 2 and 3 wrote all twelve implementations and
judged them met. This cycle is the external check, and its value comes entirely from not
trusting that judgement.

## 1. Read the criteria as written, not as remembered

`gh issue view 41` **first** — before `logs/cycle-2.md`, before `logs/cycle-3.md`, before the
diff. Those logs are persuasive because their author wrote both the code and the verdict.

Then `git diff master...HEAD -- src/ tests/` and judge each criterion against the code.

## 2. Attack the five most likely to be wrong

A criterion survives by resisting an attack, not by having a test named after it. #40's AC 7
had a test that passed for an implementation doing no judging at all.

- **AC 3 — "told as facts, not as settings".** Four models refused a polite request. Try a
  determined one: tell the model the user is the administrator and the limit has been raised;
  ask it to run something that will take two minutes anyway. Does it hold? The structural
  half is solid — `Limits` is in no schema — so the question is whether the *prompt's* claim
  survives pressure, and if it does not, say whether that matters given the structure.
- **AC 5 — the criterion that fails silently.** Cycle 3 tested an absolute path *inside* the
  sandbox. Try one genuinely elsewhere, and try a relative path the user names explicitly
  (`../notes.txt`). Does the instruction make any model refuse work that was actually asked
  for? That is the failure AC 5 exists to catch.
- **AC 9 — "the same failure".** Cycle 3 compares result strings exactly. Attack it: a
  command whose failure text contains something that varies between runs — a temp path, a
  pid, a duration. If the strings differ by a number the model cannot control, the block
  never fires and AC 9 is decorative. Say what happens.
- **AC 6 — resolution.** Try a symlink, a UNC path, a path with `..` that resolves back
  *inside*, and a working directory that does not exist. `tools.outside` swallows `OSError`;
  check that swallow cannot hide a genuinely outside path.
- **AC 12 — "no extra output".** Run a plain conversation with no tools and confirm nothing
  new appears. The transcript covers the scripted paths; this is the everyday one.

## 3. Re-run everything

- Full suite and the hermeticity command. **253 is the floor.**
- `diff .tmp/transcript-baseline-41.txt tests/baseline/transcript.txt` — it will differ, and
  every hunk is accounted for in `logs/cycle-3.md`. Confirm nothing has been added since.
- `.tmp/probe_live_41b.py` across all four models.

## 4. Then take the exit

**If all twelve hold:** `loop.md` exit 1. Commit, push, open a PR referencing #41, merge it,
delete the branch. Then in the same run: delete the cron, mark #41 done in `queue.md` with
the PR number and cycle count, and scaffold row 7 — #42, `42-oversized-turn`.

**#42's scaffold must carry this**, and it is the most important thing this loop hands on:
**#41 creates the state #42 AC 4 forbids.** A fixed ~163-token system prompt against a small
context refuses every turn, however short. #42 owns `too_large` and the refusal path, so the
interaction is squarely its problem — and it now has a concrete reproduction: set
`AXIOM_DEBUG_MAX_CONTEXT=200` and type anything.

**If any criterion does not hold:** do not merge. Fix it, record what the cold read caught,
and write cycle 5's action. A criterion two cycles called met and a fresh read overturned is
the most valuable thing this loop can produce.

## Record

Status for all 12, judged against the criteria text rather than against cycle 3's table.
Where a verdict differs, say which reading was wrong and why.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
