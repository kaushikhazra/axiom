# Cycle 2 - 2026-08-25 01:07 IST

Instrument proven, then the first two extractions. First cycle to change `src/`.

## The instrument detects a change

The golden master had only ever passed, so it was not yet known to catch anything.

Changed one character in the startup line - `"axiom: "` to `"axiom:  "`, a single extra
space - and ran the characterization test. It failed, and named the exact scenario and line:

```
At index 2 diff: 'axiom:  qwen2.5:7b at http://localhost:11434 (context: 32768 tokens)'
              != 'axiom: qwen2.5:7b at http://localhost:11434 (context: 32768 tokens)'
```

Reverted with `git checkout --`; suite back to 25/25. **AC 1 now rests on something
demonstrated rather than assumed.** A one-character difference in one of thirteen scenarios
is caught and localized.

## Extractions

`config.py` (51 lines) - `DEFAULT_HOST`, `DEFAULT_MODEL`, `parse_args`, and a frozen
`Settings` dataclass carrying host, model and the debug override. `resolve()` is the single
place command line, environment and default are reconciled.

`context.py` (79 lines) - `_find`, `model_max_context`, `kv_cache_bytes_per_token`,
`available_memory`, `memory_safe_context`, and the constants. Added `effective_context()`,
which takes the `min()` decision out of `main()` - that arithmetic *is* "how the effective
context size is decided", so leaving it in `main()` would have failed AC 4 while looking
extracted.

`model_info_for` stayed behind deliberately: it calls the client, so it belongs to the
backend question, not this one.

## What broke, and what that proves

One test failed: `axiom.available_memory` no longer exists at that path. Fixed by pointing
the assertion at `axiom.context.available_memory` - relocated, which AC 2 explicitly allows,
not dropped or weakened.

Notably the characterization test **passed throughout**. The behaviour did not move; only one
test's reach into the module did. That is the distinction the two criteria are built to
separate, and it held on the first real test of it.

Rejected the alternative of re-exporting `available_memory` from `__init__.py` to keep the
old path working. It would have kept the test green while leaving `__init__.py` as a
god-module, which is what AC 4 and AC 5 exist to prevent.

## Numbers

| | lines |
|---|---|
| `config.py` | 51 |
| `context.py` | 79 |
| `__init__.py` | 216 |
| **total** | **346** of 447 |

Started at 298, so the two extractions cost 48 lines of module overhead, docstrings, the
dataclass, and the new `effective_context()`.

**Revised AC 14 projection.** Four modules remain to be split out of `__init__.py`'s 216
lines: compaction, backend, terminal, session. At roughly 8 lines of overhead each, plus the
protocol (~15) and the translated error types (~10), the landing estimate is **390-400**.
That is 47-57 lines of headroom rather than the comfortable margin cycle 1 assumed, but it
fits, and AC 12 and AC 13 forbid the kind of structure that would eat it.

## Criteria status

**Behaviour is preserved**
1. `met-with-evidence` - transcript identical after both extractions, and the instrument is
   now proven to catch a one-character change. **Standing, not closed** - re-verified every
   cycle.
2. `met-with-evidence` - 52 assertions, one relocated, none dropped or weakened
3. `met-with-evidence` - `axiom:main` resolves via `importlib.metadata`

**One responsibility per module**
4. `attempted` - 2 of AC 4's 5 change kinds now have exactly one home
5. `not-started` - `__init__.py` still both talks to Ollama and prints
6. `attempted` - one class exists, `Settings`, and it is data only

**A substitutable seam**
7. `not-started` - tests still patch `axiom.ollama.Client`
8. `not-started` - no session module yet
9. `not-started` - compaction still takes `client: ollama.Client`

**No repetition**
10. `not-started` - three near-identical failure blocks remain
11. `not-started` - `feed()` and `_chunk()` still triplicated across test modules

**No unearned structure**
12. `attempted` - holds so far: a dataclass and plain functions, no framework
13. `attempted` - holds so far: no abstraction introduced yet
14. `met-with-evidence` - 346 of 447, projection 390-400

**Failure paths**
15. `met-with-evidence` - in the transcript, unchanged
16. `met-with-evidence` - in the transcript, unchanged
17. `met-with-evidence` - in the transcript, unchanged
18. `met-with-evidence` - in the transcript, unchanged

**Exit**
19. `met-with-evidence` - all four exits at status 0 in the transcript

**Tests**
20. `attempted` - suite green at 25/25 with no live model, but `config` and `context` have
    no dedicated test modules of their own yet

## Assumptions

Unchanged.

## Goal check

**Not met.** Real movement: 8 criteria now carry evidence, against 0 at cycle 1.

## What is still missing

Everything still in `__init__.py` is entangled with the vendor client. `model_info_for`,
`compact`, `compacted_history` and `maybe_compact` all take `client: ollama.Client`, and
`main()` catches three vendor error types directly.

That is the constraint this cycle exposes: **config and context moved cleanly precisely
because they never touch the client, and nothing that remains has that property.** The seam
is not one extraction among four - it is the precondition for the other three. Cycle 3 builds
it.
