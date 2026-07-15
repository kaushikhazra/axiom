# M3 · Memory — Design Dry-Run Review #2

**Spec:** `005-m3-memory`
**Reviewed:** `design.md` (DRAFT, 2026-07-14 — post-round-1 fixes)
**Reviewer:** Velasari (manual dry-run — `/e-spec:dryrun-design` not available)
**Date:** 2026-07-14
**Method:** Verification of G1–G7 closures from round 1, plus fresh adversarial pass focusing on the newly-added `append_unit` port method, the two-write-paths split, and cross-document consistency (design ↔ requirement ↔ task).

---

## Part A — Round-1 Gap Verification

---

### G1 — ConversationUnit model: fields undefined

**Verdict: RESOLVED**

**Evidence:** Design §4.2 "ConversationUnit model" now provides the full dataclass:

```
user_text: str, agent_text: str, turn_index: int, timestamp: datetime,
embedding: list[float], token_count: int
```

All fields have documented semantics. `embedding` is explicitly marked "set by `append_unit`, NOT at construction." `token_count` is defined as `len(user_text + agent_text) // 4`, set by `append_unit`. Task 1.1 mirrors these fields verbatim. No ambiguity remains.

---

### G2 — Working buffer embedding: who computes it, and when?

**Verdict: RESOLVED**

**Evidence:** Design §4.2 "Two write paths" specifies the answer unambiguously: `append_unit` (awaited) calls `EmbeddingService.embed(unit.user_text + " " + unit.agent_text)`, sets `unit.embedding`, then appends to the ring buffer. This is "Option 2" from the round-1 analysis — eagerly embed at write time, not fire-and-forget. §3.2 invariant table lists `append_unit` as "AWAITED (fast)" with the note "embedding computed at call time; must complete before next cycle's Perceive." Task 10.4b mirrors the three-step sequence. No race condition possible.

---

### G3 — `store(content: str)` → ConversationUnit mapping (conflation)

**Verdict: RESOLVED**

**Evidence:** The conflation is eliminated. The design now defines two independent write paths:

1. `store(content: str, ...)` — cognitive store only. Fire-and-forget. Takes a string. Does NOT touch the working-context ring buffer (§3 port docstring, §4.2, §17 invariant 11).
2. `append_unit(unit: ConversationUnit)` — working-context only. Awaited. Takes a structured `ConversationUnit`. Does NOT touch the cognitive store (§3, §4.2, §13).

§13 loop-wiring table shows both at Observe as separate calls. §17 invariant 11 codifies: "store is cognitive-store-only. The working-context ring buffer is fed exclusively via `append_unit`. There is no `memory_type` routing in `store`." The round-1 tension between `store`'s `content: str` parameter and the structured `ConversationUnit` is fully resolved — they are now separate concerns on separate methods.

---

### G4 — Negation signal detection: mechanism undefined

**Verdict: RESOLVED**

**Evidence:** Design §9 now contains a dedicated subsection "Negation signal detection (used by Stages 5 and 6) — G4" with:

- **Step 1:** Lexical negation-cue scan with an explicit `NEGATION_CUES` set of 20 words (not, never, no, wrong, incorrect, false, mistake, but, however, actually, contradicts, contradicted, disagree, disagrees, retract, retracted, changed, updated, correction).
- **Step 2:** Similarity guard — negation cues only evaluated on pairs that already satisfy the cosine threshold (≥ 0.90 for Stage 5; ≥ 0.80 for Stage 6).
- Explicit known-limitation acknowledgement: false positives (e.g. "not only X but also Y") and semantic contradictions without negation words will occur; tolerated for M3, improved in M8.

An implementer has no room to guess. Tasks 9.5 and 9.6 are now actionable.

---

### G5 — Token counting mechanism unspecified

**Verdict: RESOLVED**

