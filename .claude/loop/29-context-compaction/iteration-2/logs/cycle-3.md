# Cycle 3 — 2026-08-24 18:47 IST

## What this cycle did

Started `action.md`'s research half — "investigate what's actually available before committing to a mechanism" for a size check more reliable than the character estimate. Answer, confirmed rather than assumed:

```
$ curl -X POST http://localhost:11434/api/tokenize -d '{"model":"qwen2.5:7b","content":"hello world"}'
404 page not found
```

`ollama.Client` exposes no tokenize method either (`chat, close, copy, create, create_blob, delete, embed, embeddings, generate, list, ps, pull, push, show, web_fetch, web_search` — nothing token-count-related that doesn't require a full generation). **No real pre-send token count is available from Ollama at all.** `estimated_tokens()`'s character-based guess (cycle-1-of-iteration-1's `CHARS_PER_TOKEN_ESTIMATE = 4`) is the practical ceiling for choosing an escalation rung without adding a separate tokenizer dependency per model family — a real, useful answer, even though it doesn't move C or D forward on its own.

## Why nothing else was attempted

19 minutes remained against the 19:06 fail-safe when this cycle started; roughly 15 after the research above. Every real step left for C or D — reproducing C's overflow with a deliberately-grown summary, implementing a cap on D's unbounded growth, proving either live — has taken multiple minutes per attempt in every prior cycle tonight, several with real-world surprises along the way (the crash investigation, the plan changing under live evidence in cycle 1). Starting any of them now would mean either rushing past the fail-safe with something unproven, or leaving code changed and unverified at the deadline. Cycle 2 already established the standard for this iteration: don't claim more than the evidence supports. Stopping clean here is that standard applied to time pressure, not just to test results.

## Criteria — unchanged from cycle 2

| | State |
|---|---|
| A - never re-summarize a summary | met (cycle 2, full live proof) |
| B - single-pass fidelity | met (cycle 2, full live proof) |
| C - post-compaction overflow | not started (no tokenize API exists, confirmed; reproduction not attempted) |
| D - long-run summary growth | observed live (cycle 2), not fixed |

## Regression check

Unchanged since cycle 2 — no source edits this cycle. 24/24 passing as of the last commit.

## Goal check

**Not met — fail-safe reached.** A and B are genuinely done, with complete live proof each. C and D are not, and this cycle is honest that "not enough time left to do it properly" is the reason, not a hidden difficulty or a code blocker. The loop stops here per its own rule rather than pushing past the deadline.

## What's left, concretely, for whoever picks this up next

Both real, both scoped, both understood well enough to start immediately rather than re-investigate from zero:

1. **C** — reproduce with a scenario that deliberately grows the carried-forward summary large (many turns, tiny `AXIOM_DEBUG_MAX_CONTEXT`, past where cycle 2's run stopped), and confirm whether it actually overflows and gets silently truncated, matching the mechanism already proven live with a raw oversized message earlier tonight.
2. **D** — a cap on the carried-forward summary's size, triggering a fresh (bounded) re-compaction of the summary itself once it would exceed the cap — this is a deliberate, bounded exception to "never re-summarize a summary," not a contradiction of it: A's fix stops *accidental*, uncontrolled re-summarization; D's fix would be a *deliberate*, size-triggered one, using the same anti-narrative-drift instruction B already proved.
3. Given cycle 2's finding, these are one investigation, not two — C is very plausibly just D's failure mode showing up downstream.
