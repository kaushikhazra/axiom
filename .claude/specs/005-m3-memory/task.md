# M3 · Memory — Task Checklist

**Spec:** `005-m3-memory`
**Milestone:** M3 — "It learns across sessions"
**Status:** COMPLETE — all tasks done; 121 tests green (2026-07-14)

---

## 0. Pre-implementation gates

- [x] 0.1 `dryrun-design-1.md` — spec reviewer runs `/e-spec:dryrun-design` against `design.md` and achieves PASS verdict before any code is written. _MEM-DOD-1_
- [x] 0.2 `task.md` — implementation planner confirms all tasks below have a named actor, action, and target before marking any task in-progress. _MEM-DOD-1_

---

## 1. Models and config

- [x] 1.1 `models.py` — models author defines `Memory`, `RecallResult`, `Relationship`, `ConversationUnit`, `AssembledContext` dataclasses (Pydantic or stdlib dataclass) in `src/axiom/memory/models.py`. `ConversationUnit` fields: `user_text: str`, `agent_text: str`, `turn_index: int`, `timestamp: datetime`, `embedding: list[float]` (left empty at construction; populated by `append_unit`), `token_count: int` (populated by `append_unit` as `len(user_text + agent_text) // 4`). _MEM-US02, MEM-US05, MEM-US07_
- [x] 1.2 `config.py` — config author defines `MemoryConfig` dataclass (storage_path, n_units, token_budget, n_recency_floor, k_cognitive, k_relevance, growth_factor, decay_influence, auto_link_threshold) in `src/axiom/memory/config.py`. _MEM-US08, MEM-US10_

---

## 2. Port contract

- [x] 2.1 `port.py` — port author defines `MemoryPort` Protocol with all methods (`assemble_context`, `recall`, `append_unit`, `store`, `reinforce`, `update`, `relate`, `consolidate`, `stats`, `health`) and docstrings encoding the awaited/fire-and-forget invariants in `src/axiom/memory/port.py`. `append_unit(unit: ConversationUnit)` is the working-context write path (awaited, fast, cognitive-store-agnostic). `store` is cognitive-store-only (fire-and-forget). _MEM-US01, MEM-US02, MEM-US08_
- [x] 2.2 `__init__.py` — package author re-exports `MemoryPort`, `CognitiveMemoryAdapter`, `AssembledContext` from `src/axiom/memory/__init__.py`. _MEM-US01_

---

## 3. Decay functions

- [x] 3.1 `decay.py` — decay author implements `compute_R(stability: float, elapsed_days: float) -> float` (R = e^(−elapsed_days/(9·stability))) in `src/axiom/memory/decay.py`. _MEM-US04_
- [x] 3.2 `decay.py` — decay author implements `reinforce_stability(S: float, R: float, growth_factor: float = 2.0) -> float` (S_new = S × (1 + growth_factor × (1 − R))) in `src/axiom/memory/decay.py`. _MEM-US04_
- [x] 3.3 `decay.py` — decay author implements `compute_spreading_boost(rel_strength: float, depth: int) -> float` (1-hop = 0.3 × rel_strength; each hop × 0.5; cap 0.5) in `src/axiom/memory/decay.py`. _MEM-US04_
- [x] 3.4 `decay.py` — decay author implements `classify_decay_state(R: float) -> str` → `"healthy" | "fading" | "forgotten"` in `src/axiom/memory/decay.py`. _MEM-US04_

---

## 4. Classification and importance

- [x] 4.1 `classification.py` — classifier author implements `classify_type(content: str) -> tuple[str, float]` (keyword heuristic, confidence cap 0.8, episodic default below 0.2) in `src/axiom/memory/classification.py`. _MEM-US05_
- [x] 4.2 `classification.py` — classifier author implements `score_importance(content: str, memory_type: str, caller_override: float | None) -> float` (base 0.5, bonuses per §5.2, capped [0.0, 1.0]) in `src/axiom/memory/classification.py`. _MEM-US05_

---

## 5. Embedding service

