# M7 · Orchestrator — Tasks

## 1. Policy engine

- [ ] **Implementer** updates `src/axiom/router/policy.py` — add `consortium_patterns`, `max_committee_size`, `RoutingDecision.CONSORTIUM`, `should_form_committee()`. _OR-2, OR-5, OR-8_

## 2. Router

- [ ] **Implementer** updates `src/axiom/router/router.py` — add `Router.select_committee()`; guard `select_conductor()` against `forced_provider == "committee"`. _OR-1, OR-2, OR-5, OR-8_

## 3. Loop wiring

- [ ] **Implementer** updates `src/axiom/loop.py` — ACT branch: committee check before existing `select_worker()` path; committee dispatch loop with per-member failure tolerance and combined-result synthesis via the existing `observe()` call. _OR-1, OR-3, OR-4, OR-6, OR-7, OR-9_

## 4. CLI

- [ ] **Implementer** updates `src/axiom/interface/cli.py` — `--provider` gains `"committee"` as a third choice. _OR-1_
- [ ] **Implementer** updates `src/axiom/agent.py` — extend `Agent.__init__`'s provider whitelist to accept `"committee"` (dryrun-design-1 C1 fix). _OR-1_

## 5. Tests

- [ ] **Implementer** extends `tests/test_router_policy.py` — `should_form_committee()` precedence combinations. _OR-1, OR-2, OR-5_
- [ ] **Implementer** extends `tests/test_router.py` — `select_committee()` membership, capping, determinism, `None` when not triggered, Conductor guard. _OR-1, OR-2, OR-8_
- [ ] **Implementer** extends `tests/test_contracts.py` — loop-level committee dispatch: fan-out, synthesis, partial failure, all-fail, no-fallback, spawn_count, trace attributes. _OR-3, OR-4, OR-6, OR-7_
- [ ] **Implementer** updates `tests/fake_adapter.py` — `FakeRouter` gains `committee_selections` option. _OR-3, OR-4, OR-6_
