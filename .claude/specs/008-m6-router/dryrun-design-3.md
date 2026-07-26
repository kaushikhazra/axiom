# Design Dry-Run Report #3

**Document**: `.claude/specs/008-m6-router/design.md`
**Reviewed**: 2026-07-26

Full 10-pass re-review after `dryrun-design-2`'s 1 Critical / 1 Warning were addressed (commit `9707c21`).

- **C1 (unexposed `conductor_provider`)**: confirmed fixed — `Router.conductor_provider` is now a public read-only property; `agent.py`'s §6 shows the concrete derivation (`self._provider_kind = _PROVIDER_KIND.get(router.conductor_provider, "KIND_A")`) rather than an unbacked prose claim.
- **W1 (no failure-path attribution)**: confirmed fixed — `act_span` attributes are now set immediately after `select_worker()` returns (before dispatch, surviving a hard failure), then overwritten only if `final_selection is not selection` (a fallback changed the outcome). Traced the variable lifetime of `final_selection` across all three exit paths (primary success, fallback success, uncaught raise) — no risk of an undefined-variable reference, since the post-dispatch block is only reached on the two success paths.
- Also fixed: the stale "D6 in §6" cross-reference in the Error Handling table, now correctly described in prose.

Re-ran all 10 passes against the full current document. No new issues surfaced. `task.md` confirmed still at 12 items, matching all 12 `Files Changed` rows (11 from iteration 1 + `cli.py`, no new files introduced by either fix pass — the `conductor_provider` property and the two-point attribute setting both land inside already-traced files).

---

## Critical Gaps (must fix before implementation)

None.

---

## Warnings (should fix, may cause issues)

None.

---

## Observations (worth discussing)

None.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 0        | 0        | 0             |

**Verdict**: PASS
