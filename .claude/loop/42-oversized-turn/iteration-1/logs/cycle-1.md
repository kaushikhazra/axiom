# Cycle 1 — 2026-08-26, 02:58 IST

No production code. The failure reproduced, the boundary bisected, and one number in this
loop's own scaffold corrected.

## Criteria status

All eight `not-started`. Nothing is built. What follows is what a fix has to satisfy.

Suite: **255 passed**, hermetic. Transcript copied to `.tmp/transcript-baseline-42.txt`.

## The reproduction

`AXIOM_DEBUG_MAX_CONTEXT` unset, `context_length: 200`, four short messages:

```
error: this turn is about 7 tokens too large to send - try a shorter message, or start a new session
error: this turn is about 6 tokens too large to send - try a shorter message, or start a new session
error: this turn is about 5 tokens too large to send - try a shorter message, or start a new session
error: this turn is about 5 tokens too large to send - try a shorter message, or start a new session

turns the model was actually asked : 0
compactions that ran               : 0
```

Four messages, four refusals, **the model never reached once**. The overage shrinks as the
message shortens — 7, 6, 5 — and stops at 5, because what remains is fixed. The advice cannot
be taken.

## A correction to this loop's own scaffold

`assumption.md` and `loop.md` both say the system prompt costs "~163 tokens". **It is 205.**

The prompt is 616 characters; under `too_large`'s `SAFE_CHARS_PER_TOKEN = 3` that is 205
tokens, and `estimated_tokens` puts it at 154. The 163 figure came from #41 cycle 2, measured
on a shorter draft before the prompt gained its fetch-timeout line. Corrected in
`assumption.md` rather than left to mislead a later cycle — this is the second time in two
issues that a number was quoted from the wrong divisor or the wrong draft.

## The boundary, bisected

Smallest context each payload fits in, prompt included:

| payload | fits from |
|---|---|
| empty message | **205 tokens** |
| one word | 207 |
| a short question | 215 |
| 200 characters | 272 |
| prompt + one exchange + "hello" | 278 |
| 2000 characters | 872 |

**205 is the floor.** Below it nothing works, whatever the user types.

And what the real models actually offer:

| model | effective context |
|---|---|
| qwen2.5:7b | 32,768 |
| qwen2.5-coder:7b | 32,768 |
| gemma4:e2b | 131,072 |
| ornith:9b | 48,266 |

**Every real model is at least 160× the floor.** So the sub-floor case is reachable only
through `AXIOM_DEBUG_MAX_CONTEXT`. That matters for how much weight AC 6 should carry, and it
is recorded so a later cycle does not over-build for a case no real user meets.

## Two routes in, and only one of them is broken

**Route B — the history outgrows the context.** Measured on a 1000-token context with usage
above the trigger: compaction ran twice, three turns reached the model, **zero refusals**.
This already works, and #29 and #32 are why.

**Route A — the size check refuses and compaction never ran.** This is the whole issue, and
the decisive measurement is AC 1's:

```
context 2000, compaction triggers above 1800 reported tokens
usage held at 1750 - just under - so maybe_compact declined every turn

refusals: 1     "this turn is about 287 tokens too large to send"
last sent payload     : 1939 safe tokens
after full compaction : 226 safe tokens against a 2000 context
*** compaction WOULD have rescued it: True ***
```

The turn was refused while a compaction that would have taken it from 1939 tokens to 226 was
never attempted, because the *previous* turn's reported usage happened to sit under a
threshold. That is AC 1 in one measurement, and it is not a small margin — it is an eightfold
reduction that was available and unused.

Related: `running_usage` is `None` on the first turn of every session, so a large first
message is refused with compaction never having run. There, though, the refusal is **correct**
and the advice is achievable: there is no history to compact, and the message really is what
is too large. Full compaction of a real history is very effective — 4266 tokens to 25 in the
probe — so when there *is* history, refusing without trying is never right.

## What the fix will be

`too_large` currently refuses and the turn is dropped, with nothing after it. Instead: when
the payload will not fit, **compact because of the size** — the same ladder, driven by the
measurement rather than by last turn's usage — and re-check. That is AC 1 and AC 2 together,
and AC 2's ordering falls out of it, since the refusal can then only happen after compaction
has had its turn.

Reporting it uses the existing `note_compaction` and `note_facts_forgotten` paths unchanged,
which is AC 8 — a second compaction that forgot silently would undo what #32 spent three
cycles building.

When it still will not fit after `kept_pairs=0`, three things are now distinguishable, and
the message should differ between them because AC 5 asks it to name what is actually too
large:

- **the message itself** is the bulk — a shorter one genuinely helps, which is today's advice
  and correct in that case;
- **the conversation** is the bulk but compaction has already run — then say the conversation
  is too large and a new session is the way out;
- **prompt + minimal summary + the message still exceeds the context** — nothing will help,
  and AC 6 says to tell the user plainly rather than let them find out by retrying.

The floor of 205 tokens is what separates the third case from the other two, and it is
computable rather than guessed.

## Nothing here needs an answer from Kaushik
