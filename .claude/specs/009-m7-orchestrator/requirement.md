# M7 · Orchestrator — Requirements

**Spec:** `009-m7-orchestrator`
**Milestone:** M7 — "Orchestrator. Multi-provider consortium — the 'committee.' Velhari-pattern." (`001-agent-core-roadmap.md`)
**Status:** DRAFT

---

## Purpose

M7's roadmap line is far thinner than M4/M5/M6's — a single sentence, no elaborated dimensions the way Router's five policy axes were already spelled out before M6 began. The scope in this document was worked out through direct design discussion with velasari (crosstalk, 2026-07-26 night session — Kaushik asleep, explicitly authorized to co-think rather than escalate and wait) rather than lifted from a pre-existing architecture.md section, the way M6's stories were.

**The one load-bearing constraint that *is* already fixed, from `architecture.md` itself:** *"The loop IS the orchestrator. There is no separate Orchestrator component... It is a behaviour of the loop, not a structural box."* M7 does not introduce a new component named `Orchestrator` — "Orchestrator" is the milestone name, not a class. What M7 actually builds is the mechanism for the loop's Act phase to dispatch one instruction to **multiple** Worker adapters simultaneously ("the committee") instead of exactly one, and for the loop's existing gather-then-reason seam to do the synthesis — a capability `architecture.md`'s Worker row already named as a future possibility ("Multiple Workers may run per Act phase; results are gathered in Observe") but M1 through M6 never built.

**Three design questions this milestone had to answer that the roadmap line didn't** (worked out with velasari, not invented unilaterally):

1. **Does committee mode fan out by default, or only when explicitly triggered?** Explicitly triggered. Default fan-out would directly contradict RT-5's whole point (M6 — reserve subscription/API capacity, most instructions are cheap/single-provider) and would make every ACT N times more expensive. `architecture.md`'s Router bullet list already names *"Consortium override"* as one of Router's own policy dimensions, in the same list `RT-8`'s single-provider override came from — "override" is the operative word: an exception state, not a default.
2. **Where does synthesis happen — a new dedicated step, or the existing loop seam?** The existing seam, unchanged. `architecture.md`'s own sentence above answers this directly: Act dispatches to N Workers, Observe gathers all N results, and the **next Reason cycle** synthesizes them as part of normal reasoning — no new `Intent` kind, no new PRAO phase. The loop already has exactly this shape for one result; committee mode is "the same seam, more data in it."
3. **Is committee membership Router-driven or Conductor-driven?** Router-driven, for the same reason M6 kept all provider-allocation policy in Router: the Conductor's wire-format contract (`RESPOND`/`ACT`/`USE_SKILL`/`FINISH`) stays provider-agnostic — it never needs to know which providers exist or how many. `RoutePolicy` gains a `consortium_patterns` field, evaluated the same declarative, pattern-based way `privacy_patterns`/`capability_patterns` already are (M6's own Purpose section: *"deliberately NOT an NLP classifier... every field here is a plain glob/regex/length rule"*) — this milestone does not depart from that precedent.

**Explicit CLI-reachable trigger, not just a policy pattern.** M6's own dryrun-design-1 C1 finding is directly relevant precedent here: a feature reachable only through a policy pattern with no CLI-configuration surface (`--router-config` was deferred) risks shipping unverifiable-through-the-real-interface, or worse, silently unreachable. To avoid repeating that exact failure class, `--provider` gains a third choice, `"committee"` — an explicit override (mirroring RT-8's existing single-provider override mechanism exactly), giving every behavioral AC in this document a guaranteed real-CLI path independent of whether `consortium_patterns` configuration ever gets a CLI surface.

---

## User Stories

---

### OR-1 — Committee mode is explicit, not default fan-out

**Purpose:** Establishes the trigger boundary this whole milestone depends on. Every other story assumes committee mode is an exception state the caller opted into — if this story's AC is wrong, every cost/behavior assumption in the rest of this document breaks.

**As a** user running Axiom normally,
**I want** ordinary ACT dispatches to continue going to exactly one provider, unchanged from M6,
**so that** M7 doesn't silently multiply my API/subscription usage without me asking for it.

