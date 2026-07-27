# M8 · Self-correction — Design

**Spec:** `010-m8-self-correction`
**Milestone:** M8 — "Self-correction. Capture lessons + deliver them at the decision point."
**Status:** DRAFT
**Inputs:** `requirement.md` (this spec); `001-agent-core/architecture.md` (INJECT/CAPTURE call-point contracts); `005-m3-memory/design.md` (the `MemoryPort` this milestone reuses unmodified, and its own deferred "LLM-assisted extraction is M8" commitments); `008-m6-router/design.md` / `009-m7-orchestrator/design.md` (Router's own precedent for adding narrow, purpose-built selection methods without touching `select_worker()`'s contract); installed source read directly on `feature/m8-self-correction` (branched from `master` post-M7 merge, `52420eb`).

**Process note:** `requirement.md`'s one open design question (CAPTURE's selective-trigger extraction mechanism) was proposed to velasari via crosstalk and a genuine ~20-minute wait was observed (both `axiom` and `velasari` crosstalk registrations showed live heartbeats throughout, confirming the channel itself was healthy) with no reply delivered. Proceeding on the proposed resolution as the working design, per the same "Kaushik asleep, co-think and proceed rather than block" authorization already exercised for M6's OQ-1 and M7's three open questions.

---

## 1. Overview

M8 adds exactly one new field to `RunState` (`lessons`), one new rendering block to `PraoAdapterBase.perceive()` (mirroring the existing `memory_context` block exactly), one new local-variable-driven call-point inside `loop.py`'s `_run_async()` (CAPTURE), one new narrow `Router` method (`select_extraction_worker()`, mirroring M7's `select_committee()` precedent of not touching `select_worker()`'s contract), and one schema/decay-table addition in `axiom.memory` (a new `"lesson"` `memory_type`). No new port, no new adapter, no new `IntentKind`, no new top-level phase — directly satisfying SC-4 and DoD item 3.

**A concrete blocker found during design (not present in the requirement, verified against live source):** `axiom/memory/schema.py`'s `memory_type` field carries a hard SurrealDB `ASSERT $value IN [...]` constraint — `['working', 'episodic', 'semantic', 'procedural', 'identity', 'person']`. `"lesson"` is not in this list. Without extending it, every `store(content, memory_type="lesson")` call SC-1 requires would be rejected at the database layer. Resolved in §4 below — a one-line schema addition, applied idempotently at every `StorageSeam` init (`schema.py`'s own docstring: "applied idempotently at StorageSeam init"), no separate migration mechanism needed.

---

## Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | INJECT is **not** a new loop.py-level call-point function — it folds into the **existing** once-per-turn context-assembly point `run_state.memory_context` already uses (`_run_async()`, before the `while True:` loop), via a new `run_state.lessons: list[str]` field and a new rendering block in `PraoAdapterBase.perceive()`. | `architecture.md`'s "immediately before the Reasoner invokes the Conductor" is naturally satisfied by folding into the SAME assembly step `memory_context` already uses for exactly the same reason M3 built it that way: lessons are background knowledge injected once per turn, not re-fetched every cycle (re-fetching every cycle would itself conflict with token efficiency — the same concern CAPTURE's own selectivity addresses on the write side). SC-2's own AC text ("render into the context `PraoAdapterBase.perceive()` already builds") already specifies this mechanism. |
| D2 | CAPTURE lives **inside** `loop.py`'s `_run_async()`, inserted once, right after the ACT branch's `if committee is not None: ... else: ...` converges — reading a local `correction_signal: str \| None` variable set inside each branch — not as a call-point living inside `base.py`'s `observe()`. | `observe()` (M1, `PraoAdapterBase`) has no access to Router/dispatch-outcome information (which provider was used, whether a fallback or per-slot failure occurred) — that information exists only in `loop.py`'s own ACT-branch locals. CAPTURE genuinely needs to live where that information already is, unlike INJECT (D1), which only needs `user_input` — already available at the point `memory_context` is assembled. |
| D3 | `correction_signal` is a **local variable**, not a new `RunState` field. | It's produced and consumed within the same `_run_async()` call, in the same iteration of the `while True:` loop — nothing outside that scope needs it. Contrast with `run_state.lessons` (D1), which genuinely must cross the `loop.py` → `base.py` module boundary, hence needs to live on `RunState`. |
| D4 | `Router` gains `select_extraction_worker() -> WorkerSelection`, a new method that deterministically prefers `"local"` (falling back to whatever else is configured if `"local"` isn't available), **completely bypassing** `RoutePolicy` evaluation. | The extraction call is an internal system task (summarizing a correction), not a user-facing ACT dispatch — RT-4/5/6's privacy/capability/bulk-threshold policy exists to route *user* instructions; applying it to an internal summarization call would be a category error (e.g., a privacy pattern matching the correction text by coincidence would be meaningless here). Mirrors M7's own precedent (`select_committee()`, D1 in `009-m7-orchestrator/design.md`) of adding a narrow, purpose-built method rather than overloading `select_worker()`'s existing contract. "Local" is preferred because it's the cheapest configured provider (mirrors RT-5's own cost-conscious precedent), not because of any capability requirement — the extraction task is a short, bounded summarization, well within a small local model's ability. |
| D5 | `correction_signal`'s three trigger sources, matching SC-1's AC exactly: (a) single-dispatch fallback occurred (`final_selection is not selection` in the M6/M7 `else` branch); (b) at least one committee member failed (`not any_succeeded` is the all-fail case, already fatal — the *partial*-failure case, where `"FAILED" in` at least one `parts` entry but the cycle still succeeded overall, is what triggers CAPTURE here); (c) this cycle's `run_state.cycle_count` has just reached `self._max_cycles` (checked with the *same* condition the existing `MaxCyclesExceededError` raise already uses, evaluated one line earlier so CAPTURE fires before the raise propagates). | Directly implements SC-1's AC's three named signals. Using the *same* conditions the existing M6/M7/M1 code already computes (`final_selection is not selection`, `"FAILED" in part` string checks on the already-built `parts` list, `run_state.cycle_count >= self._max_cycles`) means no new state tracking is needed anywhere else in the loop — CAPTURE observes facts the surrounding code already produces. |
| D6 | `memory_type="lesson"` requires two small `axiom.memory` changes: `schema.py`'s `ASSERT` enum gains `'lesson'`; `decay.py`'s `STABILITY_BY_TYPE` gains `"lesson": 60.0` (matching `"procedural"`'s own value). | The schema change is the concrete blocker (Overview). The stability value: without an explicit entry, `STABILITY_BY_TYPE.get(memory_type, 2.0)` would silently fall back to `episodic`'s low 2.0-day half-life — appropriate for a raw conversational turn, wrong for a distilled correction that should persist (a lesson, once learned, shouldn't decay as fast as a passing exchange). `60.0` matches `"procedural"` (durable how-to knowledge) — a lesson is conceptually the same kind of distilled, durable knowledge, not a moment-in-time episodic fact. |
| D7 | The extraction dispatch (`Router.select_extraction_worker().adapter.act(...)`) and the lesson `store()` call are both **best-effort** — wrapped in `try/except`, logged on failure, never propagated. A failure to self-correct must never break the user's actual turn. | Matches the existing best-effort philosophy already established for memory-adjacent side effects elsewhere in the codebase — `agent.py`'s `finally` block already wraps `memory_adapter.consolidate()`/`.close()` in `try/except Exception` with a `logger.warning(...)`, not a raise, for exactly this reason (a memory-subsystem hiccup shouldn't crash a successful turn). CAPTURE firing at all is itself already conditional on something having gone wrong in THIS turn (D5) — a second failure, in the correction-capturing machinery itself, must not compound into a user-visible crash. |
| D8 | The extraction dispatch gets **no new observability phase span** — it is untraced at the phase level, same as M3's own `append_unit`/`reinforce`/`store` calls at RESPOND exit (confirmed by re-reading `loop.py`'s RESPOND branch: none of those calls are wrapped in `_maybe_record(...)`). `run_state.spawn_count` still increments by 1 when the extraction call actually dispatches (matches `spawn_count`'s documented contract: "loop-dispatched query() calls"). | Directly satisfies SC-4's "no new top-level phase" AC using an existing, already-established precedent rather than inventing a new tracing convention. `spawn_count` incrementing (but no new span) keeps the existing cost-accounting invariant correct without adding a new trace dimension SC-4 doesn't ask for. |
| D9 | `run_state.lessons` retrieval (`recall(query=user_input, type_filter="lesson", limit=3)`) is also best-effort (D7's same philosophy) — a `recall()` failure leaves `run_state.lessons` empty, INJECT silently renders nothing, the turn proceeds normally. | Symmetric with D7: a failure in the *delivery* half of self-correction must be as non-fatal as a failure in the *capture* half. `limit=3` mirrors M3's own `k_cognitive`-style bounded-retrieval precedent (a small, fixed cap, not unbounded). |
| D10 | **Live-verification finding, fixed at the source (two-part — Phase 1 and Phase 2):** `RetrievalPipeline.recall()` (M3, `src/axiom/memory/retrieval.py`) only passed `type_filter` to the semantic strategy (`vector_search`) — `fulltext_search` (keyword) and `get_by_recency` (temporal) ran with no type constraint at all, and RRF-fused their untyped hits into the same ranked result set before `limit` truncation. A live two-turn verification run surfaced this directly: `recall(type_filter="lesson")` returned 1 genuine lesson plus 2 unrelated `episodic` entries, and — the worse failure mode — a real lesson can be silently crowded out of the final `limit`-N slots by higher-scoring untyped keyword/temporal hits with **no error, no warning, degrading silently as the memory store grows**. Fixed at the source: `keyword_results`/`temporal_results` are now filtered to `memory_type == type_filter` immediately after the `asyncio.gather(...)` and before RRF fusion (Phase 1 fix). **A second, deeper leak in the same function survived that first fix**: Phase 2 (graph traversal, `get_neighbours_bulk(top_seeds, ...)`) adds a seed's graph neighbours to `final_scores` with no type check at all — since neighbours are edge-based, not type-scoped, a `type_filter="lesson"` seed's neighbour (added via an unrelated `memory_relate`/spreading-activation edge) can be any type, and would silently re-enter a `type_filter`'d result set through this second path even after the Phase 1 fix closed the first one. This is pre-existing M3 behavior in both cases (SC-2 is the first M8 consumer to depend on `type_filter` actually filtering); a same-typed neighbour is legitimate graph expansion and must stay included, so the fix is a type check inside the Phase 2 loop (`if type_filter is not None and m.memory_type != type_filter: continue`) rather than disabling graph expansion under a type filter. Rejected the alternative of a defensive filter inside `loop.py`'s own INJECT code for both parts — that would suppress the visible symptom (wrong-typed entries in the rendered section) while leaving the invisible one (real lessons silently losing their ranked slot to untyped competitors, in Phase 1 or Phase 2) completely unfixed. Verified: 4 new unit tests (`TestTypeFilter` in `test_memory_retrieval.py`) cover Phase 1 exclusion, Phase 2 exclusion, Phase 2's same-type inclusion (so the fix isn't a blanket ban on typed graph expansion), and the `type_filter=None` no-op case; plus the same live verification script post-fix: `recall(type_filter="lesson")` returns exactly the 1 genuine lesson, and the rendered `[LESSONS FROM PAST CORRECTIONS]` section contains only that lesson. |

---

## 2. `RunState` and `perceive()` — INJECT

`src/axiom/interfaces.py` — one new field on the existing `RunState` dataclass:

```python
@dataclass
class RunState:
    ...
    # M8: lessons retrieved once per turn (same cadence as memory_context, D1),
    # rendered by perceive() into their own section. Empty list = no lessons
    # matched (the common case) -- never None, so perceive() doesn't need a
    # None-guard beyond the existing "if run_state.lessons:" truthiness check.
    lessons: list[str] = field(default_factory=list)
```

`src/axiom/loop.py` — `_run_async()`, immediately after the existing `memory_context` assignment (before the `while True:` loop):

```python
run_state.memory_context = assembled_context

# M8 (SC-2, D1, D9): INJECT -- once per turn, same cadence as memory_context.
# Best-effort: a recall() failure must not abort the turn (D9).
try:
    lesson_hits = await self._memory.recall(
        query=user_input, type_filter="lesson", limit=3
    )
    run_state.lessons = [hit.content for hit in lesson_hits]
except Exception as exc:  # noqa: BLE001 -- best-effort, matches agent.py's own
    # memory-adjacent try/except Exception precedent (D9)
    _axiom_logger.warning("Self-correction INJECT failed (non-fatal): %s", exc)
```

`src/axiom/providers/base.py` — `perceive()`, a new rendering block placed immediately after the existing `[ADDITIONAL CONTEXT FROM MEMORY]`/`[PREVIOUS CONVERSATIONS]` block (same "what the Conductor already knows" grouping the skills-catalog comment already names):

```python
# M8 (SC-2): lessons from past self-corrections, rendered only when present
# (empty list = no section, no wasted prompt tokens -- SC-2's own AC).
if run_state.lessons:
    lesson_lines = [f"  - {lesson}" for lesson in run_state.lessons]
    sections.append(
        "[LESSONS FROM PAST CORRECTIONS]\n" + "\n".join(lesson_lines)
    )
```

---

## 3. `Router.select_extraction_worker()`

`src/axiom/router/router.py` — additive method, mirrors `select_fallback_worker()`'s own shape:

```python
def select_extraction_worker(self) -> WorkerSelection:
    """M8 (D4): the cheapest configured provider, for internal system tasks
    (self-correction lesson extraction) -- NOT user-facing ACT dispatch, so
    RoutePolicy evaluation is deliberately bypassed entirely (unlike
    select_worker()). Prefers "local"; falls back to whatever else is
    configured if "local" isn't available.
    """
    provider_name = "local" if "local" in self._factories else next(iter(self._factories))
    if provider_name not in self._factories:
        raise RouterError("no adapter factories configured for extraction")
    adapter = self._get(provider_name)
    return WorkerSelection(
        adapter=adapter,
        provider_name=provider_name,
        control_level=adapter.control_level,
        fallback_allowed=False,  # D7: extraction failures are absorbed locally, not retried
    )
```

`select_worker()`, `select_committee()`, `select_conductor()`, `select_fallback_worker()` are all **unmodified** — confirmed by re-reading the current `router.py` (post-M7) line by line.

---

## 4. Memory schema/decay additions

`src/axiom/memory/schema.py` — one line changed (the blocker, Overview):

```python
"DEFINE FIELD OVERWRITE memory_type     ON memory TYPE string ASSERT $value IN ['working', 'episodic', 'semantic', 'procedural', 'identity', 'person', 'lesson']",
```

`src/axiom/memory/decay.py` — one new entry:

```python
STABILITY_BY_TYPE = {
    "working": 0.04,
    "episodic": 2.0,
    "semantic": 14.0,
    "procedural": 60.0,
    "identity": 365.0,
    "person": 90.0,
    "lesson": 60.0,  # M8 -- distilled, durable knowledge, same class as procedural (D6)
}
```

No other memory-layer change — `store()`/`recall()`/`classify_type()`/`score_importance()` are all unmodified; passing `memory_type="lesson"` explicitly already bypasses `classify_type()` (existing `if memory_type is None:` guard in `adapter.py`), and `STABILITY_BY_TYPE.get(memory_type, 2.0)` already handles any type present in the dict correctly once D6's entry exists.

---

## 5. CAPTURE — loop wiring

`src/axiom/loop.py` — the ACT branch, immediately after the `if committee is not None: ... else: ...` block (both branches already set `result`; this is the shared code that already exists just above the `if run_state.cycle_count >= self._max_cycles:` check):

```python
# M8 (SC-1, D2, D5): CAPTURE -- correction_signal set inside whichever ACT
# branch ran above; None on an ordinary clean cycle (SC-3's own AC).
if correction_signal is None and run_state.cycle_count >= self._max_cycles:
    correction_signal = (
        f"reached max cycles ({self._max_cycles}) without a terminal intent"
    )

if correction_signal is not None:
    await self._capture_lesson(correction_signal, run_state)

if run_state.cycle_count >= self._max_cycles:
    raise MaxCyclesExceededError(
        f"max cycles ({self._max_cycles}) exceeded without terminal intent"
    )
```

`correction_signal: str | None = None` is (re-)declared at the top of the ACT-intent-handling section, immediately before the `committee = self._router.select_committee(...)` line — this section runs fresh on every loop iteration that processes an `ActIntent`, so `correction_signal` is freshly reset every time, never carried over from a prior cycle (including across a `USE_SKILL` cycle's `continue`, which skips this section entirely and loops back to `perceive()` without ever touching `correction_signal`). Set inside each branch (dryrun-design-1 W1 — reworded for clarity):

- **Committee branch** (D5b): the per-member dispatch loop tracks the actual outcome of each member's `.act()` call in an `outcomes: list[bool]` (aligned by index with `committee`) — **not** a substring match on the already-formatted `parts` display text (dryrun-code-1 B1: a genuine success whose content happens to contain the literal word "FAILED" must never be misclassified as a failure). After the loop:
  ```python
  any_succeeded = any(outcomes)
  if not any_succeeded:
      raise AdapterError(f"all {len(committee)} committee members failed")
  result = "\n".join(parts)

  failed_members = [m.provider_name for m, ok in zip(committee, outcomes) if not ok]
  if failed_members:  # partial failure -- full failure already raised above
      correction_signal = (
          f"committee member(s) {', '.join(failed_members)} failed; "
          f"{len(committee) - len(failed_members)} member(s) succeeded"
      )
  ```
- **Single-dispatch branch** (D5a): immediately after `final_selection = fallback` (the fallback-succeeded line) —
  ```python
  correction_signal = (
      f"provider {selection.provider_name} failed; "
      f"fallback to {final_selection.provider_name} succeeded"
  )
  ```

`_capture_lesson()` — a new `PraoLoop` method:

```python
async def _capture_lesson(self, correction_signal: str, run_state: RunState) -> None:
    """M8 (D7): best-effort. A failure here must never abort the turn."""
    try:
        selection = self._router.select_extraction_worker()
        instruction = (
            f"A correction occurred while handling this request: {correction_signal}\n"
            f"Original request: {run_state.user_input}\n"
            "In one concise sentence, state the lesson learned -- what to watch "
            "for or do differently next time. Do not repeat the raw error text "
            "verbatim; distill the actionable insight."
        )
        run_state.spawn_count += 1  # D8: a real dispatch, no new phase span
        lesson_text = await asyncio.to_thread(selection.adapter.act, instruction)
        await self._memory.store(lesson_text, memory_type="lesson")
    except Exception as exc:  # noqa: BLE001 -- D7: best-effort, never propagates
        _axiom_logger.warning("Self-correction CAPTURE failed (non-fatal): %s", exc)
```

(`_axiom_logger` — `loop.py` needs its own module-level `logging.getLogger("axiom")` call, matching `agent.py`'s existing pattern; currently `loop.py` has no logger of its own.)

---

## Error Handling

| Failure | Behavior |
|---|---|
| `recall(type_filter="lesson")` raises (INJECT) | Caught, logged as a warning, `run_state.lessons` stays `[]` — turn proceeds with no lessons rendered (D9). |
| `select_extraction_worker()` raises `RouterError` (no adapters configured at all) | Caught by `_capture_lesson()`'s own `try/except`, logged, lesson silently not captured (D7) — this is a genuinely degenerate config (zero adapters), already unreachable via the real `agent.py` composition root (always configures `claude` + `local`), same class of edge case as M7's dryrun-design-1 W2. |
| Extraction's `.act()` call itself raises `AdapterError` (e.g., local Ollama down) | Caught by `_capture_lesson()`'s `try/except`, logged, lesson not captured — the ORIGINAL correction (the one that triggered CAPTURE) is unaffected; the user's turn already completed successfully before CAPTURE ever fires. |
| `memory.store(..., memory_type="lesson")` raises (e.g., a schema/DB issue) | Same `try/except` in `_capture_lesson()` — caught, logged, non-fatal. |
| A cycle has *both* a fallback (single-dispatch) and would also breach max-cycles | Not reachable in the same cycle — `correction_signal` is set once, by whichever branch actually ran (single-dispatch XOR committee), and the max-cycles check only overwrites it when still `None`. If a fallback already set it, the max-cycles line's `if correction_signal is None` guard prevents overwriting a more specific signal with a generic one. |

---

## Files Changed

| File | Change | AC Trace |
|------|--------|----------|
| `src/axiom/interfaces.py` | Add `RunState.lessons: list[str]` field. | SC-2 |
| `src/axiom/loop.py` | Assign `run_state.lessons` via `recall()` once per turn (INJECT, D1); add `correction_signal` local + set-points in both ACT branches (D5); add the CAPTURE call-point + `_capture_lesson()` method (D2, D7, D8); add a module-level `_axiom_logger`. | SC-1, SC-2, SC-3, SC-4 |
| `src/axiom/providers/base.py` | `perceive()` gains the `[LESSONS FROM PAST CORRECTIONS]` rendering block. | SC-2 |
| `src/axiom/router/router.py` | Add `Router.select_extraction_worker()`. | SC-1 |
| `src/axiom/memory/schema.py` | Add `'lesson'` to `memory_type`'s `ASSERT` enum. | SC-1 |
| `src/axiom/memory/decay.py` | Add `"lesson": 60.0` to `STABILITY_BY_TYPE`. | SC-1 |
| `src/axiom/memory/retrieval.py` | D10 (live-verification finding, two-part): `recall()`'s keyword/temporal strategy results are re-filtered to `memory_type == type_filter` before RRF fusion (Phase 1); Phase 2's graph-neighbour scoring loop gains the same type check so a type-filtered seed's differently-typed neighbour cannot re-enter the result set via graph traversal. | SC-2 |
| `tests/test_memory_retrieval.py` | New `TestTypeFilter` class (4 tests): Phase 1 keyword/temporal exclusion, Phase 2 neighbour exclusion, Phase 2 same-type neighbour inclusion, `type_filter=None` no-op. | SC-2 |
| `tests/test_router.py` | Extend. `select_extraction_worker()` — prefers local, falls back, raises `RouterError` on zero adapters. | SC-1 |
| `tests/test_contracts.py` | Extend. Loop-level: `correction_signal` set correctly on fallback / partial committee failure / max-cycles breach; `_capture_lesson()` called exactly once per triggering cycle, never on a clean cycle (SC-3); `run_state.lessons` populated from a scripted `recall()`; `perceive()`'s new section renders only when `lessons` is non-empty. | SC-1, SC-2, SC-3 |
| `tests/fake_adapter.py` | `FakeMemory` gains a scriptable `recall()` return value (mirrors `FakeRouter`'s scripted-selection pattern); `FakeRouter` gains `extraction_selection`. | SC-1, SC-2 |
| `tests/test_shared_base.py` (or equivalent existing `base.py` perceive test file) | New test: `[LESSONS FROM PAST CORRECTIONS]` section renders correctly when `run_state.lessons` is populated, absent when empty. | SC-2 |

---

## Future Work (Out of Scope)

- **A dedicated completion-only extraction call-path** — `_capture_lesson()` reuses the full `Worker.act()` interface (D4), which for `LocalAdapter` means the entire smolagents `CodeAgent` tool-loop is available even though extraction never needs tools. Accepted as a pragmatic trade-off (no new port/adapter surface, per SC-4) rather than built around here; a leaner completion-only seam (`reason()`'s own "no tools" pattern, generalized) is a plausible future refinement if extraction-call overhead becomes a measured problem.
- **Learned/persisted routing policy**, **LLM-assisted contradiction detection**, **reflection/higher-order insights over the full memory store**, **`MemoryAdmin` interface placement** — all explicitly out of scope per `requirement.md`'s own Out of Scope section; not designed here.