**Evidence:** Design §4.2 "Buffer mechanics" states: `token_count = len(unit.user_text + unit.agent_text) // 4` — character-based approximation. Explicitly notes: "No tokenizer dependency; no per-model variance. Consistently slightly underestimates (safe direction for a budget cap). `tiktoken` is NOT imported in M3." The upgrade path is named: "only `ConversationUnit.token_count` and the `append_unit` compute step change." Task 1.1 mirrors the formula. No ambiguity.

---

### G6 — `get_neighbours_bulk` max_depth default (2) vs spreading activation depth (3)

**Verdict: RESOLVED**

**Evidence:** Design §10.2 `StorageSeam` interface now shows `get_neighbours_bulk(ids, max_depth: int = 3)` with comment "Default 3 — consistent with 3-hop spreading activation (§6.4)." §7.4 Phase 2 explicitly says `storage.get_neighbours_bulk(seeds, max_depth=3)`. Task 6.2 notes `get_neighbours_bulk` default `max_depth=3`. All three locations are consistent.

---

### G7 — SurrealKV embedded mode: no spike documented

**Verdict: RESOLVED**

**Evidence:** Design §10.1 now provides:

1. **Provenance:** "Lifted from a proven prior production-deployed memory system (shipped at v1.0.0 in production)." This is the functional equivalent of a spike result — the embedded mode has been verified in a real deployment.
2. **Connection pattern:** Explicit code sample: `Surreal("surrealkv://<absolute_path>")`, `await db.connect()`, `await db.use("axiom", "memory")`. In-process, no TCP port, no spawned process.
3. **LET caveat:** Documented as a mandatory constraint inherited from the lifted implementation — all `StorageSeam` methods must avoid `LET`-based multi-statement SurrealQL.
4. **Named fallback:** "SQLite + sqlite-vec" is explicitly named as the fallback behind the `StorageSeam` seam. "Swapping to the fallback requires only replacing `storage.py` — no other component changes."
5. **Verified capabilities:** "This mode has been verified in the prior implementation to support vector search, native graph traversal, and full-text search from Python without any external server."

The gap is closed. The prior-implementation provenance substitutes for a fresh spike, and the fallback ensures no dead end.

---

## Part B — Fresh Adversarial Pass

New gaps or issues introduced by the round-1 fixes.

---

### NG1 — Requirement AC-02.6 contradicts the design's two-write-path model (WARNING)

**Where:** `requirement.md` AC-02.6 vs `design.md` §3, §4.2, §13, §17 invariant 11.

**What:** AC-02.6 still reads:

> "Observe writes a new conversation unit to the buffer at session-end of each cycle via `memory.store(...)` (the same port method used for cognitive stores); the working tier intercepts units designated as `working` type. The working tier and cognitive tier are served by the same `store` call, differentiated by memory type."

The design explicitly rejects this model. §17 invariant 11: "store is cognitive-store-only. The working-context ring buffer is fed exclusively via `append_unit`. There is no `memory_type` routing in `store`."

**Impact:** An implementer reading the requirement first and the design second will be confused. AC-02.6 describes the pre-round-1 architecture that was explicitly replaced. The design is authoritative (per spec-driven-development conventions, design supersedes requirement on mechanism details), so implementation will follow the design. But the stale requirement text is a documentation debt that should be updated before the spec gate closes.

**Severity:** WARNING — does not block implementation (design is unambiguous), but the requirement should be updated to say `append_unit` instead of `store(...)` for the working-context write path.

---

### NG2 — Task 14.1 E2E test uses stale `store(memory_type="working")` for cross-session recall

**Where:** `task.md` 14.1 vs `design.md` §4.2, §17 invariant 11.

**What:** Task 14.1 says: "store a conversation unit (`memory_type='working'`)." Under the new design, `store` writes to the cognitive store only. A `memory_type="working"` cognitive-store memory has S₀ = 0.04 (~58 minutes) — it would decay to R < 0.2 quickly and could be archived by consolidation before session B's recall. Meanwhile, the working-context ring buffer (fed by `append_unit`) is ephemeral and does not survive adapter teardown.

