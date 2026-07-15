# Code Dry-Run Report #3

**Scope**: `src/axiom/memory/` + loop wiring (`src/axiom/loop.py`, `src/axiom/agent.py`, `src/axiom/interface/cli.py`)
**Design**: `.claude/specs/005-m3-memory/design.md`
**Reviewed**: 2026-07-15
**Methodology**: e-spec@apex-tools 1.2.0 (includes Pass 10: Value-Path Trace)

---

## Bugs (will cause incorrect behavior)

### [B1] Value computed but dropped — assembled_context never reaches reasoning/prompt
- **File**: `src/axiom/loop.py`:159-160
- **Pass**: Pass 10 (Value-Path Trace)
- **What**: `assembled_context` is computed at line 159 via `await self._memory.assemble_context(user_input)` and used only at line 160 to derive `recalled_ids = [r.id for r in assembled_context.cognitive_memories]`. After that, `assembled_context` is never referenced again. It is not passed to `perceive()` (line 165), not rendered into the system prompt, not injected into the conversation history, and not supplied to `reason()`. The `context` variable at line 165 is produced by `self._perceive.perceive(run_state)` which has no knowledge of the memory result. The two-tier context (working_context + cognitive_memories) is silently discarded.
- **Impact**: The entire M3 feature silently no-ops at runtime. The agent assembles memory context (incurring embedding + SurrealKV + retrieval latency), then throws it away. The model never sees recalled memories or prior conversation units. The story's stated purpose ("Memory is the difference between a sophisticated one-shot chatbot and an agent that genuinely knows you" — requirement.md) is not served even when the code runs without errors. US-01 AC-01.4 ("The loop renders working-tier content as 'Previous Conversations'... and cognitive-tier content as 'Additional Context'") is violated. Design Q2 decision ("the loop renders the result") is violated.
- **Fix**: Wire `assembled_context` into `perceive()` or directly into the prompt-assembly step. Either: (a) pass `assembled_context` as a parameter to `self._perceive.perceive(run_state)` and have the perceive adapter render it into the chat-API slots, or (b) inject `assembled_context` into `run_state` so the perceive adapter can read it from there. Confirm with an end-to-end test that verifies the model's prompt contains recalled memory content.

### [B2] Feature unreachable from user interface — no CLI entry path exists
- **File**: `src/axiom/interface/cli.py`:60
- **Pass**: Pass 10 (Value-Path Trace)
- **What**: Memory defaults to off in `Agent.__init__()` (`memory: bool = False`, agent.py:68). The CLI (`cli.py`) constructs the Agent at line 60 as `Agent(debug=args.debug, provider=args.provider, observe=args.observe)` — the `memory` parameter is never passed. The CLI's `argparse` definition (lines 19-47) has no `--memory` flag. Therefore, from the CLI (the only user-facing interface), `memory` is always `False`, `self._memory_adapter` is always `None`, and `PraoLoop` receives `memory=None`. Every memory code path in `loop.py` is gated on `if self._memory is not None` (lines 158, 172, 189), so all memory operations are skipped unconditionally.
- **Impact**: Behavioral AC for US-01 through US-09 cannot be demonstrated through the real interface. The Memory faculty is fully implemented but permanently dormant in shipped code. A user cannot enable memory without editing source code. The story's Definition of Done #11 ("perceive() calls assemble_context") is technically satisfied in the code, but never reachable from the product.
- **Fix**: Add a `--memory` flag to the CLI argparse and pass it to the Agent constructor:
  ```python
  parser.add_argument("--memory", action="store_true", default=False,
                       help="Enable M3 memory faculty (persistent cross-session memory)")
  # ...
  agent = Agent(debug=args.debug, provider=args.provider, observe=args.observe, memory=args.memory)
  ```

---

## Gaps (missing implementation)

