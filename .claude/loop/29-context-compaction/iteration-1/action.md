# Action

Both hard unknowns are solved. Wire them into `main()`.

Before each send, use the running total from the *last* response (`prompt_eval_count + eval_count`, cycle 1's finding) against `effective_context` to decide whether to compact this turn. Track that running total across the loop — it doesn't exist as state yet.

Implement the escalation ladder as its own function, something like `history_to_send(messages, client, model, threshold) -> list[dict]` — given the current `messages` list and a decision that compaction is needed, try keeping the last 10 pairs intact and compacting everything older via `compact()`; if the result would *still* not fit (check the same way — you may need a cheap size estimate before actually sending, since you won't have a fresh `prompt_eval_count` for a hypothetical payload; character length as a rough proxy is acceptable here, doesn't need to be exact), drop to 5 pairs kept, then 2, then 0 (compact everything, append only the new message). AC 6 — compact the older portion even when the kept pairs alone dominate the space — falls out of this naturally if the ladder always compacts "everything older than the currently kept window" rather than checking whether that's worthwhile first.

A "pair" is 2 entries in `messages` (one user, one assistant) — the last 10 pairs means the last 20 entries, not 10.

Wire AC 9's visibility: when compaction happens, print something before the reply (which level it compacted to, e.g. "compacting older history (kept: 5)..."). AC 11's boundary (fewer than 10 pairs total) should fall out for free if the ladder just looks at `len(messages)` before trying to compact anything older than the kept window - there's nothing older, so nothing happens.

Target AC 1, 2, 3, 4, 5, 6, 9, 11. AC 10 (compacted stays compacted, doesn't re-expand) should also fall out naturally if the ladder actually *replaces* the compacted portion of `messages` in place rather than computing a compacted view fresh each time - decide which approach you're taking and say so in the log, since it affects whether AC 10 needs separate proof or comes for free.

Evidence to produce: a scripted conversation that actually crosses the 90% threshold (you'll need many turns, or a way to force it — consider a small effective context via a real but small model, or directly testing `history_to_send()` with a synthetic long `messages` list rather than generating 90%-of-32768-tokens of real conversation) showing which level the ladder lands on and that the visibility line appears · confirmation the model can still answer a question about the compacted portion after this real trigger fires, not just in isolation like cycle 1.
