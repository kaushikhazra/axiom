# Action

Reproduce the bug first, live, before changing anything — confirm the failure is real and repeatable on the current code, not a one-off. Use `AXIOM_DEBUG_MAX_CONTEXT` with a small value and a run of natural, varied (non-repetitive) messages designed to trigger at least two separate compaction passes, ending on a question about a fact stated in the very first message. Save the transcript.

Then implement the first candidate fix: in `compacted_history()`, when the portion being compacted (`older`) already starts with a `system`-role message (an existing summary from a prior pass), do not hand it to `compact()` again for re-summarization. Carry that prior summary's text forward verbatim, summarize only the genuinely new messages after it, and combine the two (old summary text + new summary text) into the resulting system message. Everything else about the ladder (kept-window sizes, the trigger, the escalation order) stays as iteration-1 left it.

Re-run the exact same live reproduction from step one against the fixed code. The fact must now survive. Then run the full `pytest` suite — this touches `compacted_history()`, which existing tests exercise directly; confirm nothing regresses, and add a test (mocked is fine for this one, since it's about mechanism, not semantics) that a `system`-role message in `older` is passed through rather than re-summarized.

Evidence to produce: the live "before" transcript showing the bug reproduced · the live "after" transcript with the same scenario, same fact, now answered correctly across 2+ compaction passes · full suite pass count.
