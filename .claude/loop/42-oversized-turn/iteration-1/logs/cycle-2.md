# Cycle 2 — 2026-08-26, 03:13 IST

Size-driven compaction, three refusal messages, and one decision that goes beyond the literal
criteria and is flagged as such. All eight criteria have evidence. **Convergence is not
declared** — cycle 3 is the cold check.

## Criteria status

| AC | status | evidence |
|---|---|---|
| 1 | `met-with-evidence` | compaction runs with usage under the trigger, and on a first turn where it is `None` |
| 2 | `met-with-evidence` | a refusal can only follow a compaction attempt |
| 3 | `met-with-evidence` | the turn after a refusal is not refused again |
| 4 | `met-with-evidence` | short messages keep working; the sub-floor case ends rather than looping |
| 5 | `met-with-evidence` | three causes, three messages, each naming its own |
| 6 | `met-with-evidence` | said once, then the session ends |
| 7 | `met-with-evidence` | **transcript byte-identical**; a fitting turn compacts nothing and prints nothing |
| 8 | `met-with-evidence` | reports through the existing lines; a planted fact survives |

**Suite: 266 passed** (255 + 11), hermetic. **Transcript unchanged and not regenerated.**

## What the fix does

`compaction.compact_to_fit` walks the same `KEPT_PAIRS_LADDER`, calls the same
`compacted_history`, applies the same `bounded` — only the *reason* for running is different.
It takes an `overhead` in characters for the system prompt, which rides in every request but
is held outside `messages` where compaction cannot reach it.

At the call site, a payload that will not fit now compacts and re-checks before any refusal.
Both AC 1 and AC 2 fall out of that ordering.

**A bug this introduced, caught before it shipped.** `before = len(messages)` indexes into the
history as it was; compaction replaces it with a shorter list, so the existing
`del messages[before:]` rollback would have deleted the wrong slice. `before` is recomputed as
`len(messages) - 1` after compaction — the user's line is still last, and **that is the only
thing a refusal rolls back.** Whatever compaction achieved is kept, which is what AC 3
actually needs: undoing it would send the next turn into the same wall.

## The measured before and after

Cycle 1's AC 1 scenario, unchanged, run against both:

| | before | after |
|---|---|---|
| compactions | 0 | 1 |
| turns reaching the model | 5 | 6 |
| refusals | 1 | **0** |

The refusal at 287 tokens over is gone, because the compaction that takes the payload from
1939 tokens to 226 now actually runs.

And the reproduction from cycle 1 — four short messages at a 200-token context:

```
before: 4 refusals, "try a shorter message", model never reached, 0 compactions
after:  1 message, "this session cannot continue - ... nothing you type will fit", then out
```

## A decision that goes past the literal criteria

**The sub-floor case now ends the session.** No criterion says "exit", so this is a judgement
and it is recorded rather than slipped in.

The reasoning: AC 6 asks that the user be told plainly *"rather than discovering it by
retrying"*. Printing the same unhelpable line at every prompt **is** that discovery — cycle 1
watched it four times in a row. And AC 4 says no session may reach a state where every
message is refused; where the fixed part alone exceeds the context, the only way that
statement can be true is if the session does not continue to refuse.

It also stops a real cost: the first implementation ran a compaction per doomed message,
which on a live backend is a model call each time, summarising a history that cannot help.
The cause is now computed *before* compacting, so a hopeless session spends nothing.

**This is the thing for cycle 3 to attack.** If ending the session is wrong, it is wrong here
and the criteria as written would not catch it.

## What is deliberately not covered

**The three new messages are not in the golden transcript.** It contains no `too large`
scenario at all — the refusal path was never scripted there, before or after this change.
That is why AC 7 passed with the transcript byte-identical, and it is a gap in the record
rather than a pass: three new user-visible messages exist that the behaviour file does not
know about. Cycle 3 adds scenarios for them and regenerates deliberately, reading the whole
diff as a diff.

## Nothing here needs an answer from Kaushik

## Why this cycle does not declare convergence

Cycle 2 wrote the code and cycle 2 judged it. That pass has been wrong in each of the last two
issues — #40's AC 7 and #41's AC 9, both marked met by the cycle that implemented them, both
broken by one hostile input. Cycle 3 reads #42's criteria from GitHub before the diff and
before this log, and attacks each rather than confirming it.
