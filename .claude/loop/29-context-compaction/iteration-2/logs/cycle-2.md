# Cycle 2 — 2026-08-24 18:22 IST

## Infrastructure recovered

Kaushik restarted Ollama (`Get-Process ollama* | Stop-Process -Force` then `ollama serve`). Confirmed independently before relying on it: daemon reachable, and — the check that actually matters, since the daemon staying up didn't predict the last three crashes — a trivial real generation succeeded. His restart log also explains *why* the crashes happened: an RTX 3060 Laptop GPU, 6.0 GiB total VRAM, 5.0 GiB available — genuinely tight for a 7B model under the sustained heavy real-call load this whole session produced. Consistent with "GPU/driver instability from accumulated load," not anything in axiom's code.

## A and B — closed, complete live proof this time

Re-ran the exact scenario from cycle 1 (six natural turns, `AXIOM_DEBUG_MAX_CONTEXT=400`, teal in the first message) all the way through, no interruption:

```
compaction fired at turns: [2, 3, 4, 5] (4 events, + 1 final before the recall question = 5 total)

--- final answer ---
Your favourite colour is teal. Teal is a calming and sophisticated shade that
evokes a sense of tranquility. It can be a great choice for home decor,
wardrobe, and digital projects.

PASS
```

The fact survived **five** consecutive real compaction passes. This is the complete, uninterrupted live run `observe.md` required — not the partial mid-run evidence cycle 1 had to settle for. A and B are met.

Added mocked regression coverage for the specific mechanism (`test_compacted_history_never_resummarizes_an_existing_summary`, `test_compacted_history_carries_summary_forward_with_no_new_turns`) — supporting evidence, per the evidence rules, not what closed A/B on its own. Full suite: 24 passed (was 22; +2 new).

## D — not fixed, but no longer theoretical

The final system message from that same run is worth reading past the PASS: dozens of bullet points spanning every topic across all six turns — bookshelf organizing, three full recipes with ingredients and steps, declining a meeting invite with example phrasing, a stretch routine. Several thousand characters. **This is D actually happening**, not a hypothetical raised during scoping — carrying every summary forward verbatim while compacting on almost every turn (this scenario's tiny context triggers compaction constantly) made the "compacted" history balloon past what its own context budget could hold.

It didn't crash *this* run only because the test script's final recall call didn't pass `options={"num_ctx": ...}` and fell back to Ollama's own default (4096, per the restart log's VRAM-based default) — comfortably larger than the artificial 400 used during the scenario itself. That's a gap in the test script, not evidence D is safe. If the *real* `main()` loop had kept going with this same ballooned summary at the same tiny `num_ctx`, the next real turn would very plausibly hit exactly the "single request still overflows post-compaction" failure mode C already names.

**D is not fixed this cycle.** Named honestly as an observed, real, currently-unmitigated risk — not the "accepted limit, reasoned out" the goal allowed for, because there's now concrete evidence it can actually bite, not just a theoretical concern to wave through.

## C — not started

No time left to do it justice. ~24 minutes remained after A/B's proof and D's write-up, against a 19:06 fail-safe. Starting a genuine investigation into C now would mean either rushing it without real live evidence (exactly what this iteration exists to not do) or leaving it half-finished at the fail-safe with nothing solid to show. Better to stop clean here with A/B genuinely done, and let the next cycle take C with a full budget — plus C and D turned out to be more connected than the original scoping guessed (D's growth is a direct contributor to C's overflow risk), which the next cycle should treat as one investigation, not two separate ones.

## Criteria

| | State | Evidence |
|---|---|---|
| A - never re-summarize a summary | **met** | full live run above, 5 real compaction passes, correct final answer |
| B - single-pass fidelity | **met** | same run — teal survived the very first pass and every one after |
| C - post-compaction overflow | not started | deferred; now understood to be connected to D, not independent |
| D - long-run summary growth | **observed live, not fixed** | the ballooned final summary in this cycle's own run; named honestly rather than claimed safe |

## What is still missing, and is it closable

C, and a real fix for D (or a much more carefully reasoned "accepted limit" than "not yet observed" — that framing no longer holds, since it's now been observed). Both closable — nothing found this cycle suggests either is structurally blocked, just not yet attempted with real time and a stable GPU.

## Assumptions that changed

The GPU/Ollama instability from cycle 1 is resolved (Kaushik restarted it, independently verified). No longer treat every crash as environmental-and-ignorable without a quick health re-check first — but no longer expect it either.

## Goal check

**Not met.** A and B genuinely done. C untouched, D observed but not fixed. Two of four — real progress, not the full goal. Next cycle should treat C and D as one connected problem.
