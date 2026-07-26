# M5 · Skills — Requirements

**Spec:** `007-m5-skills`
**Milestone:** M5 — "agentskills.io progressive disclosure; self-authoring" (`001-agent-core-roadmap.md`)
**Status:** DRAFT

---

## Purpose

M5 gives Axiom its sixth and final architecture-defined port: **Skills** — "Self-authored, packaged capabilities the agent saves / searches / reuses. Higher-order than a Tool" (`001-agent-core/architecture.md`). Unlike Tools (M4), which is deliberately **adapter-side** (D1 in `006-m4-tools/design.md` — `loop.py`/`interfaces.py` import nothing from `axiom.tools`), Skills is named in `architecture.md` as a **loop-level port**, in the same list as Memory: the Perceiver / Context Assembler's job already includes "available tool/skill catalog" as part of what it assembles each cycle. M5 makes that real.

**What "progressive disclosure" means here**, per the open **Agent Skills** standard (agentskills.io, originally published by Anthropic, adopted by 40+ agent products including Claude Code itself): a skill is a directory containing a `SKILL.md` file (YAML frontmatter + Markdown body), optionally alongside `scripts/`, `references/`, `assets/`. Agents load skills in three stages — **discovery** (name + description only, ~100 tokens, always in context), **activation** (the full `SKILL.md` body loads when a task matches), **execution** (bundled files load only as needed). M5 adopts this standard's on-disk format as-is rather than inventing a new one — Axiom-authored skills should be usable by any other agentskills.io-compatible agent, and skills authored elsewhere should be usable by Axiom.

**What "self-authoring" means here**: the agent can write a new skill to disk — using M4's already-gated `write_file` tool (M4 Non-Goal explicitly named this: "Tool registry exposed to Skills (M5) — M5 builds on top of M4's registry") — and have it appear in its own discovery catalog on a subsequent cycle, without a restart. No separate approval mechanism is introduced for this: `write_file` is already `DESTRUCTIVE` and gated by M4's `GuardrailsGate` (US-02/US-03 in `006-m4-tools/requirement.md`); authoring a skill is just a `write_file` call to a path under the skills directory.

**Dependency note (per crosstalk decision, 2026-07-26):** M4's `ToolsPort`/`GuardrailsGate`/`ToolRegistry` exist only on the unmerged `feature/agentcore-skeleton` branch — `master`'s `src/axiom/tools/` and `src/axiom/skills/` are still empty stubs. M5 branches off `feature/agentcore-skeleton` (has M4 already) rather than waiting on the master merge, which is separately on hold pending more incoming changes. This does not change M5's requirements, only where the branch starts from.

---

## User Stories

---

### SK-1 — Skills port contract: a loop-level port, not an adapter-side concern

**Purpose:** Skills is named in `architecture.md` as one of the 6 ports at the same level as Memory — the core loop consumes it directly (via Perceive), unlike Tools which is adapter-side (M4 D1). This story establishes that seam so every later story has a stable contract to build against, and so the loop stays provider-agnostic: neither `LocalAdapter` nor `ClaudeAdapter` should need their own skills-loading logic.

**As a** developer extending Axiom's capabilities,
**I want** a `SkillsPort` protocol with a small `SkillSpec` value-object contract, consumed by the core loop the same way `MemoryPort` already is,
**so that** skill storage is swappable (local filesystem today, something else later) without touching `loop.py`'s call sites.

**Acceptance Criteria:**
- `axiom/skills/port.py` defines a `SkillsPort` Protocol with at minimum `list_skills() -> list[SkillSpec]` (discovery-level: name + description only) and `get_skill(name: str) -> SkillContent` (activation-level: full parsed `SKILL.md`).
- `SkillSpec` carries `name` and `description` only — matching agentskills.io's discovery-stage payload (no body, no bundled-file contents).
- `loop.py`'s Perceiver call-point consumes `SkillsPort.list_skills()` directly (mirroring how it already consumes `MemoryPort` at Perceive), not through an adapter.
- **[behavioral]** Running `axiom-cli` with at least one valid skill present on disk and asking "what skills do you have available?" produces a response naming that skill — demonstrating the discovery-level catalog reached the Conductor's context via the real CLI, not just a unit-level `list_skills()` call.

