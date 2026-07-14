# M3 · Memory — Design Dry-Run Review #1

**Spec:** `005-m3-memory`
**Reviewed:** `design.md` (DRAFT, 2026-07-14)
**Reviewer:** Velasari (manual dry-run — `/e-spec:dryrun-design` not available)
**Date:** 2026-07-14
**Method:** Simulated fresh-engineer implementation. Read design.md cover-to-cover, cross-referenced against requirement.md, task.md, research `006-m3-memory-architecture-2026-07-14.md` §10, `001-agent-core/architecture.md`, and sibling `004-m2-observability/design.md` for bar/style.

---

## Gaps

Numbered. Each gap is something under-specified that would block or fork implementation — an implementer would have to invent or guess.

---

### G1 — ConversationUnit model: fields undefined

**Where:** §4.2, §3.1 (`AssembledContext`), §12 layout (listed in `models.py`), task 1.1.
**What:** `ConversationUnit` is referenced throughout — the working buffer stores them, `assemble_working_context` returns them, `AssembledContext.working_context` is `list[ConversationUnit]`. But the design never defines its fields. The §4.2 pseudocode uses `unit.embedding` (so it has an embedding). §10.3 "Unit definition" says it's a user message + agent response pair. But the dataclass fields are never listed:

- `user_message: str`? `agent_response: str`?
- `embedding: list[float]`? Who sets it?
- `token_count: int`? (needed for the token cap in `_apply_token_cap`)
- `created_at: datetime`?
- `conversation_id: str`?

Without this, two implementers will produce incompatible models.

**Severity:** Blocks task 1.1, 7.1, 10.2.

---

### G2 — Working buffer embedding: who computes it, and when?

**Where:** §4.2 pseudocode (`assemble_working_context` uses `cosine(unit.embedding, query_embedding)`), §4.2 "Writing to the working buffer," §14 init sequence.
**What:** The `store(content, memory_type="working")` path is fire-and-forget (§3.2 invariant, §15 invariant 1). Embedding is done asynchronously inside the `asyncio.create_task` that runs after ID mint. But the working buffer's relevance query needs `unit.embedding` to exist *immediately* (it's used at the next Perceive). Two forks:

1. **Working path embeds synchronously** (blocking) before adding to the buffer — contradicts the fire-and-forget invariant.
2. **Working path has a separate embedding step** — the adapter embeds the unit eagerly for the buffer, then fires the cognitive store insert as fire-and-forget. This is plausible but not stated.
3. **Units enter the buffer without embeddings** and only get relevance-queried after the async embed completes — creates a race where recent units have no embedding.

The design must specify which path is taken. Option 2 is the likely intent (the working buffer is in-memory, embedding is fast at <100ms, and the buffer is a runtime tier distinct from the cognitive store), but it's not written.

**Severity:** Blocks tasks 7.1, 10.4. An implementer choosing option 1 violates invariant 1; choosing option 3 produces broken relevance; choosing option 2 is correct but undocumented.

---

### G3 — `store(content: str)` → ConversationUnit mapping

**Where:** §3 MemoryPort (`store(content: str, ...)`), §4.2 "Writing to the working buffer," §13 loop wiring.
**What:** `store` takes a single `content: str` parameter. But a ConversationUnit is a *pair* — user message + agent response (§4.2 unit definition: "one user message paired with the agent's response"). How does the loop pass a two-field structure through a single string?

Options:
- (a) `content` is a serialized/concatenated string ("User: ... \n Agent: ..."), and the working buffer parses it back into two fields.
- (b) `store` has additional parameters not shown in the port contract (e.g. `user_message` + `agent_response`).
- (c) The loop constructs the ConversationUnit itself and passes it via some side-channel, with `store` only handling the cognitive-store string.

None of these are stated. The port contract (§3) and the unit definition (§4.2) are in tension — the contract's `content: str` cannot carry the structured unit without a convention.

**Severity:** Blocks tasks 10.4, 11.3. The port contract or the working-buffer entry path must be revised.

---

### G4 — Negation signal detection: mechanism undefined

