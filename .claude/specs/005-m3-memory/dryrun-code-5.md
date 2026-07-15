# Code Dry-Run Report #5 (Finding-3 Verification Pass)

**Scope**: Verification that Finding 3 (cognitive-tier persistence wiring) is closed by commit da7864a. Files: `src/axiom/loop.py`, `src/axiom/memory/adapter.py`, `src/axiom/memory/port.py`, `src/axiom/memory/storage.py`, `src/axiom/memory/embeddings.py`
**Design**: `.claude/specs/005-m3-memory/design.md`
**Reviewed**: 2026-07-15
**Methodology**: e-spec@apex-tools 1.2.0 (Pass 10: Value-Path Trace — verification mode)
**Prior report**: `dryrun-code-4.md` — verdict PASS (B1/B2 closed)

---

## 1. Finding 3 — loop never persisted to cognitive tier: **CLOSED**

### Pass 10 Value-Path Trace

**Value**: exchange content string → Memory record in persistent SurrealKV
**Entry**: `PraoLoop._run_async()` RespondIntent branch

**Step 1 — Value constructed:**
`loop.py:194`: `exchange_content = f"User: {user_input}\nAgent: {intent.text}"` — concatenates the user turn and the agent response into a single string. Content is non-empty for any RespondIntent (intent.text is the agent reply). ✔

**Step 2 — store() called and AWAITED:**
`loop.py:195`: `await self._memory.store(exchange_content, memory_type="episodic")` — `await` keyword present. This is inside the `async def _run_async()` method, which is driven by `asyncio.run()` at `loop.py:135`. Because it is `await`ed (not `create_task`), the coroutine completes before the function returns, and therefore before `asyncio.run()` tears down the event loop. **Teardown-cancellation hazard is eliminated.** ✔

**Step 3 — adapter.store() awaits end-to-end:**
`adapter.py:102-145`: `async def store(...)` builds a `Memory` dataclass with `memory_type="episodic"`, `state="active"`, auto-classified importance, stability from `STABILITY_BY_TYPE`, then:
`adapter.py:144`: `await self._embed_and_store(memory)` — **AWAITED** (not `create_task`). The docstring and comment at line 143 confirm the B3-store fix. ✔

**Step 4 — _embed_and_store completes embedding + DB write:**
`adapter.py:147-155`: `async def _embed_and_store(memory)`:
- `adapter.py:150`: `embedding = await self._embeddings.embed(memory.content)` — embedding computed via `EmbeddingService.embed()` which offloads to a ThreadPoolExecutor (`embeddings.py:36-40`). Awaited. ✔
- `adapter.py:151`: `await self._storage.store_memory_with_embedding(memory, embedding)` — writes to StorageSeam. Awaited. ✔
- `adapter.py:153`: `await self._auto_link(memory.id)` — creates relationship edges for similar memories. Awaited. ✔

**Step 5 — StorageSeam writes to persistent SurrealKV:**
`storage.py:84-91`: Constructor opens `surrealkv://{path}` URI via `Surreal(uri)` + `connect()`. SurrealKV is an embedded persistent key-value store (disk-backed, not in-memory). Data survives process restart. ✔
`storage.py:139-166`: `store_memory_with_embedding()` executes a `CREATE` query with all Memory fields + embedding vector. The SurrealDB embedded SDK call is synchronous/blocking — the `await` completes when the data is on disk. ✔

**Step 6 — FinishIntent correctly SKIPS store:**
`loop.py:199-209`: FinishIntent branch calls `append_unit()` (working-context) but does NOT call `store()`. This is correct — FinishIntent has `agent_text=""`, there is no meaningful exchange to persist. ✔

**Conclusion**: The full persist path `loop.py:195 (await) → adapter.py:144 (await) → adapter.py:150-151 (await embed + await DB write) → storage.py:139-166 (SurrealKV disk write)` is fully awaited end-to-end. The exchange genuinely lands in persistent SurrealKV. Cross-session learning is now real. **Finding 3 is CLOSED.**

---

## 2. Regression Check — store() semantics change

### 2a. Callers of adapter.store()

Exhaustive grep of `src/` for `.store(` on memory objects:

| Caller | File:Line | Behavior |
|--------|-----------|----------|
| PraoLoop._run_async | `loop.py:195` | `await self._memory.store(...)` — sole production caller. Awaited. ✔ |

**No other production callers.** The loop is the only code path that calls `store()` in `src/`. Test files (`test_memory_integration.py:26,433,554`, `test_memory_port_contract.py:68`, `test_memory_e2e.py:26`) call it directly but these are test harnesses, not production paths.

### 2b. MemoryPort contract (port.py)

`port.py:45`: Comment reads `# Cognitive store ONLY. Fire-and-forget. Returns UUID4 id synchronously.`

