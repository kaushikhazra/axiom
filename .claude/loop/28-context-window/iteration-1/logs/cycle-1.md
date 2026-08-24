# Cycle 1 — 2026-08-24 12:05 IST

## Where the artifact stood before this cycle

`src/axiom/__init__.py` was #26's finished state — 91 lines, no context-sizing work. Confirmed by reading it before writing anything.

## What this cycle did

Got both raw numbers on screen, nothing wired together yet, per the action's scope.

**Model's max context length.** Inspected the real `ollama.show()` response before assuming a key name:

```
$ ollama show qwen2.5:7b -> model_info
qwen2.context_length = 32768
qwen2.embedding_length = 3584
qwen2.feed_forward_length = 18944
```

Architecture-prefixed, as expected. Checked two more locally installed models before generalizing:

```
qwen2.5-coder:7b -> qwen2.context_length = 32768
gemma4:e2b       -> gemma4.context_length = 131072
```

Confirmed generic: search `model_info` for any key ending in `.context_length`, not a hardcoded architecture name. `model_max_context()` does that scan, returns `None` if nothing matches.

**Available memory.** `psutil` added as a direct dependency (per `assumption.md`). `available_memory()` wraps `psutil.virtual_memory().available` — bytes currently free, not total installed.

```
$ psutil.virtual_memory()
total     17024741376 (17.0 GB)
available  7820845056 (7.8 GB)
percent used 54.1
```

**Evidence — both real values on a live run:**

```
$ printf '/exit\n' | uv run axiom
axiom: qwen2.5:7b at http://localhost:11434
[cycle-1 debug] model max context: 32768
[cycle-1 debug] available memory: 7769026560
>
```

The debug lines are temporary — `[cycle-1 debug]` prefix, not the AC 4 visibility line. They print the raw queried values as this cycle's own evidence; the next cycle replaces them with the computed minimum and the real visibility format.

**Regression — chat still works:**

```
$ printf 'Say hello in three words.\n' | uv run axiom
axiom: qwen2.5:7b at http://localhost:11434
[cycle-1 debug] model max context: 32768
[cycle-1 debug] available memory: 7750320128
> Hello, there!
```

## Criteria

| AC | State | Evidence |
|---|---|---|
| 1 query model's max context length | **met — new** | real `.context_length` value queried and printed, 3 models confirmed |
| 2 determine 70%-of-available memory | **not met** | available memory is queried; the 70% computation is not written yet |
| 3 use whichever is smaller | **not met** | nothing computed yet, values only printed |
| 4 effective context shown alongside model/host | **not met** | debug lines are not this criterion's format |
| 5 no max reported → Ollama's default | **untested** | fallback path not written; `model_max_context()` can return `None`, nothing consumes that yet |
| 6 memory undeterminable → Ollama's default | **untested** | same — `available_memory()` can return `None`, nothing consumes that yet |
| 7 determined once at startup, fixed for process life | **not met** | not yet wired into the chat call at all |
| 8 restart re-runs both queries | **not met** | same |
| 9 both fail → still starts on Ollama's default | **untested** | no failure path written |

**1 met, 6 not met, 2 untested.**

## Movement

From nothing to two real, verified query paths. The key finding — `.context_length` is architecture-prefixed but suffix-stable — is what makes AC 1's implementation generic rather than a hardcoded lookup per model family.

## What is still missing, and is it closable

Everything except AC 1. All closable. The shape of what's left: compute min(model_max, 70% of available) → wire it into `client.chat(..., options={"num_ctx": ...})` → replace the debug lines with the real AC 4 visibility line → handle both `None` cases by omitting `num_ctx` entirely (Ollama's own default) → confirm restart re-queries.

## Assumptions that changed

None. `psutil` was already anticipated in `assumption.md`; this cycle just installed it.

## Goal check

**Not met.** 1 of 9. Next action written.
