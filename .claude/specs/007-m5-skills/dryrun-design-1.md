# Design Dry-Run Report #1

**Document**: `.claude/specs/007-m5-skills/design.md`
**Reviewed**: 2026-07-26

---

## Critical Gaps (must fix before implementation)

### [C1] Unguarded filesystem exceptions crash discovery on a single bad skill
- **Pass**: Pass 5 (Failure Path Analysis)
- **What**: `parser.py::parse_skill_md()` calls `path.read_text(encoding="utf-8")` with no `try/except`. `registry.py::_discover()` calls `self._skills_dir.iterdir()` with no `try/except` either, and only catches `SkillValidationError` around `parse_skill_md()` — not `OSError`/`PermissionError`/`UnicodeDecodeError`. A single unreadable `SKILL.md` (permission-denied file, binary garbage that fails UTF-8 decoding, a dangling symlink) or an unreadable `skills_dir` itself will raise an uncaught exception straight out of `list_skills()` / `get_skill()` / `search()`.
- **Risk**: Because D3 has `list_skills()` called **every Perceive cycle** (not once per turn), this isn't a rare cold-start failure — it crashes every single cycle of every run for as long as the bad file exists, taking down the whole loop. This is the *exact* failure class M4's own `design.md` §6 already documented and fixed for `read_file`/`write_file`/`list_dir` ("previously unguarded here and would have escaped as raw exceptions, violating `ToolsPort.execute()`'s 'never raises' contract") — M5's parser reintroduces the same bug M4 just closed, one milestone later, in a component that (unlike a single `read_file` call) runs unconditionally on every cycle.
- **Fix**: Wrap `path.read_text(...)` in `parse_skill_md()` with `except OSError as exc: raise SkillValidationError(f"{path}: failed to read: {exc}") from exc`. Wrap `self._skills_dir.iterdir()` in `_discover()` similarly, converting `OSError` (e.g. permission-denied on the directory itself) into an empty/degraded result (log + return `{}` for that scan) rather than letting it propagate — matching SK-6's existing "missing skills_dir → empty catalog, not an error" precedent.

---

### [C2] `_parse_frontmatter_block`'s nested-`metadata` handling is broken — crashes on the spec's own documented example
- **Pass**: Pass 2 (Data Flow Trace) — traced the frontmatter dict literally line-by-line.
- **What**: For input like:
  ```
  metadata:
    author: example-org
    version: "1.0"
  ```
  the first line (`"metadata:"`) hits the generic branch: `k, sep, v = line.partition(":")` → `current_key = "metadata"`, `result["metadata"] = ""` (an empty **string**, not a dict). The *next* line (`"  author: example-org"`) matches the nested-indentation branch and executes `result.setdefault("metadata", {})[k.strip()] = v...` — but `setdefault` only inserts `{}` if the key is **absent**; `"metadata"` already exists (as `""` from the line before), so `setdefault` returns that string unchanged, and `""[k.strip()] = v` raises `TypeError: 'str' object does not support item assignment`.