**Where:** §9 Stage 5 ("no negation signals"), Stage 6 ("negation signals detected"), §7.5 ("negation signals detected (flagged during consolidation as CONTRADICTS edges)").
**What:** Consolidation's merge pass (Stage 5) proceeds when similar pairs have *no* negation signals; the contradiction pass (Stage 6) fires when negation signals *are* detected. But the design never defines how negation signals are detected:

- Keyword-based? ("not", "however", "but", "incorrect", "wrong")
- Embedding-based? (e.g. cosine of negation-augmented query)
- Content diff? (same entity, contradictory predicate)
- LLM-assisted? (explicitly out of M3 scope per §16)

Without this, an implementer has no basis for implementing Stage 5/6 of consolidation. A keyword heuristic is the most likely M3-appropriate approach (consistent with the classification heuristic in §5.1), but no keywords or algorithm are specified.

**Severity:** Blocks tasks 9.5, 9.6.

---

### G5 — Token counting mechanism unspecified

**Where:** §4.2 (`TOKEN_BUDGET`, `_apply_token_cap`), config.py (`token_budget`).
**What:** The working buffer has a hard token budget cap. `_apply_token_cap(assembled, TOKEN_BUDGET)` truncates from the relevance slice first. But how are tokens counted?

- Which tokenizer? `tiktoken` (OpenAI)? Model-specific? `sentencepiece`?
- Character approximation (chars / 4)?
- A tokenizer dependency must be declared.
- Different models have different tokenizers — Axiom targets small/local models where tokenizers vary.

The observability design (M2) didn't need this; M3 does. The token-counting approach must be specified or explicitly delegated to a named abstraction.

**Severity:** Blocks task 7.1. An implementer will pick an arbitrary method; different choices yield different buffer behavior.

---

### G6 — `get_neighbours_bulk` max_depth default (2) vs spreading activation depth (3)

**Where:** §10.2 `get_neighbours_bulk(ids, max_depth=2)` (default 2), §6.4 spreading activation ("3-hop boost = 0.3 × rel_strength × 0.5²").
**What:** The spreading activation spec (§6.4) defines boosts for 1-hop, 2-hop, and 3-hop neighbours. But `get_neighbours_bulk` defaults to `max_depth=2`, which only returns 1-hop and 2-hop neighbours. The 3-hop boost formula has no data to act on unless the caller overrides to `max_depth=3`.

Similarly, §7.4 Phase 2 graph traversal doesn't specify the depth for `get_neighbours_bulk` — just says "one call." Is Phase 2 depth=2 (the default)? Is spreading activation depth=3 (requiring override)?

