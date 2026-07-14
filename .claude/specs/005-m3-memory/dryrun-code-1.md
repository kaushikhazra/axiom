# Code Dry-Run Report #1

**Scope**: `src/axiom/memory/` (all 13 modules) + `src/axiom/loop.py` + `src/axiom/agent.py`
**Design**: `.claude/specs/005-m3-memory/design.md` (§1–§18)
**Reviewed**: 2026-07-15

---

## Bugs (will cause incorrect behavior)

### [B1] `access_count` is never incremented — all consolidation promotions are dead code
- **File**: `src/axiom/memory/adapter.py`:129 (init to 0), entire codebase (no increment)
- **Pass**: Pass 2 (Execution Path Trace) + Pass 7 (Contract Violations)
- **What**: `Memory.access_count` is initialised to `0` in `adapter.store()` and **never incremented** by any code path — not by `reinforce()`, not by `recall()`, not by `assemble_context()`. The `_do_reinforce` method (adapter.py:177–197) updates `stability` and `last_accessed` but not `access_count`. `bulk_update_stability` (storage.py:339–349) likewise only touches stability and last_accessed.
- **Impact**: Every consolidation promotion rule in `consolidation.py` Stage 2 is gated on `access_count >= 3` or `>= 5` (lines 141, 145, 147, 149, 153). Because the count is always 0, **no promotion will ever fire**: working→episodic, episodic→person, episodic→procedural, episodic→semantic, semantic→person are all unreachable. The consolidation test `test_consolidation_promotion_episodic_to_semantic` (integration test, line 69–70) works around this by manually setting `access_count=5` via `_storage.update_memory`, masking the bug.
- **Fix**: In `_do_reinforce` (adapter.py:177–197), after computing new stability, also increment `access_count` for each reinforced memory. Change the `bulk_update_stability` path or add a separate `update_memory(mid, access_count=m.access_count + 1)` call. Alternatively, increment `access_count` in the retrieval pipeline's write-back path so "recalled = accessed."

### [B2] Fire-and-forget `reinforce` tasks cancelled by `asyncio.run()` teardown
- **File**: `src/axiom/loop.py`:178, `src/axiom/memory/adapter.py`:174–175
- **Pass**: Pass 6 (Concurrency & Async)
- **What**: `PraoLoop.run()` calls `asyncio.run(self._run_async(...))`. Inside `_run_async`, at the terminal exit (RespondIntent), line 178 fires `asyncio.create_task(self._memory.reinforce(recalled_ids))` and then **immediately returns**. `asyncio.run()` enters its cleanup phase, calling `_cancel_all_tasks(loop)`, which cancels every pending task — including the reinforce task (T1) and, if T1 managed to start, the inner `_do_reinforce` task (T2 created at adapter.py:175). Python's `asyncio.run` explicitly cancels all tasks in its finally block (CPython `_cancel_all_tasks`). The net result: **reinforce stability updates are silently lost on every turn.**
- **Impact**: The testing-effect reinforcement (design §6.2: "retrieving a fading memory strengthens it more than revisiting a fresh one") never fires in production use. Memories decay without any access-based stability boost. The integration test `test_spreading_activation_raises_neighbour_stability` uses `asyncio.sleep(0.5)` within the same event loop run to give tasks time to complete, so it passes — but the real loop path has no such sleep.
- **Fix**: Instead of `asyncio.create_task`, **await the reinforce call** before returning. Since `reinforce` is designed to be fast (just reads + updates a few rows), the latency cost is negligible. Alternatively, await all pending fire-and-forget tasks before `_run_async` returns (collect them in a list, `await asyncio.gather(*pending)` before the return statement). A third option: move reinforce out of the async coroutine and into the `agent.py` finally block alongside consolidate.

### [B3] Working→episodic promotion missing "OR relationships ≥ 2" alternative path
- **File**: `src/axiom/memory/consolidation.py`:139–142
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §9 Stage 2 specifies working→episodic promotion as: "`access_count >= 3 AND importance >= 0.4, **OR relationships >= 2**`". The code implements only the first conjunction:
  ```python
  if m.access_count >= 3 and m.importance >= 0.4:
      new_type = "episodic"
  ```
  The `OR relationships >= 2` branch is entirely absent. No test checks this path.
- **Impact**: Working-type memories that have accrued ≥ 2 graph relationships but have low access count or low importance will never be promoted to episodic — they will fade and be archived instead.
- **Fix**: Add the alternative condition. Requires counting relationships for the memory. Either add a `get_relationship_count(memory_id)` method to StorageSeam, or query outgoing+incoming relationship edges for each working-type memory in the promotion loop.

