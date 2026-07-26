# M8 · Self-correction — Tasks

## 1. Memory schema/decay

- [ ] **Implementer** updates `src/axiom/memory/schema.py` — add `'lesson'` to `memory_type`'s `ASSERT` enum. _SC-1_
- [ ] **Implementer** updates `src/axiom/memory/decay.py` — add `"lesson": 60.0` to `STABILITY_BY_TYPE`. _SC-1_

## 2. Router

- [ ] **Implementer** updates `src/axiom/router/router.py` — add `Router.select_extraction_worker()`. _SC-1_

## 3. RunState + INJECT

- [ ] **Implementer** updates `src/axiom/interfaces.py` — add `RunState.lessons: list[str]` field. _SC-2_
- [ ] **Implementer** updates `src/axiom/providers/base.py` — `perceive()` gains `[LESSONS FROM PAST CORRECTIONS]` rendering block. _SC-2_

## 4. Loop wiring (CAPTURE)

- [ ] **Implementer** updates `src/axiom/loop.py` — assign `run_state.lessons` via `recall()` once per turn (INJECT); add `correction_signal` local + set-points in both ACT branches; add the CAPTURE call-point + `_capture_lesson()` method; add a module-level `_axiom_logger`. _SC-1, SC-2, SC-3, SC-4_

## 5. Tests

- [ ] **Implementer** extends `tests/test_router.py` — `select_extraction_worker()` prefers local, falls back, raises `RouterError` on zero adapters. _SC-1_
- [ ] **Implementer** extends `tests/test_contracts.py` — `correction_signal` set correctly on fallback/partial committee failure/max-cycles breach; `_capture_lesson()` fires exactly once per triggering cycle, never on a clean cycle; `run_state.lessons` populated from a scripted `recall()`. _SC-1, SC-2, SC-3_
- [ ] **Implementer** updates `tests/fake_adapter.py` — `FakeMemory` gains scriptable `recall()`; `FakeRouter` gains `extraction_selection`. _SC-1, SC-2_
- [ ] **Implementer** extends the `base.py` perceive test file — `[LESSONS FROM PAST CORRECTIONS]` renders correctly when populated, absent when empty. _SC-2_
