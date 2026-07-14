# M3 · Memory — Architecture Research

**Project:** Axiom (agent-core)
**Milestone:** M3 — Memory ("it learns across sessions")
**Author:** axiom-m3-memory-research (Velhari, sonnet) — 2026-07-14
**Status:** DESIGN RESEARCH — pre-spec.

---

## 1. Purpose

M3 gives the agent a persistent, decay-aware memory that survives across sessions. Without it every conversation starts cold — no learned preferences, no prior context, no accumulated knowledge about Kaushik or project history. Memory is the difference between a sophisticated chatbot and an agent that genuinely knows you.

**What M3 builds:** A sovereign **Memory faculty** behind the Memory port — a CM-kind cognitive memory system rebuilt in-process for Axiom. It stores, recalls, and ages memories across the agent lifecycle; it reinforces what gets used and lets the rest fade; it surfaces relevant context into the Perceive phase and captures new knowledge from the Observe phase.

**What M3 does not build:** connectors (email/Slack intake — M9), self-correction lesson capture (M8 owns that call-point), or a public API / web dashboard. The consumer is the agent loop and nothing else in M3 scope.

**Rebuild-vs-adapt (locked):** The existing `cognitive-memory` project runs as an external MCP HTTP server. The decision to **rebuild in-process** (not wrap the MCP) is locked in the roadmap. The engineering reason is stated in §4.

---

## 2. Cognitive-Memory Deep Dive

This section mines the existing `C:/Projects/cognitive-memory` codebase — the system Axiom's memory will be rebuilt from. All citations are real file paths and class/function names.

### 2.1 Memory type taxonomy and initial stability

**Source:** `src/cognitive_memory/models.py` (class `MemoryType`), `src/cognitive_memory/decay.py` (function `get_initial_stability`), `config.default.yaml`.

CM defines six memory types. Each carries a different **initial stability S₀** (in days), which governs how long it persists before fading:

| Type | S₀ (days) | Half-life intuition | Archive threshold | Notes |
|------|-----------|---------------------|-------------------|-------|
| `working` | 0.04 | ~58 minutes | R < 0.2 | Conversation ephemera; very fast decay |
| `episodic` | 2.0 | ~13 days | R < 0.2 | Specific events, dated interactions |
| `semantic` | 14.0 | ~3 months | R < 0.2 | Facts, definitions, durable knowledge |
| `procedural` | 60.0 | ~1.5 years | R < 0.2 | How-to knowledge; workflows |
| `identity` | 365.0 | never auto-archived | never archived | Self-knowledge; foundational; protected |
| `person` | 90.0 | ~6 years | R < 0.05 (stricter) | Knowledge about people; harder to lose |

The type taxonomy is well-designed. The `person` type is a practical addition for agent-human relationship context; the `identity` type provides a foundation for stable self-knowledge. The asymmetric archive threshold for `person` (0.05 vs 0.2) reflects that losing knowledge about people is more costly than forgetting a random fact.

**Classification** (`src/cognitive_memory/classification.py`, function `classify`): heuristic pattern-matching — keyword sets for each type, scored and capped at 0.8 confidence. Defaults to `episodic` when confidence < 0.2. Agent may override at store time. This is a reasonable fallback; in practice agents override often when they know the type.

**Importance scoring** (`classification.py`, function `score_importance`): base 0.5, bonuses for named entities (+0.1), relational keywords (+0.1), content length >200 chars (+0.1), identity type (+0.2), person type (+0.15); penalty for working type (-0.1). Agent override accepted. Simple and workable.

### 2.2 FSRS-inspired decay model

**Source:** `src/cognitive_memory/decay.py`.

CM uses an FSRS-*inspired* single-factor exponential decay — simpler than true FSRS but sharing its key intuition (stability grows on access, low-retrievability recalls give bigger boosts):

**Retrievability (computed on-the-fly):**
```
R(t) = e^(-t / (9 * S))
```
where `t` = elapsed days since last access, `S` = stability in days.

At `t = 9S`, retrievability falls to `e^(-1) ≈ 0.37`. The factor of 9 sets the "comfortable forgetting curve" — a memory is still above 50% retrievable until `t ≈ 6.2S`.

**Reinforcement on access** (`reinforce` function):
```
S_new = S_old * (1 + growth_factor * (1 - R))
```
With `growth_factor = 2.0` (default): a memory accessed when R=0.1 (nearly forgotten) gets `S_new = S_old * (1 + 2.0 * 0.9) = S_old * 2.8` — nearly triples its stability. A memory accessed when R=0.9 (fresh) gets `S_new = S_old * 1.2` — modest boost. This correctly implements the testing-effect intuition: retrieving a fading memory strengthens it more than revisiting a fresh one.

**Decay health classification** (`classify_decay_state`):
- `healthy`: R > 0.5
- `fading`: 0.2 < R ≤ 0.5
- `forgotten`: R ≤ 0.2 → candidate for archival

**Spreading activation** (`compute_spreading_boost`, `apply_spreading_boost`): when a memory is recalled, its graph neighbors get a stability boost proportional to relationship strength and hop distance:
```
1-hop boost = activation_strength * rel_strength       (default: 0.3 * rel_strength)
2-hop boost = 1-hop * spread_factor                    (default: * 0.5)
N-hop boost = (N-1 hop) * spread_factor^(depth-1)     (capped at max_boost = 0.5)
S_neighbor_new = S_neighbor * (1 + boost)
```
This models associative memory strengthening — recalling a fact reinforces related facts you didn't explicitly query.