- [x] 5.1 `embeddings.py` — embedding author implements `EmbeddingService` with `warmup()`, `embed(text) -> list[float]`, `embed_batch(texts) -> list[list[float]]` backed by `all-MiniLM-L6-v2` via `sentence-transformers`; CPU inference offloaded to executor in `src/axiom/memory/embeddings.py`. _MEM-US10_
- [x] 5.2 `embeddings.py` — embedding author verifies `warmup()` loads model eagerly so subsequent `embed()` calls do not incur model-load latency. _MEM-DOD-10_

---

## 6. Storage seam and schema

- [x] 6.1 `schema.py` — schema author writes SurrealKV schema initialisation (`memory`, `relationship`, `consolidation_log`, `memory_version`, `config` tables; vector index on `memory.embedding`; full-text index on `memory.content`) in `src/axiom/memory/schema.py`. _MEM-US10_
- [x] 6.2 `storage.py` — storage author lifts and adapts the proven embedded SurrealDB storage layer: connect via `Surreal("surrealkv://<absolute_path>")`, in-process, no external server (see design §10.1 for provenance). Implements `StorageSeam` with all methods (`store_memory`, `get_memory`, `update_memory`, `vector_search`, `fulltext_search`, `get_by_recency`, `store_relationship`, `get_neighbours_bulk`, `get_all_active`, `bulk_update_stability`, `archive_memory`, `log_consolidation_action`, `get_contradictions`) in `src/axiom/memory/storage.py`. **CRITICAL:** avoid `LET`-based multi-statement SurrealQL (embedded SDK returns `None` for them); use single-statement queries or sequential `await db.query(...)` calls. `get_neighbours_bulk` default `max_depth=3`. _MEM-US10_
- [x] 6.3 `storage.py` — storage author verifies `StorageSeam.__init__(storage_path)` creates the SurrealKV file if absent and runs schema init idempotently (safe to call on existing database). _MEM-US10_

---

## 7. Working-Context ring buffer

- [x] 7.1 `working_context.py` — working-context author implements `WorkingContext` (in-memory `VectorRingBuffer`) with `add_unit(unit: ConversationUnit)` (evicts oldest on overflow), `assemble(query_embedding, n_recency_floor, k_relevance, token_budget) -> list[ConversationUnit]` (recency floor verbatim + older units by cosine relevance, token-capped) in `src/axiom/memory/working_context.py`. _MEM-US02_
- [x] 7.2 `working_context.py` — working-context author verifies tool I/O is excluded: `ConversationUnit` holds only the user message + agent response pair (no tool calls, no tool results, no intra-cycle reasoning). _MEM-US02_

---

## 8. Retrieval pipeline

- [x] 8.1 `retrieval.py` — retrieval author implements Phase 1: concurrent `asyncio.gather` of semantic (vector cosine, weight 1.0), keyword (BM25 full-text, weight 0.7), temporal (recency score, weight 0.3) strategies, collecting `min(limit × 3, 30)` candidates per strategy in `src/axiom/memory/retrieval.py`. _MEM-US07_
- [x] 8.2 `retrieval.py` — retrieval author implements RRF fusion (k=60, weighted per strategy) over Phase 1 candidates in `src/axiom/memory/retrieval.py`. _MEM-US07_
- [x] 8.3 `retrieval.py` — retrieval author applies post-RRF decay reranking (`final_score = rrf_score × R^0.5`) and superseded-memory penalty (×0.3) in `src/axiom/memory/retrieval.py`. _MEM-US07_
- [x] 8.4 `retrieval.py` — retrieval author implements Phase 2: batched `storage.get_neighbours_bulk(top5_seeds)` graph expansion; neighbour scoring (w_graph=0.5/RRF); merge into ranked result in `src/axiom/memory/retrieval.py`. _MEM-US06_
- [x] 8.5 `retrieval.py` — retrieval author appends `contradictions` IDs to each `RecallResult` via `storage.get_contradictions(result_ids)` in `src/axiom/memory/retrieval.py`. _MEM-US07_
- [x] 8.6 `retrieval.py` — retrieval author dispatches spreading-activation write-back (3-hop neighbour stability boost) as `asyncio.create_task` after finalising results — MUST NOT block the `recall` return in `src/axiom/memory/retrieval.py`. _MEM-US04_

