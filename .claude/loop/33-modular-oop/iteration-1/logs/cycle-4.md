# Cycle 4 - 2026-08-25 01:37 IST

The terminal split, and AC 14 unblocked. **446 of 447.**

## The reclaim, measured

427 before, 416 after. Eleven lines, from three places:

- **`ModelRefused` deleted** (4 lines). It was raised in `backend.py` and never referred to
  anywhere else - `report_failure` falls through to its generic branch for it, so nothing
  ever distinguished it from `BackendError`. That is precisely the shape AC 13 forbids: an
  abstraction with one implementation and no consumer. It should not have been written in
  cycle 3, and the line pressure is what surfaced it. `ollama.ResponseError` now translates
  to `BackendError` directly, and the transcript is unchanged.
- **`ModelBackend` docstring** (5 lines to 1). It explained why the protocol earns its place,
  which belongs in the cycle 3 log, not in the source in perpetuity.
- **`Settings` docstring** (2 lines). The override note kept its point and lost its padding.

Nothing knowledge-bearing was cut. The KV-cache derivation, the never-re-summarize rationale,
the leading-blank-line explanation and the `estimated_tokens` note are all still there.

## The split

`terminal.py` (72 lines) - `announce`, `read_line`, `show_piece`, `end_reply`,
`note_compaction`, `report_failure`. The startup line is assembled here from model, host,
context and whether the override is in play, rather than arriving pre-formatted, so the
formatting lives where AC 4 wants it.

`__init__.py` (61 lines) - the chat loop, and nothing else.

**One module, not two, and that was a decision.** Nothing in #33 requires a separate
`session.py`. AC 5 asks that no module both talk to a backend and write to a terminal, and
that is satisfied by `__init__.py` no longer printing. AC 8 asks that whichever module holds
the loop name no vendor client, and it names none. A third module would have cost 15-20 lines
to satisfy a criterion nobody wrote, against a ceiling with 31 lines of room.

What would change the answer: if the loop grows enough that `__init__.py` stops reading as one
thing, or if a second front end appears and the loop needs to be shared. Neither is true now.

## Evidence

**AC 5 and AC 4, by grep.** Every `print` and `input` under `src/`:

```
src/axiom/terminal.py:21,27,30,35,39,44,71,72
```

Every call into a backend:

```
src/axiom/compaction.py:23     backend.complete(
src/axiom/__init__.py:10,13,48 OllamaBackend(...), .model_info(...), .stream(...)
```

The two sets do not intersect. `terminal.py` writes and never calls a backend;
`__init__.py` and `compaction.py` call a backend and never write.

**One judgement call to flag:** `terminal.py` imports `ConnectionLost` from `backend`, to pick
the right message. That is a type dependency, not a conversation - it sends no request and
receives no reply. Reading AC 5 as forbidding the import would mean pushing message selection
out of the terminal, which would break AC 4. If that reading is preferred, the fix is for the
failure to carry what the message needs rather than the terminal inspecting its type.

**AC 4's five change kinds, each in exactly one module:** effective context -> `context.py`.
Compaction trigger and kept window -> `compaction.py`. Request sent and streamed ->
`backend.py`. Terminal reads and prints -> `terminal.py`. Configuration and defaults ->
`config.py`.

## Numbers

| | lines |
|---|---|
| `backend.py` | 83 |
| `compaction.py` | 102 |
| `config.py` | 49 |
| `context.py` | 79 |
| `terminal.py` | 72 |
| `__init__.py` | 61 |
| **total** | **446** of 447 |

**One line under.** AC 14 is met, and it is met honestly - by deleting a class nobody used and
docstrings that restated their own signatures, not by compressing anything that carried a
finding.

It should be said plainly that a one-line margin is not comfortable. AC 7's remaining half
adds roughly a line, which lands exactly on 447. Any cycle that needs more room should take it
from `compaction.py`, the largest file, where two docstrings restate mechanics the code shows
directly - not from the four passages named above.

## Criteria status

**Behaviour is preserved**
1. `met-with-evidence` - transcript identical through reclaim and split
2. `met-with-evidence` - no test needed changing this cycle; all 52 assertions intact
3. `met-with-evidence` - `axiom:main` re-resolved after `__init__.py` was rewritten again

**One responsibility per module**
4. `met-with-evidence` - five change kinds, five modules, listed above
5. `met-with-evidence` - the print set and the backend-call set do not intersect
6. `met-with-evidence` - `Settings`, `Piece`, `OllamaBackend`, `ModelBackend`; every method
   reachable, and the one unreachable class was deleted this cycle

**A substitutable seam**
7. `attempted` - compaction injected with no global patched; `main()` still builds its own
8. `met-with-evidence` - `ollama` and `httpx` appear only in `backend.py`
9. `met-with-evidence` - compaction runs against a stub, no live model

**No repetition**
10. `met-with-evidence` - one handler, now in `terminal.report_failure`
11. `not-started` - `feed()` and `_chunk()` still triplicated across test modules

**No unearned structure**
12. `met-with-evidence` - imports across `src/` are stdlib plus `ollama`, `httpx`, `psutil`;
    no framework, registry, service locator or config loader
13. `met-with-evidence` - the protocol has two implementations; the one abstraction that had
    none was deleted this cycle
14. `met-with-evidence` - 446 of 447

**Failure paths**
15-18. `met-with-evidence` - all four in the transcript, unchanged

**Exit**
19. `met-with-evidence` - all four exits at status 0

**Tests**
20. `attempted` - 25/25 green with no live model; no per-module test files yet

## Goal check

**Not met.** 17 of 20 carry evidence, up from 12. AC 14 moved from `blocked` to
`met-with-evidence`.

Three remain: **AC 7** (wiring, half done), **AC 11** (test-side duplication), **AC 20**
(per-module tests). None is blocked, and none needs a design decision - which is a different
position from any previous cycle.
