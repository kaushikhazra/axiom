# 29-context-compaction, iteration 2

## Goal

> Fix context loss in compaction (#29, kaushikhazra/axiom) across all of the ways it can happen, not just the one first observed:
>
> **A — repeated re-summarization.** A later compaction pass folds an *already-compacted* `system`-role summary into `older` and re-summarizes it alongside new turns, diluting or dropping facts the first summary preserved. Confirmed live: a real "teal" fact survived one compaction, then was lost after a second. Applies at every rung of the escalation ladder, not just a single "normal" path.
>
> **B — single-pass fidelity under load.** A `compact()` call is a soft prompt instruction, not a guarantee. Every live proof so far summarized 1–13 pairs with one or two facts; none stress-tested a single pass over many pairs carrying many distinct facts.
>
> **C — a single request can still overflow after compaction.** Already demonstrated live: Ollama silently truncated an oversized message (`prompt_eval_count: 10002` against a 20,000 ceiling), dropping a fact with no error raised. Two causes feed this: an individually huge *kept* raw message, or `estimated_tokens()`'s character-based guess accepting a rung that doesn't actually fit once really sent.
>
> **D — long-run summary growth.** Whatever fixes A by carrying prior summaries forward verbatim risks that summary text itself growing across many compaction cycles in a very long session. Does not need to be solved outright — needs to be named as a known, accepted limit, with a stated reason it's out of scope for tonight if it isn't fixed.
>
> Finished when: a live, real conversation survives two or more compaction passes and still correctly answers a question about a fact from the first message (closes A) · a live run compacts a single pass over a large, multi-fact history and every fact is still answerable afterward (closes B) · a live run shows a request that would have overflowed post-compaction either not being sent as an overflowing request, or failing loudly rather than silently truncating (closes C) · D is explicitly addressed in the log, either fixed or named as an accepted, reasoned limit · the full test suite is green.
