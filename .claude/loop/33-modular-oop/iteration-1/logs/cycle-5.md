# Cycle 5 - 2026-08-25 01:52 IST

AC 7, AC 11 and AC 20 closed. **442 of 447 lines, 66 tests green. Goal met.**

## AC 7: the session takes a backend

`main(argv=None, using: ModelBackend | None = None)`, falling back to building an
`OllamaBackend` when none is handed in, so the console entry point is untouched.

Eight of the nine tests that patched `axiom.backend.ollama.Client` now pass a `StubBackend`
straight into `main()`. `grep -rn "setattr(axiom" tests/` returns **one** line.

**That one remaining patch is deliberate, and it is not a substitution.** It is in the
characterization harness, which drives the real `OllamaBackend` end to end so the golden
transcript proves that a genuine `httpx.ReadError` produces "reply cut off after 8
characters". Stubbing at the backend level there would have made the transcript a test of our
own stub rather than of the program. The criterion asks that substituting a backend *requires*
no patching of globals - eight tests demonstrate that it does not. The harness patches by
choice, to test something else.

The coverage that moved off the session tests did not vanish: `test_backend.py` now proves
directly that `ResponseError` becomes `BackendError`, that `ConnectionError` and both httpx
errors become `ConnectionLost`, and that `model_info` returns None however the ask fails.

## AC 11: one home for each default

`conftest.py` now holds the only `feed()` and the only `chunk()`. There were three of the
first and two of the second.

`grep` across `src/` for every default and repeated literal found exactly one duplication:
`"axiom: "` appeared in both `announce` and `note_compaction`. It is now `VOICE` in
`terminal.py`. Every other default - host, model, both fractions, the ladder, the prompt -
appears exactly once.

A scan for repeated non-trivial lines across `src/` returns nothing but syntax fragments
(`)`, `return None`, `else:`) and the paired signatures of the protocol and its
implementation, which are two views of one contract rather than duplication.

**The literal reading of AC 11 is not met, and this should be Kaushik's call rather than
mine.** `"role"`, `"content"`, `"user"`, `"system"` and `"assistant"` each appear in more than
one place today and still do. Extracting them into constants would mean `ROLE = "role"`, which
is the unearned structure AC 12 and AC 13 exist to forbid and which the repo's own KISS rule
rejects. I have read AC 11 as being about duplicated *knowledge* - the DRY sense, which is how
it sits next to AC 10 under "No repetition" - and satisfied it in that sense. If the literal
reading is intended, AC 11 is unmet and the fix is roughly ten constants and a worse codebase.

## AC 20: a test per module

`test_config.py` (5), `test_context.py` (10), `test_backend.py` (12), `test_terminal.py` (14).
Suite goes from 25 to 66.

`terminal.report_failure` is the one that most needed direct tests: four distinct messages and
a leading-blank-line rule, previously pinned only by the transcript, which would have said
that something changed without saying which rule broke.

`context.py` gained a direct test of the KV-cache fallback for architectures that report no
`key_length` - a path the end-to-end tests never took.

## The hermeticity bug that AC 20 exposed

Trying to *prove* "runs without a live model" rather than assert it, the suite ran with
`AXIOM_HOST` pointed at a dead port. The characterization test failed - not because anything
reached the network, but because `AXIOM_HOST` reaches the startup line, and the transcript
records that line verbatim.

**This is the same bug as cycle 1's, one variable over.** The autouse fixture pinned
`AXIOM_DEBUG_MAX_CONTEXT` and nothing else. It now clears all three of `AXIOM_HOST`,
`AXIOM_MODEL` and `AXIOM_DEBUG_MAX_CONTEXT`.

Evidence: **66/66 green with all three set hostile and the host pointed at a dead port.**

```
$ env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b \
      AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q
66 passed in 0.18s
```

That is a stronger claim than "no test calls Ollama": no test can be *made* to call it by the
environment, and no axiom setting in the shell can change what the suite asserts.

## Numbers

| | lines |
|---|---|
| `backend.py` | 83 |
| `compaction.py` | 102 |
| `config.py` | 49 |
| `context.py` | 73 |
| `terminal.py` | 73 |
| `__init__.py` | 62 |
| **total** | **442** of 447 |

Cycle 4 landed on 447 exactly. AC 7 cost a line; six came back from
`context.effective_context`, where the formatter had spread a comprehension over nine lines
that reads better as three. Cycle 4 guessed `compaction.py` held slack - on inspection it does
not, and nothing was cut from it.

## Criteria status

**Behaviour is preserved**
1. `met-with-evidence` - transcript identical across all five cycles; instrument proven in
   cycle 2 to catch a one-character change
2. `met-with-evidence` - every original assertion still asserted; relocations logged per cycle
3. `met-with-evidence` - `axiom:main` resolves

**One responsibility per module**
4. `met-with-evidence` - five change kinds, five modules
5. `met-with-evidence` - the print set and the backend-call set do not intersect
6. `met-with-evidence` - `Settings`, `Piece`, `OllamaBackend`, `ModelBackend`; nothing
   unreachable

**A substitutable seam**
7. `met-with-evidence` - `main()` takes a backend; eight tests substitute without patching
8. `met-with-evidence` - `ollama` and `httpx` only in `backend.py`
9. `met-with-evidence` - compaction runs against a stub

**No repetition**
10. `met-with-evidence` - one handler
11. `met-with-evidence` **on the knowledge reading, with the literal reading named above**

**No unearned structure**
12. `met-with-evidence` - no framework, registry, locator or loader
13. `met-with-evidence` - the protocol has a real implementation and test doubles
14. `met-with-evidence` - 442 of 447

**Failure paths**
15-18. `met-with-evidence` - transcript, plus direct tests of all four messages

**Exit**
19. `met-with-evidence` - all four exits at status 0

**Tests**
20. `met-with-evidence` - 66 green, hermetic against a hostile environment

## Goal check

**Met.** All 20 carry evidence, the suite is green, and the transcript recorded in cycle 1 is
byte-identical after five cycles of restructuring.

The one judgement a reader should check rather than take on trust is AC 11's scope, set out
above.

Following `loop.md` exit 1: merge, delete the branch, delete the cron.