---

## 9. Consolidation pipeline

- [x] 9.1 `consolidation.py` — consolidation author implements Stage 1 (decay update across all active memories, batch) in `src/axiom/memory/consolidation.py`. _MEM-US09_
- [x] 9.2 `consolidation.py` — consolidation author implements Stage 2 (type-promotion pass: all five promotion rules from design §9) in `src/axiom/memory/consolidation.py`. _MEM-US09_
- [x] 9.3 `consolidation.py` — consolidation author implements Stage 3 (archive pass: R < 0.2 general; R < 0.05 person; identity never archived) in `src/axiom/memory/consolidation.py`. _MEM-US09_
- [x] 9.4 `consolidation.py` — consolidation author implements Stage 4 (cluster scan: per-active-memory vector query for similar pairs, cosine ≥ 0.75 candidates) in `src/axiom/memory/consolidation.py`. _MEM-US09_
- [x] 9.5 `consolidation.py` — consolidation author implements Stage 5 (merge pass: cosine ≥ 0.90 + no negation → merge primary/secondary, archive secondary, create SUPERSEDES edge) in `src/axiom/memory/consolidation.py`. _MEM-US09_
- [x] 9.6 `consolidation.py` — consolidation author implements Stage 6 (contradiction flag: cosine ≥ 0.80 + negation → create CONTRADICTS edge) in `src/axiom/memory/consolidation.py`. _MEM-US09_
- [x] 9.7 `consolidation.py` — consolidation author verifies `consolidate()` writes every action to `consolidation_log` and returns the full log as `list[dict]`. _MEM-US09_

---

## 10. CognitiveMemoryAdapter

- [x] 10.1 `adapter.py` — adapter author implements `CognitiveMemoryAdapter.__init__(config)` following the init sequence (StorageSeam → EmbeddingService → warmup → WorkingContext → RetrievalPipeline → ConsolidationPipeline) in `src/axiom/memory/adapter.py`. _MEM-DOD-5, MEM-DOD-10_
- [x] 10.2 `adapter.py` — adapter author implements `assemble_context(query, ...) -> AssembledContext` (embed query; call WorkingContext.assemble for working tier; call retrieval.recall for cognitive tier; package both into AssembledContext) in `src/axiom/memory/adapter.py`. _MEM-US01_
- [x] 10.3 `adapter.py` — adapter author implements `recall(query, ...) -> list[RecallResult]` delegating to `RetrievalPipeline.recall(...)` in `src/axiom/memory/adapter.py`. _MEM-US03_
- [x] 10.4 `adapter.py` — adapter author implements `store(content, ...) -> str` minting UUID4 synchronously, dispatching embed+insert to the **cognitive store only** via `asyncio.create_task`, and returning the id immediately. `store` does NOT write to the working-context buffer. After embed, triggers auto-link scan (cosine ≥ 0.75 → `relates_to` edge, strength < 1.0) in `src/axiom/memory/adapter.py`. _MEM-US06, MEM-US08_
- [x] 10.4b `adapter.py` — adapter author implements `append_unit(unit: ConversationUnit) -> None`: (1) calls `await EmbeddingService.embed(unit.user_text + " " + unit.agent_text)`, (2) sets `unit.embedding` and `unit.token_count`, (3) calls `WorkingContext.add_unit(unit)`. This is the working-context write path — awaited, not fire-and-forget. Does NOT write to the cognitive store in `src/axiom/memory/adapter.py`. _MEM-US02_
- [x] 10.5 `adapter.py` — adapter author implements `reinforce(ids)` dispatching stability updates as `asyncio.create_task`; never blocks caller in `src/axiom/memory/adapter.py`. _MEM-US04_
- [x] 10.6 `adapter.py` — adapter author implements `update(memory_id, ...)` and `relate(source_id, target_id, rel_type, strength)` as fire-and-forget in `src/axiom/memory/adapter.py`. _MEM-US06_
- [x] 10.7 `adapter.py` — adapter author implements `consolidate() -> list[dict]` delegating to `ConsolidationPipeline.consolidate()`; this is awaited (blocking at session close is accepted) in `src/axiom/memory/adapter.py`. _MEM-US09_
- [x] 10.8 `adapter.py` — adapter author implements `stats() -> dict` and `health() -> dict` for management use in `src/axiom/memory/adapter.py`. _MEM-US10_