### [G1] No cognitive store writes at Observe — store() never called by the loop
- **File**: `src/axiom/loop.py`:171-199
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: The loop's Observe phase calls `append_unit()` (working-context write) and `reinforce()` (stability boost) but never calls `memory.store()` (cognitive-tier write). Design §13 specifies: "Observe: `asyncio.create_task(memory.store(...))` — One call per cognitive knowledge item to persist (facts, decisions)." The task.md CV1 reconciliation note (task 11.3) documents this as intentional: "cognitive `store` calls at Observe are AGENT-DRIVEN (future M8 callsite), not automatic per turn." This is an acknowledged gap, not an oversight — but it means the cognitive tier is never populated during normal agent operation in M3.
- **Design ref**: Design §13, Table row "Observe | store(content, ...) | Fire-and-forget"

### [G2] FinishIntent does not fire reinforce — recalled memories are not reinforced on finish exits
- **File**: `src/axiom/loop.py`:189-198
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: On a `FinishIntent` exit (lines 189-198), the loop calls `append_unit` but does NOT call `reinforce(recalled_ids)`. On a `RespondIntent` exit (lines 172-185), reinforce IS called. Memories recalled at Perceive but consumed by a cycle that ends in FinishIntent are never reinforced.
- **Design ref**: Design §13 says "Observe: `asyncio.create_task(memory.reinforce(ids))` — IDs of memories assembled into context." No carve-out for FinishIntent exits.

---

## Warnings (potential issues)

### [W1] reinforce() is awaited directly, not fire-and-forget — port contract deviation
- **File**: `src/axiom/loop.py`:184, `src/axiom/memory/adapter.py`:176-185
- **Pass**: Pass 7 (Contract Violations)
- **What**: The design (§3.2, §13) specifies `reinforce` as fire-and-forget: "Loop dispatches via `asyncio.create_task(memory.reinforce(...))`." The loop at line 184 calls `await self._memory.reinforce(recalled_ids)` — a direct await, not `create_task`. The adapter's docstring (adapter.py:177-183) explains this was a deliberate B2 fix to prevent `asyncio.run()` teardown from cancelling pending tasks. The deviation is functionally correct (reinforce completes reliably) but violates the port contract's fire-and-forget invariant and adds latency to the RESPOND exit path.
- **Risk**: If reinforce becomes slow (many IDs, large stability updates), the latency appears on the user-facing response path. The design's fire-and-forget intent was specifically to avoid this.

### [W2] StorageSeam methods are async but execute synchronously — no executor offloading
- **File**: `src/axiom/memory/storage.py`:77-82
- **Pass**: Pass 6 (Concurrency & Async Correctness)
- **What**: The class docstring acknowledges that "All methods are async but call surrealdb synchronously (the embedded SDK is blocking). No executor needed — DB ops are fast (<5ms)." However, this means every storage call blocks the asyncio event loop. If SurrealKV operations ever exceed a few milliseconds (e.g., during large cluster scans in consolidation, or with growing dataset), the event loop is blocked.
- **Risk**: At scale (thousands of memories), consolidation Stage 4 performs O(N) vector queries sequentially on the event loop thread. Each one blocks the loop. Acceptable at personal scale; problematic if memory grows large.

### [W3] Spreading activation write-back uses create_task — may be cancelled by asyncio.run() teardown
- **File**: `src/axiom/memory/retrieval.py`:171
- **Pass**: Pass 6 (Concurrency & Async Correctness)
- **What**: `asyncio.create_task(self._spreading_activation_writeback(top_seeds))` is dispatched fire-and-forget. Since the loop uses `asyncio.run()` (loop.py:133), pending tasks are cancelled when `asyncio.run()` exits. If `_run_async` returns before the spreading activation write-back completes, the task is silently cancelled and neighbour stability is not updated.
- **Risk**: Spreading activation becomes unreliable. The B2 fix for `reinforce()` was to await directly; the same concern applies here but was not addressed.

### [W4] Tests assert intermediate returns, not end behavior — green tests do not prove value reaches user
- **File**: `tests/test_memory_e2e.py`, `tests/test_memory_integration.py`
- **Pass**: Pass 10 (Value-Path Trace)
- **What**: The existing tests (per task.md §14) assert that `assemble_context()` returns the correct `AssembledContext` object and that `recall()` returns `RecallResult` objects. These test the intermediate return value of the memory faculty. No test asserts that the assembled context actually reaches the model's prompt — i.e., no test verifies that `perceive()` or `reason()` receives the memory content. The tests can pass (and do — "121 tests green") while B1 (value dropped) remains undetected.
- **Risk**: False confidence from green test suite. The test boundary stops at the memory faculty output; it does not cross the loop→perceive→reason integration boundary where the value is dropped.

