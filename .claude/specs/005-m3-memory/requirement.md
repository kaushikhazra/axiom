# M3 · Memory — Requirements

**Spec:** `005-m3-memory`
**Milestone:** M3 — "It learns across sessions"
**Author:** Velasari — 2026-07-14
**Status:** DRAFT — authored from research `006-m3-memory-architecture-2026-07-14.md` (K+V design pass)

---

## Purpose

M3 gives Axiom a persistent, decay-aware Memory faculty behind the Memory port so the agent learns across sessions. Without M3, every conversation starts cold — no retained preferences, no prior context, no accumulated knowledge about the user or project history. Memory is the difference between a sophisticated one-shot chatbot and an agent that genuinely knows you.

**What M3 builds:** A sovereign in-process **Memory faculty** implementing the `MemoryPort` protocol. It stores, recalls, and ages memories across the agent lifecycle. It reinforces what gets used and lets the rest fade. It surfaces relevant context into the Perceive phase and captures new knowledge from the Observe phase. Two tiers: an ephemeral **Working-Context** (in-session vector ring buffer) and a persistent **Cognitive** store (decay-aware, typed, graph-connected).

**Memory is constitutive — not optional.** The Memory faculty is always active. There is no `memory=True/False` toggle, no opt-in flag, and no code path where `PraoLoop` runs without a wired `MemoryPort`. Every session assembles context at Perceive and writes a conversation unit at Observe. This is a hard architectural invariant, not a feature flag.

**Behavioral acceptance criterion (cross-session recall):** After a fact is stated in one CLI session (e.g. the user mentions a preference and the agent acknowledges it), asking about that fact in a later CLI session must produce a response that reflects the stored fact — without the user restating it. This is the observable proof that memory is persistent and constitutive.

**How the AC is met (Finding-3 wiring):** At every RespondIntent turn-exit, the loop persists the completed exchange (`"User: {input}\nAgent: {response}"`) to the cognitive tier as an awaited episodic memory. The store is awaited end-to-end (not fire-and-forget) so it completes before `asyncio.run()` teardown — making cross-session learning real from the first session. LLM-assisted selection of what to extract is M8; M3 stores the full exchange per turn.

**What M3 does not build:** persona genesis; seed or migration from any prior memory store; LLM-assisted memory extraction (M8); connectors (M9); multi-agent memory sharing (M7); web dashboard or admin UI. The consumer of the Memory port is the agent loop and nothing else within M3 scope.

---

## User Stories

---

### US-01 — Context assembly at Perceive: two-tier, owned by Memory

**As** the agent loop at the Perceive phase,
**I want** to call `memory.assemble_context(query, ...)` and receive a structured two-tier context object back,
**so that** I can render it into the model's chat slots without the loop knowing anything about how Memory organises its tiers.

#### Acceptance criteria

- AC-01.1: `assemble_context(query, conversation_id?, tags?, limit?)` is a method on `MemoryPort`; it is awaited at Perceive (<100 ms target for the combined call).
- AC-01.2: The returned object carries two distinct payload fields: one for the working-tier content (recent conversation units) and one for the cognitive-tier content (recalled memories from the persistent store).
- AC-01.3: Memory owns the composition of both tiers — the loop does NOT assemble them independently; it calls `assemble_context` once and gets a unified result.
- AC-01.4: The loop renders working-tier content as "Previous Conversations" in the history/human-turn slot and cognitive-tier content as "Additional Context" in the system-prompt slot. The exact heading text and rendering are a thin step in the loop; Memory returns structured content, not prompt syntax.
- AC-01.5: If either tier is empty (no units in buffer, no relevant cognitive memories), the result carries an empty list for that field — not an error.

---

### US-02 — Working-Context tier: in-session ring buffer with recency floor and relevance

**As** the agent loop,
**I want** the Memory faculty to maintain an in-memory vector ring buffer of recent conversation units during a session,
**so that** the assembled context always includes the last N units verbatim (recency floor for coherence) and can pull older units by semantic relevance (relevance for small-model efficiency).