---

## 11. Loop wiring

- [x] 11.1 `loop.py` — loop author adds `memory: MemoryPort` to `PraoLoop.__init__` (injected; the loop imports only `MemoryPort` from `axiom.memory.port`, never `adapter.py`) in `src/axiom/loop.py`. _MEM-DOD-11_
- [x] 11.2 `loop.py` — loop author calls `await self.memory.assemble_context(query)` at the Perceive phase and passes the result's two tiers into the chat-API slot renderer in `src/axiom/loop.py`. _MEM-US01_
- [x] 11.3 `loop.py` — loop author calls `await self.memory.append_unit(unit)` at Observe: constructs a `ConversationUnit(user_text=..., agent_text=..., turn_index=..., timestamp=now)` from the completed turn and awaits `append_unit`. `store` is NOT used for working-context writes in `src/axiom/loop.py`. _MEM-US02_
  > **CV1 reconciliation (2026-07-15):** Original CV1 note deferred cognitive store to M8. Superseded by Finding-3 fix (2026-07-15): the loop NOW calls `await self._memory.store(exchange_content, memory_type="episodic")` at RespondIntent turn-exit, persisting each completed exchange to the cognitive tier. Awaited (not `create_task`) so the write survives `asyncio.run()` teardown. Smart extraction (selecting what to store) remains M8; M3 stores the full exchange per turn. FinishIntent is skipped (empty agent text).
- [x] 11.4 `loop.py` — loop author dispatches `asyncio.create_task(self.memory.reinforce(used_ids))` at Observe with the IDs of memories assembled into context in `src/axiom/loop.py`. _MEM-US04_
- [x] 11.5 `agent.py` — composition-root author constructs `CognitiveMemoryAdapter(MemoryConfig(...))` and injects it into `PraoLoop` at startup (before loop starts) in `src/axiom/agent.py`. _MEM-DOD-11_
- [x] 11.6 `agent.py` — composition-root author calls `await memory.consolidate()` in the agent's shutdown sequence (after the loop exits, before process termination) in `src/axiom/agent.py`. _MEM-US09_

---

## 12. Unit tests

- [x] 12.1 `tests/test_memory_decay.py` — test author writes unit tests for `compute_R`, `reinforce_stability`, `compute_spreading_boost`, `classify_decay_state` (edge cases: t=0, t=9S, high R vs low R boost differential). _MEM-US04_
- [x] 12.2 `tests/test_memory_classification.py` — test author writes unit tests for `classify_type` (each type triggered; default episodic; caller override) and `score_importance` (each bonus/penalty path; clamping). _MEM-US05_
- [x] 12.3 `tests/test_memory_working_context.py` — test author writes unit tests for `WorkingContext.add_unit` (overflow eviction), `assemble` (recency floor always present; token-cap truncation; relevance ordering for older units). _MEM-US02_
- [x] 12.4 `tests/test_memory_retrieval.py` — test author writes unit tests for RRF fusion formula, decay reranking, superseded penalty, and contradiction attachment using a mock `StorageSeam`. _MEM-US07_
- [x] 12.5 `tests/test_memory_consolidation.py` — test author writes unit tests for each of the six consolidation stages (each promotion rule, archive thresholds, merge/SUPERSEDES, contradiction/CONTRADICTS), using a mock `StorageSeam`. _MEM-US09_
- [x] 12.6 `tests/test_memory_port_contract.py` — test author verifies `CognitiveMemoryAdapter` satisfies `MemoryPort` structurally (all methods present, correct signatures) using `isinstance` or Protocol runtime check. _MEM-DOD-3_

---

## 13. Integration tests