### [W5] consolidate() called in Agent.run() finally block — runs on every turn, not just session end
- **File**: `src/axiom/agent.py`:181-188
- **Pass**: Pass 2 (Execution Path Trace)
- **What**: `Agent.run()` calls `asyncio.run(self._memory_adapter.consolidate())` in its `finally` block. `Agent.run()` is called once per user turn. The design (§9, AC-09.1) specifies: "consolidate() is awaited at session close only — never mid-session, never on a timer, never per-store." If a caller invokes `agent.run()` multiple times in a session, consolidation fires after every turn, not just at session end.
- **Risk**: Performance degradation (consolidation is expensive) and incorrect decay behavior (stage 1 recomputes R frequently, stage 3 may archive memories prematurely because the elapsed time since session start is short). Architecturally, `Agent.run()` is a one-turn API, and the composition root treats each `run()` as a session. This is a design-implementation tension rather than a clear bug, but multi-turn callers will hit it.

---

## Style (code quality, conventions)

### [S1] Duplicate _elapsed_days and _now_utc helper across modules
- **File**: `src/axiom/memory/retrieval.py`:25-34, `src/axiom/memory/consolidation.py`:52-61
- **What**: Both modules define identical `_elapsed_days()` and `_now_utc()` functions. These should be in a shared utility or in `decay.py`.

### [S2] schema.py not reviewed — missing from diff
- **File**: `src/axiom/memory/schema.py`
- **What**: `schema.py` is referenced by `storage.py:90` (`init_schema(self._db)`) but was not available for review in this pass. Unable to verify schema matches design §10.3.

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 2 | 2 | 5 | 2 |

**Verdict**: **FAIL** — two bugs at blocking severity.

B1 is a showstopper: the core value of the M3 milestone (memory context reaching the model) is computed and dropped. The feature silently no-ops. B2 means a user cannot even reach the code path that would trigger B1. Together, they mean M3's stated purpose ("It learns across sessions") is not delivered in the shipped code.

---

## Pass 10 Trace Detail

### Trace: US-01 — Context assembly at Perceive

**Entry point**: `cli.py:main()` → `Agent.run()` → `PraoLoop.run()` → `_run_async()`
**Core value**: `AssembledContext` (two-tier memory: working_context + cognitive_memories)
**Observable effect**: User sees agent response informed by recalled memories

1. **Is the entry point reachable?** NO. `cli.py:60` constructs `Agent(debug=..., provider=..., observe=...)` — no `memory` parameter passed. `Agent.__init__` defaults `memory=False` (agent.py:68). `self._memory_adapter` is `None`. `PraoLoop` receives `memory=None`. All memory paths in `_run_async` are gated on `if self._memory is not None` (loop.py:158). **The feature is unreachable.** → **B2**

2. **Is the core value computed?** YES (when memory is non-None). `assembled_context = await self._memory.assemble_context(user_input)` at loop.py:159 correctly produces an `AssembledContext` object with both tiers.

3. **Is the core value consumed at the right place?** NO. `assembled_context` is used only at loop.py:160 to derive `recalled_ids = [r.id for r in assembled_context.cognitive_memories]`. After line 160, `assembled_context` is never referenced. The `perceive()` call at line 165 receives `run_state` which does not contain memory context. The value is **dropped**. → **B1**

4. **Does the value reach the observable effect?** NO. The model prompt is constructed from `context` (line 165, output of `perceive(run_state)`), not from `assembled_context`. The user's response is generated from a prompt that never contains recalled memories.

### Intermediate-test check

Existing tests (`test_memory_e2e.py`, `test_memory_integration.py`) assert that `assemble_context()` returns correctly shaped objects. These are intermediate-return assertions. No test drives a full `PraoLoop.run()` or `Agent.run()` with memory enabled and asserts the output contains recalled content. The tests are green but do not cover the B1 failure. → **W4**