- **Risk**: This is not a hypothetical edge case — it is **literally the example given in the fetched agentskills.io specification itself** (`requirement.md`'s own "Example with optional fields" block, reproduced from the live spec fetch). Any skill using the standard `metadata:` pattern — including one the agent itself might plausibly self-author (SK-4) if it follows the spec's own example shape — crashes `parse_skill_md()`, which (per C1's same propagation path, or even if C1 is fixed and this becomes a caught `SkillValidationError`) silently excludes every skill using this common, spec-sanctioned pattern.
- **Fix**: Detect the `metadata:` header line specially — when the line is exactly `"metadata:"` (empty value), initialize `result["metadata"] = {}` directly instead of falling into the generic string-assignment branch:
  ```python
  k, sep, v = line.partition(":")
  if not sep:
      continue
  key = k.strip()
  if key == "metadata" and not v.strip():
      current_key = "metadata"
      result["metadata"] = {}
      continue
  current_key = key
  result[current_key] = v.strip().strip('"')
  ```

---

### [C3] Skill-activation markers are injected into the ACT-result channel with ACT-specific instructional framing that actively discourages using the skill just activated
- **Pass**: Pass 3 (Interface Contract Validation) / Pass 2 (Data Flow Trace)
- **What**: §5's `UseSkillIntent` handling produces `result = "[SKILL ACTIVATED] {name}"` (or `[SKILL ERROR] ...`) and feeds it through the **existing, unmodified** `observe()` → `run_state.history` path. `base.py::perceive()` (unchanged by this design) renders `run_state.history` under a fixed header:
  > `[TOOL EXECUTION RESULTS — read these carefully]` ... `[NOTE: The above are REAL outputs from tool executions. The task has been partially or fully completed. ... Use RESPOND to deliver the answer to the user — do NOT request another ACT unless there is clearly something missing.]`

  A `[SKILL ACTIVATED] csv-summarizer` marker is not a tool-execution result and the task is very much *not* complete — activation is the setup step, not the payoff. This framing directly instructs the Conductor to treat skill activation as if it were completed work and prefer `RESPOND` immediately afterward.
- **Risk**: This directly threatens SK-3's own behavioral AC (`requirement.md`) — the whole point of activation is that the *next* reasoning cycle uses the now-loaded `[ACTIVE SKILL: ...]` body to inform a subsequent `ACT` or a better `RESPOND`. But the surrounding boilerplate text explicitly nudges the Conductor toward an immediate `RESPOND` right after seeing "[SKILL ACTIVATED] ...", which is likely to produce a generic response that never actually consults the skill body that was just loaded into `[ACTIVE SKILL: ...]` two sections above it in the same prompt — silently defeating progressive disclosure's entire purpose while still returning a plausible-looking answer (exactly the "ships done, doesn't work" failure class the project's own dryrun conventions exist to catch).
- **Fix**: Do not route skill-activation results through `run_state.history`/the ACT-result channel. Either (a) give `UseSkillIntent` handling its own render slot (e.g., a `run_state.skill_activation_note` field, rendered under a distinct `[SKILL ACTIVATION]` header with its own instructional text — "the skill's full instructions are now available below under [ACTIVE SKILL: ...]; use them to inform your next ACT or RESPOND"), or (b) skip a textual marker in `history` entirely and rely solely on the `[ACTIVE SKILL: ...]` block itself (§6) as the signal — the Conductor can see its own prior `USE_SKILL` intent was honored simply by the skill's content now being present. Either fix must not reuse the ACT-result boilerplate verbatim.

---

## Warnings (should fix, may cause issues)

### [W1] No idempotency check on repeated activation of an already-active skill
- **Pass**: Pass 2 (Data Flow Trace)
- **What**: Nothing in §5's loop branch checks whether `intent.skill_name` is already present in `run_state.active_skills` before appending. A Conductor that re-emits `USE_SKILL` for the same name (plausible with a weak/local model, or simply because the catalog is still visible and the model doesn't track what it already activated) appends a duplicate `SkillContent` and duplicate `[ACTIVE SKILL: name]` block into every subsequent prompt.
- **Risk**: Wasted context/tokens, and duplicate identical instructions in the prompt is a mild but real correctness smell (models can behave oddly when they see literal duplicate instruction blocks). Bounded by `max_cycles=10` (D6) so not unbounded, but still avoidable waste on every occurrence.
- **Suggestion**: Before appending in loop.py, check `if intent.skill_name not in {s.name for s in run_state.active_skills}`; if already active, still return a graceful `result` (e.g. `"[SKILL ALREADY ACTIVE] {name}"`) rather than silently re-fetching and re-appending.

### [W2] No length cap on a skill's body when injected into context — unlike M4's `read_file`
- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: `SkillContent.body` has no size limit enforced anywhere in the design, and once activated it is rendered into **every** subsequent `perceive()` call for the rest of the run (D4). M4's `filesystem.py::read_file` set an explicit precedent for exactly this hazard (`MAX_READ_CHARS = 8000`, "An uncapped `read_file` on a large file would flood the reasoning prompt the same way uncapped shell output would") — M5 doesn't carry that precedent forward for skill bodies, which the spec itself only *recommends* (not enforces) keeping under ~5000 tokens.
- **Risk**: A large or malformed `SKILL.md` body (whether human-authored or agent-self-authored) that passes SK-2's `name`/`description` validation (which has no body-length check) could bloat every subsequent prompt for the rest of the run, degrading response quality or hitting provider context limits — especially compounded if W1's duplicate-activation gap also fires.
- **Suggestion**: Apply a body length cap (e.g., reuse or mirror M4's `MAX_READ_CHARS`-style constant) when rendering `[ACTIVE SKILL: ...]` blocks in `base.py::perceive()`, with a `"...[truncated N chars]"` suffix matching the existing `read_file`/`run_shell` truncation pattern.

### [W3] Reusing the "act" observability phase label for skill activation blurs M2 traces
- **Pass**: Pass 6 (Concurrency & Ordering) / general cross-cutting-faculty check
- **What**: §5's `UseSkillIntent` branch wraps activation in `_maybe_record("act", run_id, provider_kind)` — the same phase label used for genuine `ActIntent` dispatch (tool calls, provider queries).
- **Risk**: M2 Observability's stated purpose (`architecture.md`) is to make every phase judgeable/"watch it think" — collapsing two semantically distinct events (a real provider Act call vs. an in-loop filesystem lookup with no provider round-trip) under the same phase label makes trace analysis (e.g. "how much of this run's latency was real Act-phase provider calls vs. skill bookkeeping?") misleading.
- **Suggestion**: Use a distinct phase label (e.g. `"use_skill"`) for the `_maybe_record()` call, or keep `"act"` but add a distinguishing attribute if `record_phase()` supports extra attributes — a `design.md` decision either way, just not silent reuse.

### [W4] DoD item 4 overstates "verbatim" spec compliance relative to what's actually validated
- **Pass**: Pass 1 (Completeness Check)
- **What**: `requirement.md`'s Definition of Done item 4 states validation "matches the agentskills.io frontmatter rules verbatim... no bespoke deviation." The design (§4, `parser.py`) only enforces the `name`/`description` required-field rules; optional-field constraints the spec also defines (e.g., `compatibility` ≤ 500 characters, `license` shape) are parsed into `frontmatter` but never validated.
- **Risk**: Low functional risk (SK-2's actual ACs only require `name`/`description` enforcement — this is a self-consistency issue between the requirement's DoD wording and its own AC scope, not a violated AC), but "verbatim...no bespoke deviation" is a claim the design doesn't fully back, and a future reader (or `dryrun-code`) could reasonably flag it as unmet.
- **Suggestion**: Either add optional-field length/shape validation to `parser.py` (cheap — a few more `len()` checks), or narrow DoD item 4's wording to "required-field (`name`/`description`) validation matches the spec verbatim."

### [W5] Hand-rolled frontmatter parser doesn't support multi-line YAML scalars for `description`
- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: D8's line-based parser assumes every frontmatter value fits on one `key: value` line. The fetched spec's own "Good example" `description` is a full multi-clause sentence a human author might plausibly wrap across lines using YAML block-scalar syntax (`description: |` / `>`), which this parser does not support — it would either misparse or produce a truncated/garbled description.
- **Risk**: Lower than C1-C3 — SK-2's own degrade-gracefully behavior (exclude + log, not crash) already contains the blast radius, and the one path M5 fully controls (self-authoring, SK-4) can trivially avoid the failure mode by having the agent emit single-line frontmatter. Risk is limited to externally-authored skills a human drops into `skills_dir` by hand.
- **Suggestion**: Note this as an accepted M5 limitation explicitly in `design.md` (it's currently silent on this specific case, unlike D8's explicit callout for nested `metadata`), or extend the parser to at least detect and reject (not silently mis-truncate) a multi-line scalar indicator (`|`/`>`) with a clear `SkillValidationError`.

---

## Observations (worth discussing)

### [O1] `search()` relevance is unranked
`SkillsPort.search()` (§3/§4) returns matches in filesystem-sort order, not relevance-ranked (e.g., a name match isn't prioritized over a description substring match). `requirement.md` SK-5 only requires the filter to "discriminate" (exclude non-matches), which this satisfies — ranking is legitimately Future Work (embeddings), not a gap. Noted for completeness, no action needed.

### [O2] `RunState.active_skills` never shrinks
D4 explicitly defers an eviction policy to Future Work and bounds worst-case growth via `max_cycles=10`. Combined with W1 (dedup) and W2 (body cap), the actual worst-case context growth from Skills alone in a single 10-cycle run is `10 × (uncapped body size)` if every cycle re-activates a large skill — worth keeping in mind when W1/W2 are fixed, since fixing either one substantially shrinks this bound on its own.

---

### Pass 9: Design-to-Task-to-AC Traceability

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| `src/axiom/skills/port.py` — new: SkillSpec, SkillContent, SkillNotFoundError, SkillsPort | task.md item 1 | SK-1 |
| `src/axiom/skills/parser.py` — new: parse_skill_md(), SkillValidationError | task.md item 2 | SK-2 |
| `src/axiom/skills/registry.py` — new: SkillsRegistry(SkillsPort) | task.md item 3 | SK-1, SK-2, SK-5, SK-6 |
| `src/axiom/interfaces.py` — IntentKind.USE_SKILL, UseSkillIntent, RunState fields | task.md item 4 | SK-3 |
| `src/axiom/loop.py` — skills param, per-cycle refresh, UseSkillIntent handling | task.md item 5 | SK-1, SK-3, SK-4 |
| `src/axiom/providers/base.py` — wire format, _parse_intent, perceive() rendering | task.md item 6 | SK-3 |
| `src/axiom/agent.py` — skills_dir param, SkillsRegistry construction | task.md item 7 | SK-6 |
| `tests/test_skills_parser.py` — new | task.md item 8 | SK-2 |
| `tests/test_skills_registry.py` — new | task.md item 9 | SK-1, SK-2, SK-5, SK-6 |
| `tests/test_loop.py` — extended | task.md item 10 | SK-3, SK-4 |
| Existing `PraoLoop(...)` call sites — updated to pass `skills=` | task.md item 11 | SK-1 |

**Result**: All 11 file-level prescriptions traced to tasks and ACs. No traceability gaps.

---

### Pass 10: Behavioral DoD Challenge

Every story (SK-1 through SK-7) has an explicit **Purpose** paragraph and at least one **[behavioral]** acceptance criterion exercised through a live `axiom-cli` invocation (not a structural proxy) — SK-1's "what skills do you have" CLI probe, SK-2's malformed-vs-valid-skill CLI contrast, SK-3's csv-summarizer end-to-end demonstration, SK-4's fresh-process re-discovery test, SK-5's search-discriminates-CLI scenario, SK-6's empty-skills_dir CLI run, SK-7's cross-provider repeat of SK-1/SK-3/SK-4's behavioral ACs.

No story is satisfiable purely by structural proxies (e.g., a green unit test on `list_skills()` alone would not satisfy any of SK-1/SK-3/SK-4/SK-5/SK-6's behavioral ACs as written — each requires the real CLI). Confirmed: behavioral DoD coverage is present for all 7 stories.

**However**: C3 above means that even though the *written* AC correctly demands CLI-observable behavior, the *design as specified* is at real risk of failing that exact behavioral AC once implemented literally — the ACT-channel framing bug would very plausibly cause SK-3's live-CLI demonstration to fail in practice (Conductor responds generically instead of using the activated skill). This is flagged here as a cross-reference, not a second instance of the same finding — see C3 for the fix.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 3        | 5        | 2             |

**Verdict**: FAIL — needs revision