### [B4] `turn_index` resets to 0 on every `PraoLoop.run()` call — not monotonically increasing
- **File**: `src/axiom/loop.py`:153
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: `turn_index` is a local variable in `_run_async` initialised to `0` on every call (line 153). It only increments on ACT cycles within a single turn (line 206). For a typical single-cycle resolution (user asks → agent responds), `turn_index` is always `0`. Across multiple calls to `Agent.run()`, all `ConversationUnit` objects in the working buffer will carry `turn_index=0`.
- **Impact**: The `ConversationUnit.turn_index` field is defined as "Monotonically increasing turn counter within the session" (design §4.2). The field is semantically meaningless in practice: all units have the same value. Nothing in M3 actually uses `turn_index` for ordering (the deque preserves insertion order), so this is a data-correctness bug, not a functional crash — but it violates the model contract and will cause confusion if future code relies on `turn_index` for ordering or dedup.
- **Fix**: Move `turn_index` to instance state on `PraoLoop` (or a session-level counter passed from `Agent`), incrementing it once per `run()` call (each user turn = one turn_index bump).

---

## Contract Violations

### [CV1] Loop does not call `store()` at Observe — task.md 11.3 marked complete
- **File**: `src/axiom/loop.py` (absent code)
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §13 specifies: "Observe | `store(content, ...)` | Fire-and-forget via `create_task` | One call per cognitive knowledge item to persist." Task.md 11.3 is marked `[x]` done and reads: "For cognitive-store items (facts, decisions worth persisting), separate `asyncio.create_task(self.memory.store(content, ...))` calls are issued." But the loop code contains **no** `store()` call anywhere. The only memory calls in loop.py are `assemble_context`, `append_unit`, and `reinforce`.
- **Impact**: In M3, no cognitive memories are ever stored from the loop. The `store()` path works (tested independently), but without an extraction mechanism to decide *what* to store, the loop has nothing to persist. This is arguably acceptable if M8 (LLM-assisted extraction) is the planned source of store calls — but the task checklist claims it's done, which is incorrect.
- **Fix**: Either (a) add a minimal extraction heuristic in the Observe phase that stores the agent's response text as a cognitive memory, or (b) remark task 11.3 as partially complete and note that cognitive store calls require M8 extraction. Do NOT mark the task done if the code doesn't do it.

---

## Gaps (missing implementation)

### [G1] No `close()`/`shutdown()` lifecycle method on `CognitiveMemoryAdapter`
- **File**: `src/axiom/memory/adapter.py` (missing method)
- **Pass**: Pass 5 (Resource Management)
- **What**: `StorageSeam` has a `close()` method (storage.py:406–410) that calls `self._db.close()`. But `CognitiveMemoryAdapter` has no `close()`, `shutdown()`, or `__del__` method that calls it. In `agent.py`'s finally block, only `consolidate()` is called — never `close()`. The integration and E2E tests use `del adapter` and rely on GC to release the SurrealKV file handle.
- **Design ref**: Not explicitly specified in design (no lifecycle section), but implied by the "held open for the adapter's lifetime" statement in §10.1.
- **Risk**: On Windows, unreleased file handles may prevent reopening the same SurrealKV file or cause lock-file contention across sessions. GC-based cleanup is non-deterministic.

### [G2] `EmbeddingService._executor` ThreadPoolExecutor is never shut down
- **File**: `src/axiom/memory/embeddings.py`:17
- **Pass**: Pass 5 (Resource Management)
- **What**: The `ThreadPoolExecutor(max_workers=1)` is created at `__init__` but never `shutdown()`. Python's atexit handler will clean it up at interpreter exit, so this is not a leak — but in test scenarios that create many adapters, threads accumulate.
- **Design ref**: Not specified.

---

## Warnings (potential issues)

### [W1] `asyncio.get_event_loop()` deprecated pattern in `embeddings.py`
- **File**: `src/axiom/memory/embeddings.py`:38, 42
- **Pass**: Pass 8 (Code Quality)
- **What**: `asyncio.get_event_loop()` is deprecated for getting the running loop in Python 3.10+. When called from an async context (which is the case here — `embed` is awaited), it works correctly. But the documented replacement is `asyncio.get_running_loop()`.
- **Risk**: DeprecationWarning may be emitted in Python 3.12+. Will break in a future Python version that removes the fallback.

### [W2] `_auto_link` exception catch is too broad
- **File**: `src/axiom/memory/adapter.py`:169
- **Pass**: Pass 3 (Error Path Trace)
- **What**: The inner `except Exception: pass` block (line 169) is intended for duplicate-edge errors but catches **all** exceptions — including connection errors, schema errors, serialization failures. These are silently swallowed with no logging.
- **Risk**: Storage failures during auto-linking are invisible. A systematic failure (e.g. schema corruption) would silently prevent all auto-linking with no diagnostic trail.

### [W3] `get_neighbours_bulk` issues O(8 × |seeds| × depth) individual queries
- **File**: `src/axiom/memory/storage.py`:288–337
- **Pass**: Pass 7 (Contract Violations)
- **What**: For 5 seed IDs at depth 3, the method issues up to 5 × 8 × 2 × 3 = 240 individual `db.query()` calls (8 edge tables × outgoing+incoming × 3 hops × expanding frontier). Design §7.4 says "One call to `storage.get_neighbours_bulk(seeds, max_depth=3)` — not per-seed" (meaning the caller makes one call), but internally the implementation is N individual queries. Since these are synchronous in-process calls (no network), each takes <1ms, but 240 calls at 1ms = 240ms — which blows the <100ms recall target for non-trivial graphs.
- **Risk**: Recall latency will exceed the <100ms target once the graph has real content. This is the primary contributor to latency risk identified in design W7.

