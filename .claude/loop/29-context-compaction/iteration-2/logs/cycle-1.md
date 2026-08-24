# Cycle 1 — 2026-08-24 17:36 IST

## Where this cycle started

Iteration-1 converged 11/11 on mocks and small live proofs. Manual verification by Kaushik then found a real bug the loop's own evidence bar had missed: a fact ("teal") survived one compaction pass and was lost after a second. Scope was widened before this cycle started to four distinct context-loss vectors (A/B/C/D, see `goal.md`). This cycle targeted A only, per the prior `action.md`.

## The plan changed under live evidence, honestly, mid-cycle

Reproducing A live (small `AXIOM_DEBUG_MAX_CONTEXT`, six natural varied-topic turns, instrumented to print exactly what `compact()` receives) surfaced something the plan didn't anticipate: **the fact was lost on the very first-ever compaction pass**, not only on a repeated one. Direct evidence — turn 3's `compact()` input already shows the prior summary with teal missing:

```
"system: Summary of earlier conversation: The conversation focused on organizing
a small bookshelf by genre and author. Here are the key points: ..."
```

That summary was produced compacting turns 0–1 (teal + a bookshelf question). The model chose to keep the longer, more detailed bookshelf topic and dropped the one-line teal statement. That is **B** (single-pass fidelity), not A — and it happens *before* A ever gets a chance to compound anything. Fixing A alone would not have made the original failing scenario succeed. Adjusted scope to fix A and B together this cycle rather than defer B artificially when the evidence showed they're empirically inseparable in ordinary use.

## Fix A — never re-summarize an existing summary

`compacted_history()`: if `older` already starts with a `system`-role message (a prior pass's summary), carry its text forward verbatim and only `compact()` the genuinely new messages since then, appending rather than re-compressing. Applies uniformly regardless of which ladder rung calls it, since the check is inside `compacted_history()` itself, not duplicated per rung.

## Fix B — structural extraction instead of narrative summary

`COMPACTION_INSTRUCTION` rewritten: bulleted, one-fact-per-line extraction, explicit instruction that an early brief statement is exactly as important as a later detailed topic, no narrative summarization. The prior instruction already *asked* for facts to be preserved but produced flowing prose that naturally emphasized the most recent/substantive topic.

## Live evidence the fixes work, and why it's not complete

Same six-turn scenario, same tiny `EFFECTIVE_CONTEXT=400`, against the fixed code:

```
[turn 2] COMPACTED (kept_pairs=0)
  -> system message now: 'Summary of earlier conversation: - My favourite colour is teal, by the way.
     - I really like how calming it looks.
     - Teal is indeed a very soothing and elegant color.
     - It combines the calmness of blue'
[turn 3] COMPACTED (kept_pairs=0)
  -> system message now: 'Summary of earlier conversation: - My favourite colour is teal, by the way.
     - I really like how calming it looks. ...'   (UNCHANGED from turn 2)
```

Direct evidence for both fixes: B — teal survives the *first* compaction pass now, as the first bullet, not dropped in favour of a longer topic. A — the summary carried forward **byte-identical** from turn 2's compaction to turn 3's, proving the "never re-summarize" path fired and did not touch already-captured content.

**What's missing: a complete run reaching the final recall question.** Three consecutive attempts crashed partway through — not at the same point twice:

1. Second `compact()` call (a re-summarization-path call)
2. First `compact()` call (the original-summarization path)
3. The very first, ordinary `chat()` call, before any compaction logic ran at all

`ollama._types.ResponseError: llama-server process has terminated ... CUDA error: shared object initialization failed`, each time. The daemon (`/api/version`) stayed healthy and reachable throughout; only the per-model worker process crashed, and recovered on its own after the first two crashes but not by the third attempt. The failure point moving backward each retry — ending on the *simplest possible call* — rules out anything about axiom's compaction logic or content triggering it: this is GPU/driver-level instability, likely accumulated from many hours of heavy real model calls this session, degrading rather than recovering by the third attempt.

**This blocks completing A and B's live proof per `observe.md`'s own evidence bar** ("a live run is required... does not by itself close A, B, or C"). What exists is strong, direct partial evidence (both mechanisms observably working, mid-run, on the exact scenario that failed before the fix) — not the complete run-to-recall-answer proof the bar demands. Not claiming A or B met on partial evidence; that would be exactly the kind of self-grading the loop's own rules exist to prevent.

## Criteria (informal - not #29's original 11, this iteration's own four)

| | State | Evidence |
|---|---|---|
| A - never re-summarize a summary | **attempted, strong partial live evidence, not fully proven** | fixed code; teal preserved unchanged across 2 real compaction passes; GPU crash blocked reaching the final recall check |
| B - single-pass fidelity | **attempted, strong partial live evidence, not fully proven** | same evidence — teal survived the *first* pass, which is B's specific claim |
| C - post-compaction overflow | not started | deferred, per this cycle's own scope |
| D - long-run summary growth | not started, but newly relevant | fix A's "carry forward verbatim, append" is exactly the mechanism D warned about — the summary *did* grow (concatenating) across the two observed passes. Not yet a problem at 2 passes; worth watching once C or a longer run is tested. |

## What is still missing, and is it closable

A full, uninterrupted live run through to the recall answer — blocked by infrastructure, not by anything the loop can fix in `src/`. Closable once the GPU/model-worker is stable again; not closable by writing more code.

## Assumptions that changed

**A new one, load-bearing for future cycles:** the local Ollama/GPU state is currently unreliable after a long session of heavy real-model use — failures move to different call sites on each retry and are worsening, not self-healing. Retrying blindly is not the right response past 2–3 attempts.

## Regression check

Full mocked suite (no real Ollama calls, unaffected by the GPU issue): `pytest tests/` — 22 passed, no regressions from either fix.

## Goal check

**Not met.** Real progress on A and B, evidenced but not to the bar this iteration set for itself. C and D untouched. Flagging the infrastructure blocker to Kaushik directly rather than continuing to retry against a degrading GPU state.