**What this is NOT:** true FSRS (Anki's algorithm) includes a difficulty parameter `D`, a stability formula that accounts for lapsed vs successful reviews, and is fitted to human memory data. CM's model is a simplified single-factor exponential that borrows the core intuition. The py-fsrs library (`pip install py-fsrs`) implements true FSRS 5 and would be worth evaluating for the rebuild (see §5).

### 2.3 Retrieval — four-strategy fusion with RRF

**Source:** `src/cognitive_memory/retrieval.py`, function `recall`. Config weights from `config.default.yaml`.

CM's retrieval is a two-phase pipeline:

**Phase 1 — concurrent strategies (asyncio.gather):**
1. **Semantic** (weight 1.0): vector similarity search against embedded query. Cosine search over stored embedding vectors.
2. **Keyword** (weight 0.7): BM25 full-text search via FTS virtual table. BM25 scores normalized (negative scores flipped).
3. **Temporal** (weight 0.3): recency signal — `e^(-elapsed_days / 30)`, a 30-day half-life. Returns recently-accessed IDs sorted by recency.

Phase 1 candidates: `min(limit * 3, 30)` — up to 30 candidates for a default limit of 10.

**Phase 1 RRF Fusion** (Reciprocal Rank Fusion, k=60):
```
score(id) += w / (k + rank + 1)   for each strategy that found id
```
Weighted RRF: semantic adds `1.0 / (60 + rank)`, keyword `0.7 / (60 + rank)`, temporal `0.3 / (60 + rank)`.

**Phase 2 — graph traversal from top-5 seeds:**
- `storage.get_neighbors_bulk(seeds)` — one batched call (not per-seed)
- Graph-discovered neighbors scored with `w_graph / (60 + rank)` where `w_graph = 0.5`
- Phase 2 IDs not in Phase 1 get Python-side filter applied

**Post-RRF decay reranking:**
```
final_score = rrf_score * R^decay_influence   (decay_influence = 0.5)
```
Multiplying by `R^0.5` (square root of retrievability) gives a gentle penalty for fading memories — they can still surface if semantically very relevant.

**Supersede penalty:** `score *= 0.3` for memories that have been superseded (merged away).

**Spreading activation write-back:** top-K results trigger a bulk stability update for their graph neighbors (3-hop walk). This happens on every recall — the write-back is concurrent with the contradiction fetch but is still on the recall hot path.

**Contradiction tagging:** results carry `contradictions` field — other memories with high semantic similarity but negation signals (flagged during consolidation). Surfaced to the caller; the agent decides what to do.

**Result shape** (`RecallResult`): id, content, type, importance, retrievability (on-the-fly), score, found_by (which strategies contributed), tags, timestamps, contradictions.

**What works well:** the three-strategy Phase 1 is genuinely useful — semantic alone misses keyword-exact matches; keyword alone misses paraphrases; temporal alone has no semantic content. The fusion is well-calibrated.

**Pain point:** the spreading-activation write-back fires on every recall. In a tight agent loop (recall on every Perceive), this means every context assembly triggers multiple stability writes. In an external MCP server, this is acceptable. In-process behind a port, the write latency hits the Perceive phase directly — async isolation becomes critical (see §6).

### 2.4 Consolidation pipeline

**Source:** `src/cognitive_memory/consolidation.py`, function `consolidate`.

Six stages, triggered on-demand (no background scheduler in CM):

1. **Decay update** — recompute R for all active memories, write `retrievability` field. Batch operation across all active.
2. **Promotion pass** — type upgrades based on access count, importance, relationship count, retrievability:
   - `working` → `episodic`: access ≥ 3 AND importance ≥ 0.4, OR relationships ≥ 2
   - `episodic` → `person`: has `person:` tag AND access ≥ 3
   - `episodic` → `procedural`: matches procedural patterns AND access ≥ 3
   - `episodic` → `semantic`: access ≥ 5 AND R > 0.6
   - `semantic` → `person`: has `person:` tag AND access ≥ 3
   - When promoted, S is reset to the new type's S₀ (higher stability)
3. **Archive pass** — R < 0.2 for general memories, R < 0.05 for person; identity never archived
4. **Cluster scan** — vector_search_for_memory per memory to find similar pairs
5. **Merge pass** — cosine sim ≥ 0.90 AND no negation: merge into primary (higher importance * access_count); archive secondary with SUPERSEDES relationship
6. **Contradiction flag** — cosine sim ≥ 0.80 AND negation signals detected: create CONTRADICTS relationship

The consolidation log records every action with source/target IDs and reason — useful for debugging and auditing.

**Pain point:** Stage 4 (cluster scan) is O(N²) — per-memory vector search. Fine for hundreds of memories; will hurt at tens of thousands. The rebuild should consider approximate nearest-neighbor indexing for consolidation clustering or a smarter candidate selection strategy.

**Pain point:** consolidation is synchronous and on-demand. There is no background scheduler. In CM this is fine (the user/agent triggers `memory_consolidate`). In Axiom, we need to decide: trigger at session end, on a timer, or not at all during M3 (let the agent call it explicitly). This is a design fork (see §7).

### 2.5 Relation graph

**Source:** `src/cognitive_memory/models.py` (`RelType` enum), `migrations/001_initial.py` (schema).

Eight typed relationships: `causes`, `follows`, `contradicts`, `supports`, `relates_to`, `supersedes`, `part_of`, `describes`.

- `supersedes`: created by merge; the merged-away memory points to the primary with this type. Used to suppress superseded memories in recall (penalty factor 0.3).
- `contradicts`: created by consolidation when two similar memories have negation signals.
- `relates_to`: auto-created by `auto_linking` on store (cosine sim ≥ 0.75 to existing memories); strength < 1.0 (invariant — manual links are strength = 1.0).

The graph is stored in a `relationship` table with `UNIQUE(source_id, target_id, rel_type)` — prevents duplicate edges of the same type.

**What works well:** typed relationships are more expressive than a generic "similar" edge. The distinction between `supports` and `causes` is meaningful; `part_of` enables hierarchical structure; `supersedes` is load-bearing for merge tracking. This taxonomy is worth keeping.

### 2.6 Storage layer and schema evolution

**Source:** `src/cognitive_memory/storage.py`, `src/cognitive_memory/surreal_server_storage.py`, `migrations/001_initial.py`, `pyproject.toml`.

CM has undergone storage backend evolution:
- **Original:** SQLite + FTS5 + numpy in-memory embedding matrix. Clean, local-first, zero external dependencies.
- **Current:** SurrealDB — two modes: `surrealkv-file` (embedded SurrealKV, single file) and `rocksdb-server` (external SurrealDB process, WS connection). The migration was driven by vector search capability (SurrealDB has native vector index support) and graph traversal.

**SQLite schema** (from `001_initial.py`) — the original, clean shape:
- `memory`: (id TEXT PK, content, memory_type, state, importance, stability, retrievability, access_count, created_at, updated_at, last_accessed, source, conversation_id, tags TEXT JSON, embedding BLOB)
- `memory_version`: (id, memory_id FK, content, metadata TEXT JSON, created_at)
- `relationship`: (id, source_id FK, target_id FK, rel_type, strength REAL, created_at; UNIQUE on source+target+type)
- `consolidation_log`: (id, action, source_ids TEXT JSON, target_id, reason, created_at)
- `config`: (key TEXT PK, value TEXT, updated_at)
- FTS5 virtual table on `memory.content` (unicode61 tokenizer)
- WAL mode, foreign keys enabled, busy_timeout=30s

**Key lesson from the SurrealDB migration:** the move introduced an external process dependency (for `rocksdb-server`) and significant complexity in the storage layer (async SurrealDB client, WS reconnect, two code paths). The rebuild should not repeat this pattern. SQLite + a local in-process vector index is the right shape for Axiom's local-first, zero-external-dependency principle.

**Embeddings (embeddings.py):** `all-MiniLM-L6-v2` (sentence-transformers), 384 dimensions, float32, L2-normalized (cosine search via dot product). Lazy-loaded — cold start ~10 seconds on first `embed()` call. `warmup()` call at startup moves this out of the first user interaction.

### 2.7 MCP tool surface

**Source:** `src/cognitive_memory/server.py`. 16 MCP tools exposed via FastMCP (HTTP, streamable):

| Tool | Signature summary | Write/Read |
|------|-------------------|------------|
| `memory_store` | content, type?, importance?, tags?, source?, conversation_id? | Write |
| `memory_recall` | query, type_filter?, tags?, time_range?, limit? | Read + write-back (reinforcement) |
| `memory_get` | id | Read |
| `memory_update` | id, content?, type?, importance?, tags? | Write |
| `memory_relate` | source_id, target_id, rel_type, strength? | Write |
| `memory_related` | id, depth?, rel_types? | Read |
| `memory_unrelate` | source_id, target_id, rel_type | Write |
| `memory_list` | search?, type?, state?, tags?, time_range?, importance_min/max?, limit?, offset? | Read |
| `memory_archive` | id? / ids? / below_retrievability? | Write |
| `memory_restore` | id? / ids? | Write |
| `memory_delete` | confirm, id? / ids? | Write (destructive) |
| `memory_stats` | — | Read |
| `memory_consolidate` | dry_run? | Write (heavy) |
| `memory_self` | query, tags? | Read (identity shortcut) |
| `memory_who` | person, query?, tags? | Read (person shortcut) |
| `memory_health` | — | Read |

The tool surface is well-designed. The port method surface for Axiom (§4) will be derived from this but simplified — the loop only needs recall, store, update, relate, and consolidate. The richer admin surface (health, stats, list, archive, restore, delete) is useful for management but not loop-critical.

### 2.8 Known pain points — what the rebuild fixes

1. **External process dependency:** the SurrealDB backend introduces an external server. For Axiom, the Memory faculty must be sovereign and in-process — no external process to start, connect to, or lose.

2. **MCP-over-HTTP latency:** CM exposes its tools via HTTP MCP (FastMCP + uvicorn on port 8050). Every recall from Axiom would be an HTTP round-trip. The write path (store) would also block on HTTP. This is the same argument used for observability: adopt the library/SDK in-process, not the service.

3. **Spreading activation on recall hot path:** every `recall` triggers async stability writes back to graph neighbors. In an in-process faculty, these writes need to be fire-and-forget (async, non-blocking) so they don't extend the Perceive phase latency.

4. **O(N²) cluster scan in consolidation:** fine at low scale, needs a smarter approach (ANN index or pre-clustered candidates) as memory grows.

5. **No background consolidation:** promotion and archival only happen when explicitly triggered. The rebuild should support a session-end trigger or a lightweight background task (not a daemon, just an async task when the loop is idle).

6. **all-MiniLM-L6-v2 cold start:** ~10 seconds. Acceptable — warm it up at agent startup like CM does. But model choice is revisitable (see §5).

7. **Vector search in SQLite:** the original CM stored embeddings as BLOBs and loaded them into a numpy matrix in-memory for cosine search. This works for small corpora but doesn't scale. `sqlite-vec` (a SQLite extension) now provides proper ANN vector search in-process. This is the right path for the rebuild (see §5).

---

## 3. Field Landscape

*Synthesized from training knowledge; web searches used where noted. See §3.9 for source citations.*

### 3.1 MemGPT / Letta — tiered context management

**Core idea:** MemGPT (Packer et al., 2023) treats the context window as a scarce CPU register and manages three tiers: in-context (main context = "RAM"), external storage (archival = "disk"), and conversation history (recall storage). The agent actively manages what stays in context via explicit `core_memory_append/replace` and `archival_memory_search` tool calls. Letta is the productized evolution.

**Transferable idea:** the explicit **working-memory tier** — a small, always-in-context block that the agent actively curates. CM has a `working` type but it's just a fast-decaying memory, not a managed in-context block. Axiom's Perceive phase could maintain a small "context assembly" step that promotes the top-K recalled memories into the reasoning prompt — this is effectively what MemGPT's core_memory provides but via the recall pipeline rather than explicit agent tool calls.

**Does it improve on CM?** Partially. MemGPT's active management gives the agent explicit control; CM's decay-based approach is more passive and elegant. The right synthesis: CM's decay semantics with a Perceive-phase assembler that surfaces the right memories automatically (the agent shouldn't have to call explicit memory tools to load context on every turn).