The inconsistency means either: (a) the default should be 3, or (b) spreading activation is only 2-hop (contradicting §6.4's 3-hop formula), or (c) the retrieval pipeline calls with explicit `max_depth=3`.

**Severity:** Partial block on tasks 8.4, 8.6 — implementer must guess the correct depth.

---

### G7 — SurrealKV embedded mode: no spike documented

**Where:** §10.1, research §5.3/§6 (spikes), research §9 (summary table).
**What:** The research document recommended **SQLite + sqlite-vec** (§5.3, §9 summary) and identified four spikes — including Spike 1 (sqlite-vec) as "HIGHEST RISK." The design switched to SurrealKV without:

1. Documenting a spike result for the SurrealKV Python client in embedded mode.
2. Confirming the `surrealdb` Python package supports `surrealkv-file` as truly in-process (no spawned server process) on Windows.
3. Confirming vector search, full-text search, and graph traversal work via the Python client in embedded mode.

The research §2.6 notes CM uses SurrealKV, but also warns: "the move introduced an external process dependency and significant complexity." The design asserts embedded mode avoids this, but the assertion is unverified.

If the Python `surrealdb` client's `surrealkv-file` mode spawns a background process, or doesn't support vector/FTS/graph natively from Python, the entire storage layer (§10) is blocked. This is the highest-risk technical assumption in the design.

**Why it's a gap, not just a warning:** The requirement says "zero external services" (AC-10.1). If the SurrealKV Python client doesn't deliver embedded mode, there is no fallback specified in the design. The research had a fallback (chromadb, numpy scan) for the SQLite path — the SurrealKV path has none.

**Severity:** Potentially blocks ALL of §10 (tasks 6.1–6.3) and transitively everything that touches storage.

---

## Warnings

Risks, ambiguities, or untestable patterns that don't block implementation but deserve attention.

---

### W1 — SurrealKV reverses research recommendation without rationale trail

**Where:** §10.1 vs research §5.3, §9.
**Detail:** The research concluded "SQLite + WAL, single file, in-process" with "High" confidence. The design adopted SurrealKV. The K+V design pass presumably made this decision, but the *rationale* is only implicit (§10.1 lists what SurrealKV provides natively). A one-liner like "K+V design pass decision: SurrealKV chosen over SQLite+sqlite-vec because [reason]" would close the audit trail. Without it, a future reader (or this reviewer) cannot distinguish a deliberate decision from a drift.

---

### W2 — O(N²) consolidation fires every session end

**Where:** §9.2, §15 invariant 7.
**Detail:** Acknowledged in §9.2 as a "known scaling concern." But it fires every session end (invariant 7). For a frequently-used agent with 5K+ memories, Stage 4 alone could take seconds to minutes. The design notes "future concern" but doesn't specify an escape hatch (e.g. "skip if last consolidation was < N minutes ago"). Requirement AC-09.5 mentions the debounce option but says it's "not required in M3." Consider at least defining the config knob even if unused.

---

### W3 — Concurrent fire-and-forget stores may miss each other for auto-linking

**Where:** §8.1 auto-linking, §3.2 fire-and-forget invariant.
**Detail:** If Observe fires multiple `store` calls in the same cycle (one working unit + additional cognitive facts), the async embed+insert tasks run concurrently. Store A's auto-linking scan may not see Store B (not yet inserted), and vice versa. The result: two semantically similar memories stored in the same cycle may not get auto-linked until the next consolidation's cluster scan. This is likely acceptable but undocumented.

---

### W4 — `Memory` model field `retrievability` dual semantics

**Where:** §6.1 ("R is computed on-the-fly at recall time — it is not stored"), §10.3 schema (`retrievability` field), §9 Stage 1 ("write the retrievability field").
**Detail:** The `memory` table schema includes a `retrievability` field, and consolidation Stage 1 writes to it. But §6.1 says R is "not stored." These are reconcilable (the stored value is a consolidation-time snapshot; the authoritative R is always recomputed), but the design should state this explicitly to prevent an implementer from reading the stored value instead of recomputing.

---

### W5 — `MemoryAdmin` interface placement unspecified

**Where:** §3.3.
**Detail:** The admin surface (`list`, `archive`, `restore`, `delete`, `who`, `self_query`) is described as "NOT part of MemoryPort" and living on "a separate MemoryAdmin interface (or a CLI entrypoint)." But no file is specified for this interface in the module layout (§12), no model is defined, and no task covers it. If M3 includes admin operations (requirement §Non-Goals doesn't exclude them — only "web dashboard"), the design needs a `MemoryAdmin` Protocol or explicit deferral.

---

### W6 — `config.py` defaults not specified

**Where:** §12 layout, task 1.2.
**Detail:** `MemoryConfig` is listed with field names (`storage_path`, `n_units`, `token_budget`, `n_recency_floor`, `k_cognitive`, `k_relevance`, `growth_factor`, `decay_influence`, `auto_link_threshold`) but no default values are specified in the design. Some are inferrable from the text (e.g. `n_units ≈ 50`, `growth_factor = 2.0`, `decay_influence = 0.5`, `auto_link_threshold = 0.75`), but `n_recency_floor`, `k_cognitive`, `k_relevance`, and `token_budget` have no stated defaults. An implementer must hunt through prose to reconstruct them, and may miss or misinterpret.

---

### W7 — `assemble_context` latency target (<100ms) may be tight with SurrealKV + embedding

**Where:** §3.2 ("<100 ms target"), §11 (embedding offloaded to executor).
**Detail:** `assemble_context` must: (1) embed the query (~50-100ms CPU), (2) query the working buffer's cosine similarity (in-memory, fast), (3) call `recall` against the cognitive store (SurrealKV vector search + BM25 + temporal + RRF + graph expansion). Step 1 alone may consume the budget. The 100ms target was inherited from the research but may need to be re-evaluated with the SurrealKV backend. Consider: is the target wall-clock or excludes embedding?

---

## Coverage Check

### Design ↔ Requirement

| User Story | Covered in Design | Notes |
|-----------|-------------------|-------|
| US-01 (context assembly) | §3, §4.4, §13 | ✅ Full |
| US-02 (working context) | §4.2 | ✅ Except ConversationUnit model (G1, G3) |
| US-03 (cognitive tier) | §4.3, §7, §10 | ✅ Full |
| US-04 (decay) | §6 | ✅ Full |
| US-05 (type taxonomy) | §5 | ✅ Full |
| US-06 (relation graph) | §8 | ✅ Full |
| US-07 (multi-strategy retrieval) | §7 | ✅ Full |
| US-08 (fire-and-forget store) | §3.2, §15 | ✅ Full |
| US-09 (consolidation) | §9 | ⚠️ Negation detection undefined (G4) |
| US-10 (embedded storage) | §10, §11 | ⚠️ No spike for SurrealKV (G7) |

### Design ↔ Task

| Task Group | Actionable from Design? | Notes |
|-----------|------------------------|-------|
| 1. Models/config | ⚠️ ConversationUnit fields missing (G1); config defaults missing (W6) | |
| 2. Port contract | ✅ Fully specified in §3 | |
| 3. Decay | ✅ Fully specified in §6 | |
| 4. Classification | ✅ Fully specified in §5 | |
| 5. Embedding | ✅ Fully specified in §11 | |
| 6. Storage seam | ⚠️ SurrealKV client unverified (G7); depth inconsistency (G6) | |
| 7. Working context | ⚠️ Embedding timing (G2); token counting (G5); content→unit mapping (G3) | |
| 8. Retrieval | ✅ Fully specified in §7 (modulo G6 depth) | |
| 9. Consolidation | ⚠️ Negation detection mechanism missing (G4) | |
| 10. Adapter | ⚠️ Depends on G2, G3 resolution | |
| 11. Loop wiring | ⚠️ Depends on G3 resolution (how loop passes ConversationUnit via store) | |
| 12–14. Tests | ✅ Testable once gaps resolved | |

### Locked Decisions Honored

| Decision | Honored? |
|----------|----------|
| Fresh start (no seed/migration) | ✅ §15 Q4, §16 |
| Persona genesis fenced out | ✅ §5 note, §15 Q5, §16 |
| No py-fsrs | ✅ §6.5 |
| No SQLite/sqlite-vec | ✅ §10.1, §16 |
| No blocking spikes required | ⚠️ SurrealKV choice has no documented spike (G7) |

---

## Verdict

**NEEDS FIXES — 7 gaps must be resolved before implementation.**

The design is architecturally strong — the two-tier model, the port contract, the fire-and-forget invariants, the decay/retrieval/consolidation pipelines are well-specified and internally consistent. The house-style matches the M2 observability design in depth and precision.

However, seven gaps would cause an implementer to guess or fork:

| Priority | Gaps | Fix effort |
|----------|------|-----------|
| **Critical** | G7 (SurrealKV spike) | Verify the Python `surrealdb` client's `surrealkv-file` mode works in-process on Windows with vector/FTS/graph. Document the result. If it doesn't, fall back to SQLite+sqlite-vec per the research recommendation. |
| **High** | G1 (ConversationUnit model), G2 (embedding timing), G3 (content→unit mapping) | These three are related — define the ConversationUnit dataclass fields, specify that the working-buffer path embeds eagerly (not fire-and-forget), and decide whether `store` takes a structured unit or a string. ~1 paragraph addition to §4.2 + field spec in §3.1 or a new §4.2.1. |
| **Medium** | G4 (negation detection), G5 (token counting) | Each needs a ~3-line spec: negation = keyword heuristic (list the keywords); token counting = character/4 approximation or a named tokenizer. |
| **Low** | G6 (depth inconsistency) | One-line fix: either change the default to 3 or note that retrieval/spreading-activation callers pass `max_depth=3` explicitly. |

Once these seven gaps are addressed, the design reaches GO.
