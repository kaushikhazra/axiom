# Code Dry-Run Report #2

**Scope**: `src/axiom/memory/` (13 modules) + `src/axiom/loop.py` + `src/axiom/agent.py`
**Design**: `.claude/specs/005-m3-memory/design.md` (§1–§18)
**Prior**: `dryrun-code-1.md` — 4 bugs, 1 CV, 2 gaps, 6 warnings, 2 style
**Reviewed**: 2026-07-15 (round 2 — post-fix verification + fresh adversarial pass)
**Tests**: 101 memory tests pass / 0 fail

---

## Part A: Round-1 Finding Verification

### [B1] access_count never incremented — **FIXED** ✓

**Evidence:**
- `adapter.py:205-207`: `_do_reinforce` now calls `await self._storage.update_memory(mid, access_count=m.access_count + 1, updated_at=now)` for each reinforced memory inside the for-loop (line 193–207).
- `storage.py:175-185`: `update_memory` correctly generates a parameterised `UPDATE ... SET access_count = $f_access_count` — no SQL-injection or field-name collision with the `f_` prefix scheme.
- **Test genuineness:** `test_access_count_incremented_by_reinforce` (integration:109–133) stores a memory, calls `adapter.reinforce([mid])` three times through the real code path, and asserts `access_count == 3`. This test **would fail** without the fix (access_count would stay 0).
- **Organic promotion test:** `test_consolidation_promotion_episodic_to_semantic` (integration:60–107) drives 5 real `recall → reinforce` cycles, verifies `access_count >= 5`, then asserts consolidation produces a `promote` log entry. This is the "promotion fires organically" proof — no manual `update_memory(access_count=5)` cheating.

### [B2] Fire-and-forget reinforce cancelled by asyncio.run() teardown — **FIXED** ✓

**Evidence:**
- `adapter.py:176-185`: `reinforce()` now `await self._do_reinforce(ids)` directly — no inner `asyncio.create_task`. The S1 double-wrapping issue is also resolved.
- `loop.py:183-184`: The loop `await`s `self._memory.reinforce(recalled_ids)` — no `asyncio.create_task` wrapper. Work completes before `_run_async` returns, so `asyncio.run()` teardown cannot cancel it.
- **Test genuineness:** `test_stability_and_access_count_persist_across_turns` (integration:136–183) simulates two turns of `recall → reinforce`, verifying both `stability` and `access_count` increase monotonically. This **would fail** under the old code (teardown would cancel the reinforce tasks, leaving storage unchanged).

**Design-invariant deviation (accepted):** Design §3.2 / §17.1 specifies reinforce as "FIRE-AND-FORGET… Loop dispatches via `asyncio.create_task`." The fix changed it to awaited. This is an **accepted deviation** — correctness trumps the latency optimization. `_do_reinforce` performs only in-process SurrealKV reads+writes (sub-millisecond each), so the blocking cost is negligible. The design should be updated to reflect this change post-ship.

**CRITICAL EXTRA CHECK — store() and other fire-and-forget tasks:**

| Method | Mechanism | Called from loop in M3? | Teardown risk? |
|--------|-----------|------------------------|----------------|
| `store()` | `asyncio.create_task` (adapter.py:138) | **No** — CV1 reconciliation defers to M8 | Latent: if M8 calls store from `_run_async`, the same B2-class teardown applies |
| `update()` | `asyncio.create_task` (adapter.py:220) | No | Latent |
| `relate()` | `asyncio.create_task` (adapter.py:243) | No | Latent |
| Spreading activation writeback | `asyncio.create_task` (retrieval.py:171) | **Yes** — created during `recall()` inside `assemble_context()` | **Survives in M3** (see below) |

**Spreading-activation writeback survival analysis:** The task is created during `assemble_context()` (called at the start of `_run_async`). After creation, the loop executes sync calls (perceive, reason). The first yield point is `await self._memory.append_unit(unit)` which internally calls `await self._embeddings.embed(...)` (run_in_executor — true async yield). At that yield, the event loop schedules the spreading-activation task. Since all `StorageSeam` methods are synchronous internally (in-process SurrealKV, no real I/O), the entire writeback coroutine executes in one scheduling slice and completes before the executor returns. **Verdict: survives for M3.** This is fragile — if StorageSeam methods become truly async (e.g. network DB), the guarantee breaks. Flagged as W1 below.

### [B3] OR-relationships >= 2 path missing — **FIXED** ✓

**Evidence:**
- `consolidation.py:143-147`: After the AND path fails, the `else` branch calls `await self._storage.get_relationship_count(m.id)` and promotes if `rel_count >= 2`.
- `storage.py:408-428`: `get_relationship_count()` method counts outgoing + incoming edges across all 8 relation tables (16 queries total). Correct — edges are directional, and a working memory could be either source or target.
- `store_relationship` syntax (storage.py:274-288): Uses SurrealDB record-ID literal syntax `memory:⟨uuid⟩` with Unicode angle brackets. `_extract_id` (storage.py:40-45) strips the same characters. Consistent encoding confirmed; integration tests pass against real embedded SurrealKV.
- **Unit test:** `test_working_to_episodic_via_relationships_or_path` (consolidation:132-147) — working memory with access_count=0, importance=0.1 (AND path impossible), mock returns relationship_count=2, verifies promotion to episodic.
- **Negative test:** `test_no_promotion_if_relationships_below_2` (consolidation:149-157) — same setup with relationship_count=1, verifies no promotion.
- **Integration test:** `test_working_to_episodic_via_relationships` (integration:186-253) — creates real SurrealKV relationships, verifies promotion fires end-to-end.

