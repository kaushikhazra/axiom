# Cycle 2 — the cold read, and the row has not converged

2026-08-28 03:06–03:30 IST. Fail-safe 06:18 IST.

Criteria read from `gh issue view 62` **before** the diff and before cycle 1's log.
**536 tests, green and hermetic.** Transcript unchanged.

**This row is not done.** Six of twelve criteria are met; six are not, and three of those were
never attempted. Cycle 3 has work and the fail-safe has nearly three hours left.

## AC 5 — not met, and never addressed

Cycle 1 never probed it. It is a different claim from AC 4 - about duplication between the
summary and the surviving turns, not about general knowledge - and the instruction change does
nothing for it.

A transcript where a deadline is stated, acknowledged, asked about, and answered:

```
gemma4:e2b                                  qwen2.5:7b
* my project deadline is the 14th of March  - my project deadline is the 14th of March
* the 14th of March                         - Noted, the 14th of March.
* Your project deadline is the 14th of March - what is my deadline again?
                                            - Your project deadline is the 14th of March.
```

**The same fact three and four times**, in a store bounded at half the window. Worse than the
row's original complaint: at least "an MMORPG is a genre" was a *different* fact.

And there is a structural reason it cannot be met as things stand. **`compact()` is given only
the pairs being summarised**, never the turns being kept - so it cannot know what it would be
duplicating. AC 5 as written needs the kept turns passed in as context. That is a real,
tractable change and cycle 3's main work.

## AC 11 — not met

*"A conversation with nothing worth summarising produces no summary rather than an invented
one."* Four turns of pure pleasantries:

```
gemma4:e2b            qwen2.5:7b
* hi                  - hi
* Hello! How can I... - Hello!
* just saying hello   - I can help you today
* Of course...        - just saying hello
```

Neither *invented* anything - they transcribed. But the criterion is that nothing worth
summarising produces **no summary**, and both produced one. Not met on either model.

## AC 4 — not met as written, and cycle 1 said as much

The criterion does not say "on some models". Cycle 1 measured `qwen2.5:7b` at 3.5 general
bullets before and 3.8 after - inside the noise. **On that model the criterion is not met and
the change did not make it met.**

Recording it as met because the code changed would be exactly the rounding-up `action.md`
forbade. AC 1 and AC 2 inherit the same problem: both are about what the summariser keeps in
preference to what, and both rest on an instruction one of two measured models ignores.

## The break — the honest measure

Reverting the instruction turns **exactly two tests red**, and both assert *substrings of the
instruction*. `tests/test_compaction.py` mentions `COMPACTION_INSTRUCTION` only in a comment.

So the suite holds **nothing** about this row's actual behaviour. That is not a defect to fix by
writing more stub tests - a stub cannot demonstrate what a summariser does - but it must be
stated rather than hidden behind a green run of 536.

Which also means the two instruction tests are decoration in the sense the cold read keeps
finding: they will pass forever while the behaviour rots. They earn a small place as a record of
intent, and the log has to carry the effect.

## AC 3's decision — re-examined, and it holds

Cycle 1 argued role is not a proxy for particularity because an assistant turn carries both
general knowledge and the answers to the user's questions. Looked for a counter-example and the
AC 5 probe supplies the opposite - a *confirmation*: `Your project deadline is the 14th of
March` is assistant-authored and maximally particular. A rule that dropped assistant-derived
bullets first would drop it. The argument stands.

## Status — all 12 criteria

| criteria | status | evidence |
|---|---|---|
| AC 1 | **not met as written** - model-dependent | live measurement |
| AC 2 | **not met as written** - model-dependent | live measurement |
| AC 3 | `met-with-evidence`, by decision not ordering | reasoning + `bounded()` tests |
| AC 4 | **not met** on `qwen2.5:7b` | six-run measurement |
| AC 5 | **not met** on either model, never attempted | probe above |
| AC 6 | `met-with-evidence` | test |
| AC 7 | `met-with-evidence` | test |
| AC 8 | `met-with-evidence` | test |
| AC 9 | `met-with-evidence` | test |
| AC 10 | `met-with-evidence` | test |
| AC 11 | **not met** on either model, never attempted | probe above |
| AC 12 | `met-with-evidence` | test + transcript |

## Exit — none. Cycle 3 continues.

Not exit 1: six criteria are unmet. Not exit 2 or 3: the fail-safe is at 06:18 and there are
nearly three hours left, with two unmet criteria that have **never been attempted** and a clear
route for each.

Nothing is merged. The branch holds a change that is a measured improvement on one model and
neutral on the other, and it stays there until the row is done or the clock runs out.
