# Action

Two unknowns everything else depends on. Establish both, standalone, before wiring any trigger or ladder logic.

**1 — How to measure "would this use 90% of the effective context."** Nothing in the codebase counts tokens yet. Before assuming a tokenizer library is needed, check what Ollama's own `chat()` response already returns — inspect a real streamed response's final chunk for `prompt_eval_count` / `eval_count` fields (or whatever the `ollama` package actually exposes; don't assume the field name, inspect the real object). If Ollama already reports how many tokens a request used, that's a free, accurate running total to check against #28's `effective_context` before the next send — no separate tokenizer needed. Document what you find and why in the cycle log, the way #28's cycle 1 documented the real `model_info` keys before writing `kv_cache_bytes_per_token`.

**2 — A compaction mechanism.** Given N message pairs, produce something smaller that still lets the model answer questions about what was in them. The most direct approach: ask the model itself to summarize the pairs, using the same client already in `main()`. Write a standalone `compact(client, model, pairs) -> str` (or similar shape — the exact signature is yours to decide) and prove it in isolation, not wired into the chat loop yet:

- Have a short scripted conversation with a specific, checkable fact early on (e.g. "my favourite colour is teal").
- Compact everything except the last message.
- Send the compacted result plus a new question ("what colour did I say?") and confirm the model answers correctly from the compacted text alone.
- Show the character or token count of the compacted result is smaller than what it replaced.

That's AC 6 and AC 7's evidence, produced standalone before either criterion is wired into the real trigger.

Do not touch the 90%-trigger, the escalation ladder, or `main()`'s message loop this cycle. Both unknowns need to be solid before either gets used for real.

Evidence to produce: what field(s) Ollama's response actually carries for token usage, with a real transcript · a standalone `compact()` call showing a real fact survives compaction while the text shrinks.
