# M3 · Memory — Design

**Spec:** `005-m3-memory`
**Milestone:** M3 — "It learns across sessions"
**Author:** Velasari — 2026-07-14
**Status:** DRAFT
**Inputs:** Research `006-m3-memory-architecture-2026-07-14.md` (§10 authoritative for working-context; §2 mechanics restated as Axiom's own); `001-agent-core/architecture.md`; `001-agent-core-roadmap.md`; sibling spec `004-m2-observability/`; K+V design pass (locked decisions).

> **Note — self-containment:** This design document is fully self-contained. All memory mechanics (decay, retrieval, consolidation, taxonomy, relation graph) are stated in Axiom's own terms. The mechanics were adapted from a proven prior implementation but are reproduced here in full — a future reader in this repo requires no external reference.

> **Note — task.md:** `task.md` is intentionally sparse at design phase. It is fleshed out at implementation time.

---

## 1. Overview

M3 adds a persistent, decay-aware **Memory faculty** to Axiom. The faculty is structured as a hexagonal-port adapter: the agent loop imports only `MemoryPort` (a Protocol); the concrete implementation (`CognitiveMemoryAdapter`) is wired at composition time. The loop is memory-backend-agnostic.

The design has four axes:

1. **Two-tier:** a runtime **Working-Context** (in-session ephemeral ring buffer) and a persistent **Cognitive** store (decay-aware, typed, graph-connected).
2. **Port contract:** `MemoryPort` defines six awaitable/fire-and-forget methods that exactly cover the loop's needs at each PRAO phase. Richer admin methods live in a separate management interface.
3. **Sovereign storage:** embedded SurrealKV (in-process, single-file) provides vector search, graph, and full-text natively — no external database process.
4. **Async invariant:** `assemble_context` and `recall` are awaited; `store`, `reinforce`, `relate`, `update` are fire-and-forget at the port contract level, enforced by construction.

---

## 2. Component Map

```
╔══════════════════════════════════════════════════════════════════════╗
║  AGENT LOOP (PraoLoop)                                               ║
║  perceive → reason → act → observe                                   ║
║                                                                      ║
║  Perceive: await memory.assemble_context(query)                      ║
║  Observe:  asyncio.create_task(memory.store(...))     [fire-forget]  ║
║  Observe:  asyncio.create_task(memory.reinforce(ids)) [fire-forget]  ║
║  Shutdown: await memory.consolidate()                                ║
╚══════════════════════╤═══════════════════════════════════════════════╝
                       │  MemoryPort Protocol
                       │  (loop imports port.py ONLY; never adapter)
                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│  MEMORY FACULTY  (src/axiom/memory/)                                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  CognitiveMemoryAdapter   (adapter.py)                      │    │
│  │  Implements MemoryPort; wires all sub-components            │    │
│  │                                                             │    │
│  │  ┌─────────────────┐   ┌──────────────────────────────┐    │    │
│  │  │ WorkingContext  │   │  Cognitive Tier               │    │    │
│  │  │ (working_ctx.py)│   │                               │    │    │
│  │  │                 │   │  ┌─────────────┐             │    │    │
│  │  │ in-memory       │   │  │ retrieval.py│ (Phase 1+2) │    │    │
│  │  │ vector ring buf │   │  │ semantic +  │             │    │    │
│  │  │ N≈50 units      │   │  │ keyword +   │             │    │    │
│  │  │ token-capped    │   │  │ temporal    │             │    │    │
│  │  │ recency floor + │   │  │ RRF fusion  │             │    │    │
│  │  │ relevance query │   │  └─────────────┘             │    │    │
│  │  └─────────────────┘   │  ┌─────────────────────────┐ │    │    │
│  │                         │  │ decay.py                │ │    │    │
│  │                         │  │ R(t), reinforce,        │ │    │    │
│  │                         │  │ spreading activation    │ │    │    │
│  │                         │  └─────────────────────────┘ │    │    │
│  │                         │  ┌─────────────────────────┐ │    │    │
│  │                         │  │ classification.py       │ │    │    │
│  │                         │  │ type heuristic +        │ │    │    │
│  │                         │  │ importance scoring      │ │    │    │
│  │                         │  └─────────────────────────┘ │    │    │
│  │                         │  ┌─────────────────────────┐ │    │    │
│  │                         │  │ consolidation.py        │ │    │    │
│  │                         │  │ 6-stage pipeline        │ │    │    │
│  │                         │  └─────────────────────────┘ │    │    │
│  │                         └──────────────────────────────┘    │    │
│  └──────────────┬──────────────────────────────────────────────┘    │
│                  │                                                    │
│  ┌───────────────▼────────────────────────────────────────────────┐  │
│  │  EmbeddingService  (embeddings.py)                             │  │
│  │  all-MiniLM-L6-v2 · 384d · warmed at startup                  │  │
│  └───────────────┬────────────────────────────────────────────────┘  │
│                  │                                                    │
│  ┌───────────────▼────────────────────────────────────────────────┐  │
│  │  StorageSeam  (storage.py)                                     │  │
│  │  Thin Axiom-side abstraction over embedded SurrealKV           │  │
│  │  Provides: vector search · graph traversal · full-text         │  │
│  │  Backend: surrealkv-file (in-process, single-file, sovereign)  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. MemoryPort Protocol (the contract)

**File:** `src/axiom/memory/port.py`

```python
from typing import Protocol
from axiom.memory.models import RecallResult, AssembledContext, ConversationUnit

class MemoryPort(Protocol):

    # ── AWAITED — loop blocks until result is available ─────────────────

    async def assemble_context(
        self,
        query: str,
        conversation_id: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> AssembledContext: ...
    # Returns both tiers as a structured object. The loop renders them
    # into chat-API slots; Memory owns the substance, not the prompt syntax.

    async def recall(
        self,
        query: str,
        context: dict | None = None,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        limit: int | None = None,
    ) -> list[RecallResult]: ...
    # Exposed as a primitive beneath assemble_context; available for
    # targeted callers. Target: <100 ms end-to-end.

    async def consolidate(self) -> list[dict]: ...
    # Awaited at session close ONLY. Returns action log.

    async def stats(self) -> dict: ...
    async def health(self) -> dict: ...

    async def append_unit(self, unit: ConversationUnit) -> None: ...
    # Called by the loop at Observe when a turn completes.
    # Embeds the ConversationUnit (user_text + agent_text) and appends it to
    # the working-context ring buffer. Embedding is computed at call time (not
    # fire-and-forget) so unit.embedding is ready for the next turn's relevance
    # query. Does NOT write to the cognitive store. Awaited by the loop.

    # ── FIRE-AND-FORGET — invariant enforced by construction ────────────
    # Every adapter MUST implement these as non-blocking: the ID is minted
    # synchronously; embed+insert runs as asyncio.create_task internally.

    async def store(
        self,
        content: str,
        memory_type: str | None = None,   # None = auto-classify
        importance: float | None = None,  # None = auto-score
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> str: ...
    # Writes to the COGNITIVE STORE ONLY. Does NOT write to the working-context buffer.
    # Returns the minted UUID4 id immediately. Embed+insert is async behind it.
    # For writing to the working-context ring buffer, use append_unit(unit).

    async def reinforce(self, ids: list[str]) -> None: ...
    # Fire-and-forget stability boost for memories used this cycle.

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
```

### 3.1 AssembledContext model

```python
@dataclass
class AssembledContext:
    working_context: list[ConversationUnit]
    # Last N units verbatim (recency floor) + older relevant units.
    # Rendered by loop as "Previous Conversations" in history slot.

    cognitive_memories: list[RecallResult]
    # Top-K recalled memories from the persistent store.
    # Rendered by loop as "Additional Context" in system prompt.
```

### 3.2 Sync/Async invariants (hard)

| Method | Contract | Mechanism |
|--------|----------|-----------|
| `assemble_context` | AWAITED | Loop cannot proceed to Reason without context |
| `recall` | AWAITED | Primitive used by assemble_context; also awaited by direct callers |
| `consolidate` | AWAITED at session close | Loop is already exiting; blocking is accepted |
| `stats`, `health` | AWAITED | Management; not on hot path |
| `append_unit` | AWAITED (fast) | Working-context write path; embedding computed at call time; must complete before next cycle's Perceive |
| `store` | FIRE-AND-FORGET (cognitive only) | Cognitive store only; ID minted synchronously; embed+insert via `asyncio.create_task`; does NOT touch working buffer |
| `reinforce` | FIRE-AND-FORGET | Loop dispatches via `asyncio.create_task(memory.reinforce(...))` |
| `relate` | FIRE-AND-FORGET | Dispatched; write arrives asynchronously |
| `update` | FIRE-AND-FORGET | Same |

The fire-and-forget invariant is **enforced by construction**: all adapters implementing `MemoryPort` must honor non-blocking store/reinforce — the protocol docstring states this. The loop always dispatches these via `asyncio.create_task`; an adapter that blocks inside `store` would delay subsequent task scheduling, not the loop's return, but internal blocking is still a contract violation.

### 3.3 Full admin surface (management interface — NOT MemoryPort)

These operations are NOT part of `MemoryPort` and are NOT called by the loop. They live on a separate `MemoryAdmin` interface (or a CLI entrypoint) for operator use:

- `list(search?, type?, state?, tags?, time_range?, importance_min?, importance_max?, limit?, offset?)`
- `archive(ids)` / `restore(ids)` / `delete(ids, confirm)`
- `who(person, query?, tags?)` — person-type shortcut
- `self_query(query, tags?)` — identity-type shortcut

---

## 4. Two-Tier Memory Model

### 4.1 Overview

M3's memory is **two-tier**:

| Tier | Scope | Storage | Purpose |
|------|-------|---------|---------|
| **Working-Context** | In-session, ephemeral | In-memory ring buffer | Live conversation context; assembled into "Previous Conversations" |
| **Cognitive** | Cross-session, persistent | Embedded SurrealKV file | Learned knowledge; assembled into "Additional Context" |

Both tiers are assembled in a single `assemble_context` call. The loop never deals with tiers directly.

### 4.2 Working-Context tier

**File:** `src/axiom/memory/working_context.py`

#### Unit definition

The buffered unit is a **Conversation Unit**: one user message paired with the agent's response — the exchange that Observe emits at loop-conclude. This is NOT a single message and NOT the loop's internal steps.

**Tool I/O is excluded.** Axiom runs `perceive → reason → act → observe`. The loop's internal machinery — tool calls, tool results, intermediate reasoning, intra-cycle scratch — is transient per-cycle state. Only the final user↔agent exchange enters the buffer. This has two payoffs:

1. **No buffer pollution.** A large tool dump (e.g. a file read) never consumes the recency floor or blows the token budget.
2. **Clean tier division.** Anything from inside a cycle worth keeping crosses into the cognitive tier via an explicit `store` at Observe. Nothing durable is lost by dropping the intermediates.

*A question and its answer travel together as one unit, so any retrieved slice is self-contained — you never pull an answer without its ask.*

#### ConversationUnit model

```python
@dataclass
class ConversationUnit:
    user_text: str          # The user's message for this turn
    agent_text: str         # The agent's response for this turn
    turn_index: int         # Monotonically increasing turn counter within the session
    timestamp: datetime     # When the turn concluded (set at Observe)
    embedding: list[float]  # 384-dim L2-normalised vector — set by append_unit, NOT at construction
    token_count: int        # Character-approximate token count: len(user_text + agent_text) // 4
                            # Set by append_unit. Used by _apply_token_cap.
```

`ConversationUnit` is the working-context unit: one complete user↔agent exchange. It is NOT a single message. The `embedding` covers the concatenated user+agent text and is computed by `append_unit` at write time — the field is empty at construction. The `token_count` is set by `append_unit` using the character approximation.

`ConversationUnit` is defined in `src/axiom/memory/models.py`.

#### Buffer mechanics

```
buffer = VectorRingBuffer(max_units=N_UNITS, max_tokens=TOKEN_BUDGET)
```

- **Bounded:** `N_UNITS ≈ 50` (count ceiling); `TOKEN_BUDGET` (token budget cap, the binding constraint for small models).
- **Token counting (G5):** `token_count = len(unit.user_text + unit.agent_text) // 4` — character-based approximation. No tokenizer dependency; no per-model variance. Consistently slightly underestimates (safe direction for a budget cap). Stored in `ConversationUnit.token_count` at `append_unit` time. `tiktoken` is NOT imported in M3. If exact per-model counts are needed in a future milestone, only `ConversationUnit.token_count` and the `append_unit` compute step change.
- **Recency floor:** the last N units are ALWAYS included verbatim, regardless of their embedding similarity to the current query.
- **Relevance augmentation:** units older than the recency floor are scored by cosine similarity to the embedded query; the top-K relevant older units are appended after the recency floor.

**Why both?**

Pure recency (verbatim last N) preserves conversational coherence — pronoun referents, the arc of an argument, "as I said above." Pure relevance shreds coherence: a relevance-only assembly might drop the last five turns because they scored lower than a two-week-old exchange. The recency floor guards the thread; relevance augments with older material that happens to be topical. This is the correct blend for a small-model context window.

#### Context assembly from the working tier

```python
def assemble_working_context(
    self,
    query: str,
    query_embedding: list[float],
) -> list[ConversationUnit]:
    # 1. Pop recency floor: last min(N_RECENCY_FLOOR, len(buffer)) units verbatim.
    recency_slice = self._buffer[-N_RECENCY_FLOOR:]

    # 2. For units older than the floor, embed-score against query_embedding.
    older_units = self._buffer[:-N_RECENCY_FLOOR]
    if older_units:
        scored = [(unit, cosine(unit.embedding, query_embedding)) for unit in older_units]
        scored.sort(key=lambda x: x[1], reverse=True)
        relevance_slice = [u for u, _ in scored[:N_RELEVANCE_TOP_K]]
    else:
        relevance_slice = []

    # 3. Combine: relevance slice first (older, topical), then recency floor (newest, verbatim).
    assembled = relevance_slice + list(recency_slice)

    # 4. Apply token budget cap: truncate from the relevance slice first.
    return _apply_token_cap(assembled, TOKEN_BUDGET)
```

#### Two write paths — working tier vs cognitive tier (G3)

**The working tier and cognitive tier use separate, independent write paths. Do not conflate them.**

**Cognitive tier write path — `store(content: str, ...)`:**
`MemoryPort.store(content, ...)` writes a content string to the **persistent cognitive store only**. The loop calls `store` at Observe for knowledge items worth retaining across sessions (facts, decisions, notable context). Inside the adapter, `store` mints a UUID4 synchronously, then fires embed+insert via `asyncio.create_task` (fire-and-forget). `store` does **not** touch the working-context ring buffer.

**Working-context write path — `append_unit(unit: ConversationUnit)`:**
At Observe, when a turn completes, the loop constructs a `ConversationUnit` (populating `user_text`, `agent_text`, `turn_index`, `timestamp`) and calls `await memory.append_unit(unit)`. The adapter then:

1. Calls `EmbeddingService.embed(unit.user_text + " " + unit.agent_text)` — offloaded to executor (~50 ms CPU).
2. Sets `unit.embedding` (384-dim L2-normalised vector) and `unit.token_count = len(user_text + agent_text) // 4`.
3. Appends the fully-populated unit to the in-memory ring buffer.

Embedding runs **at append time** — not fire-and-forget. This guarantees `unit.embedding` exists before the next turn's `assemble_working_context` call (which uses cosine similarity against stored embeddings). The embedding cost is paid at Observe, not at Perceive. `append_unit` is **awaited** by the loop.

On buffer overflow (exceeding `max_units`), the oldest unit is evicted automatically. `append_unit` does **not** write to the cognitive store. If a conversation unit should also persist to the cognitive store (for long-term cross-session recall), the loop issues a separate `store(content, ...)` call in the same Observe phase — two distinct calls, two distinct effects.

### 4.3 Cognitive tier

The persistent tier. All details in §5–§10. At `assemble_context` time, the adapter calls `recall(query, limit=K_COGNITIVE)` against the cognitive store and packages the results into `AssembledContext.cognitive_memories`.

### 4.4 Loop rendering contract

`AssembledContext` carries substance, not prompt syntax. The loop renders it:

- `cognitive_memories` → system prompt section labelled "Additional Context" (each RecallResult rendered as its `content` field with optional type/importance metadata).
- `working_context` → conversation history slot labelled "Previous Conversations" (each ConversationUnit rendered as its user+agent text pair).
- The current query goes LAST as the final user turn.

The exact heading text, separator format, and markdown style are loop-level decisions (driven by a persona template); Memory does not produce prompt strings.

---

## 5. Memory Type Taxonomy

Axiom's cognitive tier stores six memory types. Each type has a distinct **initial stability** S₀ (days) governing its default forgetting rate and an **archive threshold** below which it is retired at consolidation time.

| Type | S₀ (days) | Half-life intuition | Archive threshold | Notes |
|------|-----------|---------------------|-------------------|-------|
| `working` | 0.04 | ~58 minutes | R < 0.2 | Conversation ephemera; promoted or fades fast |
| `episodic` | 2.0 | ~13 days | R < 0.2 | Specific events, dated interactions |
| `semantic` | 14.0 | ~3 months | R < 0.2 | Facts, definitions, durable knowledge |
| `procedural` | 60.0 | ~1.5 years | R < 0.2 | How-to knowledge; workflows |
| `identity` | 365.0 | ~never | Never archived | Self-knowledge; foundational; protected |
| `person` | 90.0 | ~6 years | R < 0.05 (strict) | Knowledge about people; harder to lose |

The asymmetric archive threshold for `person` (0.05 vs 0.2) reflects that losing knowledge about people is costlier than forgetting a random fact.

**Identity type and persona genesis:** M3 supports the `identity` type mechanically — memories of this type are stored, recalled, and never auto-archived. How the agent's identity/persona is *initially populated* (e.g. from a persona template or first-boot onboarding) is a **separate future milestone (persona genesis)**, explicitly OUT of M3 scope.

### 5.1 Auto-classification heuristic

When `store(content, memory_type=None)` is called, the Memory faculty classifies content automatically:

- Keyword sets per type (procedural: "how to", "steps", "workflow", …; person: named-entity patterns + "person:" tag; semantic: factual/definitional patterns; identity: self-referential patterns; episodic: default).
- Confidence cap: 0.8. Below 0.2 confidence → `episodic` default.
- Caller override via the `memory_type` argument always wins.

### 5.2 Importance scoring

Default: 0.5 (base)
- +0.2 for `identity` type
- +0.15 for `person` type
- +0.1 for named entities detected
- +0.1 for relational keywords ("because", "therefore", "causes", etc.)
- +0.1 for content length > 200 characters
- −0.1 for `working` type
- Capped at [0.0, 1.0]
- Caller override via the `importance` argument always wins.

---

## 6. Decay Model

### 6.1 Retrievability formula

Axiom uses a **single-factor exponential decay** model (adapted from a proven prior implementation):

```
R(t) = e^(−t / (9 · S))
```

where:
- `t` = elapsed days since last access
- `S` = stability in days (starts at the type's S₀; grows on access)
- `R` is computed **on-the-fly at recall time** — it is not stored (it changes continuously)

At `t = 9S`, retrievability falls to `e^(−1) ≈ 0.37`. A memory is above 50% retrievable until `t ≈ 6.2S`. The factor of 9 sets the "comfortable forgetting curve."

### 6.2 Reinforcement on access

When `reinforce(ids)` is called or when recall fires a write-back:

```
S_new = S_old × (1 + growth_factor × (1 − R))
```

with `growth_factor = 2.0`.

Interpretation:
- Memory accessed when R = 0.1 (nearly forgotten): `S_new = S_old × (1 + 2.0 × 0.9) = S_old × 2.8` — nearly triples stability.
- Memory accessed when R = 0.9 (very fresh): `S_new = S_old × (1 + 2.0 × 0.1) = S_old × 1.2` — modest boost.

This correctly implements the **testing-effect** intuition: retrieving a fading memory strengthens it more than revisiting a fresh one.

### 6.3 Decay health classification

For consolidation and monitoring:

| State | Condition |
|-------|-----------|
| `healthy` | R > 0.5 |
| `fading` | 0.2 < R ≤ 0.5 |
| `forgotten` | R ≤ 0.2 — candidate for archival |

### 6.4 Spreading activation

When a memory is recalled and appears in the top-K results, its graph neighbours receive a stability boost (fire-and-forget write-back):

```
1-hop boost  = 0.3 × rel_strength
2-hop boost  = 0.3 × rel_strength × 0.5
3-hop boost  = 0.3 × rel_strength × 0.5²
```

Capped at `max_boost = 0.5`. Applied as:

```
S_neighbour_new = S_neighbour × (1 + boost)
```

This models **associative memory strengthening**: recalling a fact reinforces related facts you didn't explicitly query, mirroring how human associative memory works.

**Write-back is fire-and-forget.** The spreading activation writes do NOT block the `recall` return path. They are dispatched as `asyncio.create_task` from within the retrieval pipeline.

### 6.5 Why not FSRS

The production-proven simple model is used. True FSRS (Anki's algorithm) requires a "rating" signal (Again/Hard/Good/Easy) on each recall — it is designed for deliberate study. In agent memory, recall is automatic; no rating is available without approximation. The simple model is simpler, has no additional dependency, and is sufficient for personal-scale memory. This decision is locked.

**File:** `src/axiom/memory/decay.py` — pure functions, no I/O.

---

## 7. Multi-Strategy Retrieval Pipeline

**File:** `src/axiom/memory/retrieval.py`

`recall(query, ...)` runs a two-phase pipeline.

### 7.1 Phase 1 — Concurrent strategies

Three strategies run concurrently via `asyncio.gather`:

| Strategy | Method | Weight | Description |
|----------|--------|--------|-------------|
| Semantic | Vector cosine search | 1.0 | Embedding of query vs stored embeddings; finds paraphrases |
| Keyword | BM25 full-text search | 0.7 | Exact and near-exact keyword matches; finds what semantic misses |
| Temporal | Recency score `e^(−elapsed_days/30)` | 0.3 | Surfaces recently-accessed memories |

Candidates per strategy: `min(limit × 3, 30)`.

### 7.2 Phase 1 — RRF fusion

**Reciprocal Rank Fusion** (k = 60) merges the three candidate lists:

```
rrf_score(id) += w_strategy / (60 + rank + 1)
```

where `rank` is 0-based position in that strategy's result list. A memory appearing in all three strategies accumulates from all three terms.

### 7.3 Post-RRF decay reranking

```
final_score(id) = rrf_score(id) × R(id)^0.5
```

`decay_influence = 0.5`. The square-root dampens the penalty — a fading but highly relevant memory can still surface; it just ranks below a comparably relevant fresh one.

**Superseded penalty:** memories with state `superseded` (merged away during consolidation) carry an additional multiplier of ×0.3.

### 7.4 Phase 2 — Graph traversal

Top-5 seeds from Phase 1 trigger a batched graph-neighbour lookup:

- One call to `storage.get_neighbours_bulk(seeds, max_depth=3)` — not per-seed. Depth 3 is consistent with the 3-hop spreading-activation formula in §6.4; the `StorageSeam.get_neighbours_bulk` default is also 3 (G6).
- Neighbours scored: `w_graph / (60 + rank)` where `w_graph = 0.5`.
- New neighbours (not already in Phase 1) added to the candidate pool and ranked.

### 7.5 Contradiction tagging

Post-ranking, results carry a `contradictions` field: IDs of other active memories with cosine similarity ≥ 0.80 AND negation signals detected (flagged during consolidation as CONTRADICTS edges). The caller decides how to use this signal; Memory surfaces it.

### 7.6 Spreading activation write-back

After finalising the top-K results, the retrieval pipeline dispatches a fire-and-forget task to update stability for graph neighbours of the recalled memories (3-hop walk, per §6.4). This write does not block the `recall` return.

### 7.7 RecallResult model

```python
@dataclass
class RecallResult:
    id: str
    content: str
    memory_type: str
    importance: float
    retrievability: float          # R(t) computed on-the-fly
    score: float                   # final_score after decay rerank
    found_by: list[str]            # which strategies contributed
    tags: list[str]
    created_at: datetime
    last_accessed: datetime
    contradictions: list[str]      # IDs of contradicting memories
```

---

## 8. Relation Graph

**File:** `src/axiom/memory/models.py` (`Relationship` dataclass)

Eight typed directed relationships:

| Type | Semantics |
|------|-----------|
| `causes` | Source causes target |
| `follows` | Source temporally follows target |
| `contradicts` | Source contradicts target (created by consolidation on negation detection) |
| `supports` | Source supports / corroborates target |
| `relates_to` | General association (auto-created by store at cosine ≥ 0.75) |
| `supersedes` | Source has been merged into target; source is archived (created by consolidation merge) |
| `part_of` | Source is a component of target |
| `describes` | Source describes target |

### 8.1 Auto-linking at store time

On every `store`, after embedding, the storage layer performs a similarity scan against existing memories. Pairs with cosine ≥ 0.75 get an automatic `relates_to` edge (strength < 1.0). Manual links via `relate(...)` always use strength = 1.0 — the invariant distinguishes auto from manual.

### 8.2 Uniqueness constraint

`UNIQUE(source_id, target_id, rel_type)` — prevents duplicate edges of the same type between the same pair.

### 8.3 Relationship model

```python
@dataclass
class Relationship:
    id: str
    source_id: str
    target_id: str
    rel_type: str
    strength: float        # 0.0–1.0; auto-links always < 1.0; manual = 1.0
    created_at: datetime
```

---

## 9. Consolidation Pipeline

**File:** `src/axiom/memory/consolidation.py`

`consolidate()` is **awaited at session close only** — never mid-session, never on a timer, never per-store. Triggered by the loop's shutdown sequence.

Six stages in order:

### Stage 1 — Decay update

Recompute R for all active memories; write the `retrievability` field and update `last_computed_at`. Batch operation.

### Stage 2 — Type promotion pass

Promote memories that have earned durability through access patterns:

| Rule | Promotion |
|------|-----------|
| `working` → `episodic` | access_count ≥ 3 AND importance ≥ 0.4, OR relationships ≥ 2 |
| `episodic` → `person` | has `person:` tag AND access_count ≥ 3 |
| `episodic` → `procedural` | matches procedural patterns AND access_count ≥ 3 |
| `episodic` → `semantic` | access_count ≥ 5 AND R > 0.6 |
| `semantic` → `person` | has `person:` tag AND access_count ≥ 3 |

On promotion: stability resets to the new type's S₀ (higher stability — the promotion is a fresh start at the new tier).

### Stage 3 — Archive pass

Mark memories as archived (inactive state; not returned by `recall`):
- General types: R < 0.2
- `person` type: R < 0.05 (strict threshold — losing person knowledge is costly)
- `identity` type: NEVER archived

### Stage 4 — Cluster scan

For each active memory, query the vector index for similar memories. Collect candidate pairs with cosine ≥ 0.75 as potential merge or contradiction targets.

### Negation signal detection (used by Stages 5 and 6) — G4

Stages 5 and 6 require a "negation signals present/absent" test on candidate pairs. The mechanism is a lightweight two-step heuristic. LLM-assisted semantic contradiction detection is deferred to M8 and is out of scope here.

**Step 1 — Lexical negation-cue scan:** Check both memory contents for presence of negation marker words (case-insensitive, whole-word match):

```python
NEGATION_CUES = {
    "not", "never", "no", "wrong", "incorrect", "false", "mistake",
    "but", "however", "actually", "contradicts", "contradicted",
    "disagree", "disagrees", "retract", "retracted",
    "changed", "updated", "correction",
}
```

**Step 2 — Similarity guard:** Negation cues are only evaluated on pairs that already satisfy the cosine threshold for the relevant stage (≥ 0.90 for Stage 5; ≥ 0.80 for Stage 6). Negation cues on unrelated content are ignored — low-cosine pairs never reach negation detection.

**Stage 5 rule:** Pair proceeds to merge if cosine ≥ 0.90 **AND** neither memory contains negation cues. If either contains a cue, skip merge and let Stage 6 evaluate.

**Stage 6 rule:** Pair is contradiction-flagged if cosine ≥ 0.80 **AND** at least one memory contains negation cues → create CONTRADICTS edge.

Known limitations (accepted for M3): false positives (e.g. "not only X but also Y" is not a real contradiction) and semantic contradictions that use no negation words will both occur. Both are tolerated — the `contradictions` field is a hint to the caller, not a hard block. Precision improves in M8.

### Stage 5 — Merge pass

For each candidate pair from Stage 4:
- cosine ≥ 0.90 AND no negation signals → merge.
- Primary: the memory with higher `importance × access_count`.
- Secondary: archived, state set to `superseded`; a SUPERSEDES relationship created from secondary → primary.
- Superseded memories receive a ×0.3 score penalty in future recall.

### Stage 6 — Contradiction flag

For each candidate pair from Stage 4:
- cosine ≥ 0.80 AND negation signals detected → create a CONTRADICTS relationship between the pair.
- Neither memory is archived; both surface in recall with `contradictions` populated.

### 9.1 Consolidation log

Every action (promote, archive, merge, contradict) is appended to a `consolidation_log` with source_ids, target_id, action, and reason. Returned by `consolidate()`. Used for debugging and audit; the loop discards the return value.

### 9.2 Known scaling concern

Stage 4 (cluster scan) is O(N) vector queries = O(N²) comparisons. This is acceptable for personal-scale memory (hundreds to low thousands of memories). At tens of thousands of memories, a smarter ANN pre-clustering strategy would be needed. This is noted as a future concern — not required for M3.

**Debounce config knob (W2 — defined now, unused in M3):** `MemoryConfig` carries a `consolidation_debounce_sessions: int = 0` field. When > 0, `consolidate()` skips the run if it was called fewer than N sessions ago (tracked by a session counter in the `config` storage table). In M3 this is always 0 — every session-end triggers a full consolidation pass. Defining the knob now preserves a zero-interface-change escape hatch for future scaling without altering `consolidate()`'s signature.

---

## 10. Storage — Embedded SurrealKV

**File:** `src/axiom/memory/storage.py` (the seam) + `src/axiom/memory/schema.py` (schema init)

### 10.1 Decision, provenance, and fallback — G7

Axiom's Memory faculty uses **embedded SurrealKV** (in-process, single-file) as its **primary** storage backend.

SurrealKV provides natively:
- **Vector search** — no separate vector extension needed
- **Graph traversal** — native graph model (no recursive CTE hand-rolling)
- **Full-text search** — native FTS (no FTS5 virtual table)

This eliminates the three highest-complexity concerns of the previous SQLite plan:
- No sqlite-vec Windows installation spike
- No recursive CTE graph traversal
- No FTS5 virtual table maintenance

**Mode decision:** Embedded in-process, single file. NOT the external server mode. The external mode requires a separate SurrealDB process — exactly what the architecture rejects.

**Provenance — lifted from a proven prior embedded implementation:** The embedded SurrealDB storage layer is lifted and adapted from a prior production-deployed memory system (shipped at v1.0.0 in production). The connection pattern used by that implementation:

```python
db = Surreal("surrealkv://<absolute_path_to_file>")
await db.connect()
await db.use("axiom", "memory")
```

This uses the Python `surrealdb` SDK's embedded mode (`surrealkv://` URI scheme). The database runs **in-process** — no background thread, no TCP port, no spawned external process. The file is created if absent. The same `db` instance is held open for the adapter's lifetime. This mode has been verified in the prior implementation to support vector search, native graph traversal, and full-text search from Python without any external server.

**Known caveat — LET pattern in embedded mode:** The embedded SurrealDB Python SDK returns `None` for multi-statement queries that use the `LET` variable-binding syntax (e.g. `LET $x = (SELECT ...); RETURN $x;`). This is a known limitation of the embedded Python binding. The workaround (inherited from the lifted implementation and mandatory here): **avoid `LET`-based multi-statement patterns in all SurrealQL queries**. Use single-statement queries or explicit sequential `await db.query(...)` calls instead. Every method in `StorageSeam` must honor this constraint.

**Documented fallback:** The thin `StorageSeam` abstraction (§10.2) makes the backend swappable without changing any other component. If the embedded SurrealKV Python client fails on the target platform (architecture not supported, embedding mode regression, or other breakage), the documented fallback is **SQLite + sqlite-vec**: a single `.db` file providing vector search via sqlite-vec, BM25 via FTS5 virtual table, and graph traversal via recursive CTEs. Swapping to the fallback requires only replacing `storage.py` — no other component changes. The fallback is not the primary path; it is named here explicitly to close the "no fallback specified" gap from the dryrun.

**Seam:** `StorageSeam` in `storage.py` is the only file that imports the `surrealdb` Python client. All other components call `StorageSeam` methods only. If the backend is swapped, only `storage.py` changes.

### 10.2 Storage seam interface

```python
class StorageSeam:
    async def store_memory(self, memory: Memory) -> None: ...
    async def get_memory(self, id: str) -> Memory | None: ...
    async def update_memory(self, id: str, **fields) -> None: ...
    async def vector_search(
        self, embedding: list[float], limit: int, type_filter: str | None = None
    ) -> list[tuple[str, float]]: ...          # (id, score)
    async def fulltext_search(
        self, query: str, limit: int
    ) -> list[tuple[str, float]]: ...          # (id, bm25_score)
    async def get_by_recency(self, limit: int) -> list[tuple[str, float]]: ...
    async def store_relationship(self, rel: Relationship) -> None: ...
    async def get_neighbours_bulk(
        self, ids: list[str], max_depth: int = 3
    ) -> list[tuple[str, int, float]]: ...     # (neighbour_id, depth, rel_strength)
                                               # Default 3 — consistent with 3-hop spreading activation (§6.4)
    async def get_all_active(self) -> list[Memory]: ...
    async def bulk_update_stability(
        self, updates: list[tuple[str, float, float]]  # (id, new_S, new_accessed_at)
    ) -> None: ...
    async def archive_memory(self, id: str) -> None: ...
    async def log_consolidation_action(self, action: dict) -> None: ...
    async def get_contradictions(
        self, ids: list[str]
    ) -> dict[str, list[str]]: ...             # {id: [contradicting_ids]}
```

### 10.3 Schema

**File:** `src/axiom/memory/schema.py`

Tables/collections initialised at `StorageSeam.__init__()`:

- `memory` — id (UUID4), content, memory_type, state (active/archived/superseded), importance, stability, retrievability (consolidation-time snapshot — see W4 note below), access_count, created_at, updated_at, last_accessed, source, conversation_id, tags (list), embedding (384-dim float32 vector).

  > **W4 — Retrievability field semantics:** The stored `retrievability` value is a **consolidation-time snapshot**, written by Stage 1 of `consolidate()`. It is NOT the authoritative current R. The authoritative R is always computed on-the-fly at recall time: `R = e^(−elapsed_days / (9 × stability))` where `elapsed_days` is derived from `last_accessed` at the moment of the query. Code that reads the stored `retrievability` and treats it as the current value is a bug. The field exists for consolidation bookkeeping (archive-threshold comparisons at Stage 3) and the `stats()` surface only.
- `memory_version` — id, memory_id, content, metadata, created_at. (Content history.)
- `relationship` — id, source_id, target_id, rel_type, strength, created_at. UNIQUE on (source_id, target_id, rel_type).
- `consolidation_log` — id, action, source_ids (list), target_id, reason, created_at.
- `config` — key (PK), value, updated_at.

Vector index on `memory.embedding` (cosine similarity).
Full-text index on `memory.content`.

### 10.4 Data file location

Default: `~/.axiom/memory/memory.surrealkv`
Configurable via `MemoryConfig.storage_path`.

---

## 11. Embedding Service

**File:** `src/axiom/memory/embeddings.py`

```python
class EmbeddingService:
    MODEL_NAME = "all-MiniLM-L6-v2"
    DIMENSIONS = 384

    def warmup(self) -> None:
        """Load the model eagerly. Called at adapter init. ~10s on first call."""

    async def embed(self, text: str) -> list[float]:
        """Encode text to a 384-dim L2-normalised float32 vector.
        Offloads to executor to avoid blocking the asyncio event loop."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch encode; more efficient than repeated embed() calls."""
```

The model is `all-MiniLM-L6-v2` via `sentence-transformers`. 384 dimensions, L2-normalised (cosine search via dot product). The `warmup()` call at adapter init moves the ~10-second model load out of the first user interaction.

The `EmbeddingService` is behind an abstraction. Swapping to a different model requires only changing `MODEL_NAME` and `DIMENSIONS` — no other component changes.

**CPU inference:** `sentence-transformers` encodes on CPU by default. Inference runs in a `ThreadPoolExecutor` via `asyncio.get_event_loop().run_in_executor(None, ...)` to avoid blocking the asyncio event loop.

---

## 12. Adapter Layout

**Directory:** `src/axiom/memory/`

```
src/axiom/memory/
├── __init__.py             # Re-exports MemoryPort, CognitiveMemoryAdapter
├── port.py                 # MemoryPort Protocol; AssembledContext; ConversationUnit
│                           # The ONLY memory import that loop.py touches.
├── adapter.py              # CognitiveMemoryAdapter — implements MemoryPort.
│                           # Wires all sub-components at __init__.
│                           # Composition root for the memory faculty.
├── working_context.py      # WorkingContext: in-memory VectorRingBuffer.
│                           # Unit = ConversationUnit. Recency floor + relevance.
├── decay.py                # Pure functions: compute_R(), reinforce_stability(),
│                           # compute_spreading_boost(), classify_decay_state().
│                           # No I/O; no asyncio.
├── models.py               # Pydantic/dataclass models: Memory, RecallResult,
│                           # Relationship, ConversationUnit.
├── classification.py       # classify_type(content) → (MemoryType, confidence).
│                           # score_importance(content, type, entities) → float.
│                           # Pure functions; no I/O.
├── retrieval.py            # RetrievalPipeline: recall() full two-phase pipeline.
│                           # Phase 1: asyncio.gather(semantic, keyword, temporal).
│                           # RRF fusion → decay rerank → Phase 2 graph expansion.
│                           # Spreading-activation write-back as create_task.
├── consolidation.py        # ConsolidationPipeline: consolidate() 6-stage pipeline.
│                           # Returns list[dict] action log.
├── embeddings.py           # EmbeddingService: warmup(), embed(), embed_batch().
│                           # Wraps sentence-transformers all-MiniLM-L6-v2.
├── storage.py              # StorageSeam: thin abstraction over embedded SurrealKV.
│                           # Only file that imports the SurrealKV Python client.
└── schema.py               # Schema initialisation: create tables/collections/indexes.
│                           # Called once at StorageSeam.__init__().
└── config.py               # MemoryConfig dataclass: storage_path, n_units,
                            # token_budget, n_recency_floor, k_cognitive, k_relevance,
                            # growth_factor, decay_influence, auto_link_threshold,
                            # consolidation_debounce_sessions.
```

### MemoryConfig defaults (W6)

```python
@dataclass
class MemoryConfig:
    storage_path: str = "~/.axiom/memory/memory.surrealkv"
    n_units: int = 50                        # Max units in working-context ring buffer
    token_budget: int = 4000                 # Token budget cap for assembled working context
    n_recency_floor: int = 5                 # Last N units always included verbatim
    k_cognitive: int = 10                    # Top-K cognitive memories in assemble_context
    k_relevance: int = 5                     # Top-K older units by relevance (beyond recency floor)
    growth_factor: float = 2.0              # Stability growth factor for reinforce_stability
    decay_influence: float = 0.5            # Exponent for decay reranking (final_score = rrf × R^0.5)
    auto_link_threshold: float = 0.75       # Cosine threshold for auto relates_to edges at store time
    consolidation_debounce_sessions: int = 0 # 0 = always consolidate; >0 = debounce (future use, §9.2)
```

**Import boundary rule:** `loop.py` imports ONLY `axiom.memory.port` (the `MemoryPort` Protocol and data models). It never imports `adapter.py`, `storage.py`, `embeddings.py`, or any other memory submodule. The `CognitiveMemoryAdapter` is wired in the composition root (`agent.py`) and injected into the loop as a `MemoryPort`-typed reference.

---

## 13. Loop Wiring — Which Phase Calls Which Port Method

| PRAO Phase | Memory call | Await? | Notes |
|------------|-------------|--------|-------|
| **Perceive** | `assemble_context(query, ...)` | Awaited | Returns `AssembledContext`; loop renders into chat-API slots |
| **Perceive** (targeted) | `recall(query, ...)` | Awaited | Optional; only when targeted recall is needed beyond assemble_context |
| **Observe** | `append_unit(unit)` | Awaited | Loop constructs a `ConversationUnit` from the completed turn and awaits `append_unit`; ring buffer updated with embedding computed at call time |
| **Observe** | `store(content, ...)` | Fire-and-forget via `create_task` | One call per cognitive knowledge item to persist (facts, decisions); does NOT write to working buffer; loop does not wait |
| **Observe** | `reinforce(ids)` | Fire-and-forget via `create_task` | IDs of memories that actually influenced the cycle's reasoning |
| **Session shutdown** | `consolidate()` | Awaited | Called by loop teardown; loop is already exiting |

**Observe — two separate write paths (G3):**
1. `await memory.append_unit(unit)` — loop constructs a `ConversationUnit(user_text, agent_text, turn_index, timestamp)` from the completed exchange and awaits `append_unit`. This is the working-context write path (in-memory, fast, embedding computed at call time).
2. `asyncio.create_task(memory.store(content, ...))` — for each cognitive knowledge item worth retaining across sessions (facts, decisions, notable context), the loop fires a fire-and-forget store to the cognitive tier. Explicit cognitive stores in M3 are loop-driven; LLM-assisted extraction is M8.

**These are always separate calls.** `store` does NOT write to the working buffer. `append_unit` does NOT write to the cognitive store.

**Observe — reinforce signal:** The loop tracks which `RecallResult` IDs from the Perceive-phase context were materially used in the Reason phase (e.g. the agent referenced them). These IDs are passed to `reinforce(ids)` at Observe. The mechanism for tracking "used" IDs is a loop implementation detail — at minimum, the IDs assembled into the context are considered used.

---

## 14. Adapter Initialisation Sequence

`CognitiveMemoryAdapter.__init__(config: MemoryConfig)`:

1. Construct `StorageSeam(config.storage_path)` — opens the SurrealKV file (creates if absent), runs schema initialisation.
2. Construct `EmbeddingService()` — does NOT load model yet.
3. Call `EmbeddingService.warmup()` — loads `all-MiniLM-L6-v2` eagerly. ~10s on first ever run; ~1s if already cached by sentence-transformers.
4. Construct `WorkingContext(config)`.
5. Construct `RetrievalPipeline(storage, embeddings, config)`.
6. Construct `ConsolidationPipeline(storage, embeddings, config)`.
7. All port methods are now callable.

The composition root (`agent.py`) constructs `CognitiveMemoryAdapter` before starting `PraoLoop`.

---

## 15. Resolved Design Questions

These were open forks in the research document, resolved in the K+V design pass. Encoded here as decisions, not questions.

| # | Question | Decision |
|---|----------|----------|
| Q1 | Consolidation trigger | Session end only. `await memory.consolidate()` called in the loop's shutdown sequence. Accepted: modest shutdown linger. |
| Q2 | Who assembles two-tier context? | Memory owns composition. `assemble_context` pulls both tiers; the loop renders the result. No tier-assembly logic in the loop. |
| Q3 | Should `store` be fire-and-forget? | Yes, fully fire-and-forget at the port contract level. ID minted synchronously (UUID4 in-process); embed+insert runs as `asyncio.create_task`. Accepted: a `store` then immediate `recall` of the same item may miss it until the async insert lands (fine — store@Observe, recall@Perceive next cycle). |
| Q4 | Seed / migrate from existing store? | FRESH START. No seed, no migration. This product instance (Second Brain) is not a carry-forward of any prior system — it learns its user from sessions. Migration tooling is explicitly out of M3 scope. |
| Q5 | Identity memories and persona initialisation? | M3 supports the `identity` memory type mechanically. Persona genesis (populating identity memories at first boot from a template or onboarding Q&A) is a **separate future milestone**. `persona.md` remains the loop's persona source during M3; identity memories accumulate from experience. |
| Q6 | Pre-seed person/user context? | No pre-seeding. The agent learns the user from sessions, not from a bootstrap import. |

---

## 16. Non-Goals (M3 scope fence)

| Non-Goal | Notes |
|----------|-------|
| Persona genesis | Separate milestone. `identity` type is supported mechanically; initial population is not. |
| Seed / migration | No import from any prior store. Fresh start. |
| LLM-assisted extraction | M8 (CAPTURE call-point). M3 stores what the loop explicitly tells it. |
| Reflection / higher-order insights | M8. No LLM pass over own memories. |
| Multi-agent memory sharing | M7 (Orchestrator). |
| Web dashboard / admin UI | Management CLI only; no browser UI. |
| External SurrealDB server | `surrealkv-file` (embedded) only. No `rocksdb-server`. No external process. |
| Background consolidation timer | Session-end only. No async background task. |
| py-fsrs / FSRS | Dropped. Simple proven single-factor model is used. |
| Working buffer cross-session persistence | Buffer is ephemeral. Future decision. |
| sqlite-vec / SQLite FTS5 / recursive CTEs as primary | SurrealKV provides these natively. SQLite+sqlite-vec remains the named fallback behind the seam (§10.1) — it is not the primary path. |

---

## 17. Architecture Invariants (hard — may not be relaxed without updating requirement.md and this document)

1. **Non-blocking store.** `store`, `reinforce`, `relate`, `update` never block the loop. Fire-and-forget by construction.
2. **Recall is awaited, fast.** `recall` and `assemble_context` are awaited; <100 ms target.
3. **Memory owns two-tier composition.** The loop calls `assemble_context`; it does NOT independently assemble tiers.
4. **Memory is confined to the Memory faculty.** The loop imports only `MemoryPort` (from `port.py`). No direct storage, embedding, or retrieval imports in the loop.
5. **Embedded storage only.** No external database process. SurrealKV in `surrealkv-file` mode.
6. **Fresh start.** No seed, no migration from any prior store.
7. **Consolidation at session end only.** Never mid-session, never on a timer.
8. **Spreading activation is fire-and-forget.** Graph neighbour write-backs never block `recall`.
9. **Embedding warm-up at init.** `EmbeddingService.warmup()` called at adapter construction; first recall does not incur model-load latency.
10. **ID minted synchronously.** `store` returns the UUID4 id before the embed+insert completes.
11. **Two write paths.** `store` is cognitive-store-only. The working-context ring buffer is fed exclusively via `append_unit`. There is no `memory_type` routing in `store`.

---

## 18. Dryrun-1 Warning Dispositions

**W2 (O(N²) consolidation + debounce) — addressed:** The `consolidation_debounce_sessions` config knob is defined in `MemoryConfig` (§12, default 0 — always consolidate). Unused in M3, available for future scaling.

**W4 (retrievability dual semantics) — addressed:** Clarified in §10.3. The stored `retrievability` field is a consolidation-time snapshot only. Authoritative R is always computed on-the-fly at recall time. Reading the stored field as current is a bug.

**W6 (config defaults missing) — addressed:** All `MemoryConfig` field defaults specified in §12.

**W1 (SurrealKV reverses research recommendation — no rationale trail) — accepted:** §10.1 now documents provenance (lifted from a proven prior embedded implementation, shipped at v1.0.0), the verified capability set, and the fallback path. The K+V design-pass decision itself is treated as locked; the audit trail is encoded in §10.1.

**W3 (concurrent fire-and-forget stores may miss each other for auto-linking) — accepted:** Two cognitive memories stored in the same Observe cycle may not be auto-linked until the next consolidation cluster scan. Documented behaviour, not a bug. The `store@Observe → recall@next-Perceive` cycle gap already means same-cycle cross-linking is a degenerate case.

**W5 (MemoryAdmin interface placement) — deferred:** Admin operations (`list`, `archive`, `restore`, `delete`, `who`, `self_query`) are noted as NOT part of `MemoryPort` in §3.3. Their home (`admin.py`, CLI module, or separate Protocol) is a task-time decision. No task covers this in M3 — the admin surface is M8-era scope per §16.

**W7 (assemble_context <100ms may be tight with SurrealKV + embedding) — accepted risk:** The <100ms target is wall-clock and excludes model load (pre-warmed). The three contributors are: query embedding (~50ms CPU, executor), in-memory working-buffer cosine (< 1ms), SurrealKV vector+BM25+temporal+graph queries. The target may need re-evaluation once the storage layer is benchmarked. It is a soft goal at M3; hard breach is a M4-era tuning concern.