**Acceptance Criteria:**
- Without `--provider committee` and without a `consortium_patterns` match, `Router` behavior is byte-for-byte unchanged from M6 — single `WorkerSelection`, same precedence chain, same fallback behavior.
- `--provider committee` (new CLI choice, mirroring `--provider claude`/`--provider local`'s existing override mechanism) forces committee mode for every ACT dispatch in the session, bypassing policy evaluation entirely — same override semantics RT-8 already established.
- **[behavioral]** A live `axiom-cli` run with **no** `--provider` flag and no consortium configuration completes using exactly one provider per ACT dispatch (observable via `--observe`'s trace: exactly one `act` span per ACT cycle, `axiom.router.provider` naming a single provider) — proving M7 introduced no default behavior change for the common case.

---

### OR-2 — Router selects a committee, not just a single Worker, when triggered

**Purpose:** The concrete mechanism question 3 (Purpose section) resolves to. `Router` needs a way to express "dispatch to all of these" without breaking `select_worker()`'s existing single-`WorkerSelection` contract, which M6's loop.py, tests, and every other caller already depend on unchanged.

**As a** developer extending Router's dispatch surface,
**I want** a separate `Router.select_committee(instruction)` method returning `list[WorkerSelection] | None` (`None` when committee mode doesn't apply),
**so that** `select_worker()`'s existing single-dispatch contract (M6, unchanged) is never touched, and the loop can cleanly check "is this a committee dispatch?" before falling through to the existing single-provider path.

**Acceptance Criteria:**
- `Router.select_committee(instruction: str) -> list[WorkerSelection] | None` returns `None` when neither `--provider committee` is forced nor `consortium_patterns` matches the instruction — the loop's existing `select_worker()` call path handles that case exactly as it does today.
- When triggered (override or pattern match), returns one `WorkerSelection` per configured adapter (capped by `max_committee_size`, OR-8), each with its own real `provider_name`/`control_level` — not placeholder/duplicate entries.
- `select_worker()`'s own signature, return type, and behavior are unmodified by this story (M6's existing unit tests for `select_worker()` continue to pass unchanged).

---

### OR-3 — Act phase dispatches to every committee member for the same instruction

**Purpose:** The actual "consortium" behavior — one `ActIntent.instruction` reaching multiple providers, each forming an independent opinion on the same bounded task.

**As** the Axiom loop executing an ACT cycle in committee mode,
**I want** the same `instruction` string dispatched to every `WorkerSelection` in the committee,
**so that** each provider genuinely answers the identical question, making their results comparable.

**Acceptance Criteria:**
- When `Router.select_committee()` returns a non-`None` list, the loop calls `.act(instruction)` on every member's adapter with the **same, unmodified** instruction string — no per-member instruction variation.
- Each member's result is captured independently — one member's return value must not overwrite or be lost because of another member's concurrent/sequential execution.
- **[behavioral]** A live `axiom-cli --provider committee` run with an instruction requiring a real answer shows (via `--observe`'s trace) one `act` span per configured provider for that single ACT cycle, each carrying its own `axiom.router.provider` value — proving genuine per-member dispatch, not one call relabeled twice.

---

### OR-4 — Synthesis happens in the existing Reason seam, no new intent or phase

**Purpose:** Directly implements Purpose question 2's resolution. This is the story that keeps M7 from becoming "a new Orchestrator component" in violation of `architecture.md`'s explicit constraint — synthesis must be something the *existing* loop already does, just fed richer input.

**As** the Axiom loop's Reason phase,
**I want** the next reasoning cycle to see all committee members' results (each attributed to its provider) via the same history-rendering path a single ACT result already uses,
**so that** the Conductor synthesizes across opinions using its own reasoning — no new `Intent` kind, no dedicated "synthesis" mechanism to build or maintain.

**Acceptance Criteria:**
- Committee results are gathered into `run_state.history` via the **existing** `ObservePort.observe()` call — one call, one combined, provider-attributed string (e.g. `"[claude]: <result>\n[local]: <result>"`), not N separate `observe()` calls and not a new run-state field.
- `PraoAdapterBase.perceive()`'s existing `[TOOL EXECUTION RESULTS]` rendering (M1, unchanged) is what carries the combined result into the next Reason cycle's context — no new section header, no new rendering path.
- No new `IntentKind` is added. The Conductor's wire-format contract (`RESPOND`/`ACT`/`USE_SKILL`/`FINISH`) is unmodified by this story.
- **[behavioral]** A live `axiom-cli --provider committee` run's final response demonstrably reflects information that could only have come from **more than one** provider's distinct answer (e.g., each provider given a distinguishing instruction-embedded marker, both markers referenced in the synthesized final response) — proving synthesis genuinely happened in Reason, not that only one member's result silently won.

---

### OR-5 — Precedence: privacy is absolute, even over committee mode

**Purpose:** M6 established privacy as a hard, unconditional gate (RT-4) that even RT-8's explicit override doesn't bypass in the *policy-driven* path (only an explicit single-provider override bypasses it, by that story's own deliberate design). Committee mode must not become a backdoor that fans privacy-gated content out to non-local providers.

**As a** user with privacy-sensitive content,
**I want** a privacy-pattern match to route to local-only, never fanned out to a committee that includes non-local providers,
**so that** committee mode can never leak privacy-gated content to a subscription/API provider.

**Acceptance Criteria:**
- Precedence order in `Router`'s combined evaluation: privacy (RT-4) > consortium (`consortium_patterns` match) > capability (RT-6) > bulk-default (RT-5) > Conductor-fallthrough — consortium sits second, directly after privacy, ahead of capability and bulk-default.
- An instruction matching **both** `privacy_patterns` and `consortium_patterns` routes to the single local-only path (RT-4's existing behavior) — `select_committee()` returns `None` for it, `select_worker()` handles it exactly as M6 already does.
- `--provider committee` (the explicit override) is **not** exempted from this rule the way `--provider claude`/`--provider local` exempt privacy evaluation entirely (RT-8/D5's precedent) — the difference: single-provider override is trusted human intent about *which one* provider, but committee override doesn't get to decide privacy-gated content leaves the local boundary. (Design decision — see `design.md` for the exact mechanism; this AC fixes the required outcome, not the implementation.)

---

### OR-6 — Per-slot failure tolerance: one committee member failing doesn't kill the vote

**Purpose:** The entire value of a committee is redundancy — if any single member's failure aborted the whole dispatch, committee mode would be *more* fragile than single-provider dispatch, not more resilient, defeating its own purpose.

**As** the Axiom loop running a committee dispatch,
**I want** an individual member's `AdapterError` captured and noted (not propagated), while the remaining members' results are still gathered,
**so that** the committee's synthesis still has value even when one voice drops out.

**Acceptance Criteria:**
- A single committee member's `.act()` raising `AdapterError` does not abort the ACT cycle — that member's contribution is recorded as a failure note (e.g. `"[claude]: FAILED — <error>"`) in the same combined history string OR-4 describes, and dispatch to the remaining members proceeds/completes normally.
- If **every** committee member fails, the cycle raises `AdapterError` (propagates exactly as a single-provider dispatch failure already does today) — a committee where nobody answered is not silently treated as success.
- **[behavioral]** A live run with one committee member deliberately made unreachable (e.g. `--ollama-host` pointed at a dead address, forcing the local member to fail) while the other member succeeds still produces a complete, non-error final response — proving graceful per-slot degradation, not an all-or-nothing failure.

---

### OR-7 — RT-9's live fallback stays scoped to single-provider dispatch; it does not activate inside committee mode

**Purpose:** Resolves the RT-9 interaction question raised during design discussion. RT-9's fallback exists because losing your *only* provider means losing the whole ACT — that urgency doesn't apply per-member in committee mode (OR-6 already handles individual failures gracefully), and structurally, in a 2-provider world "the committee" already *is* every configured provider — there is no third provider left to substitute in as a fallback for a failed committee slot.

**As a** developer reasoning about M7's failure model,
**I want** `select_fallback_worker()` to remain exclusively a single-provider-dispatch mechanism, never invoked from the committee-dispatch code path,
**so that** the two failure-handling mechanisms (OR-6's per-slot tolerance, RT-9's single-hop fallback) don't overlap or interact in an untested way.

**Acceptance Criteria:**
- The committee-dispatch code path never calls `Router.select_fallback_worker()` — a failed committee member's slot is handled exclusively per OR-6 (noted, not substituted).
- M6's existing RT-9 fallback tests and behavior (single-provider dispatch, `AdapterError` → one fallback hop) are unmodified by this milestone.

---

### OR-8 — `max_committee_size`: a forward-looking cost-safety cap

**Purpose:** Consortium mode is the direct economic opposite of RT-5's whole point (M6 — reserve subscription capacity for what needs it); an N-way fanout costs N times a single dispatch. In today's 2-provider world this is naturally bounded, but the field exists so a badly-scoped `consortium_patterns` config doesn't silently become unboundedly expensive once a third (or more) adapter exists (`design.md` of M6 already named this as a plausible future: "Router's shape is not hardcoded to exactly two providers").

**As a** developer configuring `RoutePolicy`,
**I want** `max_committee_size: int` capping how many adapters `select_committee()` includes,
**so that** future growth in the number of configured providers doesn't silently and unboundedly increase per-ACT cost.

**Acceptance Criteria:**
- `RoutePolicy` gains `max_committee_size: int | None`, where `None` (the default) means "use however many adapters are configured" — resolved against the actual `adapter_factories` count wherever `Router` evaluates it (today: 2 — a no-op cap; becomes a real limit once more providers are configured). A `RoutePolicy` is constructed independently of any `Router`, so it cannot itself know the adapter count in advance — `None` is how it defers that resolution rather than guessing a concrete number.
- `select_committee()` never returns more than `max_committee_size` `WorkerSelection`s, even if more adapters are configured — selection among available adapters when capped is deterministic (documented in `design.md`, not left to iteration-order chance).

---

### OR-9 — M7 verified live via CLI

**Purpose:** Matches the standing verification bar from every prior milestone (M1 through M6) — proven end-to-end through the real interface, not just unit-tested in isolation.

**As a** developer signing off M7,
**I want** committee dispatch, synthesis, per-slot failure tolerance, and the privacy/precedence guarantee each demonstrated live via `axiom-cli`,
**so that** the milestone's actual value — a genuine multi-provider consortium — is proven working, not just structurally present.

**Acceptance Criteria:**
- OR-1's, OR-3's, OR-4's, and OR-6's behavioral ACs are each demonstrated live and recorded, matching the M1/M3/M4/M5/M6 sign-off pattern.

---

## Infrastructure Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| M6 Router (`RoutePolicy`, `Router`, `WorkerSelection`) | Exists, merged to master (`0710667`) | M7 branches from `master` directly (M6 fully merged, no unmerged-branch dependency question this time, unlike M5's fork off M4). |
| `ClaudeAdapter`/`LocalAdapter` | Exist | No structural change to either adapter's `act()` — committee dispatch calls the existing method N times, once per member. |

---

## Configuration Summary

### `RoutePolicy` additions

```
consortium_patterns: list[str] = []   # OR-2 — same glob/regex mechanism as privacy/capability
max_committee_size: int | None = None   # OR-8 — None = "use however many adapters are configured"
```

### CLI

```
--provider {claude,local,committee}   # "committee" is new (OR-1) — mirrors the existing single-provider override mechanism
```

---

## Out of Scope

- **`--router-config` / any CLI surface for `consortium_patterns`** — same deferred posture M6 already established for privacy/capability patterns; `--provider committee` is the only CLI-reachable trigger this milestone builds.
- **Weighted/ranked synthesis logic** — OR-4 explicitly leaves synthesis entirely to the Conductor's own reasoning over the combined history string; no scoring, voting, or ranking mechanism is built.
- **Fallback substitution inside committee mode** — explicitly ruled out per OR-7's own reasoning; a failed slot is never backfilled with an alternate provider.
- **A committee size larger than the number of configured adapters** (e.g. querying the same provider twice with different sampling) — `select_committee()`'s membership is one `WorkerSelection` per distinct configured provider, not a general N-samples mechanism.
- **Concurrent/parallel dispatch performance guarantees** — `design.md` decides whether committee members are dispatched sequentially or concurrently (via `asyncio.gather`-style fan-out); this requirement does not mandate one or the other, only that each member's result is captured independently and correctly (OR-3's AC).

---

## Definition of Done (M7 complete when ALL of these pass)

1. **Spec gate:** `requirement.md`, `design.md`, `task.md` exist; `dryrun-design-N.md`'s latest verdict has zero critical, zero warning, zero observation findings.
2. **Code dryrun gate:** the latest `dryrun-code-N.md` verdict has zero bugs, zero gaps, zero warnings, zero style findings.
3. **No new structural component:** `Router.select_committee()` lives in the existing `axiom/router/` package; no new `axiom/orchestrator/` package or `Orchestrator` class is introduced (matches `architecture.md`'s explicit "loop IS the orchestrator" constraint).
4. **Precedence enforced and tested:** privacy > consortium > capability > bulk-default > Conductor-fallthrough, with explicit tests proving privacy beats consortium specifically (OR-5), not just each rule tested in isolation.
5. **Unit tests green:** new `tests/test_router_committee.py` (or equivalent) covering `select_committee()`'s triggering, membership, capping (OR-8), and the loop's per-slot failure tolerance (OR-6) / all-fail propagation, with no skips.
6. **Full suite green:** the whole `pytest` suite (pre-existing + new) passes.
7. **Live verification:** OR-9's cross-story demonstrations are all completed and recorded.