The test as described can still pass (the cognitive store memory of type `working` may be retrieved if the test runs fast enough), but the scenario is fragile and doesn't test the intended path. A more robust E2E cross-session test would store a `semantic` or `episodic` memory via `store(content, memory_type="semantic")` in session A and verify it appears in `cognitive_memories` in session B.

**Severity:** WARNING — the test will work but is misleadingly named and tests a degenerate path. Should be revised at task-fleshing time.

---

### NG3 — `append_unit` contract: complete and consistent (VERIFIED — NO GAP)

Checked across four sections:

| Aspect | §3 Port | §4.2 Design | §13 Loop Wiring | §17 Invariants | Task |
|--------|---------|-------------|-----------------|----------------|------|
| Signature | `async def append_unit(self, unit: ConversationUnit) -> None` | ✓ (matches) | ✓ (matches) | — | 10.4b ✓ |
| Awaited vs FnF | AWAITED (fast) | "Awaited by the loop" | "Awaited" | Invariant 11 (working-context via `append_unit` only) | ✓ |
| Who constructs CU | — | "the loop constructs" | "Loop constructs a ConversationUnit(user_text, agent_text, turn_index, timestamp)" | — | 11.3 ✓ |
| Where embedding computed | "Embedding computed at call time" | Steps 1–3: `EmbeddingService.embed(...)` → set `unit.embedding` → append | — | — | 10.4b ✓ |
| Does NOT touch cognitive store | "Does NOT write to the cognitive store" | "Does not write to the cognitive store" | "store is NOT used for working-context writes" | Invariant 11 | 10.4b, 11.3 ✓ |

**Verdict:** The `append_unit` contract is complete, consistent across all four design sections, and fully tasked. No gap.

---

### NG4 — `store` still references `memory_type="working"` — semantic ambiguity? (VERIFIED — NO GAP)

**Where:** §3 `store(content, memory_type: str | None = None, ...)`, §5 taxonomy (type `working` with S₀ = 0.04).

**What:** Under the new design, `store` writes to the cognitive store only. But a caller *could* pass `memory_type="working"` to `store`, creating a cognitive-store memory of type `working`. This is valid — `working` as a memory type in the cognitive store represents "conversation ephemera that promoted or fades fast" (§5). This is distinct from the working-context ring buffer (ephemeral, in-memory, fed by `append_unit`).

**Verdict:** No gap. The two uses of "working" — (a) the ephemeral in-memory ring buffer tier, and (b) the `working` memory type in the cognitive store — are clearly distinguished by the two-write-paths architecture. The potential for implementer confusion exists but is addressed by §17 invariant 11's explicit statement: "There is no `memory_type` routing in `store`."

---

### NG5 — Loop wiring: who decides what cognitive items to store at Observe? (VERIFIED — ACCEPTABLE DEFERRAL)

**Where:** §13 "Observe — two separate write paths."

**What:** §13 says: "for each cognitive knowledge item worth retaining across sessions (facts, decisions, notable context), the loop fires a fire-and-forget store to the cognitive tier. Explicit cognitive stores in M3 are loop-driven; LLM-assisted extraction is M8."

This means in M3, the loop must have hardcoded logic to decide *what* to store to the cognitive tier. The design doesn't specify what those heuristics are — it defers to "loop implementation detail" and "M8 for LLM-assisted extraction." This is an acceptable deferral: M3's scope is the memory *faculty*, not the loop's extraction intelligence. The faculty's `store` method is ready; the caller's decision logic is orthogonal.

**Verdict:** No gap. Acceptable scope boundary.

---

## Warnings

---

### W1 — Requirement AC-02.6 stale (see NG1)

AC-02.6 describes the pre-fix architecture (`store` with `memory_type` routing to the working buffer). Should be updated to reference `append_unit` before the spec gate closes. Does not block implementation — the design is unambiguous — but creates a paper inconsistency.

---

### W2 — Task 14.1 tests a degenerate cross-session path (see NG2)

The E2E test stores a `memory_type="working"` memory via `store` and expects cross-session recall. Under the current design, this goes to the cognitive store with S₀ = 0.04 (fast decay). The test works but tests a fragile edge case rather than the primary cross-session path. Consider revising at task-fleshing time to store `memory_type="episodic"` or `"semantic"` instead.