### 3.2 mem0 — user-preference extraction and personalization

**Core idea:** mem0 (getmem0.ai) focuses on extracting and maintaining user facts from conversation — preferences, name, context — for personalization. Uses an LLM call to extract structured facts, stores with vector search, deduplicates.

**Transferable idea:** **LLM-assisted extraction** on the Observe write path. CM stores what the agent explicitly writes. mem0's approach of running a lightweight extraction pass over the conversation output to pull out salient facts would complement the explicit store call. In Axiom, this could be a self-correction CAPTURE call-point behavior (M8), not M3 scope.

**2025-2026 update (Mem0 paper, arxiv 2504.19413):** The published Mem0 architecture confirms: LLM extracts salient facts from conversation turns; a routing controller inspects the top-K most similar existing memories and classifies each update as ADD / UPDATE / DELETE / NOOP. Mem0g (the graph-augmented variant) builds a knowledge graph of extracted entities + relations (triplets), supporting BFS/DFS multi-hop traversal. Mem0 recently replaced external graph-store support with built-in entity linking. This confirms the direction (vector + graph hybrid is the consensus), not a reason to change CM's approach.

**Does it improve on CM?** At the extraction layer, yes. At the storage/retrieval layer, CM is more sophisticated (decay, graph, multi-strategy). Not a replacement; a complementary extraction strategy.

### 3.3 Generative Agents (Park et al., 2023) — memory stream, reflection, composite retrieval

