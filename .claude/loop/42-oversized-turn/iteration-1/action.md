# Action

**Cycle 1 writes no production code.** Reproduce the failure, record the baseline, and
measure the boundary the fix has to work inside. #32 spent its first cycle this way and its
second overturned the plan on the evidence.

## 1. Reproduce it, exactly

`AXIOM_DEBUG_MAX_CONTEXT=200` and a one-word message. Record verbatim:

- what the user sees on the first message,
- what they see on the second, third and fourth,
- whether anything ever changes,
- and whether compaction runs even once.

That is AC 3 and AC 4 failing, and the record of it is what a later cycle measures against.

## 2. Find the boundary

The fix has to know where "too small to continue" begins. Measure, do not reason:

- **What does the system prompt cost**, through `too_large`'s divisor, for a default `Limits`
  and for a long working-directory path? It is the floor under every session.
- **At what `AXIOM_DEBUG_MAX_CONTEXT` does a one-word message start to fit?** Bisect it.
- **At what value does a realistic message - say 200 characters - start to fit?**
- **What do the real models report** for `context_length`? `qwen2.5:7b`, `qwen2.5-coder:7b`,
  `gemma4:e2b`, `ornith:9b`. If every real model is far above the boundary, say so - it tells
  a later cycle how much of this is reachable outside the debug override, and AC 6's wording
  depends on knowing whether a real user can land here.

## 3. Record the baseline

- Full suite and the hermeticity check. Confirm 255 green.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-42.txt`. **AC 7 is
  measured by this file.**
- Record what a normal, comfortable turn prints today - that is AC 7's "unchanged".
- Record what compaction prints when it is triggered by usage: the `compacting older history`
  line and, if the summary is full, `the summary is full - forgetting N`. **AC 8 says a
  size-triggered compaction must report the same way**, so this is the shape to match.

## 4. Probe the ordering AC 1 and AC 2 are about

`maybe_compact` returns immediately when `running_usage is None`, which is every first turn.
Confirm by driving it, and record:

- On a first turn that is too large, does compaction run at all today? (Expected: no.)
- If `maybe_compact` is called with a `running_usage` high enough to trigger, does it
  actually reduce a history that is over the limit, or does the ladder run out?
- With `kept_pairs=0` - compact everything - **how large is the payload still?** That number
  is the floor: prompt + summary + the user's new line. If it still does not fit, no amount of
  compaction helps and AC 6 is the only honest answer.

## 5. Say what the fix will be

One paragraph, no code. Where the second compaction attempt goes relative to `too_large`,
what distinguishes "compact and retry" from "genuinely cannot continue", and what each of
AC 5 and AC 6 says in that case. If the probes show the obvious fix is wrong, say that
instead - that is a better cycle 1 than a plan that survives because nothing tested it.

## Record

Status for all 8 - most will read `not-started`, which is correct for this cycle. Then write
cycle 2's `action.md`.

**Write no questions into it.** Decide, record the decision and the reasoning in the log,
carry on. Nobody is reading between firings.
