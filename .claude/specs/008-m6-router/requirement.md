# M6 · Router (full) — Requirements

**Spec:** `008-m6-router`
**Milestone:** M6 — "Router (full): the complete intent→provider policy (local / sub / API, privacy gate, volume, fallback). Minimal version was seeded in M1." (`001-agent-core-roadmap.md`)
**Status:** DRAFT

---

## Purpose

M6 replaces the M1-era Router stub — a single CLI flag (`provider="claude"|"local"`) baked once into `Agent.__init__` and never revisited — with the real policy engine `architecture.md` describes: *"The intent → provider allocation brain... it receives the loop's intent and selects which Agent port adapter should handle this request, according to policy: privacy gate, cost/volume, capability, control-level preference, consortium override / live fallback."*

**Two distinct routing decisions, not one.** `architecture.md`'s own Conductor/Worker table draws this distinction structurally (`Conductor | Reason phase`, `Worker | Act phase`), and M6 resolves a previously-open question (`architecture.md` OQ-1) about how each is bound:

1. **Conductor selection (Reason phase)** — **fixed once per session** (Kaushik's decision, 2026-07-26, resolving OQ-1: stable identity/session coherence wins over per-cycle dynamic optimization). Chosen once at `Agent.__init__` time, before any user turn exists, and used for every `reason()` call for the lifetime of that `Agent` instance.
   **Correction to `architecture.md`:** the Conductor/Worker table's current wording — *"[Conductor] Re-evaluated each cycle (reactive, not a pre-planned DAG)"* — describes the *loop's* reactive re-evaluation of *intent* each cycle (still true — Reason still runs fresh every cycle), not re-selection of *which provider* plays Conductor. That provider-selection question is what OQ-1 asked and this milestone answers: fixed per session. Recorded here as the correction, per M4's own precedent (D3-class note) of documenting a correction without rewriting `architecture.md` mid-milestone.
2. **Worker selection (Act phase)** — re-evaluated **per ACT dispatch** (every cycle), since each `ActIntent` carries a fresh `instruction` string the Router can weigh independently — this is uncontested by OQ-1, which was specifically about the Conductor.

**What "policy" means here — deliberately explicit, not inferred.** `cost/volume`, `privacy`, and `capability` signals are **structured, declarative rules** the Router evaluates against an `ActIntent.instruction` string (pattern/glob/length-based), not a fuzzy NLP classifier. This keeps every routing decision deterministic and testable — an unverifiable heuristic ("looks privacy-sensitive to an LLM judge") would violate this project's testable-acceptance-criteria bar and isn't buildable to a behavioral AC. Building a real content classifier is explicitly out of scope (see Out of Scope).

**Two adapters exist today** (`ClaudeAdapter` KIND-B, `LocalAdapter` KIND-A) — no true-API adapter yet (roadmap's tech stack lists it as "later-milestone, not locked"). M6 builds the **policy engine and its seam** against these two; richer multi-provider *simultaneous* consortium dispatch is `architecture.md`'s Router "consortium override" wording overlapping with **M7 — Orchestrator** ("multi-provider consortium — the committee") — M6's own consortium-override story (RT-8) is scoped to *explicit single-provider override*, not simultaneous multi-provider dispatch, which stays M7's job.

---

## User Stories

---

### RT-1 — Router as a core-side component, not a port

**Purpose:** `architecture.md` is explicit that the Router is *"a core-side component (not a port)"* — unlike the six ports (Agent, Memory, Tools, Skills, Connectors, I/O Gateway), it isn't an adapter seam; it's policy logic living in the sovereign core, consuming the Agent port's adapters as its mechanism. Establishing this as a real, separate component (not more `if provider == ...` branches in `agent.py`) is the structural foundation every other story in this milestone builds on.

**As a** developer extending Axiom's provider policy,
**I want** a `Router` class (`axiom/router/router.py`) that owns provider-selection policy, separate from `Agent`'s composition-root responsibilities,
**so that** routing logic is one auditable, testable place — not scattered across `agent.py`'s constructor.

**Acceptance Criteria:**
- `axiom/router/router.py` defines a `Router` class. `axiom/router/policy.py` defines the declarative policy rule types (RT-4/RT-5/RT-6's shapes).
- `Router` imports only `axiom.interfaces`-level concepts and the provider adapter classes it selects between — it does not import `axiom.loop` (mirrors the existing import-boundary discipline `loop.py` itself already documents for its own dependencies).
- `agent.py`'s `Agent.__init__` constructs a `Router` and asks it for the Conductor adapter once; `PraoLoop`'s Act-phase dispatch (or an adapter-selecting wrapper around it) asks the Router for the Worker adapter each cycle — `agent.py` no longer contains provider-selection `if`/`elif` branching itself (that logic moves into `Router`).
- **[behavioral]** Running `axiom-cli` with no provider-forcing flags at all completes a normal turn successfully (proving `Router`'s default policy path is reachable end-to-end through the real CLI, not just constructible in a unit test).

---

### RT-2 — Conductor is selected once per session, not re-evaluated per cycle

**Purpose:** Resolves `architecture.md` OQ-1 per Kaushik's decision. A fixed Conductor gives session-coherent behavior (the same "mind" reasons across every cycle of a run) — the trade-off `architecture.md` named (dynamic quality-cost optimization) is explicitly declined in favor of stable identity.

**As a** user running an interactive Axiom session,
**I want** the same provider to serve every Reason-phase call for the whole session,
**so that** the agent's reasoning doesn't visibly change character mid-conversation.

**Acceptance Criteria:**
- `Router.select_conductor(...)` is called exactly once, at `Agent.__init__` time, and its result (an adapter instance / provider identifier) is reused for every subsequent `reason()` call for that `Agent`'s lifetime — never re-invoked mid-session.
- With no override and no privacy signal present (RT-4), `select_conductor()` returns the capability-preferred default (RT-6: the strongest available reasoner — `ClaudeAdapter`, matching the roadmap's existing framing of subscription-Claude as first-choice).
- **[behavioral]** A multi-turn `axiom-cli` session (two `Agent.run()` calls against the same `Agent` instance, or two `axiom-cli` invocations sharing a session concept if the CLI supports one) demonstrably uses the same provider for both turns' Reason phase — observable via `--observe`'s trace (`provider_kind` attribute on the `reason` phase span is identical across turns).

---

### RT-3 — Worker is selected per ACT dispatch

**Purpose:** Unlike the Conductor, each `ActIntent` is a fresh, independent unit of work with its own `instruction` string — the Router can and should weigh routing policy (privacy/cost/capability) against *that specific instruction*, not a session-wide default, since different instructions within the same session may have very different policy-relevant characteristics (e.g., one ACT touches a privacy-sensitive path, the next doesn't).

**As** the Axiom loop dispatching an ACT,
**I want** `Router.select_worker(instruction)` consulted fresh for every `ActIntent`,
**so that** per-instruction policy (RT-4/RT-5/RT-6) actually has something to act on.

**Acceptance Criteria:**
- `Router.select_worker(instruction: str)` is called once per `ActIntent` dispatch (i.e., once per loop cycle that reaches the ACT branch) — not cached across cycles within the same run.
- Two different `ActIntent.instruction` values within the *same* session can route to two *different* providers (demonstrating RT-3 is genuinely per-dispatch, not a session-level decision like the Conductor).
- **[behavioral]** A live `axiom-cli` run whose single turn triggers two ACT cycles with different instructions (one matching a configured privacy-sensitive pattern per RT-4, one not) shows — via `--observe`'s trace — two `act` phase spans with different `provider_kind` values.

---

### RT-4 — Privacy gate: a configured sensitive-path/pattern routes to local, unconditionally

**Purpose:** `architecture.md`'s first-listed policy dimension. The concrete, testable shape: a declarative list of patterns (glob-style path patterns, or substring/regex patterns against the instruction text) that, when matched, **force** local (KIND-A) regardless of any other policy signal — privacy is a hard override, not a weighted preference, because the whole point is a guarantee, not a heuristic best-effort.

**As a** user working with privacy-sensitive local files or content,
**I want** any instruction matching a configured sensitive pattern to be gated to the local provider, no exceptions,
**so that** sensitive content is never sent to a subscription/API provider even when capability policy would otherwise prefer it.

**Acceptance Criteria:**
- `RoutePolicy` (`axiom/router/policy.py`) carries a `privacy_patterns: list[str]` field (glob or regex, configurable) — empty by default (no privacy gating unless explicitly configured, since Axiom has no way to know what's sensitive without being told).
- `Router.select_worker(instruction)` checks `instruction` against `privacy_patterns` **first**, before any capability/cost evaluation (RT-4 is checked before RT-5/RT-6, per "privacy gate" being a gate, not a weighted factor) — a match forces `LocalAdapter` (KIND-A) regardless of what capability/cost policy would otherwise select.
- If `privacy_patterns` is non-empty and matches, but no `LocalAdapter` is available/configured for this session, `Router.select_worker()` raises a clear, typed error (`RouterError` or similar) rather than silently falling back to a non-local provider — privacy is a hard constraint, silent fallback would violate the guarantee.
- **[behavioral]** With a privacy pattern configured to match a specific working-dir-relative path, an `axiom-cli` run whose instruction references that path completes via the local provider (observable via `--observe`'s `provider_kind=KIND_A` on that ACT's spans) even when run with `--provider claude` as the session's *Conductor* choice — proving the Worker-level privacy gate overrides independently of Conductor selection.

---

### RT-5 — Cost/volume: short, low-complexity instructions prefer local

**Purpose:** `architecture.md`'s second policy dimension — "bulk or low-complexity tasks route to local," i.e. don't spend subscription-Claude's stronger (and costlier, rate-limited) capability on trivial work the local model can handle.

**As** the Axiom system,
**I want** short, simple ACT instructions to default toward the local provider when no privacy or capability signal overrides it,
**so that** subscription/API capacity is reserved for work that actually needs it.

**Acceptance Criteria:**
- `RoutePolicy` carries a `bulk_threshold_chars: int` (configurable, with a sane default) — an `instruction` at or under this length, with no capability-override match (RT-6) and no privacy match (RT-4), routes to `LocalAdapter`.
- This is the lowest-priority signal: privacy (RT-4) and capability (RT-6) both take precedence — RT-5 is the *default-when-nothing-else-applies* rule, not a competing weighted vote.
- **[behavioral]** A live `axiom-cli` run with a short instruction under the configured threshold (and no capability/privacy match) demonstrably dispatches that ACT to the local provider — observable via `--observe` trace.

---

### RT-6 — Capability: patterns indicating hard reasoning or rich tool use prefer the strongest available provider

**Purpose:** `architecture.md`'s third dimension — the counterweight to RT-5. Some instructions genuinely need the strongest available reasoner (complex multi-step tool use, code generation, anything the local model has already-documented weak-model failure modes for, per `local_adapter.py`'s own extensive comments on qwen2.5:7b's limitations).

**As a** user issuing a complex instruction,
**I want** it routed to the strongest available provider even if it's short enough to otherwise qualify for RT-5's local-by-default rule,
**so that** capability need overrides a bulk/cost heuristic that would otherwise misroute it.

**Acceptance Criteria:**
- `RoutePolicy` carries a `capability_patterns: list[str]` (configurable) — an `instruction` matching one of these routes to the capability-preferred provider (`ClaudeAdapter`) regardless of RT-5's length threshold.
- Precedence, made explicit and tested: RT-4 (privacy) > RT-6 (capability) > RT-5 (cost/volume default). A privacy-pattern match always wins even over a capability-pattern match (an instruction can't be routed to a non-local strong provider just because it looks complex, if it also touches sensitive content).
- **[behavioral]** A live `axiom-cli` run with a short instruction (under RT-5's bulk threshold) that also matches a configured capability pattern demonstrably routes to Claude, not local — proving RT-6 overrides RT-5's default when both could apply.

---

### RT-7 — Control-level is a real, queryable adapter attribute

**Purpose:** `architecture.md`'s fourth dimension, "control-level preference," presupposes adapters expose their `control_level` (KIND A / KIND B) as data the Router can read — today `control_level` exists only as prose in `architecture.md`, not as code anywhere in the adapters. M6 makes it real, closing that gap, so control-level can actually participate in policy (e.g., a future policy rule "prefer runtime-gatable KIND-A when the Guardrails GATE's mid-run veto matters more than raw capability" — the *rule* itself is a plausible future refinement, but the *data* must exist now for any such rule to be buildable).

**As a** developer writing Router policy,
**I want** every adapter to expose a `control_level: Literal["KIND_A", "KIND_B"]` class or instance attribute,
**so that** control-level can be read and reasoned about by policy code, not just documented in prose.

**Acceptance Criteria:**
- `ClaudeAdapter.control_level == "KIND_B"`, `LocalAdapter.control_level == "KIND_A"` — both readable without constructing a full adapter instance (class attribute) or trivially available on a constructed instance.
- `Router` records which `control_level` it selected for both the Conductor (RT-2) and each Worker dispatch (RT-3) into the observability trace (an OTel span attribute, e.g. `axiom.control_level`) — matching the existing `provider_kind` attribute pattern already on every phase span, so control-level is auditable the same way provider choice already is.
- **[behavioral]** `--observe`'s trace for a live `axiom-cli` run shows `axiom.control_level` populated correctly (`KIND_B` for a Claude-routed span, `KIND_A` for a local-routed span) — not just `provider_kind`, which already existed pre-M6.

---

### RT-8 — Explicit override: a CLI flag forces a specific provider, bypassing policy entirely

**Purpose:** `architecture.md`'s "consortium override" dimension, scoped for M6 (per this doc's Purpose section) to explicit single-provider override — the user (or an automated caller) must always be able to force a specific provider and trust that policy won't second-guess them, for debugging, cost control, or simply not trusting the heuristics yet.

**As a** user who wants explicit control,
**I want** `--provider claude`/`--provider local` (the existing CLI flags) to force that provider for **both** Conductor and every Worker dispatch, bypassing all policy evaluation (RT-4 through RT-6),
**so that** I retain a reliable manual escape hatch from the automatic policy.

**Acceptance Criteria:**
- When `--provider` is explicitly passed, `Router.select_conductor()` and every `Router.select_worker()` call return that forced provider unconditionally — no privacy/cost/capability pattern evaluation occurs at all (not even privacy — an explicit human override is trusted; RT-4's *unconditional* force applies only in the *no-override* policy-driven path).
- This preserves the pre-M6 CLI contract exactly: `axiom-cli --provider local ...` continues to behave exactly as it did before M6 (100% local, no surprises) — M6 must not be a breaking change for existing explicit-provider usage.
- **[behavioral]** A live `axiom-cli --provider local` run with an instruction that would otherwise match a configured capability pattern (RT-6, which would normally route to Claude) still executes entirely on the local provider — proving the override genuinely bypasses policy rather than just being a "strong preference."

---

### RT-9 — Live fallback: a failed provider falls back to the other, once, with the failure surfaced

**Purpose:** `architecture.md`'s "live fallback" dimension. Providers fail (auth issues, network problems, the Ollama-crash class of failure this project's own M5 live verification already hit) — a Router that can't route around a dead provider isn't meaningfully more resilient than the M1 stub it replaces.

**As a** user whose selected provider fails mid-session,
**I want** the Router to retry once with the other available provider rather than immediately failing the turn,
**so that** a transient or provider-specific failure doesn't necessarily fail my request when a working alternative exists.

**Acceptance Criteria:**
- If the Worker adapter selected for an ACT dispatch raises `AdapterError`, `Router`/the loop retries that same ACT dispatch exactly once against the other available provider (if one is configured/available) before propagating the error.
- Fallback is **not** attempted when `--provider` was explicitly forced (RT-8) — an explicit override means the user does not want a silent substitution; a forced-provider failure propagates immediately, unchanged from pre-M6 behavior.
- Fallback is **not** attempted when RT-4's privacy gate forced the local provider — falling back to a non-local provider on a privacy-gated instruction would violate RT-4's guarantee; a privacy-gated local failure propagates immediately.
- A fallback event is logged (DEBUG level, consistent with the project's existing `[TAG]`-prefixed logging convention, e.g. `[ROUTER_FALLBACK]`) recording which provider failed and which it fell back to — auditable, not silent.
- **[behavioral]** A live demonstration (e.g., pointing `--ollama-host` at an unreachable address while policy would otherwise route a bulk/no-override instruction to local) shows the turn completing successfully via the fallback provider, with the `[ROUTER_FALLBACK]` log line present — not a hard failure.

---

## Infrastructure Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| M4 Guardrails GATE, M5 Skills | Exists, merged to master (`2593fe8`) | M6 branches from `feature/m5-skills` (now master) — no separate branch-dependency decision needed this time, unlike M5's fork off the then-unmerged M4 branch. |
| `ClaudeAdapter` / `LocalAdapter` | Exist | RT-7 adds `control_level` to both; no other structural change to either adapter's own `reason()`/`act()` internals — Router wraps *selection*, not adapter internals. |
| Observability (M2) | Exists | RT-2/RT-3/RT-7's behavioral ACs depend on `--observe`'s existing trace mechanism (`provider_kind` attribute already present; RT-7 adds `axiom.control_level`). |

---

## Configuration Summary

### Constructor / policy parameters

```
RoutePolicy(
    privacy_patterns: list[str] = [],       # RT-4 — glob/regex; empty = no gating
    bulk_threshold_chars: int = <default>,  # RT-5 — instruction length cutoff
    capability_patterns: list[str] = [],    # RT-6 — glob/regex
)
```

No new environment variables. A `--router-config <path>` CLI flag (to load `RoutePolicy` from a file rather than only in-process construction) is left to `design.md` to decide as trivial-or-deferred, matching M4/M5's own posture toward optional CLI surface.

---

## Out of Scope

- **NLP/LLM-based content classification for privacy/cost/capability signals** — RT-4/RT-5/RT-6 are pattern/length-based and deterministic by design (see Purpose). A smarter classifier is a plausible future refinement, not M6.
- **Simultaneous multi-provider consortium dispatch** ("ask both providers, synthesize") — `architecture.md`'s "consortium override" wording overlaps with **M7 — Orchestrator**; M6's RT-8 is single-provider override only.
- **A third (true-API) adapter** — the roadmap's tech stack lists this as a later, not-yet-locked milestone tech choice; M6's policy engine is built to be adapter-count-agnostic in shape, but only `ClaudeAdapter`/`LocalAdapter` exist to route between today.
- **Retry beyond one fallback attempt** — RT-9 is a single fallback hop, not a retry-with-backoff loop across N providers.
- **Persisted/learned routing policy** (e.g., "this instruction pattern historically failed on local, avoid it") — static, explicitly-configured policy only; no learning loop (that class of concern belongs to **M8 — Self-correction**).
- **`--router-config` CLI flag** — deferred-or-trivial, left to `design.md` (same posture as M4/M5's own optional-flag decisions).

---

## Definition of Done (M6 complete when ALL of these pass)

1. **Spec gate:** `requirement.md`, `design.md`, `task.md` exist; `dryrun-design-N.md`'s latest verdict has zero critical, zero warning, zero observation findings.
2. **Code dryrun gate:** the latest `dryrun-code-N.md` verdict has zero bugs, zero gaps, zero warnings, zero style findings.
3. **Router seam:** `Router` class exists (`axiom/router/router.py`), core-side (not a port), consumed by `agent.py`/the loop's Act dispatch per RT-1.
4. **Precedence enforced and tested:** RT-4 (privacy) > RT-6 (capability) > RT-5 (cost/volume default), with explicit unit tests proving the ordering, not just each rule in isolation.
5. **Unit tests green:** new `tests/test_router_*.py` covering Router policy evaluation (all precedence combinations), Conductor fixed-per-session behavior, Worker per-dispatch behavior, fallback (including the no-fallback-on-override and no-fallback-on-privacy-gate exclusions), with no skips.
6. **Full suite green:** the whole `pytest` suite (pre-existing + new) passes.
7. **Live verification:** every behavioral AC (RT-1 through RT-9) demonstrated and recorded, matching the M1/M3/M4/M5 sign-off pattern.