#### Acceptance criteria

- AC-02.1: The working tier holds **conversation units** — each unit is one user message paired with the agent's response. Tool calls, tool results, and other intra-cycle loop machinery are **excluded** from the buffer; only the user↔agent exchange that Observe emits at cycle-conclude enters.
- AC-02.2: The buffer is **bounded**: a hard count ceiling of N ≈ 50 units AND a hard token budget cap. The token budget is the binding constraint for small models; the count ceiling prevents unbounded growth when units are short.
- AC-02.3: Context assembly always includes the **last N units verbatim** (recency floor) regardless of their relevance score. These form the "Previous Conversations" slice of the assembled context.
- AC-02.4: Units older than the recency floor are retrieved by **vector similarity** to the current query, using the buffer's embedded representations. Top-K semantically relevant older units are included after the recency floor.
- AC-02.5: The buffer is **ephemeral by default**: it resides in process memory only while the session is running. Cross-session persistence of the working buffer is deferred.
- AC-02.6: Observe writes a new conversation unit to the working-context buffer via `memory.append_unit(unit)`, passing a `ConversationUnit` (user_text + agent_text pair). `store(...)` writes ONLY to the cognitive store. These are two distinct write paths — `append_unit` for the working tier, `store` for the cognitive tier. There is no `memory_type` routing in `store`; the two tiers use separate methods.

---

### US-03 — Cognitive tier: memories persist and are recalled across sessions

**As** a user returning to a new session,
**I want** the agent to recall relevant memories from previous sessions automatically at Perceive,
**so that** the agent knows my preferences, past decisions, and prior context without me re-stating them.

#### Acceptance criteria

- AC-03.1: Memories written via `memory.store(...)` are persisted to durable storage. On a clean process restart, those memories are still retrievable.
- AC-03.2: `memory.recall(query, context?, type_filter?, tags?, limit?)` returns ranked `RecallResult` objects from the persistent cognitive store. This method is awaited at Perceive (<100 ms target).
- AC-03.3: `assemble_context` calls `recall` internally and includes the top-K cognitive results in the structured response. The loop never calls `recall` directly for context assembly — it calls `assemble_context`. (The `recall` method is still exposed for callers with targeted retrieval needs.)
- AC-03.4: Memories survive an agent restart: a memory stored in session A is retrievable via `recall` in session B without any manual re-import step.
- AC-03.5: The cognitive tier supports type-filtering (by `memory_type`) and tag-filtering in `recall`. Filtering is performed within the retrieval pipeline, not by post-filtering the full result set.

---

### US-04 — Decay-aware memory: memories fade; used memories are reinforced

**As** the agent (and its operator),
**I want** memories to decay over time when not accessed and to be strengthened when recalled and used,
**so that** stale or irrelevant memories fade out naturally and the memories that prove useful remain prominent.

#### Acceptance criteria

- AC-04.1: Every stored memory carries a **stability** value (S, in days) and a computed **retrievability** R(t) = e^(−t / (9·S)), where t = elapsed days since last access. R is computed on-the-fly at recall time; it is not stored as a static field (it changes with every passing second).
- AC-04.2: `memory.reinforce(ids)` is a fire-and-forget port method. When called with a list of memory IDs, it boosts each memory's stability: S_new = S_old × (1 + 2.0 × (1 − R)). A nearly-forgotten memory (low R) receives a larger boost than a recently-accessed one (high R).
- AC-04.3: At `consolidate()` time, memories with R < 0.2 are archived (moved to inactive state, no longer surfaced in recall). Person-type memories use a stricter threshold of R < 0.05. Identity-type memories are never auto-archived.
- AC-04.4: Reinforcement of graph neighbours (spreading activation) fires as a fire-and-forget write-back on recall: 1-hop neighbours of recalled memories receive a 0.3 × rel_strength stability boost; 2-hop neighbours receive a 0.15 × rel_strength boost. This is capped at a maximum boost of 0.5.
- AC-04.5: The decay model uses a single growth factor of 2.0 (no separate difficulty parameter, no rating signal). The simplicity is intentional: this model is production-proven and requires no agent-provided rating.

