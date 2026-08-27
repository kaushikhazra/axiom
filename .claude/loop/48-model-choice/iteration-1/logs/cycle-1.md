# Cycle 1 — baseline and probes

2026-08-27 13:27–13:40 IST. Fail-safe 16:27 IST. **No production code written**, as
`action.md` asked.

## Baseline

- **317 tests, green and hermetic.** Run with
  `AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7`. 67.6s.
  This is the floor.
- Golden transcript copied to `.tmp/transcript-baseline-48.txt`.
- Branch `feature/48-model-choice` at `cae7ac4`.

## The defect, reproduced

Worth recording because it is the goal's premise and it is now measured rather than reasoned:

```
$ echo "" | uv run axiom --host http://127.0.0.1:1
axiom: qwen2.5:7b at http://127.0.0.1:1 (context: Ollama default, no tools - this model cannot call them)
> >
exit status: 0
```

Against a host that does not exist, axiom names a model with total confidence, reports a
context and a tool verdict it never obtained, and **exits 0**. Both the model name and the
"cannot call them" are fabrications of the two swallowing methods. This is what #48 deletes.

## Probe 1 — what `Client.list()` returns

`ListResponse`, with `.models`. Each entry carries `model`, `modified_at`, `size`, `digest`,
`details`.

- **The attribute is `.model`. There is no `.name`.** The raw `/api/tags` JSON carries *both*
  `name` and `model` and they are equal, but the Python client's `ListResponse.Model` exposes
  only `model`. `assumption.md` had recorded the raw-API shape; reaching for `.name` would
  have raised `AttributeError` on the first run. **Assumption corrected.**
- No `capabilities` on the list entry, though the raw JSON has it — tool support still has to
  come from `show()`, which is what `supports_tools` already does. Nothing changes there.

## Probe 2 — host down versus host up and empty

**Distinguishable, which is what AC 31 and AC 32 needed.**

| host | result |
|---|---|
| `http://127.0.0.1:1` | raises `builtins.ConnectionError` — "Failed to connect to Ollama…" |
| `http://localhost:11434` | returns normally, 5 models |

So: an exception means unreachable (AC 31); a successful call returning an empty `.models`
means reachable-and-empty (AC 32). Two states, two messages, both non-zero.

**Decision — the listing method does not swallow.** `model_info` and `supports_tools` both
catch `ResponseError`, `ConnectionError` and `httpx.HTTPError` and return `None`/`False`, and
that swallowing is exactly why today's failure is silent. A listing method that did the same
would collapse AC 31 and AC 32 into one indistinguishable case. It raises `ConnectionLost`
instead, and the caller decides. Reasoning recorded here rather than rediscovered later.

## Probe 3 — how a non-zero status actually carries

The console script is a real shim, extracted from `.venv/Scripts/axiom.exe`:

```python
from axiom import main
if __name__ == "__main__":
    ...
    sys.exit(main())
```

So a returned int *would* carry. **Decision — `main()` calls `sys.exit(2)` directly anyway.**
Two reasons: it carries the status through `python -m` and a direct call as well as through
the shim, and it is measurable in a test with `pytest.raises(SystemExit)` on `.value.code`,
which is what `observe.md` demands for AC 31 and AC 32. A test asserting on a printed message
would prove nothing about the status.

Incidental: the shim hardcodes `c:\Projects\axiom\.venv\Scripts\python.exe`. That is the
known uv/pip console-shim behaviour the repo rules already carve out. Not this row's problem;
noted so a later cycle does not treat it as a discovery.

## Probe 4 — the list order, re-confirmed

```
['gemma2:2b', 'qwen2.5-coder:7b', 'gemma4:e2b', 'ornith:9b', 'qwen2.5:7b']
```

`modified_at` descending — 2026-08-25, 08-05, 08-05, 07-21, 04-28. Unchanged from scaffold
time and **not sorted**. This is the fact AC 6 exists for, and the instrument for testing it:
a stub handed *this* order must display alphabetical order.

## Status — all 38 criteria

| criteria | status |
|---|---|
| AC 1–38 | `not-started` |

Nothing implemented; this cycle was baseline and probes by design.

## Assumptions changed

- **`.model`, never `.name`.** `assumption.md` described the raw API; the client differs.
  Corrected there.
- **Added:** the listing method raises rather than swallowing, and `main()` exits via
  `sys.exit`. Both are decisions this cycle made and recorded, not open questions.

## Cycle 2 will

Implement, in dependency order:

1. `backend.installed()` on the protocol, `OllamaBackend`, and `conftest.StubBackend` —
   nothing else is testable without it.
2. `models.py` — the remembered choice (read, write, per host, per directory) and the sorted
   list. Pure functions; no printing.
3. `terminal.py` — the list, the question, the refusals, the announcements.
4. `__init__.py` — the settling logic, and the two `sys.exit(2)` paths.
5. `config.py` — delete `DEFAULT_MODEL`, make `--model` default to `None`.

The transcript is regenerated in a later cycle, once the startup line has stopped moving.
