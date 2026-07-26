# M8 · Self-correction — Requirements

**Spec:** `010-m8-self-correction`
**Milestone:** M8 — "Self-correction. Capture lessons + deliver them at the decision point." (`001-agent-core-roadmap.md`)
**Status:** DRAFT

---

## Purpose

Unlike M7, M8's scope is **not thin** — `architecture.md` already fixes the structural shape precisely, and M3's `design.md` already commits to specific deferred behavior that becomes M8's job. This requirement is assembled from those existing commitments, not invented from a one-line roadmap description.

**What `architecture.md` already fixes (§"Cross-cutting faculties — call-points, not ports"):**
- Self-correction is **not a port and not a separate structural component** — it's core-internal, wired into the loop via two named call-points, the same pattern M2 (Observability RECORD) and M4 (Guardrails GATE) already use.
- **INJECT** fires "immediately before the Reasoner invokes the Conductor" — i.e., right before the Reason-phase call inside `loop.py`'s `_run_async()` (the same phase-boundary granularity M2's `_maybe_record("reason", ...)` already hooks). Relevant lessons from Memory are retrieved and injected into the Reasoner's context.
- **CAPTURE** fires "immediately after the Observer updates Run State" — right after `self._observe.observe(...)` returns inside the ACT branch (M2's `_maybe_record("observe", ...)` boundary). Lessons extracted from this cycle are written to Memory.
- Confirmed by re-reading `loop.py` directly: no INJECT/CAPTURE stubs exist today. `002-m1-prao-proof/design.md` explicitly deferred even the M1 no-op stubs architecture.md's own M1 table had originally scoped: *"wiring named no-ops into `loop.py` before the call-point contracts are designed risks locking in a wrong call signature. M8 will introduce call-points when their contracts are known."* M8 is building these from scratch, not filling in placeholders.

**What M3's `design.md` already commits M8 to (found via direct grep across existing specs, not invented here):**
- *"Smart extraction / distillation is M8; M3 stores the full exchange"* (§Files Changed, the Observe-phase `store()` row) — M3 deliberately stores every completed exchange verbatim (`memory_type="episodic"`) with **no** judgment about what's worth keeping; that judgment is explicitly M8's.
- *"LLM-assisted extraction | M8 (CAPTURE call-point). M3 stores what the loop explicitly tells it."* and *"Reflection / higher-order insights | M8. No LLM pass over own memories."* (§16, Future Work) — M3's own design document names the CAPTURE call-point specifically and commits to it being **LLM-assisted**, not a mechanical heuristic. This is prior project documentation, not a choice this requirement is inventing.
- The Memory port (`MemoryPort`, M3, unmodified by this milestone) already exposes exactly what INJECT/CAPTURE need generically: `recall(query, type_filter=..., limit=...)` for retrieval and `store(content, memory_type=..., importance=..., tags=...)` for writing — the same two calls M3's own `assemble_context()`/episodic-store path already uses. No new Memory port methods are needed; M8 is a new *caller* of the existing port, using a new `memory_type` value (`"lesson"`) to keep self-correction content queryable separately from ordinary episodic history.

**The one genuinely open design question — resolved here, not left to guesswork:**

M3's design commits CAPTURE to being LLM-assisted, but calling an LLM at *every single* Observe-phase boundary directly conflicts with this project's own stated cross-cutting principle of **token efficiency** (`CLAUDE.md`) — it would roughly double the number of reasoning-shaped calls per PRAO cycle (today: 1 Reason call per cycle; with unconditional CAPTURE, 2). Neither `architecture.md` nor M3's `design.md` resolves this tension; both simply say "M8 does the LLM-assisted part" without saying *how often*.

**Resolution (this requirement's own design decision, SC-3 below):** CAPTURE fires **selectively**, gated by a cheap, mechanical trigger evaluated from `run_state` alone (no LLM call for the gate check itself) — only cycles that show a signal actually worth learning from (an ACT failure that was recovered via fallback, a committee member failure, `MAX_CYCLES` breach, or an unusually high cycle count) invoke the LLM-assisted extraction call. Ordinary, uneventful cycles (the common case — a clean RESPOND on the first pass) never pay the extra call. This satisfies M3's documented commitment (extraction genuinely is LLM-assisted when it fires) while respecting token efficiency (it doesn't fire unconditionally). The extraction call itself uses the cheapest available provider capable of the task (mirrors RT-5's own cost-conscious precedent from M6), not necessarily the session's Conductor.

This resolution was reasoned through directly against existing project documentation (`architecture.md`, M3's `design.md`) rather than guessed from the roadmap's one-line description — flagged to velasari for awareness per the standing overnight pattern (M6 OQ-1, M7's three questions), proceeding on this basis per the same "Kaushik asleep, co-think rather than block" authorization already exercised twice this session.

---

## User Stories

---

### SC-1 — CAPTURE: lessons extracted from a cycle showing a correction signal, written to Memory

**Purpose:** The concrete mechanism CAPTURE resolves to. Without this, Axiom repeats the same avoidable mistakes across sessions — M3 gives it long-term memory, but M3 explicitly stores everything undifferentiated; nothing today distills "what went wrong and what fixed it" into something the Reasoner can actually use later.

**As** the Axiom loop completing an ACT cycle,
**I want** a lesson extracted and stored whenever the cycle showed a correction signal (an ACT failure recovered via fallback, a committee member failure, `MAX_CYCLES` breach, or an unusually high cycle count for the turn),
**so that** future turns can draw on what actually went wrong and how it was resolved, not just the raw transcript.

**Relates-to:** M3 (memory `store()`/`recall()`, reused unmodified), M6 (RT-9 fallback, one of CAPTURE's trigger signals), M7 (OR-6 committee per-slot failure, another trigger signal)

**Acceptance Criteria:**
- CAPTURE fires exactly once per ACT cycle that matches a trigger signal (fallback occurred, committee member failed, `MAX_CYCLES` breached) — not on ordinary clean cycles (SC-3's own AC covers the negative case explicitly).
- The extracted lesson is written via the existing `MemoryPort.store()` call with `memory_type="lesson"` — no new Memory port method, matching the existing episodic-store pattern (M3) exactly in mechanism, differing only in `memory_type` and content (a distilled correction, not the raw exchange).
- The lesson's content names what failed and what the resolution was (e.g., "local provider failed on X; claude succeeded" — not a verbatim dump of the raw error/result already stored separately by M3's own episodic path).
- **[behavioral]** A live `axiom-cli` turn that triggers RT-9's fallback (e.g., a deliberately unreachable `--ollama-host`, mirroring M7's own OR-6 live-verification method) results in a new `memory_type="lesson"` entry queryable via the existing `recall(query, type_filter="lesson")` call in a fresh follow-up turn — proving the lesson was genuinely written and is genuinely retrievable, not just constructed in memory and dropped.

---

### SC-2 — INJECT: relevant lessons retrieved and rendered into the Reasoner's context

**Purpose:** The delivery half of "capture lessons + deliver them at the decision point" (the roadmap's own words) — a captured lesson that never reaches the Reasoner's context has no effect on future behavior; this story is what makes CAPTURE's output actually change anything.

**As** the Axiom loop about to invoke the Conductor for a Reason cycle,
**I want** lessons relevant to the current turn retrieved from Memory and rendered into the context `perceive()` already assembles,
**so that** the Conductor's next decision is informed by what's already been learned, not just the current turn's raw context.

**Relates-to:** SC-1, M3 (`assemble_context()`/`recall()`, the existing rendering path)

**Acceptance Criteria:**
- INJECT calls the existing `MemoryPort.recall(query=user_input, type_filter="lesson", limit=N)` — reusing M3's own retrieval mechanism, not a new query path.
- Retrieved lessons render into the context `PraoAdapterBase.perceive()` already builds (M1, mostly unmodified) under their own labeled section — distinguishable from M3's existing `[Additional Context]`/`[Previous Conversations]` sections, so the Conductor can tell "this is a learned correction" from "this is recalled conversation."
- When no lessons match (the common case, especially early in a fresh memory store), INJECT is a no-op — no empty section rendered, no wasted prompt tokens.
- **[behavioral]** Continuing SC-1's live scenario: a **new** `axiom-cli` turn (fresh process) whose instruction is semantically close to the one that triggered the earlier fallback shows the captured lesson's content rendered in `perceive()`'s output (verifiable via `--debug` or a direct `perceive()` call against the real `run_state`) — proving INJECT's retrieval-and-render path is real, not just SC-1's write path in isolation.

---

### SC-3 — CAPTURE is selective, not unconditional — token efficiency preserved

**Purpose:** Directly implements this requirement's own resolution to the extraction-mechanism question (see Purpose section above). Without this story's own AC, SC-1 alone could be satisfied by firing CAPTURE on every cycle — exactly the outcome this requirement's resolution rejects.

**As a** user running ordinary, uneventful turns,
**I want** CAPTURE to add zero extra LLM calls when nothing went wrong,
**so that** M8 doesn't silently double Axiom's per-turn cost for the common case.

**Acceptance Criteria:**
- A cycle with no fallback, no committee failure, and no `MAX_CYCLES` breach triggers **zero** additional LLM-shaped calls from CAPTURE — the gate check itself is answerable from `run_state` alone (cycle count, whether a fallback selection was used, whether any committee member failed), no LLM call needed to decide whether to extract.
- **[behavioral]** A live `axiom-cli --observe` run with a clean single-cycle turn (no forced failures) shows, via the trace, the same `spawn_count`/call shape M6/M7 already established for a clean cycle — no new spans or dispatches attributable to CAPTURE.

---

### SC-4 — No new IntentKind, no new PRAO phase

**Purpose:** Keeps M8 from becoming a structural component in violation of `architecture.md`'s explicit "not a port, not a separate structural component" framing — the same discipline OR-4 (M7) already enforced for committee synthesis.

**As** the Axiom loop,
**I want** INJECT/CAPTURE implemented purely as call-points inside `loop.py`'s existing `_run_async()` method,
**so that** the wire-format contract (`RESPOND`/`ACT`/`USE_SKILL`/`FINISH`) and the PRAO phase structure are both unmodified by this milestone.

**Acceptance Criteria:**
- No new `IntentKind` is added.
- No new top-level phase is added to `_maybe_record()`'s existing phase set (`run`/`perceive`/`reason`/`use_skill`/`act`/`observe`) — INJECT/CAPTURE are call-points *within* the existing `reason`/`observe` boundaries, not new phases of their own (matching how M4's Guardrails GATE lives inside the adapter's own `act()`, not as a separate loop-level phase).
- `Router`, `WorkerSelection`, and the M7 committee-dispatch mechanism are all unmodified by this milestone.

---

### SC-5 — M8 verified live via CLI

**Purpose:** Matches the standing verification bar from every prior milestone.

**As a** developer signing off M8,
**I want** the CAPTURE-then-INJECT loop demonstrated live via `axiom-cli` across two separate turns,
**so that** the milestone's actual value — Axiom genuinely learning from a correction and using it later — is proven working, not just structurally present.

**Acceptance Criteria:**
- SC-1's and SC-2's behavioral ACs are demonstrated live and recorded, matching the M1–M7 sign-off pattern (a two-turn scenario: trigger a correction, then show a later turn's context reflects it).

---

## Infrastructure Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| M3 Memory (`MemoryPort.store()`/`recall()`) | Exists, merged to master | No port changes — M8 is a new caller using `memory_type="lesson"`. |
| M6 Router / M7 Committee (fallback + per-slot-failure signals) | Exist, merged to master | CAPTURE's trigger-signal check reads `run_state`/dispatch outcome, no Router changes. |
| A cheap extraction-capable provider | Exists (`local` via M1/M6) | The extraction LLM call (when triggered) uses the cheapest configured provider, not necessarily the session's Conductor — mirrors RT-5's cost precedent. |

---

## Configuration Summary

No new CLI flags planned — CAPTURE's trigger signals are read from existing `run_state`/dispatch outcome data, and INJECT reuses the existing `recall()` call with no new parameters. (Subject to revision once `design.md` works out the exact trigger-check implementation.)

---

## Out of Scope

- **Learned/persisted routing policy** — M6's own `design.md` names this as a *possible* future M8 direction (Router learning from past outcomes), but it is not implied by the roadmap's "capture lessons + deliver them at the decision point" line and is not architecture.md's INJECT/CAPTURE mechanism (which targets the Reasoner's context, not Router's policy engine). Deferred unless explicitly requested.
- **LLM-assisted semantic contradiction detection** in memory consolidation — M3's `design.md` separately named this as deferred to M8 (§Stage 5/6 contradiction heuristic), but it's a *different* mechanism (consolidation-time contradiction detection between existing memories) from CAPTURE (per-cycle lesson extraction). Out of scope for this spec; a candidate for a future M8-adjacent spec if still desired.
- **Reflection / higher-order insights** (an LLM pass over the *entire* memory store looking for patterns) — M3's `design.md` named this too, but it's a batch/offline concern distinct from CAPTURE's per-cycle, in-line extraction. Out of scope here.
- **`MemoryAdmin` interface placement** (`list`/`archive`/`restore`/`delete`/`who`/`self_query`) — M3's own `design.md` W5 explicitly deferred this to "M8-era scope" without committing it to this specific milestone's INJECT/CAPTURE work. Not addressed here; a separate concern if still desired later.

---

## Definition of Done (M8 complete when ALL of these pass)

1. **Spec gate:** `requirement.md`, `design.md`, `task.md` exist; `dryrun-design-N.md`'s latest verdict has zero critical, zero warning, zero observation findings.
2. **Code dryrun gate:** the latest `dryrun-code-N.md` verdict has zero bugs, zero gaps, zero warnings, zero style findings.
3. **No new structural component:** INJECT/CAPTURE live as call-points inside `loop.py`'s existing `_run_async()`; no new `axiom/self_correction/` package with its own port/adapter pair (matches `architecture.md`'s explicit framing).
4. **Token efficiency preserved:** SC-3's AC — a clean cycle triggers zero additional LLM-shaped calls.
5. **Unit tests green:** new tests covering the trigger-signal gate (fires only on fallback/committee-failure/max-cycles-breach), the extraction call, and the INJECT retrieval/render path, with no skips.
6. **Full suite green:** the whole `pytest` suite (pre-existing + new) passes, modulo the already-documented pre-existing `test_local_e2e.py` pollution flake (M7 sign-off).
7. **Live verification:** SC-5's cross-story demonstration is completed and recorded.
