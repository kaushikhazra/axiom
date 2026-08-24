# Observe

Record each cycle:

- Where each of A, B, C, D stands: not started / attempted / fixed-live-evidenced / named-as-accepted-limit. All four get a line every cycle, even "no change."
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

Evidence rules — the bug that started this iteration was found by a real, live, multi-turn run, not a unit test, so each of A/B/C must be settled the same way:

- **A live run is required for A, B, and C.** `AXIOM_DEBUG_MAX_CONTEXT` is fine for this — it exists for exactly this purpose. Natural, varied sentences only — repeated/near-identical filler sent the model into a degenerate loop earlier this session; that is a real hazard for these tests too.
- A unit/mocked test proving the mechanism (e.g. an existing summary is passed through, not re-summarized) is good supporting evidence, but does not by itself close A, B, or C — the original bug survived a fully-green test suite and 11/11 mocked-plus-live-single-pass criteria. Mocking is not enough on its own here.
- **D does not need a live fix.** It needs an honest decision, recorded in the log: either a concrete mitigation with evidence it works, or an explicit statement of why it's an accepted limit for now and what would trigger revisiting it.
- If a fix changes `compacted_history()`'s shape, `maybe_compact()`'s ladder logic, or `main()`'s wiring, re-run the full `pytest` suite and note the result — do not let a fix here regress #26/#28/#29's existing criteria.

Goal check:

- **Met** — A, B, C each have live evidence they're fixed; D is either fixed with evidence or explicitly named as an accepted limit with a stated reason; full suite green. The loop ends.
- **Not met** — report which of A/B/C/D moved and which didn't, and write the next action.
- **Answer did not move** — report the flat result and stop. Do not run another variant.
