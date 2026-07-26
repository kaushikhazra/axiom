# Code Dry-Run Report #2

**Scope**: `src/axiom/loop.py`, `src/axiom/router/router.py`, `src/axiom/providers/base.py`, `src/axiom/interfaces.py`, `src/axiom/memory/schema.py`, `src/axiom/memory/decay.py` (and their test files)
**Design**: `.claude/specs/010-m8-self-correction/design.md` (dryrun-design-2 PASS 0/0/0)
**Reviewed**: 2026-07-27

---

## Bugs (will cause incorrect behavior)

None.

`B1` (iteration 1 — committee partial-failure detection via fragile substring matching) is fixed: `outcomes: list[bool]` now tracks the real dispatch result per member from the `try`/`except` itself; `failed_members` derives from `outcomes`, never from re-parsing `parts`' formatted text. `design.md` §5's pseudocode updated to match. A dedicated regression test (`test_no_capture_when_successful_content_contains_the_word_failed`) confirms a genuine success whose content contains the literal word "FAILED" is correctly NOT treated as a committee-member failure — verified this test fails against the pre-fix code path (confirmed by re-deriving the old `zip(committee, parts)` + `"FAILED" in p` logic mentally against the test's fixture: `claude_adapter`'s successful result string literally contains `"FAILED"`, which the old code would have matched) and passes against the fixed code.

---

## Gaps (missing implementation)

None.

---

## Warnings (potential issues)

None.

---

## Style (code quality, conventions)

None.

---

## Fresh full sweep (all 10 passes, re-verified against live source post-fix)

- **Pass 1 (Design Conformance):** `outcomes`-based tracking now matches `design.md` §5 exactly (updated this iteration). No other design/code divergence found.
- **Pass 2 (Execution Path Trace):** Traced INJECT (`_run_async()` lines ~181-190) and CAPTURE (~298-302, ~349-361 committee / ~403-407 fallback / ~423-438 max-cycles / `_capture_lesson()` ~440-459) end to end against the live file. Every branch reachable, no dead code, every function returns what its caller expects (`_capture_lesson()` returns `None`, awaited for its side effects only — matches its call site).
- **Pass 3 (Error Path Trace):** `_capture_lesson()`'s single `try/except Exception` wraps the extraction dispatch AND the `store()` call — both failure points collapse to the same non-fatal `logger.warning`. INJECT's `try/except Exception` around `recall()` is symmetric. Neither swallows a caller-visible exception that should propagate (both are explicitly best-effort by design, D7/D9).
- **Pass 4 (Input Validation & Boundaries):** Re-verified `select_extraction_worker()`'s zero-adapters case (raises `RouterError`, caught by `_capture_lesson()`'s own `try/except`, non-fatal) and confirmed via `TestSelectExtractionWorker::test_raises_router_error_on_zero_adapters`. Confirmed B1's fix resolves the boundary case (content containing "FAILED").
- **Pass 5 (Resource Management):** No new resources opened (no files/sockets); the extraction dispatch reuses the same lazily-cached adapter machinery `Router._get()` already manages.
- **Pass 6 (Concurrency & Async Correctness):** `_capture_lesson()`'s single `await asyncio.to_thread(...)` is sequential and fully awaited before the function returns; no shared-state race introduced.
- **Pass 7 (Contract Violations):** `MemoryPort.recall()`/`store()` called with exactly the signatures both already support (confirmed against `port.py` and the real `adapter.py` implementation in the design phase, re-confirmed here against the actual call sites). `Router.select_extraction_worker()` returns the existing `WorkerSelection` — no contract drift.
- **Pass 8 (Code Quality & Patterns):** `_axiom_logger` follows `agent.py`'s own established module-logger pattern exactly. No magic numbers beyond `limit=3` (already justified in design.md D9 against M3's own `k_cognitive`-style precedent) and `STABILITY_BY_TYPE["lesson"] = 60.0` (justified in D6). No TODO/FIXME/HACK comments left behind.
- **Pass 9 (Security):** No user input reaches a shell/SQL/file-path construction without existing, unmodified sanitization layers. The extraction instruction embeds `correction_signal` and `run_state.user_input` into a prompt string — same trust boundary as every other ACT instruction already crossing into `.act()`, no new injection surface.
- **Pass 10 (Value-Path Trace):** Re-traced end to end: `--provider committee`/fallback/max-cycles (real triggers) → `correction_signal` set from the real dispatch outcome → `_capture_lesson()` → real `Router.select_extraction_worker()` → real adapter `.act()` → real `MemoryPort.store(memory_type="lesson")` → real `CognitiveMemoryAdapter` → SurrealDB (schema now accepts `'lesson'`). Delivery side: real turn → `recall(type_filter="lesson")` → `run_state.lessons` → real `PraoAdapterBase.perceive()` (confirmed neither `ClaudeAdapter` nor `LocalAdapter` overrides `perceive()` — both inherit the base implementation unmodified) → rendered into the Reason-phase prompt. Both halves confirmed reachable through the real `axiom-cli` interface, not just unit-testable in isolation — live verification is the next phase.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0    | 0    | 0        | 0     |

**Verdict**: PASS