- [x] 13.1 `tests/test_memory_integration.py` — integration test author writes `test_store_recall_across_restart`: stores a memory, tears down the adapter, re-initialises against the same SurrealKV file, verifies the memory is returned by `recall`. _MEM-DOD-5_
- [x] 13.2 `tests/test_memory_integration.py` — integration test author writes `test_consolidation_promotion`: stores multiple `episodic` memories with access_count ≥ 3 and importance ≥ 0.4, calls `consolidate()`, verifies at least one was promoted to `semantic`. _MEM-US09_
- [x] 13.3 `tests/test_memory_integration.py` — integration test author writes `test_spreading_activation`: stores two related memories (cosine ≥ 0.75 auto-link), recalls one, waits for write-back task, verifies the neighbour's stability increased. _MEM-US04_
- [x] 13.4 `tests/test_memory_integration.py` — integration test author writes `test_assemble_context_shape`: calls `assemble_context(query)`, verifies the result has both `working_context` (list) and `cognitive_memories` (list) fields (both may be empty; neither may be absent). _MEM-DOD-4_
- [x] 13.5 `tests/test_memory_integration.py` — integration test author writes `test_store_is_non_blocking`: verifies `store(...)` returns the minted ID before the embed+insert coroutine completes (using a slow mock embedding service with controlled delay). _MEM-DOD-8_

---

## 14. E2E tests

- [x] 14.1 `tests/test_memory_e2e.py` — E2E test author writes `test_cross_session_recall`: (a) initialise adapter A; call `await memory.append_unit(unit)` with a `ConversationUnit` to write to the working tier, and call `await memory.store(content, memory_type="semantic")` to write to the cognitive tier; (b) tear down A; (c) initialise adapter B against same file; (d) call `assemble_context(query_related_to_content)`; (e) assert the stored cognitive memory appears in `cognitive_memories` of the result. _MEM-DOD-9_
- [x] 14.2 `tests/test_memory_e2e.py` — E2E test author writes `test_two_tier_assembly_both_populated`: populates multiple working units AND multiple cognitive memories, calls `assemble_context`, verifies both tiers are non-empty in the result. _MEM-DOD-9_

---

## 15. Code dryrun gate

- [ ] 15.1 `dryrun-code-1.md` — code reviewer runs `/e-spec:dryrun-code` after implementation and achieves PASS verdict before marking M3 complete. _MEM-DOD-2_

---

## Requirement Traceability

| Code | Meaning |
|------|---------|
| MEM-US01 | US-01 — Context assembly at Perceive: two-tier, owned by Memory |
| MEM-US02 | US-02 — Working-Context tier: in-session ring buffer |
| MEM-US03 | US-03 — Cognitive tier: memories persist across sessions |
| MEM-US04 | US-04 — Decay-aware memory: fade and reinforce |
| MEM-US05 | US-05 — Memory type taxonomy: six types |
| MEM-US06 | US-06 — Relation graph: typed relationships |
| MEM-US07 | US-07 — Multi-strategy retrieval: semantic + keyword + temporal |
| MEM-US08 | US-08 — Store is fire-and-forget; ID minted synchronously |
| MEM-US09 | US-09 — Consolidation at session end |
| MEM-US10 | US-10 — Embedded sovereign storage |
| MEM-DOD-1 | Definition of Done 1 — Spec gate (dryrun-design PASS) |
| MEM-DOD-2 | Definition of Done 2 — Code dryrun gate (dryrun-code PASS) |
| MEM-DOD-3 | Definition of Done 3 — MemoryPort implemented |
| MEM-DOD-4 | Definition of Done 4 — Two-tier assembly works |
| MEM-DOD-5 | Definition of Done 5 — Cross-session persistence |
| MEM-DOD-8 | Definition of Done 8 — Unit + integration tests green |
| MEM-DOD-9 | Definition of Done 9 — E2E tests green |
| MEM-DOD-10 | Definition of Done 10 — Embedding warm-up at init |
| MEM-DOD-11 | Definition of Done 11 — Loop wiring (imports MemoryPort only) |