---

### W3 — Round-1 warnings W1, W3, W5, W7 dispositions documented

Design §18 now documents dispositions for all round-1 warnings. Verified:

| Warning | Disposition | Adequate? |
|---------|------------|-----------|
| W1 (SurrealKV rationale trail) | Accepted; §10.1 documents provenance | ✓ |
| W2 (O(N²) consolidation) | Addressed; `consolidation_debounce_sessions` config knob defined | ✓ |
| W3 (concurrent FnF auto-linking) | Accepted; documented as known behaviour | ✓ |
| W4 (retrievability dual semantics) | Addressed; §10.3 clarifies stored = snapshot, authoritative = on-the-fly | ✓ |
| W5 (MemoryAdmin placement) | Deferred to task-time / M8 | ✓ (admin is out of M3 scope per §16) |
| W6 (config defaults) | Addressed; §12 specifies all defaults | ✓ |
| W7 (<100ms target tight) | Accepted risk; soft goal in M3 | ✓ |

No residual concern.

---

## Coverage Check

### Design ↔ Requirement

| User Story | Covered in Design | Notes |
|-----------|-------------------|-------|
| US-01 (context assembly) | §3, §4.4, §13 | ✓ Full |
| US-02 (working context) | §4.2 | ✓ Full — model, buffer, assembly all specified. AC-02.6 wording stale (W1) but intent met via `append_unit`. |
| US-03 (cognitive tier) | §4.3, §7, §10 | ✓ Full |
| US-04 (decay) | §6 | ✓ Full |
| US-05 (type taxonomy) | §5 | ✓ Full |
| US-06 (relation graph) | §8 | ✓ Full |
| US-07 (multi-strategy retrieval) | §7 | ✓ Full |
| US-08 (fire-and-forget store) | §3.2, §17 | ✓ Full |
| US-09 (consolidation) | §9 | ✓ Full — negation detection now specified |
| US-10 (embedded storage) | §10, §11 | ✓ Full — provenance documented, fallback named |

### Design ↔ Task

| Task Group | Actionable? | Notes |
|-----------|-------------|-------|
| 1. Models/config | ✓ | ConversationUnit fields specified; config defaults specified |
| 2. Port contract | ✓ | `append_unit` added to port; all methods documented |
| 3. Decay | ✓ | Pure functions, no deps |
| 4. Classification | ✓ | Keyword sets, importance formula |
| 5. Embedding | ✓ | Model, warmup, executor pattern |
| 6. Storage seam | ✓ | SurrealKV provenance; LET caveat; max_depth=3 |
| 7. Working context | ✓ | Ring buffer, token counting, recency+relevance assembly |
| 8. Retrieval | ✓ | All phases, depths, weights specified |
| 9. Consolidation | ✓ | All 6 stages including negation detection |
| 10. Adapter | ✓ | Including new task 10.4b for `append_unit` |
| 11. Loop wiring | ✓ | Including task 11.3 revised for `append_unit` + separate `store` |
| 12–14. Tests | ✓ | Minor task 14.1 wording issue (W2), not blocking |

---

## Verdict

**GO — all seven round-1 gaps are genuinely resolved. No new blocking gaps.**

The design is implementation-ready. The two-write-path split (`store` for cognitive, `append_unit` for working-context) is cleanly specified, internally consistent across all four reference points (§3 port, §4.2 two write paths, §13 loop wiring, §17 invariants), and fully tasked.

**Two non-blocking warnings** to address before or during implementation:

| # | Warning | Action | When |
|---|---------|--------|------|
| W1 | Requirement AC-02.6 uses stale `store(...)` wording for working-context writes | Update AC-02.6 to reference `append_unit` | Before spec gate closes |
| W2 | Task 14.1 tests `store(memory_type="working")` for cross-session — degenerate path | Revise to use `episodic` or `semantic` type | At task-fleshing time |

Neither warning blocks the start of implementation. The design document stands as-is.
