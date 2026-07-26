# Design Dry-Run Report #2

**Document**: `.claude/specs/007-m5-skills/design.md`
**Reviewed**: 2026-07-26

This is a re-review after `dryrun-design-1`'s 3 Critical / 5 Warning findings were addressed (commit `9a55bc2`). All 10 passes were re-run against the current document, not just the changed sections — a fix can introduce a new bug or leave a sibling case unfixed, so the full sweep is repeated rather than spot-checking the diff.

---

## Critical Gaps (must fix before implementation)

### [C1] C1's fix is incomplete — `UnicodeDecodeError` is not caught by `except OSError`
- **Pass**: Pass 5 (Failure Path Analysis) — re-verification of the dryrun-design-1 C1 fix.
- **What**: §4's `parse_skill_md()` now wraps `path.read_text(encoding="utf-8")` in `try: ... except OSError as exc: raise SkillValidationError(...)`. This correctly catches permission errors and other OS-level failures. But `str.read_text(encoding="utf-8")` on a file containing bytes that are not valid UTF-8 raises `UnicodeDecodeError` — which is a subclass of **`ValueError`, not `OSError`**. The dryrun-design-1 C1 finding explicitly named this failure mode ("binary garbage that fails UTF-8 decoding") as one of the three triggers, but the fix only guards the `OSError` branch of the family.
- **Risk**: Identical blast radius to the original C1 finding: a single non-UTF-8 `SKILL.md` (a binary file accidentally dropped in `skills_dir`, or a text file saved in a different encoding) still crashes `list_skills()` uncaught, every Perceive cycle (D3), taking down the whole run — the exact scenario C1 was raised to prevent, just via the one sub-case the fix didn't cover.
- **Fix**: Widen the except clause to `except (OSError, UnicodeDecodeError) as exc:` (or, more defensively, `except (OSError, ValueError)` to also catch any other decode-family error). One-line fix, same handling as already written.

---

## Warnings (should fix, may cause issues)

### [W1] `spawn_count` is incremented for `UseSkillIntent`, but no provider query() call is dispatched
- **Pass**: Pass 2 (Data Flow Trace) — traced `spawn_count` against its own documented contract.
- **What**: §5's `UseSkillIntent` branch includes `run_state.spawn_count += 1`, mirroring the `ActIntent` branch's own increment. But `RunState.spawn_count`'s docstring (`interfaces.py`, unchanged by this design) defines it precisely: "loop-dispatched query() calls (adapter-internal retries excluded)." Skill activation is a pure local filesystem lookup (`SkillsRegistry.get_skill()`) — it dispatches no `reason()`/`act()` query at all.
- **Risk**: `spawn_count` silently overcounts relative to its own documented meaning. Anything downstream that trusts `spawn_count` as "number of provider calls this run made" (cost estimation, rate-limit budgeting, a future dashboard) would be quietly wrong by one for every skill activation.
- **Suggestion**: Drop the `spawn_count += 1` line from the `UseSkillIntent` branch — it isn't a query dispatch and shouldn't be counted as one.

### [W2] `cycle_count` / `history`-length lockstep, held since M1, silently breaks for `UseSkillIntent` cycles
- **Pass**: Pass 4 (State Machine & Transitions)
- **What**: Through M1–M4, every `cycle_count` increment (always via `ObservePort.observe()`) was paired 1:1 with a `run_state.history.append(...)`. D5a/D6 deliberately increment `cycle_count` for `UseSkillIntent` **without** appending to `history` (by design — that's the whole point of C3's fix). This is the correct behavior, not a bug — but it silently breaks an invariant that held everywhere else in the codebase, undocumented as a design-level fact anywhere outside the Decisions Log's prose.
- **Risk**: Low today (nothing currently reads `cycle_count` and `len(history)` assuming they match), but this is exactly the kind of implicit assumption a future maintainer (or a future milestone's observability/debugging code) could reasonably make, given it held for M1 through M4.
- **Suggestion**: Add one sentence to D6 (or a new decision) making this explicit: "`cycle_count` and `len(run_state.history)` are no longer guaranteed equal after M5 — a `UseSkillIntent` cycle increments the former without extending the latter." Costs nothing, prevents a future false assumption.

### [W3] `Files Changed` table row for `tests/test_loop.py` still describes the pre-fix mechanism
- **Pass**: Pass 1 (Completeness Check) / Pass 9 (Design-to-Task-to-AC Traceability, internal-consistency sub-check)
- **What**: The `Files Changed` table's `tests/test_loop.py` row (§ Files Changed) still reads: "successful activation appends to `active_skills` + **history marker**; unknown-skill path **appends error marker** and does not crash." Both phrases describe the original (dryrun-design-1 C3) design, which routed skill-activation results through `run_state.history`. The corrected design (D5a, §5, §6) routes them through `run_state.skill_activation_note` instead — `history` is untouched by `UseSkillIntent` handling now.
- **Risk**: Low — `task.md`'s own item 10 is generic enough ("UseSkillIntent success/unknown-skill paths, per-cycle catalog refresh timing") that it doesn't inherit the stale wording, so this doesn't create a Pass-9-blocking traceability gap. But an implementer skimming the `Files Changed` table specifically (rather than §5's corrected pseudocode) could write tests asserting against the wrong channel.
- **Suggestion**: Update the row to: "successful activation appends to `active_skills` + sets `skill_activation_note`; unknown-skill / already-active paths set `skill_activation_note` to an error/status string and do not crash; `history` is not touched by `UseSkillIntent`."

---

## Observations (worth discussing)

### [O1] All three dryrun-design-1 Critical fixes verified correct on trace-through
C2's fix (`_parse_frontmatter_block`'s `metadata:` handling) was traced line-by-line against the exact spec example that broke it originally (`metadata:\n  author: ...\n  version: ...`) — now parses to `{"metadata": {"author": ..., "version": ...}}` correctly, no `TypeError`. C3's fix (`skill_activation_note` one-shot rendering) was traced across two consecutive loop iterations — the note is set at the end of the cycle that activates a skill, rendered exactly once by the *next* cycle's `perceive()` call, then cleared immediately after — no repeat-rendering, no channel conflation with `[TOOL EXECUTION RESULTS]`. Both hold up under re-verification.

### [O2] W1–W5 from dryrun-design-1 all correctly addressed, no regressions introduced
Dedup check (D6a), body-length cap (D6b), distinct phase label (D6c), DoD wording narrowed (D13), multi-line-scalar explicit rejection (D14) — each traced against its own original finding and confirmed present and correctly wired in the current document. No new issues found in re-checking these five.

---

### Pass 9: Design-to-Task-to-AC Traceability

No new files or prescriptions were added since dryrun-design-1's clean traceability matrix (11/11 traced) — the fixes were all modifications to already-traced files/sections. Re-confirmed: no new untraced prescriptions.

**Result**: All 11 file-level prescriptions remain traced to tasks and ACs. No traceability gaps. (W3 above is a wording-accuracy issue within an already-traced row, not a new gap.)

---

### Pass 10: Behavioral DoD Challenge

Unaffected by this iteration's fixes — re-confirmed all 7 stories retain a Purpose and at least one interface-exercised behavioral AC. The C3 risk noted in dryrun-design-1's Pass 10 section (SK-3's behavioral AC being at practical risk from the ACT-channel framing bug) is resolved now that C3 itself is fixed (O1 above) — SK-3's live-CLI demonstration is no longer working against a design that undermines its own success condition.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 1        | 3        | 2             |

**Verdict**: FAIL — needs revision