### [W4] Schema table named `axiom_config` instead of `config`
- **File**: `src/axiom/memory/schema.py`:62
- **Pass**: Pass 1 (Design Conformance)
- **What**: Design §10.3 specifies a `config` table. The schema creates `axiom_config`. This is a cosmetic divergence — no code currently reads/writes this table (the consolidation debounce counter is a future feature). But if future code follows the design document's table name, it will fail.
- **Risk**: Low; cosmetic until the debounce feature is implemented.

### [W5] Integration test `test_spreading_activation` does not assert the core invariant
- **File**: `tests/test_memory_integration.py`:122–126
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: The test asserts `s_after is not None` and `s_before is not None` but does **not** assert `s_after > s_before` (the actual spreading-activation invariant). The comment says "We can't guarantee it fires if mid1 wasn't in top results" — but the test should ensure mid1 IS in top results (it stores only two memories and queries for one). The assertion is trivially true (both are always not-None) and does not test the invariant.
- **Risk**: Spreading activation could be completely broken and this test would still pass.

### [W6] Consolidation re-fetches all active memories 4 times
- **File**: `src/axiom/memory/consolidation.py`:80, 87, 91, 95
- **Pass**: Pass 8 (Code Quality)
- **What**: `consolidate()` calls `self._storage.get_all_active()` four times (once initially, and again before Stage 2, Stage 3, and Stage 4). Each call scans the full memory table. For small stores this is fine; at scale it multiplies the consolidation cost.
- **Risk**: Low for M3 (personal-scale). Will matter if memory count grows to thousands.

---

## Style (code quality, conventions)

### [S1] Double fire-and-forget wrapping on `reinforce`
- **File**: `src/axiom/loop.py`:178 + `src/axiom/memory/adapter.py`:174–175
- **What**: The loop calls `asyncio.create_task(self._memory.reinforce(ids))`. Inside `reinforce`, another `asyncio.create_task(self._do_reinforce(ids))` is issued. This is two layers of fire-and-forget for a single operation. The design says "The loop always dispatches these via `asyncio.create_task`" (§3.2) — so either the loop should await reinforce (which internally fires-and-forgets), or the adapter's reinforce should NOT internally create_task (since the loop already did). Pick one layer, not both.

### [S2] `_apply_token_cap` uses `list.pop(0)` — O(n²)
- **File**: `src/axiom/memory/working_context.py`:23–24
- **What**: `result.pop(0)` in a while loop is O(n) per pop, O(n²) total. For max 50 units this is negligible, but a `collections.deque` or index-based slice would be O(n).

---

## Test Coverage Assessment

The 121 tests cover the happy paths well but have these blind spots:

| Invariant | Tested? | Note |
|-----------|---------|------|
| `access_count` incremented on access | ❌ | No test checks that recall/reinforce bumps count; integration test manually sets it |
| Reinforce actually persists in loop context | ❌ | Integration test uses `asyncio.sleep` workaround; no test from `PraoLoop.run()` verifying reinforce landed |
| Spreading activation invariant (s_after > s_before) | ❌ | Test asserts non-None only (W5) |
| Working→episodic "OR relationships ≥ 2" path | ❌ | Alternative path not implemented (B3) |
| `turn_index` monotonically increasing across session | ❌ | No test calls `run()` multiple times and checks turn_index sequence |
| StorageSeam.close() called on shutdown | ❌ | No test verifies the DB handle is released |
| store() called from loop at Observe | ❌ | No loop-level test exercises the cognitive store path |

---

## Summary

| Bugs | Contract Violations | Gaps | Warnings | Style |
|------|---------------------|------|----------|-------|
| 4 | 1 | 2 | 6 | 2 |

**Verdict**: **FAIL — needs fixes before M3 ships.**

B1 (access_count never incremented) and B2 (reinforce tasks cancelled) are both severity-HIGH: together they mean the decay reinforcement system — a core M3 differentiator — does not function in production. No memory ever gets its stability boosted by access, and no memory ever gets its access_count incremented, so no promotion rule ever fires. The decay model writes (design §6.2, §9 Stage 2) are effectively dead code.

### Minimum fixes required for GO:

1. **B1**: Increment `access_count` in the reinforce path (adapter.py `_do_reinforce`).
2. **B2**: Await reinforce before returning from `_run_async`, or collect fire-and-forget tasks and drain them before return.
3. **B3**: Add the `OR relationships >= 2` condition to the working→episodic promotion rule.
4. **B4**: Make `turn_index` a session-level counter on `PraoLoop` (or passed from `Agent`).
5. **CV1**: Either add store calls in the loop's Observe phase, or update task.md 11.3 to reflect the actual state.

After these five fixes, re-run the code dryrun for `dryrun-code-2.md`.