**Core idea:** the Stanford Generative Agents paper introduces three memory mechanisms that work together:
1. **Memory stream:** append-only log of observations, each with recency, importance, and relevance scores.
2. **Reflection:** a scheduled process where the agent generates higher-order insights by querying its own memory stream (e.g., "what can I infer from these events about person X?"). Reflections are stored as new memories.
3. **Retrieval scoring:** combined score = recency + importance + relevance (each 0-1), used to select what enters the reasoning prompt.

**Retrieval formula:** `score = α·recency + β·importance + γ·relevance` where recency uses an exponential decay and relevance is embedding similarity to the current query.

**Transferable ideas:**
- The **combined scoring formula** is directly analogous to CM's RRF + decay reranking. CM improves on it by using graph traversal (Phase 2) and actual FSRS-style stability tracking rather than a simple linear recency term.
- **Reflection** — generating higher-level insights from recalled episodes — is the inspiration for CM's `episodic → semantic` promotion pattern. A language-model-assisted reflection (not just pattern-matching) would be more powerful but requires an LLM call; this is M8 (self-correction) territory more than M3.

**Does it improve on CM?** CM's retrieval is more sophisticated (multi-strategy, graph). The reflection mechanism is genuinely additive but requires LLM calls — deferred to M8.

### 3.4 Zep / Graphiti — temporal knowledge graphs

**Core idea:** Zep's Graphiti engine builds a temporal knowledge graph from conversations. Entities and relationships are extracted using an LLM, timestamped, and stored as a graph. Retrieval traverses the graph with temporal awareness — queries return facts relevant at a specific point in time, respecting "as of" semantics.

**Transferable idea:** **temporal edge metadata on relationships.** CM's `Relationship` model has `created_at` but no validity range or expiration. For agent memory, the fact "Kaushik is working on Axiom" has a temporal scope. Adding `valid_from / valid_until` to relationships, or at minimum a timestamp on when a relationship was last confirmed, would make the graph semantically richer.

**Does it improve on CM?** The temporal relationship metadata is a genuine gap. The LLM-driven extraction is powerful but adds latency; for Axiom's in-process faculty, this should be optional (store with explicit metadata rather than LLM extraction on the write path). The graph structure itself is directionally aligned with CM.

### 3.5 A-MEM — agentic memory with dynamic linking

**Core idea:** A-MEM generates structured notes from experiences (using an LLM), dynamically links them by semantic similarity and explicit relation types, and evolves the network over time. Similar in spirit to CM's auto-linking + consolidation.

**Transferable idea:** **structured note generation from raw observation.** Rather than storing raw text and letting classification heuristics type it, a lightweight extraction step (even a compact local model) generates a structured "note" with explicit key facts. This reduces noise in the memory store. Again, this is more M8 (CAPTURE call-point) than M3.

**Does it improve on CM?** At the ingestion layer, yes. At the retrieval and decay layer, CM is more rigorous.

### 3.6 Sleep-time / background consolidation

**Core idea:** several systems (MemoryOS, background consolidation variants) run a consolidation pass "while the agent sleeps" — i.e., between active sessions, not during live interaction. This avoids consolidation latency on the hot path.

**Transferable idea:** directly applicable. Axiom should trigger consolidation at **session end** (after the loop exits) rather than during active processing. The consolidation pipeline is CPU-intensive (embedding comparisons for clustering) and should never fire synchronously on the Perceive or Observe paths. This is a design decision that must be locked at M3 (see §7).

### 3.7 RAG vs. agent memory — the distinction matters

**Core idea:** RAG (Retrieval-Augmented Generation) retrieves from a static or slowly-updated document corpus. Agent memory, by contrast, is **written by the agent**, **decays over time**, **changes semantics** (episodic → semantic), and **is expected to be queried with egocentric queries** ("what do I know about X?" not "what does the corpus say about X?").

**Why this matters for M3:** don't import RAG mental models. The Memory faculty is not a document store. Critically:
- **Write path is on the critical path.** RAG's indexing is async/offline. Memory's store must happen at Observe time (potentially per loop cycle).
- **Decay and reinforcement are not RAG features.** The memory system must track access patterns and age — a vector database alone is not sufficient.
- **Self-referential.** The agent queries its own memory with context-shaped queries, not user queries. The retrieval prompt should encode the current loop state, not just the user's last message.

### 3.8 Vector + graph hybrids — what the research shows

The dominant pattern in recent agent memory research is a **hybrid vector + graph store**: vector search provides semantic recall; graph traversal provides associative expansion; their combination (GraphRAG, HippoRAG, etc.) consistently outperforms either alone for complex multi-hop questions.

CM's two-phase pipeline (semantic/keyword/temporal → graph expansion → RRF fusion) is architecturally aligned with this finding. The rebuild should preserve this structure. The key engineering question is which in-process vector index to use without the SurrealDB external dependency (see §5).

### 3.9 Web sources consulted

