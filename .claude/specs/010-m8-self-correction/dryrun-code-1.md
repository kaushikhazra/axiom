# Code Dry-Run Report #1

**Scope**: `src/axiom/loop.py`, `src/axiom/router/router.py`, `src/axiom/providers/base.py`, `src/axiom/interfaces.py`, `src/axiom/memory/schema.py`, `src/axiom/memory/decay.py` (and their test files)
**Design**: `.claude/specs/010-m8-self-correction/design.md` (dryrun-design-2 PASS 0/0/0)
**Reviewed**: 2026-07-27

---

## Bugs (will cause incorrect behavior)

### [B1] Committee partial-failure detection uses fragile substring matching on formatted result text — a legitimate success containing the literal word "FAILED" would be misclassified as a failure
- **File**: `src/axiom/loop.py:351-355` (also present in `design.md` §5's own pseudocode — this bug pre-dates implementation, carried over from the design)
- **Pass**: Pass 4 (Input Validation & Boundaries) / Pass 8 (Code Quality & Patterns)
- **What**: `correction_signal`'s committee-branch trigger is computed as:
  ```python
  failed_members = [
      m.provider_name
      for m, p in zip(committee, parts)
      if "FAILED" in p
  ]
  ```
  `parts` holds the already-formatted display strings (`f"[{provider}]: {member_result}"` on success, `f"[{provider}]: FAILED — {exc}"` on failure). Checking `"FAILED" in p` is a substring match against the *rendered* text, not the actual dispatch outcome. If a committee member's genuine, successful `member_result` happens to contain the literal substring `"FAILED"` anywhere in its natural-language content (e.g., a Worker answering a question like *"why did the deployment fail last week?"* and responding with *"the deployment FAILED due to a config error"*), that member is incorrectly counted as a `failed_member` even though `any_succeeded` correctly recorded it as a success.
- **Impact**: `correction_signal` gets set for an ordinary clean cycle where every member actually succeeded — CAPTURE fires unnecessarily (violating SC-3's "zero extra calls on a clean cycle" AC for this specific false-positive case), and the resulting "lesson" is nonsensical (built from a `correction_signal` claiming a member failed when it didn't). This is a real, if narrow, correctness bug — not just a style nit — because it directly contradicts SC-3's own acceptance criterion.
- **Fix**: Track success/failure directly from the dispatch outcome (the `try`/`except` that's already there), not by re-parsing formatted strings after the fact:
  ```python
  parts: list[str] = []
  outcomes: list[bool] = []  # True = succeeded, aligned with `committee` by index
  for member in committee:
      try:
          member_result = await asyncio.to_thread(
              member.adapter.act, intent.instruction
          )
          parts.append(f"[{member.provider_name}]: {member_result}")
          outcomes.append(True)
      except AdapterError as exc:
          parts.append(f"[{member.provider_name}]: FAILED — {exc}")
          outcomes.append(False)

  any_succeeded = any(outcomes)
  if not any_succeeded:
      raise AdapterError(f"all {len(committee)} committee members failed")
  result = "\n".join(parts)

  failed_members = [
      m.provider_name for m, ok in zip(committee, outcomes) if not ok
  ]
  if failed_members:
      correction_signal = (...)
  ```
  This removes the string-matching entirely — `failed_members` is derived from the actual recorded outcome, never from content inspection.

---

## Gaps (missing implementation)

None.

---

## Warnings (potential issues)

None.

---

## Style (code quality, conventions)

None beyond B1 (already captured above as a correctness bug, not a separate style nit).

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 1    | 0    | 0        | 0     |

**Verdict**: FAIL — has bugs or critical gaps
