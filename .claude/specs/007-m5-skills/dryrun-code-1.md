# Code Dry-Run Report #1

**Scope**: `src/axiom/skills/` (new), `src/axiom/interfaces.py`, `src/axiom/loop.py`, `src/axiom/providers/base.py`, `src/axiom/providers/local_adapter.py` (interaction check), `src/axiom/agent.py`, plus the test suite touched by M5
**Design**: `.claude/specs/007-m5-skills/design.md` (dryrun-design-3, PASS)
**Reviewed**: 2026-07-26

---

## Bugs (will cause incorrect behavior)

### [B1] `RunState.skills_catalog`/`active_skills` annotations reference undefined names — `interfaces.py` is missing the `axiom.skills.port` import the design specified
- **File**: `src/axiom/interfaces.py:13-17` (import block), `92`, `94` (the annotations themselves)
- **Pass**: Pass 1 (Design Conformance) / Pass 4 (Contract Violations)
- **What**: `design.md` §2 explicitly specifies `from axiom.skills.port import SkillContent, SkillSpec` at the top of `interfaces.py`, with the rationale spelled out in the design text itself ("a direct import is fine and preferred... Typed precisely, not duck-typed"). The implementation omits this import entirely — `RunState.skills_catalog: list[SkillSpec]` and `RunState.active_skills: list[SkillContent]` reference names that are never imported anywhere in the module. Because `from __future__ import annotations` (line 13) makes all annotations lazy strings (PEP 563), this doesn't raise at class-definition time or at ordinary dataclass construction — which is why the full test suite (460 tests) passes without any failure. But it breaks the instant anything resolves the annotations for real:
  ```
  >>> import typing
  >>> from axiom.interfaces import RunState
  >>> typing.get_type_hints(RunState)
  NameError: name 'SkillSpec' is not defined
  ```
  (Reproduced directly against this codebase — confirmed, not a guess.)
