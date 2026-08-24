# Action

Cycle 1 proved both queries work and left the two real numbers sitting side by side, unused. Compute the minimum and actually apply it.

Replace the `[cycle-1 debug]` print lines. Compute `min(model_max_context, int(0.70 * available_memory-derived token budget))` — but note the two values are not directly comparable: `model_max_context` is a token count, `available_memory()` is bytes. Converting bytes of available memory into an equivalent token budget requires a per-token memory cost, which depends on the model's own architecture (layers, heads, head dimension) — the same `model_info` response from cycle 1 has these fields (e.g. `qwen2.block_count`, `qwen2.attention.head_count`, `qwen2.attention.head_count_kv`, `qwen2.attention.key_length`). Work out the KV-cache-per-token formula from those fields before computing anything, and show the arithmetic in the cycle log — do not guess a conversion factor.

Wire the result into the chat call via `options={"num_ctx": ...}`. Replace the startup line so it shows the effective context length alongside model and host (AC 4) — not a debug line, the real one.

Handle both `None` cases: if either query fails or the model reports no max, do not pass `num_ctx` at all — let Ollama use its own default, per `assumption.md`.

Target AC 2, 3, 4, and the `None`-handling half of AC 5/6 (the failure-*trigger* half — forcing an actual failure and confirming the fallback — can wait for a later cycle if this one runs long).

Evidence to produce: the computed effective context length for `qwen2.5:7b` on this machine, shown in the new startup line · the arithmetic that produced it, so the number is checkable, not asserted · a regression run confirming chat still works with `num_ctx` set.