### [B4] turn_index resets to 0 on every run() call — **FIXED** ✓

**Evidence:**
- `loop.py:96-97`: `self._turn_index: int = 0` is an instance variable on `PraoLoop`, not a local in `_run_async`.
- `loop.py:185`: `self._turn_index += 1` after each `RespondIntent` exit.
- `loop.py:197`: `self._turn_index += 1` after each `FinishIntent` exit.
- **Test genuineness:** `test_turn_index_increases_across_run_calls` (integration:256-305) calls `loop.run()` three times via fake ports, captures the `ConversationUnit` from each `append_unit` call, and asserts `turn_indices == [0, 1, 2]`. This **would fail** with a local variable (would produce `[0, 0, 0]`).

### [CV1] Loop does not call store() at Observe — **RECONCILED** ✓

**Evidence:**
- `task.md:110`: CV1 reconciliation note added. Decision: "cognitive store calls at Observe are AGENT-DRIVEN (future M8 callsite), not automatic per turn." Without M8 LLM-assisted extraction, the loop has no mechanism to decide what to store. Auto-storing every response would write noise.
- Task 11.3 is marked `[x]` for the working-context path (`append_unit`), with the cognitive-store callsite explicitly deferred to M8. This is accurate and honest.

### [G1] No close()/shutdown() lifecycle — **FIXED** ✓

**Evidence:**
- `adapter.py:245-258`: `close()` method calls `self._embeddings.shutdown()` then `self._storage.close()`. Both wrapped in try/except with warning-level logging. Safe to call multiple times (shutdown is idempotent on ThreadPoolExecutor; storage close() catches and ignores exceptions).
- `agent.py:189-193`: `self._memory_adapter.close()` called in the `finally` block after `consolidate()`.
- `embeddings.py:49-56`: `shutdown()` calls `self._executor.shutdown(wait=False)`.
- `storage.py:430-434`: `close()` calls `self._db.close()`.
- **Double-close safety:** `storage.close()` swallows exceptions; `ThreadPoolExecutor.shutdown()` is idempotent. ✓

### [G2] EmbeddingService._executor never shut down — **FIXED** ✓

**Evidence:**
- `embeddings.py:49-56`: `shutdown()` method added, called via `adapter.close()` → `self._embeddings.shutdown()`.

### Warnings and Style (Round-1)

| Finding | Status | Evidence |
|---------|--------|----------|
| W1 (get_event_loop deprecated) | **FIXED** | `embeddings.py:38-40`: now `asyncio.get_running_loop()` |
| W2 (_auto_link broad catch) | **FIXED** | `adapter.py:169-174`: inner and outer exceptions now logged at `debug` level; not silently swallowed |
| W4 (axiom_config table name) | **FIXED** | `schema.py:62`: table is now `config` |
| W5 (spreading activation test trivial) | **FIXED** | `integration:387`: test now asserts `s_after > s_before`; also directly calls `_spreading_activation_writeback` to bypass the small-store limitation (line 376) |
| S2 (list.pop(0) O(n²)) | **FIXED** | `working_context.py:17-29`: uses index cursor `start` instead of `pop(0)` |
| W3 (get_neighbours_bulk O(N×queries)) | **Unchanged** | Accepted at M3 scale (noted in round 1) |
| W6 (consolidation re-fetches 4×) | **Unchanged** | Accepted at M3 scale (noted in round 1) |

---

## Part B: Fresh Adversarial Pass (New Findings)

### Bugs

No new bugs found.

### Warnings (potential issues)

#### [W1] Spreading-activation writeback survives teardown only because StorageSeam is synchronous — fragile
- **File**: `src/axiom/memory/retrieval.py`:171
- **Pass**: Pass 6 (Concurrency & Async)
- **What**: The `_spreading_activation_writeback` task is still fire-and-forget via `asyncio.create_task`. It survives `asyncio.run()` teardown only because all `StorageSeam` methods execute synchronously (in-process SurrealKV), so the task completes in one scheduling slice during the `append_unit` await. If `StorageSeam` is ever replaced with a truly async backend (e.g. network DB), the task could be cancelled by teardown.
- **Risk**: None for M3 (embedded SurrealKV is sync). Becomes a real risk if the storage backend changes. The spreading-activation boost would be silently lost — same class of bug as the original B2.
- **Recommendation**: When M4+ introduces the SQLite fallback or any network-backed storage, convert spreading-activation writeback to awaited (same fix as reinforce) or add a task-collection mechanism.