- **Impact**: Silent today (nothing in the codebase currently calls `typing.get_type_hints()` or an equivalent on `RunState`), but this is a real dangling reference that will break the first static type checker (mypy/pyright), the first `sphinx-autodoc`-style doc generator, or the first library that introspects `RunState`'s fields via `typing.get_type_hints()` (a very common pattern — dataclass-to-schema converters, some serialization libraries, FastAPI/pydantic-adjacent tooling if ever adopted). It's also a genuine, unambiguous deviation from the design's own explicit code sample, not a stylistic alternative.
- **Fix**: Add the import exactly as the design specifies:
  ```python
  from axiom.skills.port import SkillContent, SkillSpec
  ```
  placed after the existing `typing` import in `interfaces.py`. (Likely cause: an auto-formatter/linter hook stripped the import as "unused" at some point during implementation, since annotation-only references under `from __future__ import annotations` don't count as a runtime usage to a naive unused-import checker — worth being aware this can recur if the import is re-added and then touched again before any executable code references the names.)

---

### [B2] LocalAdapter's post-act RESPOND-forcing sentinel doesn't account for a skill activation happening after a prior ACT — silently re-defeats the exact failure class dryrun-design-1's C3 fixed, on the local provider only
- **File**: `src/axiom/providers/local_adapter.py:156-176`
- **Pass**: Pass 2 (Execution Path Trace) — traced a realistic multi-cycle sequence: `ACT` (history populated) → `USE_SKILL` (activates a skill, per design's C3 fix does NOT touch `history`) → next `reason()` call.
- **What**: `local_adapter.py`'s `reason()` has a **KIND-A-only** mechanism (pre-existing, "Defect-A fix") that checks `if _POST_ACT_SENTINEL in context` (i.e. `"[TOOL EXECUTION RESULTS"` present, meaning `run_state.history` is non-empty) and, if so, prepends a "SYSTEM INSTRUCTION (highest priority...)" block that tells the model: *"Your ONLY valid response is RESPOND... Do NOT issue another ACT."* This check is a coarse substring match on the whole context string — it does not distinguish "the most recent event was a completed ACT" from "history has an old ACT result, but the most recent event was actually a `USE_SKILL` activation."

  Concretely: once `run_state.history` is non-empty (from any earlier `ActIntent` cycle in the same run), it **stays** non-empty for the rest of the run (M5 never clears it). So on every subsequent cycle — including the cycle immediately after a `UseSkillIntent` activation, where `[SKILL ACTIVATION]` and `[ACTIVE SKILL: ...]` are freshly rendered into the same context — `_POST_ACT_SENTINEL in context` is still `True`, and the hard RESPOND-forcing framing still fires and is prepended **first** (before the skill content), instructing the local model in the strongest possible terms to respond immediately and never ACT again.
- **Impact**: On the local (KIND-A) provider specifically, a plausible and realistic sequence — e.g. `ACT` to list files, then `USE_SKILL` to activate a skill that should inform how to process those files — silently reproduces the exact bug dryrun-design-1's C3 was written to prevent (the Conductor being pushed to respond generically instead of consulting the skill it just activated), just through a different code path that the M5 design review didn't examine (local_adapter.py wasn't read during the design phase). SK-3's behavioral AC ("proving activation actually happened end-to-end") is at real risk of failing specifically on `--provider local` for any scenario involving an ACT before a USE_SKILL in the same run. `--provider claude` (`ClaudeAdapter`) has no equivalent mechanism and is unaffected.
- **Fix**: Narrow the sentinel condition to skip the hard RESPOND-forcing when a skill was just activated — the whole point of `skill_activation_note`/`[SKILL ACTIVATION]` being one-shot (design.md D5a) is that it signals "something new just happened that the Conductor should act on, not just report":
  ```python
  _POST_ACT_SENTINEL = "[TOOL EXECUTION RESULTS"
  _SKILL_ACTIVATION_SENTINEL = "[SKILL ACTIVATION]"
  if _POST_ACT_SENTINEL in context and _SKILL_ACTIVATION_SENTINEL not in context:
      ...
  ```
  This preserves the original Defect-A behavior for the case it was built for (a plain ACT→RESPOND nudge for weak local models) while not overriding a fresh skill activation.

---

## Gaps (missing implementation)

None found beyond what `task.md`/`requirement.md` already correctly scope to the next lifecycle stage (SK-7 live-CLI verification is intentionally not a code-review item — it's the next step after this review, per the spec-driven process, not a missing implementation).

---

## Warnings (potential issues)

### [W1] No test exercises the interaction B2 describes
- **File**: `tests/test_contracts.py`, `tests/test_shared_base.py`
- **Pass**: Pass 10 (Value-Path Trace), Step 3 (distrust intermediate-assertion tests)
- **What**: All 15 `UseSkillIntent`-specific tests in `test_contracts.py` use `FakeAdapter` (generic, no `local_adapter.py`-specific sentinel logic) and assert against `RunState` fields directly (`active_skills`, `history`, `cycle_count`, `spawn_count`) — intermediate state, not the rendered prompt a real `LocalAdapter.reason()` call would receive. `test_shared_base.py`'s perceive()-rendering tests correctly verify `base.py`'s own output but never exercise `LocalAdapter.reason()`'s additional context-augmentation layer on top of it. Neither test suite would have caught B2.
- **Risk**: Green tests here do not prove the ACT→USE_SKILL sequence behaves correctly on the local provider — that requires either a `LocalAdapter.reason()`-level unit test asserting the framing block is/isn't prepended under each combination of `[TOOL EXECUTION RESULTS`/`[SKILL ACTIVATION]` presence, or the live-CLI verification step (SK-7) actually driving this exact sequence on `--provider local`.

---

## Style (code quality, conventions)

None worth flagging — the new code (`axiom/skills/*.py`) is consistent with the project's existing style (docstring conventions, `from __future__ import annotations`, module-level constants, logger naming pattern matching `axiom.tools`).

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 2    | 0    | 1        | 0     |

**Verdict**: FAIL — has bugs