---

### SK-2 — On-disk skill format conforms to the agentskills.io spec

**Purpose:** Adopting the open standard (rather than a bespoke Axiom format) means skills Axiom authors are portable to any other agentskills.io-compatible agent, and third-party skills are usable by Axiom unmodified. This is a deliberate reuse-before-build choice — the format, validation rules, and progressive-disclosure model already exist and are widely adopted.

**As a** skill author (human or the agent itself),
**I want** every skill Axiom recognizes to be a directory with a `SKILL.md` whose frontmatter is validated against the agentskills.io rules,
**so that** malformed skills fail loudly at discovery time instead of silently breaking activation later.

**Acceptance Criteria:**
- A skill directory is `{skills_dir}/{skill-name}/SKILL.md` (+ optional `scripts/`, `references/`, `assets/`), matching the spec's directory structure exactly.
- Frontmatter validation enforces: `name` required, 1-64 chars, lowercase alphanumeric + hyphens only, no leading/trailing/consecutive hyphens, **must match the parent directory name**; `description` required, 1-1024 chars, non-empty. Optional fields (`license`, `compatibility`, `metadata`, `allowed-tools`) are parsed if present but not required.
- A skill directory whose `SKILL.md` fails validation is excluded from `list_skills()`'s catalog and logged (DEBUG level, consistent with M4's audit-trail pattern) with the specific validation failure — it does not crash discovery for the other skills.
- **[behavioral]** Placing a skill directory with an invalid `name` (e.g. containing uppercase letters) under `{skills_dir}` and running `axiom-cli` shows that skill is *not* offered in the agent's response to "what skills do you have," while a validly-named sibling skill *is* — demonstrating the validation gate through the real CLI, not just a unit test of the parser.

---

### SK-3 — Progressive disclosure: discovery catalog every cycle, full body on activation

**Purpose:** This is the core mechanic the milestone is named for. Without it, "Skills" would just be a second Memory store — the point of progressive disclosure is bounding what's in context: every skill's name+description is cheap and always present, but a skill's full instructions (which may be substantial — the spec recommends keeping `SKILL.md` under 500 lines / ~5000 tokens) only enters context when the Conductor's own reasoning determines it's relevant to the current task.

**As** the Axiom system,
**I want** the discovery-level catalog (name + description of every valid skill) present in every Reason-phase context, and a skill's full `SKILL.md` body to enter context only on the cycle after the Conductor's intent names it,
**so that** Axiom can hold many skills "on hand" without paying their full context cost until one is actually needed.