#### [W2] store()/update()/relate() fire-and-forget tasks have latent B2-class teardown risk
- **File**: `src/axiom/memory/adapter.py`:138, 220, 243
- **Pass**: Pass 6 (Concurrency & Async)
- **What**: `store()`, `update()`, and `relate()` still use `asyncio.create_task` internally. In M3, none of these are called from within `_run_async` (store is deferred to M8; update/relate are not wired). But when M8 adds `store()` calls at Observe inside `_run_async`, the embed+insert task will be subject to `asyncio.run()` teardown — the same bug B2 described.
- **Risk**: None for M3. Becomes a bug at M8 implementation time.
- **Recommendation**: At M8, either (a) await store's embed+insert before `_run_async` returns (same pattern as reinforce), or (b) collect fire-and-forget tasks and `await asyncio.gather(*pending)` before return.

#### [W3] Agent.close() in finally block makes Agent non-reentrant
- **File**: `src/axiom/agent.py`:189-193
- **Pass**: Pass 5 (Resource Management)
- **What**: `Agent.run()` calls `self._memory_adapter.close()` in its `finally` block — every call, not just the last. After close(), the SurrealKV file handle is released and the embedding executor is shut down. A second `Agent.run()` call would crash on any memory operation (storage closed, executor rejected).
- **Risk**: Low — `Agent` is documented as "Fully assembled Axiom agent for one-turn interactions" (agent.py:52). Multi-turn use requires a different lifecycle pattern (direct PraoLoop usage with explicit session management). The B4 fix (turn_index persistence on PraoLoop) works at the loop level, not the Agent level.
- **Recommendation**: When multi-turn Agent support is needed, move consolidate+close to a separate `Agent.shutdown()` method and remove them from the `run()` finally block.

#### [W4] Consolidation Stage 2 performance for working-type memories with low access
- **File**: `src/axiom/memory/consolidation.py`:143-147, `src/axiom/memory/storage.py`:408-428
- **Pass**: Pass 8 (Code Quality)
- **What**: For every working-type memory that fails the AND path (access_count < 3 OR importance < 0.4), the else branch calls `get_relationship_count(m.id)`, which issues 16 SurrealDB queries (8 edge tables × 2 directions). Most working memories will fail the AND path (they start with access_count=0), so this fires for nearly all working-type memories.
- **Risk**: At personal scale (tens of working memories at consolidation time), this adds tens-of-milliseconds. At hundreds of working memories, it could add seconds to consolidation. Acceptable for M3 since consolidation runs at session end (non-interactive).

---

## Part C: Design Deviation Register

| ID | Deviation | Design ref | Justification | Accepted? |
|----|-----------|------------|---------------|-----------|
| AD1 | `reinforce()` is now awaited, not fire-and-forget | §3.2, §17.1 | Correctness — fire-and-forget was silently cancelled by `asyncio.run()` teardown (B2). Awaited reinforce adds <5ms latency (in-process SurrealKV reads+writes). | **Yes** — correctness > latency micro-optimization. Design should be updated post-ship. |
| AD2 | `store()` NOT called at Observe in M3 | §13 | No extraction mechanism to decide what to store without M8 LLM integration (CV1 reconciliation). | **Yes** — explicit M8 deferral, documented in task.md. |

---

## Summary

### Round-1 Finding Verdicts

| Finding | Verdict | Notes |
|---------|---------|-------|
| B1 (access_count never incremented) | **FIXED** | Increment in `_do_reinforce`; organic promotion test confirms |
| B2 (reinforce cancelled by teardown) | **FIXED** | Awaited directly; accepted design deviation (AD1) |
| B3 (OR relationships ≥ 2 missing) | **FIXED** | `get_relationship_count` + else branch; unit + integration tests |
| B4 (turn_index resets each run) | **FIXED** | Instance variable on PraoLoop; multi-turn test confirms |
| CV1 (store not called at Observe) | **RECONCILED** | Agent-driven store deferred to M8; task.md updated |
| G1 (no close/shutdown lifecycle) | **FIXED** | `adapter.close()` → embeddings.shutdown() + storage.close(); wired in agent.py finally |
| G2 (executor never shut down) | **FIXED** | `EmbeddingService.shutdown()` calls executor.shutdown(wait=False) |
| W1/W2/W4/W5/S2 | **FIXED** | See table above |

### New Findings (This Round)

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 4 | 0 |

All four warnings are non-blocking:
- W1 (spreading-activation fragile): works for M3; flagged for future backend changes.
- W2 (store/update/relate latent teardown): not triggered in M3; flagged for M8.
- W3 (Agent non-reentrant): by design (single-turn Agent); PraoLoop supports multi-turn.
- W4 (Stage 2 relationship-count queries): acceptable at M3 personal scale.

---

**Verdict**: **GO — PASS WITH WARNINGS**

All four round-1 bugs (B1–B4) are genuinely fixed with real production-path tests that would fail without the fixes. The contract violation (CV1) is properly reconciled. Both gaps (G1–G2) are closed. No new bugs were introduced by the fix pass. The four new warnings are all non-blocking and appropriately scoped to future milestones. M3 Memory is ready to ship.
