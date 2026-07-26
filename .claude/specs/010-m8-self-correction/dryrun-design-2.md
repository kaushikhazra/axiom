# Design Dry-Run Report #2

**Document**: `.claude/specs/010-m8-self-correction/design.md`
**Reviewed**: 2026-07-27

---

## Critical Gaps (must fix before implementation)

None.

`C1` from iteration 1 (`router.py`'s extraction-provider behavior had no matching AC) is fixed: SC-1 now has an explicit AC bullet ("The extraction dispatch uses the cheapest configured provider... bypassing `RoutePolicy` entirely"). Re-ran Pass 9 fresh: all Files Changed rows now trace to both a `task.md` item and a `requirement.md` AC.

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| `src/axiom/interfaces.py` — add `RunState.lessons` field | task.md §3 | SC-2 |
| `src/axiom/loop.py` — INJECT assignment, `correction_signal`, CAPTURE call-point, `_capture_lesson()`, logger | task.md §4 | SC-1, SC-2, SC-3, SC-4 |
| `src/axiom/providers/base.py` — `[LESSONS FROM PAST CORRECTIONS]` render block | task.md §3 | SC-2 |
| `src/axiom/router/router.py` — `select_extraction_worker()` | task.md §2 | SC-1 (extraction-provider AC, added this iteration) |
| `src/axiom/memory/schema.py` — `'lesson'` enum addition | task.md §1 | SC-1 (`memory_type="lesson"` AC) |
| `src/axiom/memory/decay.py` — `STABILITY_BY_TYPE["lesson"]` | task.md §1 | SC-1 (same AC, stability is the concrete mechanism behind "durable") |
| `tests/test_router.py` — extraction-worker tests | task.md §5 | SC-1; DoD item 5 |
| `tests/test_contracts.py` — trigger/capture/inject tests | task.md §5 | SC-1, SC-2, SC-3; DoD item 5 |
| `tests/fake_adapter.py` — scriptable `recall()`/`extraction_selection` | task.md §5 | SC-1, SC-2; DoD item 5 |
| `base.py` perceive test file | task.md §5 | SC-2; DoD item 5 |

**Result**: All 10 file-level prescriptions traced to tasks and ACs. No traceability gaps.

---

## Warnings (should fix, may cause issues)

None.

`W1` from iteration 1 (ambiguous "initialized once" wording for `correction_signal`) is fixed: §5 now explicitly states the variable is re-declared fresh on every loop iteration that reaches the ACT-intent-handling section, and explicitly calls out that a `USE_SKILL` cycle's `continue` never touches it — closing the specific misreading risk identified.

---

## Observations (worth discussing)

None. Full fresh sweep of all 10 passes below found no new issues.

### Fresh-sweep notes (Passes 1-8, re-verified against live source)

- **Pass 1 (Completeness):** All five stories (SC-1 through SC-5) have corresponding design sections (§2-§5) and Files Changed rows. No scope creep — `select_extraction_worker()`, the schema/decay additions, and the `RunState.lessons` field are all directly traceable to a specific AC, not invented extras.
- **Pass 2 (Data Flow):** `run_state.lessons` (created in `_run_async()`, consumed in `perceive()`) and `correction_signal` (created in the ACT branch, consumed by `_capture_lesson()`) both have a clear, traced source → consumer path. No orphaned data.
- **Pass 3 (Interface Contracts):** `MemoryPort.recall()`/`store()` reused unmodified — confirmed against the live `port.py`/`adapter.py` signatures (both already accept `type_filter`/`memory_type` as used here). `Router.select_extraction_worker()` returns the existing `WorkerSelection` dataclass, no new type.
- **Pass 4 (State Machine):** Resolved by the W1 fix above. `run_state.lessons` itself has simple, non-branching state (set once per turn, read many times, never mutated mid-turn) — no additional gap found.
- **Pass 5 (Failure Paths):** D7/D9's best-effort `try/except Exception` wrapping, matching `agent.py`'s own established precedent for memory-adjacent side effects, was checked against every failure point named in the Error Handling table — all five rows resolve to "caught, logged, non-fatal," with no path where a self-correction failure can propagate into the user's turn.
- **Pass 6 (Concurrency):** `_capture_lesson()`'s single `await asyncio.to_thread(...)` call is sequential and awaited before the function returns — no concurrent access to `run_state` or shared Router cache state beyond what M6/M7 already established as safe (adapter caching is lazy-once, already exercised concurrently-safe by the existing `_get()` cache dict).
- **Pass 7 (Edge Cases):** Checked the interaction with M3's `consolidation.py` directly (not just design.md prose) — `"lesson"` falls through consolidation's promotion stage untouched (no promotion branch matches it, same as `"procedural"` today) and is archival-eligible under the generic (non-`"person"`) threshold, which is correct, unremarkable behavior requiring no special-casing. First-turn (empty lesson store) and long-running (many accumulated lessons, bounded by `limit=3`) cases are both explicitly handled per D9.
- **Pass 8 (Task Spec Alignment):** Every `task.md` item names actor ("Implementer"), action, and target file — no task can be read two ways.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 0        | 0        | 0             |

**Verdict**: PASS
