# Cycle 2 — 2026-08-24 14:32 IST

## Where the artifact stands

`src/axiom/__init__.py` wires both cycle-1 building blocks into `main()`: `running_usage` tracked across turns from the real `prompt_eval_count + eval_count`, `maybe_compact()` checked before every send, `compacted_history()` implementing the 10 -> 5 -> 2 -> 0 ladder.

## Live proof, real client, real `compact()` calls — the ladder actually walking rungs

Rather than burn through ~30k real tokens of conversation to cross a genuine 90%-of-32768 threshold, tested the real functions with a deliberately small `effective_context`, per the action's own suggestion. First attempt (`EFFECTIVE_CONTEXT=50`) was too aggressive — every non-zero rung failed, landing straight on the floor without proving intermediate levels work. Recalibrated to 150 and instrumented every rung:

```
total pairs: 13, threshold (90% of 150): 135
  kept_pairs=10: estimated 223 tokens -> too big, escalate
  kept_pairs=5: estimated 201 tokens -> too big, escalate
  kept_pairs=2: estimated 138 tokens -> too big, escalate
  kept_pairs=0: estimated 62 tokens -> FITS, chosen
```

A second, separate `maybe_compact()` call in the same script — same inputs, fresh `compact()` calls — landed on `kept_pairs=2` instead of 0. **`compact()`'s output length varies between calls, since it's a real, non-deterministic LLM generation** — the same scenario can land on a different rung run to run. Worth recording: the escalation ladder's "does this fit" check is itself checking a quantity that isn't perfectly reproducible. It still always converges to *something* that fits, or reaches the guaranteed floor — just not always the identical rung twice.

That second run also gave better evidence than cycle 1's isolated proof: recall from a **partially** compacted history (2 pairs kept raw, everything else compacted) rather than the fully-compacted case:

```
maybe_compact() chose kept_pairs=2
--- recall check ---
You mentioned that your favorite color is teal.
```

"Teal" was in pair 0 — well outside the 2 kept pairs — so this genuinely tests recall from the compacted portion, not the raw one.

## Two real regressions found and fixed

`running_usage` reads `last_chunk.prompt_eval_count` / `.eval_count` unconditionally after every successful turn. Three fake `Chunk` objects across two existing test files predated this and didn't have those attributes — `tests/test_context_window.py` (2 sites) and `tests/test_interrupt.py`'s `_chunk()` helper. All three failed with `AttributeError: 'Chunk' object has no attribute 'prompt_eval_count'` the moment this cycle's wiring landed. Same class of regression as #28 cycle 2's `FakeClient.show()` gap — a new field `main()` now reads unconditionally breaks any fake that predates it. Fixed by adding both fields (`1, 1` — small, non-zero, deliberately uninteresting values) to all three.

One test-scenario miscalibration, not a code bug: the first AC 6 test used a `* 200` content multiplier intended to make "kept" pairs dominate the space, but overshot so badly that even the guaranteed-fit floor (`kept_pairs=0`) was needed — never demonstrating a *non-zero* rung being chosen despite dominating the space, which was the actual point of AC 6. Rewritten with exact, computed sizes (100-char kept entries, a 1-char summary, an explicit threshold) instead of a guessed multiplier, so the rung landed on is provable by arithmetic, not guessed into working.

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 90% trigger, compact to 10 pairs | **met — new** | `test_main_prints_visibility_line_when_compaction_triggers`; live ladder walk above |
| 2 below threshold, no compaction | **met — new** | `test_maybe_compact_leaves_history_untouched_below_the_trigger`, `test_main_does_not_print_a_visibility_line_below_threshold` |
| 3 escalate to 5 pairs | **met — new** | live ladder walk shows the rung tried and rejected in sequence |
| 4 escalate to 2 pairs | **met — new** | same; also the live recall run landed on 2 |
| 5 escalate to 0 (compact everything) | **met — new** | live ladder walk, first run; `test_maybe_compact_escalates_past_a_level_that_still_does_not_fit` |
| 6 still compacts even when kept pairs dominate | **met — new** | `test_maybe_compact_still_compacts_older_pairs_even_when_kept_pairs_dominate`, sizes computed exactly |
| 7 model can answer from compacted portion | met | cycle 1 (fully compacted) + this cycle's live run (partially compacted, 2 pairs kept) |
| 8 compacted history uses fewer tokens | met | cycle 1 |
| 9 visibility when compaction happens | **met — new** | integration test above |
| 10 stays compacted, no re-expansion | **met — new** | `test_compacted_history_persists_and_does_not_re_expand` — turn 3's request carries the summary marker, not the original raw pair |
| 11 fewer than 10 pairs, nothing to compact | **met — new** | `test_compacted_history_returns_unchanged_when_nothing_is_older` |

**11 of 11 met.**

## Movement

All 9 remaining criteria closed in one cycle — both hard unknowns were already solved in cycle 1, so this cycle was control flow over working pieces, exactly as predicted. Two real regressions caught by the existing suite the moment the wiring landed; one test-scenario fix where the test's own numbers, not the code, were wrong.

## Assumptions that changed

None.

## Goal check

**Met.** All 11 acceptance criteria in issue #29, each with evidence. No more cycles needed for this iteration.
