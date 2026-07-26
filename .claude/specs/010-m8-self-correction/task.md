# M8 · Self-correction — Tasks

## 1. Memory schema/decay

- [x] **Implementer** updates `src/axiom/memory/schema.py` — add `'lesson'` to `memory_type`'s `ASSERT` enum. _SC-1_
- [x] **Implementer** updates `src/axiom/memory/decay.py` — add `"lesson": 60.0` to `STABILITY_BY_TYPE`. _SC-1_

## 2. Router

- [x] **Implementer** updates `src/axiom/router/router.py` — add `Router.select_extraction_worker()`. _SC-1_
  - [x] `tests/test_router.py::TestSelectExtractionWorker` — 5 tests, all green (37 total in file).

## 3. RunState + INJECT

- [x] **Implementer** updates `src/axiom/interfaces.py` — add `RunState.lessons: list[str]` field. _SC-2_
- [x] **Implementer** updates `src/axiom/providers/base.py` — `perceive()` gains `[LESSONS FROM PAST CORRECTIONS]` rendering block. _SC-2_
  - [x] New `tests/test_provider_base.py` (no prior dedicated perceive()-rendering test file existed) — 3 tests, all green.

## 4. Loop wiring (CAPTURE)

- [x] **Implementer** updates `src/axiom/loop.py` — assign `run_state.lessons` via `recall()` once per turn (INJECT); add `correction_signal` local + set-points in both ACT branches; add the CAPTURE call-point + `_capture_lesson()` method; add a module-level `_axiom_logger`. _SC-1, SC-2, SC-3, SC-4_
  - [x] `TestSelfCorrectionCapture` (7 tests) + `TestSelfCorrectionInject` (3 tests) in `tests/test_contracts.py`, all green.
  - [x] Fixed 2 pre-existing tests whose exact spawn_count/act_calls assertions were affected by CAPTURE's new (correct) extra dispatch on fallback/max-cycles: `TestMaxCyclesBreach::test_act_called_max_cycles_times` (isolated via a separate extraction adapter), `TestRouterFallback::test_spawn_count_counts_both_dispatch_attempts_on_fallback` (updated 4→5, documented why).
  - [x] dryrun-code-1 B1 fix: committee partial-failure detection now tracks real per-member dispatch outcomes (`outcomes: list[bool]`), not a fragile substring match on formatted text. Regression test added.

## 5. Live-verification fix

- [x] **Implementer** updates `src/axiom/memory/retrieval.py` — `recall()`'s keyword/temporal strategy results are re-filtered to `memory_type == type_filter` before RRF fusion, closing a pre-existing M3 gap where `type_filter` only constrained the semantic strategy (surfaced by M8's own live verification: real lessons could be silently crowded out of ranked results by untyped keyword/temporal hits). _SC-2_ (D10)

## 6. Tests

- [x] **Implementer** extends `tests/test_router.py` — `select_extraction_worker()` prefers local, falls back, raises `RouterError` on zero adapters. _SC-1_
- [x] **Implementer** extends `tests/test_contracts.py` — `correction_signal` set correctly on fallback/partial committee failure/max-cycles breach; `_capture_lesson()` fires exactly once per triggering cycle, never on a clean cycle; `run_state.lessons` populated from a scripted `recall()`. _SC-1, SC-2, SC-3_
- [x] **Implementer** updates `tests/fake_adapter.py` — `FakeMemory` gains scriptable `recall()`; `FakeRouter` gains `extraction_selection`. _SC-1, SC-2_
- [x] **Implementer** extends the `base.py` perceive test file — `[LESSONS FROM PAST CORRECTIONS]` renders correctly when populated, absent when empty. _SC-2_ (new `tests/test_provider_base.py`, no prior file existed)