---

### US-05 — Memory type taxonomy: six types with different lifespans

**As** the Memory faculty,
**I want** every stored memory to carry a type that governs its initial stability and archival threshold,
**so that** conversation ephemera fade quickly, durable facts persist for months, and foundational identity knowledge never auto-archives.

#### Acceptance criteria

- AC-05.1: The six supported memory types are: `working`, `episodic`, `semantic`, `procedural`, `identity`, `person`. Each has a distinct initial stability S₀ (in days): working=0.04, episodic=2.0, semantic=14.0, procedural=60.0, identity=365.0, person=90.0.
- AC-05.2: When the caller omits `memory_type` on a `store` call, the Memory faculty auto-classifies the content using a heuristic pattern-matcher. Auto-classification confidence is capped at 0.8; content scoring below 0.2 confidence defaults to `episodic`. The caller may always override.
- AC-05.3: Importance scoring defaults: base 0.5; +0.2 for identity type; +0.15 for person type; +0.1 each for named entities, relational keywords, or content length >200 chars; −0.1 for working type. Caller override accepted.
- AC-05.4: `recall` results carry the memory's type, importance, current retrievability, and a `found_by` list indicating which retrieval strategies contributed.

---

### US-06 — Relation graph: typed relationships between memories

**As** the agent (or operator),
**I want** to create typed relationships between memories and have retrieval traverse those relationships to surface associated context,
**so that** recalling one memory can activate related memories the query didn't match directly.

#### Acceptance criteria

- AC-06.1: `memory.relate(source_id, target_id, rel_type, strength=1.0)` is a fire-and-forget port method that creates a directed, typed edge between two memories.
- AC-06.2: Eight relationship types are supported: `causes`, `follows`, `contradicts`, `supports`, `relates_to`, `supersedes`, `part_of`, `describes`.
- AC-06.3: At store time, the Memory faculty auto-links new memories to existing memories with cosine similarity ≥ 0.75 as `relates_to` edges (strength < 1.0; invariant: auto-links are never strength = 1.0, which is reserved for manually created links).
- AC-06.4: The recall pipeline's Phase 2 graph traversal: the top-5 Phase-1 seeds have their graph neighbours fetched in one batched call; those neighbours are scored and merged into the final ranked list (graph weight = 0.5 in the RRF formula).
- AC-06.5: Duplicate edges of the same type between the same source and target are prevented at storage level (unique constraint on source_id + target_id + rel_type).

---

### US-07 — Multi-strategy retrieval: semantic + keyword + temporal, fused with RRF

**As** the agent loop at Perceive,
**I want** `recall` to find relevant memories via semantic similarity, keyword match, and recency together,
**so that** a query finds both paraphrased-but-relevant memories (semantic) and exact-keyword matches (keyword) while still privileging recent content (temporal).

#### Acceptance criteria

- AC-07.1: Phase 1 of retrieval runs three concurrent strategies: (a) **Semantic** — cosine similarity via vector search (weight 1.0); (b) **Keyword** — BM25 full-text search (weight 0.7); (c) **Temporal** — recency score e^(−elapsed_days/30) (weight 0.3). Up to `min(limit × 3, 30)` candidates are collected per strategy.
- AC-07.2: Phase 1 candidates are fused using **Reciprocal Rank Fusion** (RRF, k=60): `score(id) += w / (k + rank + 1)` for each strategy that found the id.
- AC-07.3: Post-RRF, scores are multiplied by R^0.5 (decay reranking, `decay_influence=0.5`). This allows a fading memory to still surface if semantically highly relevant, while gently penalising low-retrievability results.
- AC-07.4: Memories marked as superseded carry a score penalty of ×0.3 in the final ranking.
- AC-07.5: `recall` results carry a `contradictions` field — the IDs of other memories that have high semantic similarity but negation signals (flagged during consolidation). The caller decides how to handle contradictions; Memory surfaces the signal.

