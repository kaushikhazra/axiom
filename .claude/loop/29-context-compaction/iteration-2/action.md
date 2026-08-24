# Action

Four things in scope now, not one — A, B, C, D (see `goal.md`). Take them in the order they're understood, not all at once.

**This cycle: A only.**

Reproduce the bug first, live, before changing anything — confirm the failure is real and repeatable on the current code, not a one-off. Use `AXIOM_DEBUG_MAX_CONTEXT` with a small value and a run of natural, varied (non-repetitive) messages designed to trigger at least two separate compaction passes, ending on a question about a fact stated in the very first message. Save the transcript.

Then implement the fix: in `compacted_history()`, when `older` already starts with a `system`-role message (an existing summary from a prior pass), do not hand it to `compact()` again. Carry that prior summary's text forward verbatim, summarize only the genuinely new messages after it, and combine old-summary-text + new-summary-text into the resulting system message. Apply this at *every* rung `maybe_compact()` tries — the ladder calls `compacted_history()` up to four times per trigger (kept_pairs 10, 5, 2, 0), and any of them could be handed an `older` that starts with a prior summary.

Re-run the exact same live reproduction from step one against the fixed code. The fact must now survive across 2+ real compaction passes. Then run the full `pytest` suite — this touches `compacted_history()`, which existing tests exercise directly; confirm nothing regresses, and add a test that a `system`-role message in `older` is passed through rather than re-summarized.

Do not start B, C, or D this cycle. Note in the log which of them the A fix incidentally touches or doesn't, but leave them for later cycles.

Evidence to produce: the live "before" transcript showing the bug reproduced · the live "after" transcript, same scenario, same fact, now answered correctly across 2+ passes · full suite pass count.
