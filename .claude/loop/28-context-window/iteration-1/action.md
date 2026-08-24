# Action

First thing to tackle: **get the two raw numbers on screen.** Everything else — the min, the fallback, the visibility line, the state behaviour — is downstream of actually being able to query them.

Query the configured model's max context length via `ollama.Client(host=...).show(model)` and find where the context length lives in `model_info` (the key is architecture-prefixed, e.g. `qwen2.context_length` — inspect the real response for `qwen2.5:7b` rather than assuming the key name). Separately, query available memory with `psutil.virtual_memory().available`.

Print both raw values — do not compute the minimum or wire it into the chat call yet. Do not touch `--host`/`--model` handling, error handling, or the REPL loop this cycle.

Evidence to produce: a run showing the actual queried max-context value for `qwen2.5:7b` and the actual available-memory figure for this machine, both printed, both real numbers from real queries — not placeholders.
