# Cycle 2 — 2026-08-24 12:31 IST

## Where the artifact stands

`src/axiom/__init__.py` computes a real effective context length and passes it to Ollama as `num_ctx`. The two cycle-1 values are no longer printed side by side — they're combined.

## The KV-cache formula, and a complication cycle 1 didn't anticipate

Converting available memory (bytes) into a token budget needs bytes-per-token, which needs the model's own architecture fields from `model_info`. Pulled the full response for `qwen2.5:7b` first:

```
qwen2.attention.head_count = 28
qwen2.attention.head_count_kv = 4
qwen2.block_count = 28
qwen2.embedding_length = 3584
qwen2.context_length = 32768
```

No explicit `key_length` field for this model — so head_dim has to be derived as `embedding_length / head_count`. But checking `gemma4:e2b` before generalizing the formula surfaced a real problem:

```
gemma4.attention.head_count = 8
gemma4.attention.key_length = 512
gemma4.embedding_length = 1536      -> 1536/8 = 192, NOT 512
gemma4.attention.shared_kv_layers = 20
```

`key_length` (512) and the derived value (192) disagree by more than 2.5x for that architecture, and `shared_kv_layers` means some layers don't need their own separate cache at all — a plain layers × heads × head_dim formula would overestimate gemma4's real memory cost. `kv_cache_bytes_per_token()` now prefers the model's own reported `key_length` when present, falling back to `embedding_length / head_count` only when it isn't. The formula still isn't exact for sliding-window/shared-cache architectures like gemma4 — that would need per-layer accounting this issue doesn't ask for — but overestimating bytes-per-token only makes the resulting budget *more* conservative, never less safe, which is the direction that matters for this issue's purpose.

**Evidence — the full arithmetic, real numbers, this machine:**

```
block_count (layers)      = 28
attention.head_count_kv   = 4
attention.key_length      = None -> derived from embedding_length/head_count
bytes_per_token = 2 x 28 x 4 x 128 x 2 = 57344 bytes (56.0 KiB)

model max context   = 32768
available memory    = 8122814464 (8.12 GB)
70% of available     = 5685970124 bytes (5.69 GB)
memory-safe context = 99155 tokens

effective context (min) = 32768
```

Worth noting: on this machine, the *model's* limit binds, not memory — there's enough RAM that 70% of it covers nearly 100k tokens, well past what `qwen2.5:7b` supports at all. Confirms AC 3 is a genuine comparison, not one side always winning.

## Criteria

**Evidence — the real startup line (AC 4):**

```
$ printf '/exit\n' | uv run axiom
axiom: qwen2.5:7b at http://localhost:11434 (context: 32768 tokens)
```

**Evidence — chat regression, num_ctx now set on every call:**

```
$ printf 'My favourite colour is teal. Reply in under five words.\nWhat colour did I say?\n' | uv run axiom
axiom: qwen2.5:7b at http://localhost:11434 (context: 32768 tokens)
> Teal is a great choice!
> Teal, you said.
```

History still works with `options={"num_ctx": ...}` on the call.

**Evidence — the None-context fallback (AC 5/6 partially, incidentally):**

```
$ printf 'hello\n' | uv run axiom --model does-not-exist:1b
axiom: does-not-exist:1b at http://localhost:11434 (context: Ollama default)
> error: model 'does-not-exist:1b' not found (status code: 404)
```

`model_info_for()` catches the same `ollama.ResponseError` the chat loop already handles; an unknown model returns `None` for `info`, so `effective_context` is `None`, `chat_options` is `None`, and the startup line correctly says "Ollama default" rather than a fabricated number. This wasn't the cycle's target, but it fell out of the wiring for free.

| AC | State | Evidence |
|---|---|---|
| 1 query model's max context length | met | cycle 1 |
| 2 determine 70%-of-available-memory context | **met — new** | arithmetic above |
| 3 use whichever is smaller | **met — new** | real min() resolves to the model's limit on this machine |
| 4 effective context shown alongside model/host | **met — new** | startup line above |
| 5 no max reported → Ollama's default | **met — new** | unknown-model transcript above (info=None covers this path too) |
| 6 memory undeterminable → Ollama's default | **untested** | `available_memory()` has a `None` path (wrapped `psutil` call) but nothing forces `psutil` to actually fail yet |
| 7 determined once at startup, fixed for process life | **met — new** | computed once before the `while True:` loop, never recomputed |
| 8 restart re-runs both queries | **untested** | plausible from the code shape (queries run at the top of `main()` every invocation) but not directly demonstrated by switching model/host between two runs |
| 9 both fail → still starts on Ollama's default | **untested** | AC 5's transcript proves the *model*-side None path starts fine; memory-side and both-together aren't forced yet |

**7 met, 0 not met, 2 untested.** Was 1 met.

## A regression found and fixed

`tests/test_interrupt.py`'s `FakeClient` had no `.show()` method — `main()` now calls it unconditionally at startup, so all 3 tests failed with `AttributeError: 'FakeClient' object has no attribute 'show'` the moment this cycle's wiring landed. Fixed by giving `FakeClient` a `show()` returning empty `model_info`, which correctly exercises the "Ollama default" fallback path rather than needing to fake a real architecture. `client.chat()` also gained an `options=None` parameter to match the new call signature. All 3 tests pass again.

## What is still missing, and is it closable

AC 6, 8, 9. All closable — none are new problems, just untested paths in code that's already shaped to handle them (`available_memory()` already returns `None` on failure; restart re-querying is just how `main()` already works, unverified by a two-run transcript).

## Assumptions that changed

None new. `SAFE_MEMORY_FRACTION = 0.70` and `KV_CACHE_BYTES_PER_VALUE = 2` (Ollama's default f16 KV cache) are now in code, matching `assumption.md`.

## Goal check

**Not met.** 7 of 9. Next action written.
