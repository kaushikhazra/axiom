# Action

**A second cold read, on the fixes themselves.** Cycle 4 found four real defects and then
fixed all four in the same cycle — which is precisely the arrangement the rule exists to
distrust. New code written under time pressure at the end of a row has had no hostile
reader at all.

This is a shorter pass than cycle 4's. It is not a re-read of the whole row.

## 1. Check the ground

- Full suite. **603 is the floor.**
- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- Golden transcript **unchanged**.
- `python .tmp/break60.py` — 25 breaks, no survivors. If any says NOT APPLIED, its target
  moved and the break is proving nothing; fix it before reading the results.

## 2. Attack the new code

Read `logs/cycle-4.md` for what each fix claims, then try to break the claim.

**The erase arithmetic** — `_rows_used`. It assumes the terminal defers its wrap. What
happens at exactly the width, one under, one over? What about a line containing a wide
character *at* the wrap point, where the terminal moves it whole to the next row and the
count is off by one? What if `_width()` returns a different number between the echo and the
commit — a resize mid-line is exactly that, and `tests/screen.py` can be told to change
width partway through.

**The lexing window** — `CODE_CONTEXT`. `_code` is capped, and `_code_line` indexes
`drawn[len(self._code) - 1]`. Does that still hold when `_highlighted` returns fewer lines
than the window — an empty line, a line that lexes to nothing? The guard is
`len(drawn) >= len(self._code)`; find an input where it is false and check what the user
gets.

**The table test** — `HEADER_RULE`. A table is recognised by a `─` appearing in the drawn
output. What draws that character other than a header rule? A row whose *content* is a box
character would be one. Try it.

**Settle on failure** — `_settle_reply` in `report_failure`. Are there other routes out of
a turn that skip `end_reply`? `report_too_large` and the round-limit path both print in
axiom's voice; check whether a reply can be pending when either runs.

## 3. Attack what cycle 4 did not reach

- **AC 6 and the table.** Formatting appears as the reply streams — but a table's does not
  appear until the table ends, measured at 4.3 to 4.5 seconds. Is that consistent with AC 6
  as written, or is it a criterion met everywhere except the one construct that holds? Decide
  and record; do not leave it unexamined because cycle 3 recorded a reason.
- **AC 9 and highlighting.** A construct still incomplete is never shown as complete. Is a
  half-arrived fence *opener* — ` ```pyth ` with the rest still coming — ever lexed as a
  language?
- **The plain path, byte for byte.** Run the same reply through both paths and diff them,
  rather than trusting that two tests assert the same literal.

## 4. Then

If it finds something: fix it with a test that fails first, add its break, and write cycle
6's action. **Name the finding in the log** with what it would have cost a user.

If it comes back clean, that is **exit 1**:

- all 29 met, suite green and hermetic, transcript unchanged, a real before-and-after
  recorded
- commit, push, open a PR referencing #60, **merge it**, delete the branch
- then, in the same run: mark row 16 done in `queue.md` with the PR number, cycle count and
  wall-clock time, **say the queue is empty**, and update `../../handoff.md` — manual testing
  is still unfinished, #41, #34, #40, #35 and #26 were never reached, and seven rows have
  merged since it was last written
- **do not touch the cron.** With the queue empty there is no next row to redirect it to;
  say so in the handover and leave it for Kaushik to stop

## 5. Say how cold it was

Cycle 4's read was not fully cold — same session, no separate agent available under this
session's standing instruction. Say the same plainly if it is true again, rather than
claiming a cold read that was not cold. What stood in for it, and worked, was **modelling
the terminal instead of re-reading the code**: three of four findings came from hostile
inputs run through `tests/screen.py`. Do that again.

## Record

Every claim of cycle 4's, with a verdict and what was tried against it. Anything found, by
name. Whether the read was cold. If nothing is found, what was attacked and came back clean.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry
on.
