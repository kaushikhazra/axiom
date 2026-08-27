# Cycle 1 — measured the instruction rather than assumed it

2026-08-28 02:18–03:05 IST. Fail-safe 06:18 IST.

**536 tests, green and hermetic** (was 521). 15 new in `tests/test_summary_facts.py`.
**Transcript unchanged** - the instruction never reaches it, because every scenario's summary
comes from a stub.

## Which criteria rest on what

`observe.md` asked for this per criterion, and it is the most important thing in this log.

| criteria | evidence |
|---|---|
| AC 1, AC 2, AC 3 | **live measurement** below, plus `bounded()` tests |
| AC 4, AC 5 | **live measurement only.** No test can settle these |
| AC 6, AC 7, AC 8 | tests - deterministic, no model |
| AC 9, AC 10 | tests, with a stub returning a summary the test wrote |
| AC 11 | **half a test, half a probe** - axiom inventing a summary is testable, a model inventing one is not |
| AC 12 | tests plus the transcript |

## The defect, reproduced live

`qwen2.5:7b`, the original instruction, on a transcript mixing a car registration with the model
explaining what an MMORPG is:

```
- my first car was a maroon Fiat Padmini
- registration number is WB-24-9931
- different topic - I play world of warcraft
- MMORPG stands for massively multiplayer online role-playing game      <- general
- World of Warcraft is the best known example of an MMORPG              <- general
- World of Warcraft was released in 2004 by Blizzard Entertainment      <- general
- I prefer the Alliance
- my main character is a night elf druid called Sylnara
```

**Three of eight slots** in a store bounded at half the window, spent on things the model would
say again unprompted.

## The mistake I nearly made, and what caught it

I changed the wording, re-probed once, saw a worse result, changed it again, probed once, saw
worse again. Three wordings, three single samples, and I was about to conclude the lever did not
work.

Then a scripted edit failed its assert, so a probe ran against the **unchanged** instruction -
and returned 8 bullets where the same instruction had returned 11 a minute earlier. **The
run-to-run variance is as large as the differences I was attributing to wording.** Every
comparison up to that point was noise.

The failed assert is what caught it. A `.replace()` that silently does nothing would have left
me comparing a wording against itself and believing the result.

## The measurement

Six runs per wording per model, same transcript, counting bullets that would be true without the
conversation, and how many of the five user facts survived.

**`qwen2.5:7b`**

| wording | bullets | general | user facts |
|---|---|---|---|
| original | 8.5 | **3.5** (2-5) | 5.0 / 5 |
| changed | 9.7 | **3.8** (3-5) | 5.0 / 5 |

**`gemma4:e2b`**

| wording | bullets | general | user facts |
|---|---|---|---|
| original | 10.8 | **5.0** (4-7) | 4.3 / 5 |
| changed | 5.5 | **0.7** (0-2) | **5.0 / 5** |

## Decision — keep the change

**It is model-dependent, and it is never harmful.**

On `gemma4:e2b` general knowledge falls 86%, and user-fact retention *improves* from 4.3 to 5.0
- less clutter turns out to mean better recall of what matters, which is the whole thesis of
this row observed directly. On `qwen2.5:7b` the difference sits inside the noise and is very
slightly negative on bullet count.

Adopting it is a large win on one model and a wash on the other, and on **neither** does it cost
a user fact - 5.0/5 in every one of twelve runs. That is the case for keeping it, stated with the
numbers rather than with a single flattering sample.

Only two models were measured. `ornith:9b` was skipped - it crashes the server intermittently.

## Decision — no ranker for AC 3, and the reason is not squeamishness

AC 3 wants "the least particular" to go first. `assumption.md` rules out a scorer that guesses
importance. The question is whether an **honest structural signal** exists instead, and I looked
for one properly:

**Role is not a proxy for particularity.** The obvious idea is to summarise user messages and
assistant messages separately and drop the assistant-derived section first - provenance from
ground truth rather than a guess. It does not work, because an assistant turn carries *both* the
general knowledge this row is about *and* the answers to the user's questions, which are as
particular to the conversation as anything the user said. Dropping that section first would lose
"you told me the capital is Canberra" to save "an MMORPG is a genre".

So there is no clean structural signal, and a content-based one would be the heuristic
`assumption.md` forbids. **AC 3 is met the way the instruction meets it** - by keeping general
knowledge out of the store in the first place, where the model cooperates - and `bounded()`'s
middle-drop stays as #32 measured it. Recorded as a decision, not an omission.

## Status — all 12 criteria

| criteria | status |
|---|---|
| AC 1, AC 2, AC 6–AC 12 | `attempted` |
| AC 3 | `attempted`, met by the instruction rather than by ordering - reasoning above |
| AC 4, AC 5 | `attempted`, **model-dependent**, evidenced only by the measurement above |

Not `met-with-evidence`. This is the cycle that wrote the code.

## Cycle 2 will

Cold-read all 12 from GitHub before the diff and before this log. Where to attack:

- **AC 4, AC 5 as written.** They do not say "on some models". Can they honestly be called met
  when one of two measured models ignores the instruction? If not, say so plainly - `observe.md`
  says a criterion that cannot be met as written is an acceptable outcome here.
- **The instruction tests** assert substrings of the instruction. That is intent, not effect, and
  it is exactly the shape - an assertion a wrong implementation also satisfies - that the cold
  read has found in four of the last five rows. Say whether they earn their place.
- **AC 3's decision.** Is the role-is-not-provenance argument actually right? Find a
  counter-example if there is one.
- **The break.** Reverting the instruction should turn *little* red, because an instruction has
  few hermetic consequences. Confirm that and name what does go red - if nothing does, say so,
  because that is the honest measure of how much of this row the suite holds.