Web searches conducted and confirmed:
- **sqlite-vec Windows support:** [asg017/sqlite-vec](https://github.com/asg017/sqlite-vec) confirmed; [sqliteai/sqlite-vector](https://github.com/sqliteai/sqlite-vector) — Windows x86-64 prebuilt binary confirmed (May 2026), SIMD + TurboQuant.
- **py-fsrs / FSRS 6:** [open-spaced-repetition/py-fsrs](https://github.com/open-spaced-repetition/py-fsrs), [PyPI: fsrs](https://pypi.org/project/fsrs/) — confirmed FSRS 6 release, actively maintained.
- **Mem0 paper:** [arxiv 2504.19413](https://arxiv.org/pdf/2504.19413) — confirms LLM extraction + ADD/UPDATE/DELETE/NOOP routing controller; Mem0g = graph-augmented variant.
- Topics researched from training knowledge (no additional live fetches): MemGPT/Letta tiered context, Generative Agents (Park et al. 2023) memory stream + reflection, Zep/Graphiti temporal knowledge graphs, A-MEM, RAG vs agent memory distinction, vector+graph hybrid retrieval (GraphRAG, HippoRAG).

---

## 4. The Memory PORT — Contract and Adapter Shape

### 4.1 What the loop needs from Memory

The Memory port is called at two loop phases:

| Phase | Call | What the loop provides | What Memory returns |
|-------|------|----------------------|---------------------|
| **Perceive** | `recall(query, context)` | The current query / user input + loop state context | Ranked list of relevant memories (RecallResult-like) for context assembly |
| **Observe** | `store(content, type?, importance?, tags?)` | New knowledge extracted from the cycle's result | Confirmation; fire-and-forget acceptable |
| **Observe** | `reinforce(ids)` | IDs of memories that proved useful this cycle | Updates stability; fire-and-forget |

Two additional non-hot-path operations:
- **Session end:** `consolidate()` — triggered when the loop exits a session; async, non-blocking to the caller.
- **Health / admin:** `stats()`, `health()`, `list()` — management calls, not loop-critical.

### 4.2 Port method surface

The Memory port contract (to be locked in the design pass) should expose:

```python
class MemoryPort(Protocol):
    async def recall(
        self,
        query: str,
        context: dict | None = None,       # loop state for context-shaped retrieval
        type_filter: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[RecallResult]: ...

    async def store(
        self,
        content: str,
        memory_type: str | None = None,    # None = auto-classify
        importance: float | None = None,   # None = auto-score
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> str: ...                          # returns memory id

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        tags: list[str] | None = None,
    ) -> None: ...

    async def relate(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float = 1.0,
    ) -> None: ...

    async def consolidate(self) -> list[dict]: ...  # session-end, non-blocking to caller

    # Management (not loop-critical):
    async def stats(self) -> dict: ...
    async def health(self) -> dict: ...
```

This is a thinning of CM's 16-tool surface to what the loop actually needs. The full admin surface (`list`, `archive`, `restore`, `delete`, `who`, `self`) can be added to a management interface or CLI separately — they are not port operations the loop invokes.

### 4.3 How a CM-kind rebuild sits behind the port

The Memory faculty is an in-process **adapter** implementing `MemoryPort`. It contains:

```
src/axiom/memory/
    __init__.py
    port.py          # MemoryPort Protocol (the contract)
    adapter.py       # CognitiveMemoryAdapter — implements MemoryPort
    decay.py         # FSRS / decay functions (pure, no I/O)
    models.py        # Memory, RecallResult, Relationship (Pydantic)
    classification.py # Type + importance heuristics
    retrieval.py     # Multi-strategy recall pipeline
    consolidation.py # Promotion, archival, merge pipeline
    embeddings.py    # EmbeddingService (lazy-load model)
    storage.py       # SQLite + sqlite-vec backend
    schema.py        # Migration runner + DDL
```

The core loop imports `MemoryPort` from `port.py` — never the adapter directly. The `CognitiveMemoryAdapter` is wired at composition time (in `main.py` / the agent factory). This is the hexagonal pattern applied: the loop is memory-backend-agnostic; swapping to a different memory backend means writing a new adapter.

### 4.4 Rebuild vs. wrap-the-MCP — the engineering reason

The roadmap decision to **rebuild in-process** rather than wrap CM as an MCP client is locked. The engineering reasons, stated plainly:

1. **Sovereign in-process faculty, no external process dependency.** Axiom must boot with `python -m axiom` and work with zero external services running. CM's MCP server requires uvicorn + either SurrealKV or a SurrealDB process. That is an installation failure point and an availability dependency — exactly what the architecture rejects for the same reason NATS was rejected for observability.

2. **No HTTP round-trip on the Perceive critical path.** Every loop cycle calls `recall` at Perceive. An HTTP call to localhost adds serialization, network stack, and deserialization overhead per cycle. In-process is a function call. This is the same latency invariant as observability: "a write must NOT block the loop."

3. **Decay write-back on recall must be fire-and-forget.** CM's recall fires async stability writes back to graph neighbors. Behind an HTTP MCP boundary, those writes either block the HTTP response (adding latency) or are orphaned (the MCP server doesn't know when to send them). In-process, they can be dispatched as `asyncio.create_task` — true fire-and-forget.

4. **No dependency on CM's architecture decisions.** CM's SurrealDB migration is pragmatically reasonable for CM's standalone server model. It is wrong for Axiom, which needs local-first SQLite. Rebuilding lets us choose the right backend without a compatibility burden.

5. **Controllability by construction.** The loop can inspect and instrument memory operations directly. Observability traces can span across the memory call without crossing a process boundary.

### 4.5 Sync vs. async — the write latency invariant

The same invariant as observability applies: **a memory write must NOT block the loop.**

- `recall` (Perceive): **awaited** — the loop needs the results before it can assemble context. But recall should be fast (< 100 ms target; see §6 spikes).
- `store` (Observe): **fire-and-forget** — dispatch as `asyncio.create_task`. The loop does not need confirmation to proceed. If the store fails, it fails silently (log it; don't crash the loop).
- `reinforce` write-backs: **fire-and-forget** — same pattern.
- `consolidate` (session end): **awaited at session close** — the loop is already exiting; blocking here is acceptable. But don't run it mid-session.

This means the `store` call in `MemoryPort.store` should be designed so the caller can fire-and-forget it — either the adapter internally creates a task, or the Observe phase wraps the call in `asyncio.create_task`. The port contract should document which model is used.

---

## 5. Reuse-Over-Build Decisions

For each subcomponent, the analysis follows: what exists, whether it fits, recommendation with rationale.

### 5.1 FSRS as a library — py-fsrs

**Exists:** `py-fsrs` (PyPI: `fsrs`, GitHub: open-spaced-repetition/py-fsrs). Implements FSRS v5 — the algorithm used by Anki, with difficulty parameter D, separate stability formulas for successful vs. lapsed reviews, and fitted constants from human memory research.

**Does it fit?** Partially. True FSRS requires a "rating" (Again/Hard/Good/Easy) on each recall — it is designed for deliberate study. In agent memory, recall is automatic (the agent doesn't rate how well it "remembered" a fact). The rating can be approximated (did the recalled memory get reinforced / used? if yes, rate Good; if recalled but not used, rate Hard), but this is an approximation.

**2025-2026 update:** py-fsrs (`fsrs` on PyPI, GitHub: open-spaced-repetition/py-fsrs) is actively maintained and has advanced to **FSRS 6**, which adds two new parameters for better scheduling of same-day reviews and more accurate forgetting-rate modeling for all cards. The library is stable, small, and designed to be embedded in larger applications. The `desired_retention` config parameter sets the target minimum retention rate (default 0.9 = schedule when predicted recall probability falls to 90%).

**Recommendation: start with CM's simplified model, evaluate py-fsrs as a spike.** CM's `R(t) = e^(-t / 9S)` with access-triggered stability boost is simpler and requires no rating. It loses FSRS's difficulty tracking but gains simplicity and no dependency. The FSRS 6 spike (§6) should test whether py-fsrs's rating approximation from usage signals (used = Good; recalled but not reinforced = Hard) produces meaningfully better retention than CM's model. If not, keep the simpler model. If yes, adopt `py-fsrs` as a library (`pip install fsrs`).

### 5.2 Local embedding model — sentence-transformers

**Current (CM):** `all-MiniLM-L6-v2` (sentence-transformers), 384d, ~80 MB model, fast CPU inference, good quality/speed tradeoff. A solid default.

**Alternatives:**
- `all-mpnet-base-v2` (768d): higher quality, 2x slower, 4x larger. Overkill for short memory fragments.
- `nomic-embed-text` (768d via nomic-ai): competitive quality, open, available via sentence-transformers or ollama.
- `snowflake-arctic-embed-m` (768d): strong benchmark scores, available on HuggingFace.
- Local vLLM (DGX Spark): could use the Llama model's embedding endpoint, but sentence-transformers models are purpose-built for embedding and faster for this workload.

**Recommendation: keep `all-MiniLM-L6-v2` for M3.** It is already validated in CM, the dependency is already in use, and the quality is adequate for personal-scale memory (thousands, not millions, of entries). The model choice is behind the `EmbeddingService` abstraction — swapping later requires only changing `MODEL_NAME` and `DIMENSIONS`. Pin `sentence-transformers>=3.0.0,<5.0` as in CM.

**Cold-start:** keep CM's `warmup()` pattern — load the model eagerly at agent startup, not on first recall. The ~10 second load is acceptable once per session.

### 5.3 In-process vector index — sqlite-vec

**The problem:** in CM's original SQLite backend, embeddings were stored as BLOBs and loaded into a numpy matrix for cosine search. This works for small corpora but means loading all embeddings into RAM and scanning all of them on every recall. It doesn't scale.

**sqlite-vec** (GitHub: asg017/sqlite-vec): a SQLite extension (loadable `.so`/`.dll`) that provides:
- `vec0` virtual table for approximate nearest-neighbor vector search
- `vec_distance_cosine`, `vec_distance_l2` functions
- HNSW index support (approximate, fast)
- Operates entirely in-process, no external service
- Available via PyPI as `sqlite-vec` (Python bindings)

**2025-2026 update — two implementations to evaluate:**
- **asg017/sqlite-vec**: the original, widely-used, `vec0` virtual table approach. Well-tested across platforms.
- **sqliteai/sqlite-vector** (PyPI: `sqliteai-vector`): newer, cross-platform (Windows x86-64 prebuilt binary as of May 2026), SIMD-accelerated, TurboQuant 2/3/4-bit quantization scans, 30 MB memory footprint, no virtual tables needed (vectors stored as BLOBs with optimized C distance kernels). Windows support explicitly confirmed.

**Alternative: chromadb in-process mode.** ChromaDB has a sqlite+parquet in-process mode (`chromadb.Client()` with no server URL). It provides vector search, metadata filtering, and collection management. However, it is a larger dependency with its own data format — not as clean a fit as sqlite-vec alongside our existing SQLite tables.

**Alternative: faiss.** Facebook's FAISS is fast and well-tested, but it stores index separately from SQLite — requires coordinating two storage systems. ID mapping between SQLite memory IDs and FAISS index positions adds complexity.

**Recommendation: evaluate both sqlite-vec implementations in the spike (§6); lean toward `sqliteai-vector` if Windows prebuilt binary installs cleanly.** Keeps everything in one SQLite database file. Same file, same WAL, same backup story. The SIMD acceleration and TurboQuant quantization in `sqliteai-vector` may provide better performance for CPU-only search on kh-legion. If the prebuilt binary is not available or has issues, fall back to `asg017/sqlite-vec`. **Spike required** (§6) — verify installation on Windows (kh-legion), Python bindings work with existing sqlite3 connection, and cosine search latency meets the < 50ms target for 384d embeddings at 10K+ memories.

### 5.4 Graph layer

**The problem:** CM's graph traversal (spreading activation walk, neighbor bulk lookup) was implemented in SurrealDB. For the rebuild on SQLite, graph traversal is SQL-based — `relationship` table joins or recursive CTEs.

**Recommendation: SQL recursive CTEs on the `relationship` table.** SQLite supports `WITH RECURSIVE` CTEs — sufficient for 2-3 hop traversals. No additional graph library needed. The spreading activation walk (up to 3 hops) can be expressed as a recursive CTE:

```sql
WITH RECURSIVE spread(neighbor_id, depth, rel_strength, state) AS (
  SELECT target_id, 1, strength, m.state
  FROM relationship r JOIN memory m ON m.id = r.target_id
  WHERE source_id IN ({seed_ids})
  UNION ALL
  SELECT r2.target_id, s.depth + 1, r2.strength, m2.state
  FROM spread s
  JOIN relationship r2 ON r2.source_id = s.neighbor_id
  JOIN memory m2 ON m2.id = r2.target_id
  WHERE s.depth < {max_depth}
)
SELECT neighbor_id, depth, rel_strength, state FROM spread;
```

For a personal-scale agent memory (thousands of memories, hundreds of relationships), this is fast. No external graph database, no dependency. If the graph grows to millions of edges in a later phase, evaluate a dedicated graph library then.

### 5.5 FTS (full-text search)

**Recommendation: SQLite FTS5 (unchanged from CM's original).** Built into Python's `sqlite3` module. Unicode tokenizer, BM25 ranking, fast. No dependency. Maintain the sync invariant: FTS5 virtual table is updated on every content insert/update/delete. Keep CM's `memory_fts` pattern.

### 5.6 Summary of reuse decisions

| Component | Decision | Library / pattern | Custom? |
|-----------|----------|-------------------|---------|
| Decay model | Keep CM's simplified model; spike py-fsrs | `py-fsrs` (optional spike) | Core formula stays custom if spike doesn't win |
| Embedding model | `all-MiniLM-L6-v2` via sentence-transformers | `sentence-transformers` | No |
| Vector search | sqlite-vec (HNSW in-process) | `sqlite-vec` | No (spike required) |
| FTS | SQLite FTS5 | stdlib sqlite3 | No |
| Graph traversal | SQL recursive CTEs | stdlib sqlite3 | Schema + query |
| Storage | SQLite + WAL (no SurrealDB) | stdlib sqlite3 | Schema is custom |
| Classification | Keep CM's heuristic (adapt) | None | Yes (lightweight) |
| Consolidation | Rebuild pipeline (same stages) | None | Yes (domain logic) |

---

## 6. Spike-Before-Spec Risks

Mirror of §3's spike section in the observability doc. These must be verified before the spec is written — unresolved, they can force rework at implementation.

### Spike 1 — sqlite-vec installation and query latency (HIGHEST RISK)

**Risk:** `sqlite-vec` is a loadable SQLite extension. On Windows (the primary development platform, kh-legion), loading `.dll` extensions requires either a sqlite3 build that allows extension loading or using the Python package's bundled binaries. The Python `sqlite-vec` package (PyPI) should handle this, but it must be verified. Additionally, HNSW index build time on 10K+ memories and approximate search latency need to be measured.

**Spike task:** install `sqlite-vec`, build a test database with 10K synthetic embeddings (384d float32), measure: (a) can `vec0` virtual table load cleanly on Windows; (b) HNSW index build time; (c) ANN query latency for top-10 at `ef_search=64`; (d) exact cosine scan latency for comparison. Target: < 50ms for the embedding search step in recall.

**If sqlite-vec fails on Windows:** fallback to chromadb in-process mode (well-tested, cross-platform) or numpy matrix scan (acceptable for < 5K memories, degrades gracefully).

### Spike 2 — embedding model latency on the write path

**Risk:** `store` fires at Observe time. `all-MiniLM-L6-v2` CPU inference on kh-legion (CPU machine, not DGX Spark) must be fast enough to not bottleneck the Observe phase. Even as a fire-and-forget task, if embedding is slow, the background task queue builds up. Target: < 100ms per embedding on CPU.

**Spike task:** run `all-MiniLM-L6-v2` encode on 50 sample texts of typical memory-fragment length (50-200 words). Measure p50 and p99 latency on kh-legion's CPU. If too slow, evaluate whether vLLM's embedding endpoint (DGX Spark) can serve embeddings with acceptable latency — though this reintroduces an external service dependency (trade-off noted).

**Alternative:** smaller model (e.g., `all-MiniLM-L12-v2` is actually faster than L6 despite the name; verify). Or quantized model via `sentence-transformers` ONNX export.

### Spike 3 — py-fsrs rating approximation (SECONDARY)

**Risk:** If we want true FSRS with difficulty tracking, we need a rating signal. The approximation (usage = Good, no reinforcement = Hard) may not produce well-calibrated stability updates.

**Spike task:** compare stability trajectories over a simulated 6-month usage pattern: CM's simple model vs py-fsrs with approximated ratings. Are the differences meaningful (> 10% difference in R at the archive threshold)? If not, keep the simple model. This is a lower-priority spike than 1 and 2.

### Spike 4 — consolidation timing and async interaction

**Risk:** consolidation (§2.4) is CPU-intensive — it does per-memory vector search for clustering. If triggered at session end while the loop is winding down, it could extend shutdown time. If triggered as a background task, it needs to be isolated from active recall (concurrent writes to stability/retrievability could race with recall reinforcement writes).

**Spike task:** profile consolidation on a corpus of 1K, 5K, 10K memories. Measure total runtime. Verify SQLite WAL mode handles concurrent read (recall) + write (consolidation) safely — WAL allows one writer, multiple readers; consolidation is a writer. If session-end consolidation is too slow, consider debounced consolidation (every N stores, or every T minutes of uptime, not every session end).

---

## 7. Open Questions for the K+V Design Pass

These are genuine forks — not silently resolved here. Each needs a decision before the spec locks.

**Q1 — Consolidation trigger: when and by whom?**
Options: (a) session end (loop exits → `await memory.consolidate()` before teardown); (b) periodic background task (every N minutes, asyncio task, careful about WAL write contention with recall); (c) explicit agent call only (agent decides when to consolidate); (d) store-count-triggered (every N stores triggers a lightweight consolidation, not the full pipeline). The session-end option is simplest and avoids hot-path contention but misses long-running sessions. K to decide.

**Q2 — How does Perceive assemble context from recalled memories?**
The Memory port returns ranked `RecallResult` items. The Perceive / Context Assembler (loop component) must format them into the reasoning prompt. Options: (a) inject top-K as text blocks in the system prompt; (b) inject as a structured section with type/importance metadata; (c) let the agent decide format via a template in `persona.md`. This is a loop design decision (Perceive phase) that touches M3's contract — RecallResult shape must support whatever format the loop needs. The design pass should define the RecallResult → prompt-fragment transformation.

**Q3 — Should `store` be synchronous or truly fire-and-forget?**
The brief says "write must NOT block the loop." Fire-and-forget via `asyncio.create_task` achieves this, but creates a subtle hazard: if the loop stores a memory and immediately recalls related memories, the store task may not have completed yet. In practice, the next recall is a different query and the store result is unlikely to be the top result immediately — but the invariant is not guaranteed. Options: (a) pure fire-and-forget (simplest, accepts the brief ordering gap); (b) store completes embedding+insert before returning, but reinforcement write-backs are fire-and-forget (middle ground); (c) store is awaited (blocking, simple, violates latency invariant). Recommend (b) — embedding is fast (< 100ms target), blocking for the insert is acceptable; spreading activation write-backs are not.

**Q4 — Seed / migrate from existing CM data?**
Kaushik has CM running with existing memories (Velasari persona, project context, etc.). When Axiom's in-process memory is first initialized, should it: (a) start fresh (clean slate — simpler, no migration burden); (b) import from CM's export (carry over existing memories — relationship types and IDs would need mapping); (c) read from CM via the MCP and re-store (lossy — loses stability and access history). The CM backup/export tooling (`src/cognitive_memory/backup/exporter.py`) exists. The design pass should decide whether M3 includes a migration path or starts fresh.

**Q5 — Identity memories and persona initialization?**
CM's `identity` type is for the agent's self-knowledge. In Axiom, persona is in `persona.md`. For M3: should the initial identity memories be seeded from `persona.md` at first boot (converting persona sections into identity-type memories), or should `persona.md` remain the canonical source and identity memories only accumulate from experience? The two models have different implications for how the agent introspects its own identity at recall time.

**Q6 — `person` type and relationship context for Kaushik?**
CM has `person` type with `person:kaushik` tags. Should Axiom's memory be pre-seeded with foundational Kaushik context at first boot (name, role, preferences, project context), or should it learn this from early sessions? Pre-seeding is faster to useful; learning is more honest to the memory-from-experience model.

---

## 8. Non-Goals (fenced)

- No external MCP server (rebuilding in-process — locked).
- No SurrealDB or any external database dependency in M3.
- No web dashboard or admin UI in M3.
- No LLM-assisted memory extraction on the write path in M3 (that is M8 — CAPTURE call-point).
- No reflection pass (MemGPT-style higher-order reasoning over memories) in M3 — M8 territory.
- No multi-agent memory sharing in M3 — M7 (Orchestrator) scope.
- No guardrails on memory content in M3 — M9 (connectors + untrusted input) triggers that.
- No migration tooling from existing CM data — unless Q4 is decided yes (then it is in scope).

---

## 9. Summary — Key Decisions for the Design Pass

| Decision | Recommendation | Confidence |
|----------|---------------|------------|
| Storage backend | SQLite + WAL, single file, in-process | High |
| Vector search | sqlite-vec (spike first); chromadb as fallback | Medium (spike-dependent) |
| FTS | SQLite FTS5 (unchanged from CM) | High |
| Graph traversal | SQL recursive CTEs (no graph library) | High |
| Embedding model | `all-MiniLM-L6-v2`, warm up at startup | High |
| Decay model | CM's simplified model; py-fsrs as optional spike | High |
| Classification | CM's heuristic (`classification.py` adapted) | High |
| Consolidation staging | 6 stages (CM's pipeline, adapted) | High |
| Consolidation trigger | Session end (Q1 — K to decide) | Pending K |
| Write latency | store = blocking for embed+insert; write-backs fire-and-forget | Medium (Q3 fork) |
| Port method surface | recall, store, update, relate, consolidate, stats, health | High |
| Seed from existing CM | Fresh start (Q4 — K to decide) | Pending K |
| **Working context (runtime tier)** | **Two-tier memory — see §10** | **Locked (K+V design pass)** |

---

## 10. Working-Context — the runtime tier (added 2026-07-14, K+V design pass)

*Net-new beyond the original research (§1–§9). It came out of a design-pass question — "in Axiom, who holds the live model context?" — and it upgrades M3 from a single persistent store to a **two-tier memory**. §1–§9 describe the persistent (cognitive) tier; this section describes the runtime (working) tier.*

### 10.1 The question and the boundary

The Memory faculty in §1–§9 is the **long-term, cross-session store** — the "disk." It does **not** hold the live model context (the message window sent to the model on each Reason call). That live context is in-session state, owned by the loop and assembled at Perceive.

The decision: make that in-session context a **first-class component** — the **Working-Context** — rather than an implicit message list buried in the loop. It is the **runtime tier of the memory system**: the same embedding + vector machinery as the cognitive tier, but it "resides in memory only while running" and is ephemeral by default.

So M3 is **two-tier**:
- **Working tier (this section):** in-memory, ephemeral, holds the live conversation.
- **Cognitive tier (§1–§9):** persistent, decay-aware, cross-session.

### 10.2 How it works — ring buffer + recency floor + relevance

The working context is held as an **in-memory vector ring buffer** (bounded). On each user turn, the model context is assembled as:

```
context = [ last N conversation units, VERBATIM ]      # recency floor
        + [ older units pulled by RELEVANCE, via a vector query on the buffer ]
```

- **Relevance-windowing** gives a small model high relevance — it sees only what matters, so a modest context window punches above its weight. This is the point: Axiom targets small / local models.
- **The recency floor is mandatory.** Pure relevance-assembly shreds conversational coherence — it drops the connective tissue (pronoun referents, "as I said above," the arc of an argument). Relevance ≠ coherence. Keeping the last N units verbatim preserves the thread; relevance only *augments* with older material. This is the Generative-Agents recency + relevance blend (§3.3) applied to the agent's own conversation buffer.

### 10.3 The unit — a conversation unit (user + agent)

The buffered unit is **one conversation unit = a user message plus the agent's response, together** — not a single message, and not the loop's internal steps.

**Tool I/O is excluded.** Axiom runs `perceive → reason → act → observe`. The loop's internal exchange — tool calls, tool results (file reads, command dumps), intermediate reasoning — is **transient per-cycle machinery**: held only for the duration of one cycle, then discarded. Only what **Observe emits at loop-conclude** — the user↔agent conversation unit — enters the buffer. Caching every intermediate state was considered and rejected as very costly and pointless.

Two payoffs:
1. **No buffer pollution.** A giant tool dump can never eat the recency floor or blow the window, because it never enters the buffer.
2. **A clean tier division.** Anything from *inside* a loop worth keeping does not bloat the working buffer — it crosses into the **cognitive tier** via an explicit `store` at Observe (or is simply re-derived by re-running the tool, which is cheap). Nothing durable is lost by dropping the intermediates.

*Pairing user + agent as one unit has a nice property: a question and its answer travel together, so any retrieved slice is self-contained — you never pull an answer without its ask.*

### 10.4 Sizing — count floor + token cap

- **Recency floor: N ≈ 50 conversation units** verbatim; older units fall to retrieval.
- **A hard token cap** on the assembled context is the real guardrail. `N` is a count ceiling; the binding constraint for a small model is *tokens*, not unit-count. With tool I/O excluded, unit sizes are predictable, so the cap is a cheap safety rail rather than a critical control — but it stays, because a run of long answers can still add up.

### 10.5 Deferred / open

- **Persistence of the working buffer** → deferred. At session end the buffer can either vanish or be pushed to the cognitive tier; decided later.
- **Reinforcement tie-in:** what the buffer *retrieves and uses* is precisely the "what got used" signal the cognitive tier needs for reinforcement / promotion (the §1 flag). The two tiers meet here.
- **Embedding granularity:** a very long, multi-topic conversation unit gets one averaged embedding, which is coarse for relevance retrieval. Acceptable to start; sub-chunk later if retrieval quality demands it.

---

*Sources consulted: `C:/Projects/cognitive-memory/src/cognitive_memory/models.py`, `decay.py`, `retrieval.py`, `consolidation.py`, `classification.py`, `server.py`, `embeddings.py`, `storage.py`, `migrations/001_initial.py`, `config.default.yaml`, `CLAUDE.md`, `pyproject.toml`. Web searches: MemGPT/Letta, mem0, Generative Agents retrieval formula, Zep Graphiti temporal knowledge graphs, sqlite-vec Python bindings.*