---

### US-08 — Store is fire-and-forget; ID minted synchronously

**As** the agent loop at the Observe phase,
**I want** `memory.store(...)` to return a memory ID immediately without waiting for the embed+insert to complete,
**so that** the Observe phase is never blocked by the cost of embedding generation or a storage write.

#### Acceptance criteria

- AC-08.1: `memory.store(...)` mints a UUID4 ID synchronously (in-process, before any async work begins) and returns it immediately. The embed+insert pipeline runs fire-and-forget behind the returned ID.
- AC-08.2: The accepted trade-off is documented: a `store` followed immediately by a `recall` of the same content may miss the new memory until the async insert lands. This is acceptable because `store` fires at Observe and `recall` fires at the next cycle's Perceive — a full cycle apart.
- AC-08.3: `memory.reinforce(ids)` is fire-and-forget at the port contract level. It never blocks the caller.
- AC-08.4: `memory.relate(...)` and `memory.update(...)` are also fire-and-forget (non-blocking callers).
- AC-08.5: `memory.recall(...)` and `memory.assemble_context(...)` are **awaited** — the loop cannot proceed to Reason without the assembled context. The <100 ms target covers the total latency of these awaited methods.

---

### US-09 — Consolidation at session end: promotion, archival, merge, contradiction

**As** the agent system at session shutdown,
**I want** the Memory faculty to run a consolidation pass when the loop exits,
**so that** frequently-accessed episodic memories are promoted to more durable types, faded memories are archived, near-duplicate memories are merged, and contradictions are flagged.

#### Acceptance criteria

