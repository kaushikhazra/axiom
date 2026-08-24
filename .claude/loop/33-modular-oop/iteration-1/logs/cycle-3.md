# Cycle 3 - 2026-08-25 01:22 IST

The seam, and compaction moved onto it. Suite green throughout, transcript unchanged.

## What was built

`backend.py` (92 lines) - the only module under `src/` that imports a vendor client, proven
by grep:

```
$ grep -rn "ollama\|httpx" src/ --include=*.py
src/axiom/backend.py:14:import httpx
src/axiom/backend.py:15:import ollama
src/axiom/backend.py:59,65,82,84,85,86   (all inside OllamaBackend)
```

It holds a `ModelBackend` protocol over the three things axiom actually asks a model to do,
an `OllamaBackend` implementing it, a frozen `Piece` carrying a streamed fragment and its
usage, and three error types - `BackendError` with `ModelRefused` and `ConnectionLost` under
it.

`compaction.py` (102 lines) - `compact`, `estimated_tokens`, `compacted_history`,
`maybe_compact`, now taking a `ModelBackend` rather than a client.

## AC 10 fell out, as predicted

The three `except` blocks in `main()` were near-identical: drop the turn, print to stderr,
continue. They could not be merged before because they caught three unrelated vendor types.
Once the backend translates those into one family, the merge is trivial:

```python
except (KeyboardInterrupt, backend.BackendError) as failure:
    messages.pop()
    report_failure(failure, reply, settings.host)
    continue
```

One handler, one reporter. The reporter still distinguishes four messages, because the user
must still be told which thing happened - but the *handling* exists once, which is what AC 10
asks for.

The subtlety that had to survive: two branches printed a leading blank line and two did not.
`print(f"\nerror: ...")` and `print(file=sys.stderr)` followed by the message produce
identical bytes, so both collapse into one rule - a blank line when a partial reply is on
screen, or always for a cancellation. The transcript confirms this held.

## What the tests needed

Repointed, not weakened:

- `axiom.ollama` to `axiom.backend.ollama` - the client moved, so the patch target moved.
- `axiom.compact` and friends to `axiom.compaction.*`.
- `RecordingClient` became `RecordingBackend`, with `chat()` replaced by `complete()`. It is
  no longer standing in for a client, it is standing in for a backend, and the name should
  say so. Every assertion it supports is unchanged.

One real catch: `test_compact_returns_empty_string_not_none_on_a_blank_reply` injects a
backend returning `None` and asserts `compact()` yields `""`. The `or ""` guard used to live
in `compact()` alongside the vendor call. Moving it into `OllamaBackend.complete()` would have
left that assertion passing for the wrong reason - the stub would simply have returned `""`
itself, testing nothing. The guard stayed with the contract it protects, in `compact()`.

## AC 7, partially

Compaction is now injected directly - `RecordingBackend` is handed to `compacted_history()`
with no module global patched. That half of AC 7 is real and demonstrated.

The `main()`-level tests still patch `axiom.backend.ollama.Client`, because `main()` still
constructs its own `OllamaBackend`. Answering the question cycle 2 asked to record: **the seam
as built would let them stop.** Nothing about `ModelBackend` prevents `main()` accepting a
backend from its caller; the loop already talks only to the protocol. It is a wiring change,
not a design change, and it belongs with the session extraction.

## Numbers - and the problem

| | lines |
|---|---|
| `backend.py` | 92 |
| `compaction.py` | 102 |
| `config.py` | 51 |
| `context.py` | 79 |
| `__init__.py` | 103 |
| **total** | **427** of 447 |

**Cycle 2 projected 390-400. The actual is 427, with the terminal split still to come.**

The estimate was wrong about the seam. It was costed as "the protocol (~15) and the translated
error types (~10)" - about 25 lines. `backend.py` is 92. The difference is not waste: it is
the protocol's three signatures, three error classes, `Piece`, and an `OllamaBackend` whose
methods carry the vendor handling that used to be scattered inline through `main()`. But it
means the headroom is 20 lines, not 50.

Splitting the remaining 103 lines of `__init__.py` into a terminal module and a session module
would add two module headers and a set of function signatures - somewhere between 30 and 45
lines - landing at **457-472, over the ceiling.**

## AC 14 is now in genuine tension with AC 4 and AC 5

Stating it plainly rather than reinterpreting it, per the observe rules.

AC 4 requires "how the terminal reads a line and prints output" to live in exactly one module.
AC 5 requires no module to both talk to the backend and write to the terminal. `__init__.py`
currently does both. Satisfying them means at least one more module. AC 14 caps the total at
447 and 427 is already spent.

Three ways this can go, in the order they should be tried:

1. **One more module, not two.** `terminal.py` takes every `print` and the `input` call. The
   chat loop stays in `__init__.py` and satisfies AC 5 by never printing itself - it calls the
   terminal instead. Nothing in #33 requires a separate `session.py`; AC 8 only requires that
   whichever module holds the loop names no vendor client, and `__init__.py` already does not.
   Estimated landing: 439-449. Tight, possibly one or two lines over.
2. **Reclaim lines that carry no knowledge.** Several docstrings restate what a signature
   already says - the `ModelBackend` docstring is six lines, `Piece` has one for a two-field
   dataclass. Trimming those is worth 15-20 lines and loses nothing. The KV-cache derivation,
   the never-re-summarize rationale, and the leading-blank-line explanation are earned findings
   and are not candidates.
3. **If it still does not fit, AC 14 is reported unmet.** It does not get met by deleting
   comments that carry knowledge, and it does not get met by redefining what counts as a line.

Route 1 plus route 2 should fit. That is cycle 4.

## Criteria status

**Behaviour is preserved**
1. `met-with-evidence` - transcript identical across both moves
2. `met-with-evidence` - every assertion preserved; three relocations, one guard kept in place
3. `met-with-evidence` - `axiom:main` re-resolved after `__init__.py` was rewritten

**One responsibility per module**
4. `attempted` - 4 of 5 change kinds single-homed; the terminal is the outstanding one
5. `not-started` - `__init__.py` still calls the backend and prints
6. `attempted` - `Settings`, `Piece`, `OllamaBackend`, `ModelBackend`, each one thing

**A substitutable seam**
7. `attempted` - compaction injected directly with no global patched; `main()` not yet
8. `met-with-evidence` - grep: `ollama` and `httpx` appear only in `backend.py`
9. `met-with-evidence` - compaction runs against a stub, no live model

**No repetition**
10. `met-with-evidence` - one handler where there were three
11. `not-started` - `feed()` and `_chunk()` still triplicated across test modules

**No unearned structure**
12. `attempted` - no framework, registry or loader
13. `attempted` - the protocol has two implementations, the real one and the test stubs
14. `blocked` - 427 of 447 with the terminal split outstanding; see above

**Failure paths**
15. `met-with-evidence` - transcript
16. `met-with-evidence` - transcript, still reports 8 characters
17. `met-with-evidence` - transcript
18. `met-with-evidence` - transcript, still reports 8 characters

**Exit**
19. `met-with-evidence` - all four exits at status 0

**Tests**
20. `attempted` - 25/25 green with no live model; no per-module test files yet

## Goal check

**Not met.** 12 criteria carry evidence, up from 8. One criterion moved to `blocked` -
honestly, and with a route out.

## Assumptions

Unchanged. The 447 ceiling stands; what changed is the estimate of whether it fits.
