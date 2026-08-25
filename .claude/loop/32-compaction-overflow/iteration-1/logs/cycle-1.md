# Cycle 1 - 2026-08-25 09:37 IST

Probe cycle. **No production code.** #32 reproduced in a real session, the overflow
behaviour measured, and one wrong reading caught by testing it.

Baseline: `src/` **1246 lines**, **179 tests** green and hermetic.

## #32 reproduced

A real session, `qwen2.5:7b`, `num_ctx=700`, twenty natural and varied turns - varied
deliberately, because #29 found repeated filler sends a small model into a degenerate loop
that looks like this bug and is not.

**The carried-forward summary grows monotonically, at every pass:**

```
279 → 712 → 1005 → 1224 → 1446 → 2129 characters
```

| turn | kept_pairs | summary chars | history messages |
|---|---|---|---|
| 8 | 10 | 279 | 21 |
| 11 | 5 | 712 | 11 |
| 12 | 2 | 1005 | 5 |
| 15 | 2 | 1224 | 5 |
| 18 | 2 | 1446 | 5 |
| 20 | **0** | **2129** | **1** |

The last row is the whole issue. The ladder reached its floor, `kept_pairs=0`, and history is
**one message** - the summary alone, at 2129 characters. Measured against this session's own
`num_ctx=700` and the character-per-token figures below, that is **roughly 550-690 tokens of
a 700-token window**. One more pass and there is nothing left to compact but the summary
itself, which today's code never does.

**The planted fact survived**: "Your cat is named Biscuit and she is ginger." #29's
carry-forward is working, and that is the baseline AC 2 must not lose.

## What happens at the limit: silent, and detectable

A 12,404-character summary-shaped payload, sent at three context sizes:

| num_ctx | prompt_eval_count | raised |
|---|---|---|
| 512 | 258 | no |
| 1024 | 514 | no |
| 4096 | 2050 | no |

**No exception at any size.** All three replies engage confidently with "the pattern" - the
model answering from a prompt it never fully saw, which is #29's silent truncation confirmed
for the summary case.

**And `prompt_eval_count` reveals it.** A payload of ~3,700 real tokens comes back reported as
258. That is AC 4's mechanism, and it is sound: sent far more than was evaluated.

## The reading I got wrong, and how

258, 514 and 2050 are almost exactly half of 512, 1024 and 4096. The obvious conclusion is
that the usable prompt budget is `num_ctx / 2`, and I nearly recorded it.

Two controls said otherwise:

- 360 characters at `num_ctx=4096` reported **100** - its true size, not 2048.
- 2,720 characters at `num_ctx=1024` reported **630** - above half, below the full window.

So the budget is the **whole** `num_ctx`. The half figure is what truncation *leaves*, not a
limit it enforces. Recording it as a limit would have made AC 3 twice as conservative as it
needs to be and compacted sessions that had plenty of room.

Two probes, three minutes, and a wrong number caught before anything was built on it.

## The token question: no tokenizer, but a measurable error

The `ollama` client exposes no `tokenize` or `count`. `embed` exists but this server answers
`501 This server does not support embeddings`.

So `estimated_tokens` stays a character count - but its error is now measured rather than
assumed:

| content | chars | chars//4 | real | chars/token |
|---|---|---|---|---|
| prose | 864 | 216 | 222 | 3.89 |
| code | 768 | 192 | **245** | **3.13** |
| addresses | 1128 | 282 | 294 | 3.84 |

**It underestimates in every case**, worst at 21% for code. That is the dangerous direction
for an overflow check - it says a payload fits when it does not. A conservative divisor is
**3**, not 4, and AC 3 can be met with a measured margin rather than a guess.

Note the real counts include chat-template overhead, so the true underestimate is slightly
smaller than these figures suggest. It is still an underestimate in every sample.

## Criteria status

All 6 `not-started` - nothing built. What this cycle bought:

1. `not-started` - the growth it addresses is now measured, not asserted
2. `not-started` - the baseline it must preserve is demonstrated: a planted fact survives today
3. `not-started` - the budget is the full `num_ctx`, and the estimate's error is measured
4. `not-started` - the mechanism is confirmed to work: truncation is silent but visible in
   `prompt_eval_count`
5. `not-started`
6. `not-started` - reproduced

## Goal check

**Not met.** Correct for a probe cycle.

## Incidental, worth Kaushik seeing

The `ollama` client exposes **`web_search` and `web_fetch`** methods. #35 shipped `ddgs` and
`trafilatura` for that, at 17 and 18 packages. This loop is not the place to act on it, and
#35's dependency decision was made deliberately with its cost recorded - but if Ollama's own
web tools work without a key, that is a smaller footprint for the same criteria, and worth a
look sometime.
