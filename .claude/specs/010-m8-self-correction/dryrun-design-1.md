# Design Dry-Run Report #1

**Document**: `.claude/specs/010-m8-self-correction/design.md`
**Reviewed**: 2026-07-27

---

## Critical Gaps (must fix before implementation)

### [C1] `router.py`'s extraction-provider change has no matching AC in `requirement.md`
- **Pass**: Pass 9 (Design-to-Task-to-AC Traceability)
- **What**: The Files Changed table's `src/axiom/router/router.py` row ("Add `Router.select_extraction_worker()`") is traced to `requirement.md`'s SC-1. Re-reading SC-1's actual AC bullets (`requirement.md:38-50`), none of them mention which provider performs the extraction, that it bypasses `RoutePolicy`, or that a new `Router` method exists at all — the only place this appears is the free-form Purpose/Resolution prose above the user stories ("The extraction call itself uses the cheapest available provider capable of the task... not necessarily the session's Conductor"), not a formal, testable acceptance criterion. Per the skill's own conservative-default rule ("when in doubt, treat as unmatched"), a Purpose-section mention is not a Tier 2 AC match — Tier 2 requires "does any AC describe verification of the same logical change."
- **Risk**: `select_extraction_worker()`'s specific behavior (prefer `"local"`, bypass policy entirely, fall back if `"local"` isn't configured) has no acceptance criterion holding it accountable — an implementer could build it differently (e.g., route through `select_worker()`'s policy evaluation instead) and nothing in `requirement.md` would catch the deviation as wrong.
- **Fix**: Add an explicit AC to SC-1: "The extraction dispatch uses the cheapest configured provider (preferring `local`), bypassing `RoutePolicy` entirely — this is an internal system task, not a user-facing ACT dispatch, so privacy/capability/bulk-threshold evaluation does not apply to it."

---

## Warnings (should fix, may cause issues)

### [W1] §5's "initialized once" wording for `correction_signal` is ambiguous about scope, risking a real cross-cycle state-leak bug if misread
- **Pass**: Pass 4 (State Machine & Transitions)
- **What**: §5 states *"`correction_signal: str | None = None` is initialized once, immediately before the `committee = self._router.select_committee(...)` line (so it's in scope regardless of which branch runs)."* The phrase "initialized once" is misleading: the `committee = ...` line itself is reached fresh on every loop iteration that processes an `ActIntent` (it's inside the ACT-handling section of the `while True:` body, not outside the loop). If a future reader takes "initialized once" literally — declaring `correction_signal = None` a single time, *outside* the `while True:` loop, rather than at the ACT-branch entry point on every relevant iteration — a stale `correction_signal` from an earlier cycle could leak into a later cycle's CAPTURE check via the `USE_SKILL` intent's `continue` path (which skips the ACT section entirely and loops back to `perceive()`, never re-touching `correction_signal` if it were declared outside the loop).
- **Risk**: A cycle sequence like ACT-with-fallback (cycle 1, sets `correction_signal`) → USE_SKILL (cycle 2, `continue`s past the ACT section) → ACT-clean (cycle 3, no real correction) would incorrectly re-fire CAPTURE for cycle 3 using cycle 1's stale signal, if the variable were scoped wrong.
- **Suggestion**: Reword to be unambiguous: *"`correction_signal: str | None = None` is (re-)declared at the top of the ACT-intent-handling section, immediately before the `committee = ...` line — freshly reset on every iteration that reaches this point, never carried over from a prior cycle (including across a `USE_SKILL` cycle's `continue`, which skips this section entirely)."*

---

## Observations (worth discussing)

None.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 1        | 1        | 0             |

**Verdict**: FAIL — needs revision
