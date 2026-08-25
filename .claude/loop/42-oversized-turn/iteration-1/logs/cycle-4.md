# Cycle 4 — 2026-08-26, 03:43 IST

AC 4 fixed. All eight criteria met with evidence.

## Criteria status

| AC | verdict | evidence |
|---|---|---|
| 1 | met | compaction runs with usage under the trigger, above it, and `None` |
| 2 | met | a refusal can only follow a compaction attempt |
| 3 | met | refused once, then five ordinary messages all answered |
| 4 | **met — was `blocked` in cycle 3** | the band now answers 10 of 10 with 0 refusals |
| 5 | met | causes told apart at the boundaries; the live one is in the transcript |
| 6 | met | said once, session ends, and safe because the verdict cannot change mid-run |
| 7 | met | transcript diff **purely additive, 0 lines removed** |
| 8 | met | facts named one by one, including on the new path |

**Suite: 272 passed**, hermetic.

## The fix

When the ladder is exhausted, what will not fit is the summary itself. `compact_to_fit` now
lets it go and reports every fact through the same `note_facts_forgotten` path #32 built —
this drops more at once than any other route, which makes saying so more important rather
than less.

**One guard, and it is the important part.** The drop only fires when an empty history would
actually fit. If the message the user just typed is what will not fit, throwing the
conversation away buys nothing and costs everything. `test_history_is_not_thrown_away_when_the_message_is_the_problem`
plants a fact, sends an oversized message, and asserts the fact is still there afterwards.

The kept_pairs=0 candidate is reused from the ladder rather than recomputed, so the last
resort costs no extra model call.

## Measured, before and after

Cycle 3's band, unchanged — context 350, ten ~80-character messages:

| | before | after |
|---|---|---|
| replies | 4 | **10** |
| refusals | 4 | **0** |
| pointless re-compactions | 3 | 0 |

AC 4 asks that no session reach a state where every message, however short, is refused. It no
longer can.

## A finding: one refusal message is now unreachable

Swept 35 combinations of context and message size. **Only `message` is ever reached.**

The reason is structural rather than accidental: the last resort's guard is *exactly* the
condition under which `what_will_not_fit` would return `CONVERSATION_TOO_LARGE`. Wherever the
conversation would have been the blocker, the session is now rescued instead of refused. The
only way `everything` is `None` is an empty history — and with an empty history, if the
prompt and the message fit, `too_large` would never have fired.

**Kept rather than deleted**, with a comment in `terminal.py` saying it is unreachable and
why. AC 5 names the conversation as something the message should be able to say, and deleting
it would mean a later change to that guard has no message for the case at all. It is recorded
so nobody reads its passing unit test as evidence of live behaviour — which is the exact
mistake this loop has now caught three times in other forms.

## The transcript

Regenerated, whole diff read as a diff: **69 lines added, 0 removed.** Three scenarios, one
per cause.

The conversation scenario was **renamed** after the fix changed what it does — it no longer
says a new session is needed, it lets the oldest of the conversation go and carries on. That
is the third scenario name corrected in two cycles. A scenario whose title does not match its
behaviour is worse than no scenario, because it is read as evidence of something that is not
happening.

## Cycle 3's defects, re-verified

- The user's message is still not compacted away: the 3358-character question is refused with
  `this message is about 124 tokens too large to send - try a shorter one`, and the model is
  never sent a turn without the question in it.
- The band carries on.

## Verdict

All eight criteria met with evidence. Taking `loop.md` exit 1.
