# Action

**Verify cold, then merge or fix.** Cycle 2 wrote all eight implementations and judged them
met. This cycle's value comes entirely from not trusting that.

## 1. Read the criteria as written

`gh issue view 42` **first** — before `logs/cycle-1.md`, before `logs/cycle-2.md`, before the
diff. Those logs argue for their own conclusions.

Then `git diff master...HEAD -- src/ tests/`.

## 2. Attack the decision cycle 2 made on its own authority

**The sub-floor case now ends the session, and no criterion says to.** Cycle 2's reasoning is
in its log; judge it, do not inherit it.

- Does AC 6 support ending, or only saying? *"Told that plainly, rather than discovering it by
  retrying."*
- Does AC 4 require it? *"A session cannot reach a state where every message, however short,
  is refused."*
- Is there a user who loses something by the session ending — work in the history, a chance to
  `/exit` cleanly, an exit status that now differs?
- **What is the exit status?** Cycle 2 returns from `main` normally. Check what that produces
  and whether it is defensible for a session that could not do anything.

If ending is wrong, say so plainly — a decision the implementing cycle made past the criteria
is exactly what a cold read is for.

## 3. Attack the other four

- **AC 1 — "whatever the previous turn's reported usage was."** Cycle 2 tested usage under the
  trigger and usage `None`. Try usage *above* the trigger, so `maybe_compact` already ran and
  still left it too large. Does `compact_to_fit` do anything, or does it find the history
  already compacted and give up? That is a real path and it is untested.
- **AC 3 — "a following turn is not refused for the same reason."** Cycle 2 asserts
  `count("too large") <= 1` over two turns. Attack it with a session that is refused and then
  sent five more ordinary messages. Does it stay usable, or does it refuse again three turns
  later once history rebuilds?
- **AC 5 — the boundary between the three causes.** `what_will_not_fit` compares against
  `effective_context` with integer division. Try a message exactly at the boundary, an empty
  message, and a context exactly equal to the prompt's cost. Does any input land in the wrong
  bucket and get advice that cannot work?
- **AC 8 — "preserves facts and reports what it let go."** Cycle 2 checks a planted fact
  survives and that `compacting older history` is printed. It does **not** check
  `the summary is full - forgetting N` appears when the bound is hit on the size-driven path.
  Force it and confirm the forgotten facts are named one by one, as #32 requires.

## 4. Close the transcript gap

The golden transcript has **no `too large` scenario at all** — the refusal path has never been
scripted there. Three new user-visible messages exist that the behaviour record does not know
about, which is why AC 7 passed byte-identical.

Add scenarios to `test_characterization.py` for each of the three causes, then regenerate
deliberately. **Run `diff .tmp/transcript-baseline-42.txt tests/baseline/transcript.txt` and
read all of it before accepting.** #41 cycle 2 regenerated off pytest's summary — which names
the first differing index only — and destroyed two compaction scenarios.

## 5. Re-run everything

- Full suite and the hermeticity command. **266 is the floor.**
- `.tmp/repro_42.py` and `.tmp/ac1_case_42.py`, both from cycle 1, unchanged.

## 6. Then take the exit

**If all eight hold:** `loop.md` exit 1. Commit, push, PR referencing #42, merge, delete the
branch. Then in the same run: delete the cron, mark #42 done in `queue.md`, and scaffold row
8 — #43, `43-mcp-servers`.

**#43's scaffold carries the MCP clause in `CLAUDE.md`'s testing section**, which binds that
loop specifically: no test fetches a server, the in-memory transport settles nearly
everything, a real process is a script the repo owns, and no test contacts a hosted server or
needs a real secret. It also carries the no-questions rule, stated as decisions.

**If any criterion does not hold:** do not merge. Fix it, record what the cold read caught,
and write cycle 4's action.

## Record

Status for all 8, judged against the criteria text rather than cycle 2's table.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