**Acceptance Criteria:**
- Every Reason-phase invocation's assembled context includes the current discovery catalog (SK-1), refreshed each cycle (a skill authored mid-run, per SK-4, appears in the very next cycle's catalog — no restart needed).
- The Decision Interpreter recognizes a skill-activation intent (the Conductor naming a skill it wants to use) distinctly from RESPOND/ACT/FINISH, or as a parameter on ACT — the exact mechanism is a `design.md` decision, but the *observable* contract is fixed here: naming a skill causes that skill's full body to be assembled into context on a subsequent cycle.
- A skill's full body, once activated, is available for the remainder of the run (or until the run ends) — the Conductor does not need to re-request it every cycle.
- Activating a skill is a read-only operation — no Guardrails GATE approval is required (mirrors `read_file`/`list_dir` being `SAFE` in M4's classification table; reading a skill is not a `DESTRUCTIVE` act).
- **[behavioral]** A live `axiom-cli` run where the discovery catalog contains a skill named e.g. `csv-summarizer` (description: "summarizes CSV files; use when asked to analyze or summarize tabular/CSV data") and the user's prompt asks it to summarize a CSV file: the response demonstrably reflects instructions from that skill's `SKILL.md` body (e.g. following a specific format the skill prescribes that a generic response would not produce) — proving activation actually happened end-to-end, not just that the catalog was visible.

---

### SK-4 — Self-authoring: the agent writes a new skill via the existing gated `write_file` tool

**Purpose:** Closes the "self-authoring" half of the milestone name. No new write mechanism or new approval path is built — M4 already gates `write_file` as `DESTRUCTIVE`, and authoring a skill is nothing more than writing a correctly-shaped `SKILL.md` (and optional bundled files) to the right path. Reusing M4's existing gate (rather than inventing a Skills-specific one) is a deliberate DRY choice per the project's coding principles.

**As a** user directing Axiom to capture a repeatable procedure,
**I want** to ask Axiom to save what it just did (or a described procedure) as a reusable skill,
**so that** the same capability is available — via the discovery catalog — on this and future runs, without me re-explaining it each time.

**Acceptance Criteria:**
- The agent authors a new skill by calling `write_file` (M4, `DESTRUCTIVE`, gated) with a path under `{skills_dir}/{new-skill-name}/SKILL.md` and frontmatter+body content it composes itself.
- An authored skill that passes SK-2's validation appears in `list_skills()`'s catalog on the immediately following cycle (SK-3) — no separate "register skill" step and no process restart.
- An authored skill that fails SK-2's validation (e.g. the agent picks a `name` that doesn't match its own reasoning about the directory, or omits `description`) is rejected at discovery time the same way any other malformed skill is (SK-2) — the write itself still succeeds (it's just a file write); the *catalog* is what enforces validity.
- **[behavioral]** A live `axiom-cli` run: prompt the agent to "save what you just did as a skill called X," then start a **new** `axiom-cli` session and ask "what skills do you have?" — the response names skill X, proving the authored skill persisted to disk (SK-2's format) and was picked up by discovery in a fresh process, not just held in the first run's in-memory state.

---

### SK-5 — Skill search, for catalogs too large to hold entirely in context

**Purpose:** The discovery catalog (SK-3) is cheap per-skill (~100 tokens) but not free at scale — the spec itself frames progressive disclosure as the mechanism that lets an agent "keep many skills on hand." `SkillsPort` needs a search capability so the catalog assembled into context can be filtered/ranked rather than growing unbounded as the skill count grows.

**As** the Axiom system with a large or growing skill collection,
**I want** `SkillsPort.search(query: str) -> list[SkillSpec]` to return the most relevant skills for a given query,
**so that** Perceive can assemble a bounded, relevant slice of the catalog instead of every skill unconditionally.

**Acceptance Criteria:**
- `SkillsPort.search()` matches against `name` and `description` text (keyword/substring-level relevance is sufficient for M5 — no requirement for embedding-based semantic search; that's a plausible future refinement, not M5 scope).
- With a small number of skills (a handful, realistic for M5's own verification), `list_skills()` (unfiltered) remains the default catalog-assembly path — `search()` exists as a capability `SkillsPort` implementations must provide, but M5 does not mandate wiring an unconditional-search-instead-of-list-all policy into Perceive (that's a Router-adjacent policy decision better suited to a later milestone once real skill volume exists).
- **[behavioral]** Calling `search()` (via a live CLI-driven scenario, not just a unit test) with a query matching one of several present skills' description returns that skill and excludes an unrelated sibling skill — demonstrating the relevance filter actually discriminates, not just returns everything.

---

### SK-6 — Skills directory is configurable, defaults under the working directory

**Purpose:** M4 established `working_dir` as the scoping root for file/shell tools (`--working-dir`, `Agent.__init__`). Skills should follow the same convention rather than introducing a second, differently-configured root — consistency with an established pattern, not a new decision.

**As a** developer running Axiom in a given project directory,
**I want** the skills directory to default to a predictable location under `working_dir` and be overridable,
**so that** skills are naturally scoped per-project the same way M4's tools already are, without extra configuration in the common case.

**Acceptance Criteria:**
- `skills_dir` defaults to `{working_dir}/skills` and is a constructor parameter on `Agent.__init__` (mirroring `working_dir` itself), threaded the same way.
- If `{skills_dir}` does not exist, discovery returns an empty catalog (not an error) — an Axiom project with no skills yet is a valid, common starting state.
- **[behavioral]** Running `axiom-cli` from a working directory with no `skills/` subdirectory present completes normally (no crash, no error surfaced to the user) and, when asked "what skills do you have," the response reflects having none.

---

### SK-7 — M5 verified live via CLI on both providers

**Purpose:** Matches the standing verification bar from M1/M3/M4 — every milestone is verified by actually running `axiom-cli`, not just by a green unit-test suite, because unit tests cannot prove the progressive-disclosure *behavior* (catalog-then-activation) actually reaches the Conductor's real context on a real provider.

**As a** developer signing off M5,
**I want** discovery, activation, and self-authoring each demonstrated live on both `--provider claude` and `--provider local`,
**so that** the milestone's core claim — progressive disclosure works, self-authoring works — is proven end-to-end on both control-levels (KIND-A and KIND-B), not just one.

**Acceptance Criteria:**
- SK-1's discovery behavioral AC, SK-3's activation behavioral AC, and SK-4's self-authoring behavioral AC are each demonstrated on `--provider claude` **and** `--provider local`.
- Results are recorded as part of M5 sign-off, matching M1's MPP-5 latency log / M3's cross-session recall proof / M4's AC-08.5 pattern.

---

## Infrastructure Dependencies

| Dependency | Status | Notes |
|-----------|--------|-------|
| M4 Tools port (`ToolsPort`, `GuardrailsGate`, `write_file`) | Exists, unmerged | Lives on `feature/agentcore-skeleton`; M5 branches from there (see Purpose, dependency note). SK-4 reuses `write_file` as-is — no new gate. |
| agentskills.io format/validation rules | External standard, stable | `SKILL.md` frontmatter rules (SK-2) taken directly from the published specification (agentskills.io/specification, fetched 2026-07-26) — not reinvented. |

---

## Configuration Summary

### Constructor parameters (mirrors M4's `working_dir` pattern)

```
skills_dir: Path   # defaults to {working_dir}/skills (SK-6)
```

No new environment variables or CLI flags are required beyond what SK-6 specifies; a `--skills-dir` CLI flag is left to `design.md` to decide (trivial-or-deferred, same posture M4 took with `--working-dir`).

---

## Out of Scope

- **Semantic/embedding-based skill search** — SK-5's `search()` is keyword/relevance-level; embedding-based ranking is a plausible future refinement, not M5.
- **`allowed-tools` frontmatter field enforcement** — the spec marks this field experimental; M5 parses it if present (SK-2) but does not enforce or wire it into the Guardrails GATE.
- **Skill versioning / updates to an existing skill** — SK-4 covers authoring a *new* skill; overwriting/versioning an existing one is not specified here.
- **MCP or `scripts/`-execution wiring** — the spec's optional `scripts/` directory (executable code bundled with a skill) is part of the on-disk format (SK-2 doesn't reject a skill for having one) but M5 does not build a mechanism to *execute* bundled scripts; that would route through M4's `run_shell`/Tools port if/when built, not a new Skills-owned execution path.
- **Multi-skill composition / skill-calls-skill** — out of scope; a `design.md` open question at most.
- **Skills exposed as MCP resources or to external consumers** — M5 is Axiom-internal discovery/activation only.

---

## Definition of Done (M5 complete when ALL of these pass)

1. **Spec gate:** `requirement.md`, `design.md`, `task.md` exist; `dryrun-design-N.md`'s latest verdict has zero critical, zero warning, zero observation findings.
2. **Code dryrun gate:** the latest `dryrun-code-N.md` verdict has zero critical, zero warning, zero observation findings.
3. **Port contract:** `SkillsPort` Protocol exists in `axiom/skills/port.py`, consumed directly by `loop.py`'s Perceiver call-point (SK-1) — not adapter-side.
4. **Format compliance:** required-field (`name`/`description`) validation matches the agentskills.io frontmatter rules verbatim (SK-2) — no bespoke deviation. Optional-field constraints (e.g. `compatibility`'s length cap) are parsed but not enforced in M5 (`design.md` D13).
5. **Unit tests green:** new `tests/test_skills_*.py` covers discovery, validation (including the malformed-skill exclusion path), activation-catalog refresh, and search, with no skips.
6. **Full suite green:** the whole `pytest` suite (pre-existing + new) passes.
7. **Live verification:** SK-7's cross-provider demonstrations are all completed and recorded.
