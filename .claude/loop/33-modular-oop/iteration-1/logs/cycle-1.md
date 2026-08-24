# Cycle 1 - 2026-08-25 00:52 IST

Baseline cycle. **No change to `src/`.** Two files added under `tests/`: the measuring
instrument and a shared isolation fixture.

## Where the artifact stands against the goal

Nothing is restructured. `src/axiom/__init__.py` is still one 298-line procedural module.
What this cycle produced is the apparatus without which none of AC 1, AC 2 or AC 14 could
ever be settled honestly.

## What was recorded

**Line count (AC 14 baseline).** `src/axiom/__init__.py` - 298 lines, the only file under
`src/`. Ceiling is 447.

**Test inventory (AC 2 baseline).** 24 tests collected from 23 functions (one parametrized
twice), 52 assertions:

| module | tests | assertions |
|---|---|---|
| `test_compaction.py` | 14 | 38 |
| `test_context_window.py` | 6 (7 collected) | 9 |
| `test_interrupt.py` | 3 | 5 |

The per-assertion inventory is the `grep -n` output of `assert` against each module,
reproducible with the same command. What each one asserts is preserved in the test names
and messages, which are unusually explicit in this repo - several cite their own AC number.

**Behaviour transcript (AC 1 baseline).** `tests/baseline/transcript.txt`, 13 scenarios,
each capturing stdout, stderr and how the run ended:

startup with a context-reporting model - startup when the model is unreachable - a normal
exchange - a blank line ignored - compaction firing and announcing itself - a model error
mid-turn - the connection dropping before any reply - the connection dropping mid-reply -
Ctrl-C during generation - Ctrl-C at an idle prompt - `/exit` - `/quit` - end of input.

All 13 end `returned normally (exit status 0)`. That is the AC 19 baseline as well.

Determinism was forced two ways: `psutil.virtual_memory` is stubbed to a fixed 8 GiB so the
memory-derived budget cannot vary with the machine, and the debug override is cleared unless
a scenario sets it deliberately.

## The environment finding

**The suite was red before any change was made.** 6 of 24 tests failed. The cause was not
the code: `AXIOM_DEBUG_MAX_CONTEXT=500` is exported in this session's environment, left from
#29's live compaction runs, and six tests read the effective context out of the startup line
without isolating that variable. With the variable unset, 24/24 passed.

It is not persisted anywhere - not in `.claude/settings.json`, not in the Windows User or
Machine environment. It exists only in this process tree, and a child cannot unset it in its
parent.

Working around it per-command would have left the trap in place for every future run. Fixed
at the source instead: `tests/conftest.py` clears it for every test through one autouse
fixture, rather than editing six tests. **The suite is now 25/25 green with the variable
still set to 500** - verified in the same shell that reports it.

This strengthens the suite rather than weakening it, so AC 2 is unaffected.

## The shape the restructure will take

Named now so cycle 2 derives its move instead of inventing one. Six responsibilities are
tangled in the single module today:

| module | holds | AC 4 change-kind it answers |
|---|---|---|
| `config.py` | defaults, env resolution, argparse, the resolved settings object | how configuration and its defaults resolve |
| `context.py` | model max, KV-cache cost per token, memory budget, the effective minimum | how the effective context size is decided |
| `compaction.py` | trigger fraction, the kept-pairs ladder, summary carry-forward | when compaction fires and how much it keeps |
| `backend.py` | the `ModelBackend` protocol, the Ollama implementation, and the translation of vendor errors into our own | how a request is sent and streamed back |
| `terminal.py` | reading a line, printing the reply, the notices and the failures | how the terminal reads and prints |
| `session.py` | the chat loop, the history, the running usage | - |
| `__init__.py` | `main()` only, wiring the above | - |

The seam is `ModelBackend` in `backend.py`. `session.py` imports the protocol and never
`ollama` or `httpx`, which is exactly what AC 8 checks by grep. The vendor error types are
translated at the backend boundary, which is also what makes AC 10 possible - the three
near-identical `except` blocks in `main()` collapse into one handler once they are catching
one error family instead of three vendor ones.

**The main risk is AC 14.** Seven files at roughly 40-80 lines each lands near 395, against
a 447 ceiling. There is room, but not room to be generous with abstraction - which is what
AC 12 and AC 13 are there to enforce anyway.

**Also noted for a later cycle:** `feed()` is now duplicated in three test modules and
`_chunk()` in three. `conftest.py` is the natural home. That is AC 11 territory.

## Criteria status

All 20 read `not-started`: nothing has been restructured, and every one of these is a
statement about the restructured code. The baseline facts sit beside them.

**Behaviour is preserved**
1. `not-started` - instrument built, 13-scenario baseline recorded
2. `not-started` - inventory recorded: 24 tests, 52 assertions
3. `not-started` - `axiom:main` currently resolves

**One responsibility per module**
4. `not-started` - shape named above
5. `not-started`
6. `not-started` - no classes exist yet

**A substitutable seam**
7. `not-started` - tests currently patch `axiom.ollama.Client`, the exact thing this forbids
8. `not-started` - `ollama` and `httpx` are imported at module top today
9. `not-started`

**No repetition**
10. `not-started` - three near-identical failure blocks in `main()`
11. `not-started`

**No unearned structure**
12. `not-started`
13. `not-started`
14. `not-started` - 298/447 baseline

**Failure paths**
15. `not-started` - captured
16. `not-started` - captured, reports 8 characters
17. `not-started` - captured
18. `not-started` - captured, reports 8 characters

**Exit**
19. `not-started` - all four exits captured, all status 0

**Tests**
20. `not-started` - suite green at 25/25, no live model needed

## Assumption that changed

Added to `assumption.md`: the leaked environment variable, why it cannot be removed from
this session, and the fixture that makes it irrelevant. Also recorded that the golden
baseline is regenerated only on purpose.

## Goal check

**Not met.** Correct for a baseline cycle - it was never going to be met here. Nothing has
moved on the artifact because nothing was permitted to.

## What is still missing, and can it be closed from here

All 20 criteria remain. Nothing looks unreachable. The one criterion with real tension is
AC 14, and the estimate says it fits.

One gap in the apparatus itself: **the golden master has never failed.** A characterization
test that has only ever passed is not yet known to detect anything. Cycle 2 settles that
before trusting it.
