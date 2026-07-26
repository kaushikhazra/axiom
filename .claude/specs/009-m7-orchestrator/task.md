# M7 · Orchestrator — Tasks

## 1. Policy engine

- [x] **Implementer** updates `src/axiom/router/policy.py` — add `consortium_patterns`, `max_committee_size`, `RoutingDecision.CONSORTIUM`, `should_form_committee()`. _OR-2, OR-5, OR-8_
  - [x] `tests/test_router_policy.py::TestShouldFormCommittee` — 9 tests, all precedence combinations, all green.

## 2. Router

- [x] **Implementer** updates `src/axiom/router/router.py` — add `Router.select_committee()`; guard `select_conductor()` against `forced_provider == "committee"`. _OR-1, OR-2, OR-5, OR-8_
  - [x] `tests/test_router.py` — 12 new tests (guard, triggering, membership, capping, determinism, caching), all green; all 20 pre-existing M6 tests unmodified and still passing (32 total).

## 3. Loop wiring

- [x] **Implementer** updates `src/axiom/loop.py` — ACT branch: committee check before existing `select_worker()` path; committee dispatch loop with per-member failure tolerance and combined-result synthesis via the existing `observe()` call. _OR-1, OR-3, OR-4, OR-6, OR-7, OR-9_

## 4. CLI

- [x] **Implementer** updates `src/axiom/interface/cli.py` — `--provider` gains `"committee"` as a third choice. _OR-1_
- [x] **Implementer** updates `src/axiom/agent.py` — extend `Agent.__init__`'s provider whitelist to accept `"committee"` (dryrun-design-1 C1 fix). _OR-1_

## 5. Tests

- [x] **Implementer** extends `tests/test_router_policy.py` — `should_form_committee()` precedence combinations. _OR-1, OR-2, OR-5_
- [x] **Implementer** extends `tests/test_router.py` — `select_committee()` membership, capping, determinism, `None` when not triggered, Conductor guard. _OR-1, OR-2, OR-8_
- [x] **Implementer** extends `tests/test_contracts.py` — loop-level committee dispatch: fan-out, synthesis, partial failure, all-fail, no-fallback, spawn_count, trace attributes. _OR-3, OR-4, OR-6, OR-7_
  - [x] 9 new tests in `TestCommitteeDispatch`, all green.
- [x] **Implementer** updates `tests/fake_adapter.py` — `FakeRouter` gains `committee_selections` option. _OR-3, OR-4, OR-6_
- [x] **Implementer** fixes pre-existing missing imports (`Router`, `RoutePolicy`, `FakeMemory`) in `tests/test_local_e2e.py` — _untraced, found while verifying "full suite green" DoD item 6; pre-dates M7 (confirmed via git stash), root-caused and fixed rather than left broken._ <!-- ⚠ not in Pass 9 skeleton — pre-existing bug found during verification, not part of design.md's Files Changed -->

## 6. Live verification (OR-9)

- [x] **Implementer** live-verifies OR-1 (default single-provider unchanged), OR-3+OR-4 (genuine independent dispatch, combined-result synthesis), OR-6 (per-slot failure tolerance) via `axiom-cli` and a direct-construction script; recorded in `sign-off.md`. _OR-1, OR-3, OR-4, OR-6, OR-9_
