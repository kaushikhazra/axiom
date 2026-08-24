# Observe

Record each cycle:

- Where the fix stands: what was tried, whether it held up, and against what evidence.
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

Evidence rules — the bug that started this iteration was found by a real, live, multi-turn run, not a unit test, so the goal check must be settled the same way:

- **A live run is required**: a real conversation, real Ollama, driving at least two separate compaction passes in the same session (`AXIOM_DEBUG_MAX_CONTEXT` is fine for this — it's exactly what it exists for), ending on a question whose answer was only ever in the first message. The transcript is the evidence.
- A unit/mocked test proving the mechanism (e.g. an existing summary is never re-summarized) is good supporting evidence, but does not by itself close the goal — the original bug survived a fully-green test suite and 11/11 mocked+live-single-pass criteria. Mocking is not enough here.
- If a fix changes `compacted_history()`'s shape or `main()`'s wiring, re-run the full `pytest` suite and note the result — do not let a fix for this regress #26/#28/#29's existing criteria.

Goal check:

- **Met** — a live run survives 2+ real compaction passes and still answers correctly, and the full test suite is green. The loop ends.
- **Not met** — report and write the next action.
- **Answer did not move** — report the flat result and stop. Do not run another variant.