**⚠ STALE CONTRACT COMMENT.** The comment says "fire-and-forget" but the implementation is now fully awaited. The behavior change is CORRECT (fire-and-forget was the bug), but the port comment is stale and misleading. Any future implementer of MemoryPort reading this comment would believe `store()` should fire-and-forget, which would reintroduce Finding 3.

**Severity**: Warning (W1). The comment does not affect runtime, but it is a documentation lie that invites regression.

### 2c. Other fire-and-forget methods still using create_task

| Method | File:Line | Still fire-and-forget? | Teardown risk? |
|--------|-----------|----------------------|----------------|
| `update()` | `adapter.py:226` | YES — `asyncio.create_task(self._do_update(...))` | **YES** — same teardown-cancellation hazard as the original store()/reinforce() bugs. If update() is called from within `asyncio.run()` and the loop returns immediately after, the task may be cancelled before the DB write completes. |
| `relate()` | `adapter.py:249` | YES — `asyncio.create_task(self._do_relate(...))` | **YES** — same hazard. |

**Current exposure**: Neither `update()` nor `relate()` is called from the loop today (grep confirms no `._memory.update(` or `._memory.relate(` in `src/`). So the hazard is latent, not active. But the inconsistency is real — `store()` and `reinforce()` were fixed to await, while `update()` and `relate()` were not.

**Severity**: Warning (W2). Latent — no current caller triggers the bug. But when these methods gain callers from the loop (M8 smart extraction will likely call `update()`), the same teardown-cancellation bug will reappear.

### 2d. _auto_link — now awaited inside _embed_and_store

`adapter.py:153`: `await self._auto_link(memory.id)` — this was always awaited within `_embed_and_store`. When `_embed_and_store` was fire-and-forget (via create_task), `_auto_link` was indirectly fire-and-forget too. Now that `_embed_and_store` is awaited, `_auto_link` is also fully awaited on the hot path. This adds latency (vector search + relationship writes) but is functionally correct. No regression.

---

## 3. New Bugs Check

### 3a. Deadlock risk
No deadlock. The persist path is linear: `await store → await _embed_and_store → await embed + await DB write + await _auto_link`. No locks, no re-entrant calls, no circular waits. ✔

### 3b. Double-store risk
No double-store. `store()` is called once per RespondIntent exit (`loop.py:195`). The loop returns immediately after. `append_unit()` writes to working-context (in-memory ring buffer), `store()` writes to cognitive store (SurrealKV) — two different targets, no duplication. ✔

### 3c. Storing noise
Minor concern. Every exchange is stored verbatim — including trivial ones like "User: hi\nAgent: Hello! How can I help you?". The design explicitly defers smart extraction to M8 (`loop.py:17-18` docstring). This is acceptable for M3 but will need pruning. Not a bug — a known M8 deferral. ✔

### 3d. Embedding cost on the hot path
`embeddings.py:36-40`: `embed()` offloads `_encode_sync` to a `ThreadPoolExecutor(max_workers=1)`. The model is `all-MiniLM-L6-v2` — a small model (~22M params), typical encode time ~5-15ms on CPU for a short string. This now runs on every RespondIntent before the response is returned to the user (it was previously fire-and-forget).

**Impact**: The user sees ~10-30ms additional latency per response (embed + DB write + auto_link vector search). For a CLI agent, this is imperceptible. Not a bug. ✔

### 3e. Blocking the loop return
The `await self._memory.store(...)` at `loop.py:195` blocks the return by the embedding + DB write time (~10-30ms). This is intentional — the design comment at `loop.py:17-19` says "Awaited (not create_task) so embed+insert completes before asyncio.run() teardown." The tradeoff (durability vs. latency) is correct for M3. ✔

---

## Summary

| # | Item | Status | Evidence |
|---|------|--------|----------|
| Finding 3 | Cognitive tier persist path | **CLOSED** | `loop.py:195 → adapter.py:144 → adapter.py:150-151 → storage.py:139-166`. Full await chain to SurrealKV disk. |
| W1 | Stale "fire-and-forget" comment in `port.py:45` | **WARNING** | Comment says fire-and-forget; implementation awaits. Misleading for future implementers. |
| W2 | `update()` and `relate()` still use `create_task` | **WARNING** | `adapter.py:226,249`. Latent teardown-cancellation hazard. No current caller triggers it. |

No blocking bugs found. No regressions from the semantics change (sole production caller is the loop, which correctly awaits). No deadlocks, no double-stores, no functional breakage.

---

## VERDICT: **PASS**

Finding 3 is definitively closed. The persist path is fully awaited end-to-end from loop to disk. Two warnings (stale port comment, inconsistent fire-and-forget on update/relate) are real but non-blocking for M3 — recommend fixing W1 now (one-line comment edit) and W2 when those methods gain loop callers (M8).