- AC-09.1: `memory.consolidate()` is **awaited at session close only** (triggered by the loop's shutdown sequence). It is never triggered mid-session, on a timer, or per-store.
- AC-09.2: Consolidation runs six stages in order: (1) decay update across all active memories; (2) type-promotion pass; (3) archive pass (R < threshold); (4) cluster scan (find similar pairs); (5) merge pass (cosine ≥ 0.90 + no negation → merge, archive secondary, create SUPERSEDES edge); (6) contradiction flag (cosine ≥ 0.80 + negation → create CONTRADICTS edge).
- AC-09.3: Promotion rules: `working` → `episodic` when access_count ≥ 3 AND importance ≥ 0.4, OR relationships ≥ 2; `episodic` → `person` when has `person:` tag AND access_count ≥ 3; `episodic` → `procedural` when matches procedural patterns AND access_count ≥ 3; `episodic` → `semantic` when access_count ≥ 5 AND R > 0.6; `semantic` → `person` when has `person:` tag AND access_count ≥ 3. On promotion, stability resets to the new type's S₀.
- AC-09.4: `consolidate()` returns a list of dicts describing actions taken (promote, archive, merge, contradict — each with source/target IDs and reason). The log is used for debugging and audit; the loop does not act on it.
- AC-09.5: Shutdown linger from consolidation is accepted — the loop is already exiting and a modest linger is preferable to skipping the pass. An escape hatch (debounce: skip if last consolidation was < N sessions ago) is noted as a future option but is not required in M3.

---

### US-10 — Embedded sovereign storage: no external process

**As** an operator running the Axiom agent,
**I want** the Memory faculty to store all data in-process with no external database process,
**so that** `python -m axiom` boots and works with zero external services running.

#### Acceptance criteria

- AC-10.1: All persistent memory data (memories, relationships, consolidation log) is stored in a single embedded SurrealKV file (in-process, single-file mode). No external SurrealDB server process is started or connected to.
- AC-10.2: The storage is accessed behind a thin Axiom-side storage seam (`storage.py`) so the backend is swappable without changing any other component.
- AC-10.3: Vector search, graph traversal, and full-text search are all provided by the SurrealKV backend natively — no additional database extensions (no sqlite-vec, no external FTS engine) are required.
- AC-10.4: Embeddings are generated by `all-MiniLM-L6-v2` (384 dimensions) via `sentence-transformers`, behind an `EmbeddingService` abstraction. The model is warmed up at agent startup to avoid cold-start latency on the first recall.
- AC-10.5: The faculty boots deterministically: after `MemoryAdapter.__init__()` completes, all port methods are immediately callable. There are no lazy-init races.

---

## Non-Goals (M3 scope fence)

| Non-Goal | Notes |
|----------|-------|
| Persona genesis | Separate future milestone. Identity-type memories are stored and retrieved by M3, but how the agent's identity/persona is initially populated is out of scope. |
| Seed / migration from any prior store | M3 starts FRESH. No import of memories from any existing store. The product is a new instance — it learns its user from sessions. |
| LLM-assisted memory extraction | M8 (CAPTURE call-point). M3 stores what the loop explicitly tells it to store. |
| Reflection / higher-order insights | M8 territory. M3 does not run an LLM pass over its own memories. |
| Multi-agent memory sharing | M7 (Orchestrator). M3 is a single-agent faculty. |
| Web dashboard / admin UI | Raw port + management interface only. |
| External database process | M3 uses embedded SurrealKV only (in-process, no rocksdb-server, no HTTP server). |
| Background consolidation timer | Consolidation fires at session end only. |
| py-fsrs / FSRS rating-based decay | Dropped. The simple proven single-factor model is used. |
| Persistence of the working buffer across sessions | The working ring buffer is ephemeral. Buffer-to-cognitive promotion happens via consolidation. |

---

## Definition of Done (M3 complete when ALL of these pass)

1. **Spec gate:** `requirement.md`, `design.md`, `task.md` exist; `dryrun-design-1.md` verdict is PASS (no blocking gaps).
2. **Code dryrun gate:** `dryrun-code-1.md` verdict is PASS (no bugs or missing error handling at blocking severity).
3. **Memory constitutive:** `grep -rn "memory: bool\|if self._memory is not None\|_memory_adapter = None" src/axiom/` returns nothing. `PraoLoop.__init__` has no optional/default for `memory`. `Agent.__init__` constructs `CognitiveMemoryAdapter` unconditionally.
4. **Port contract:** `MemoryPort` Protocol is implemented in `src/axiom/memory/port.py`; `CognitiveMemoryAdapter` in `src/axiom/memory/adapter.py` implements it without importing from `port.py` consumers.
5. **Two-tier assembly:** `assemble_context(query)` returns a structured object with both `working_context` and `cognitive_memories` fields; each field is a non-null list (empty is valid).
6. **Cross-session persistence:** A memory stored in a test session is retrievable via `recall` after the adapter is torn down and re-initialised against the same SurrealKV file.
7. **Decay correctness:** R(t) = e^(−t/(9·S)) is computed correctly; a memory accessed at low R receives a larger stability boost than one accessed at high R (AC-04.2).
8. **Unit tests green:** All files in `tests/test_memory_*.py` pass with no skips.
9. **Integration tests green:** `tests/test_memory_integration.py` covers: store→recall across adapter restart; consolidation promotion; spreading activation write-back; assemble_context two-tier result shape.
10. **E2E test green:** `tests/test_memory_e2e.py` proves: (a) a conversation unit stored in session A is surfaced by `assemble_context` in session B; (b) `assemble_context` returns both working-tier and cognitive-tier content in a single call.
11. **Embedding warm-up:** `EmbeddingService.warmup()` is called at adapter init; the first `recall` does not incur model-load latency.
12. **Loop wiring:** `perceive()` calls `assemble_context`; `observe()` calls `store` (fire-and-forget) + `reinforce` (fire-and-forget); `loop.py` imports only `MemoryPort` (never the adapter).
