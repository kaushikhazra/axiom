# Design Dry-Run Report #1

**Document**: `.claude/specs/009-m7-orchestrator/design.md`
**Reviewed**: 2026-07-27

---

## Critical Gaps (must fix before implementation)

### [C1] `agent.py`'s existing provider whitelist makes committee mode entirely unreachable — design's own §5 claim ("no changes needed") is wrong
- **Pass**: Pass 2 (Data Flow Trace) / Pass 10 (Behavioral DoD Challenge)
- **What**: `src/axiom/agent.py:150` (read directly from the current source, post-M6 dryrun-code-1 W1 fix) contains:
  ```python
  if provider is not None and provider not in ("claude", "local"):
      raise ValueError(f"unknown provider: {provider!r}")
  ```
  `design.md` §5 states: *"`agent.py`: no changes needed. `provider` already flows straight into `Router(forced_provider=provider)`... The only new interpretation is `should_form_committee()`'s `forced_provider == "committee"` check."* This is false — `Agent.__init__("committee")` raises `ValueError` at line 150-151, **before** `Router` is even constructed. Even if that check were removed, `select_conductor()` (`router.py:90-94`) would then resolve `provider_name = self._forced_provider or "claude"` → `"committee"`, and `self._get("committee")` (line 75-82) would raise `RouterError("no adapter factory configured for 'committee'")` — also uncaught by `Agent.__init__` (only `Agent.run()` catches `RouterError`, not the constructor). Either way, `Agent(provider="committee")` cannot succeed as designed.
- **Risk**: This is the exact failure class OR-1's own Purpose section warns against (citing M6's dryrun-design-1 C1 precedent) — `--provider committee` would be a CLI flag that parses successfully (`cli.py`'s `choices=[...]` accepts it) but crashes on construction with an unhandled exception, not a clean `[Error: ...]` string. OR-1's, OR-3's, OR-4's, and OR-6's behavioral ACs — which all require a live `axiom-cli --provider committee` run to actually complete — are unreachable as designed. This blocks the entire milestone's Definition of Done item 7 (live verification).
- **Fix**: Two changes needed, both belong in §5 (not "no changes needed"):
  1. `agent.py:150` — extend the whitelist: `if provider is not None and provider not in ("claude", "local", "committee"): raise ValueError(...)`.
  2. `router.py`'s `select_conductor()` — guard against `forced_provider == "committee"` (design.md's Error Handling table already names this exact guard as necessary, but §5's "no changes needed" text and the Files Changed table's `agent.py`-omission contradict it). Add: when `self._forced_provider == "committee"`, resolve the Conductor as if `forced_provider` were `None` (i.e., `provider_name = "claude"` — the same capability-preferred default M6 already uses when no override is forced), not literally `"committee"`.

---

## Warnings (should fix, may cause issues)

### [W1] `max_committee_size`'s type deviates from OR-8's AC wording (`int | None` vs `int`)
- **Pass**: Pass 1 (Completeness Check)
- **What**: OR-8's AC states *"`RoutePolicy` gains `max_committee_size: int`, defaulting to the count of configured `adapter_factories` at `Router` construction time."* Design.md §2/D4 instead types the field `int | None = None`, resolving the effective count lazily inside `select_committee()` rather than stamping a concrete `int` onto `RoutePolicy` at `Router` construction time. D4's rationale (a plain dataclass can't know `len(adapter_factories)` in advance) is sound, and the two approaches are behaviorally equivalent today (both yield an effective cap of 2, since `adapter_factories` doesn't change between `Router.__init__` and any `select_committee()` call) — but the field's declared type and defaulting mechanism don't literally match the AC's wording.
- **Risk**: Low today (behaviorally identical outcome), but a future reader diffing `RoutePolicy`'s actual type signature against OR-8's AC text would see a mismatch and might (reasonably) file this as a regression.
- **Suggestion**: Either update OR-8's AC wording in `requirement.md` to say `int | None` (documenting that `None` means "use the configured adapter count"), or note the deviation explicitly in design.md's D4 as an intentional, AC-superseding implementation choice with the rationale already given. A one-line addition to D4 resolves this without a requirement.md edit — recommend that path since the *outcome* (default = adapter count, real cap once more providers exist) is unchanged.

### [W2] `select_committee()` can return an empty list `[]` (not `None`) when zero adapters are configured, which the loop's `if committee is not None:` check treats as a real (empty) committee
- **Pass**: Pass 7 (Edge Cases & Boundaries)
- **What**: If `should_form_committee()` returns `True` (e.g. `--provider committee` forced) but `self._factories` is empty, §3's `select_committee()` computes `effective_cap = 0` and returns `[]`, not `None`. §4's loop wiring checks `if committee is not None:` — `[]` passes that check and enters the committee-dispatch branch with zero members, `any_succeeded` stays `False`, and `AdapterError("all 0 committee members failed")` is raised. The end result (a raised `AdapterError`) is arguably correct, but the message is misleading (there were no members to fail — the real problem is zero configured adapters, a misconfiguration one level up).
- **Risk**: Very low in practice — `agent.py`'s composition root always configures exactly `{"claude": ..., "local": ...}`, so `self._factories` is never empty in the real system; this is a theoretical gap surfaced only by a hand-constructed `Router` (e.g., in a test) with `adapter_factories={}`. Not worth a design change, but worth a one-line acknowledgment so a future reader doesn't mistake the confusing error message for a real bug during test-writing.
- **Suggestion**: No design change required. Optionally add a short note to §3 acknowledging the `[]`-vs-misconfiguration distinction, so the (already-planned, per Files Changed) `select_committee()` tests in `test_router.py` know to cover this case explicitly with a clear assertion on the message, rather than being surprised by it.

---

## Observations (worth discussing)

### [O1] Pass 9: Design-to-Task-to-AC Traceability

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|---|---|---|
| `src/axiom/router/policy.py` — add `consortium_patterns`, `max_committee_size`, `RoutingDecision.CONSORTIUM`, `should_form_committee()` | task.md §1 | OR-2, OR-5, OR-8 |
| `src/axiom/router/router.py` — add `select_committee()`; guard `select_conductor()` | task.md §2 | OR-1, OR-2, OR-5, OR-8 (guard itself newly required by C1 — task.md §2's wording already covers it: "guard `select_conductor()` against `forced_provider == 'committee'`") |
| `src/axiom/loop.py` — ACT branch committee dispatch | task.md §3 | OR-1, OR-3, OR-4, OR-6, OR-7, OR-9 |
| `src/axiom/interface/cli.py` — `--provider` gains `"committee"` | task.md §4 | OR-1 |
| `tests/test_router_policy.py` — `should_form_committee()` precedence | task.md §5 (row 1) | OR-1, OR-2, OR-5; DoD item 5 |
| `tests/test_router.py` — `select_committee()` membership/capping/determinism/guard | task.md §5 (row 2) | OR-1, OR-2, OR-8; DoD item 5 |
| `tests/test_contracts.py` — loop-level committee dispatch | task.md §5 (row 3) | OR-3, OR-4, OR-6, OR-7 |
| `tests/fake_adapter.py` — `FakeRouter.committee_selections` | task.md §5 (row 4) | OR-3, OR-4, OR-6 |

**Result**: All 8 file-level prescriptions traced to tasks and ACs (Tier 2 description-match used for test files, via requirement.md's Definition of Done item 5, which is the closest driving text for test-file prescriptions — consistent with how M6's own dryrun-design reviews treated test-file rows). No traceability gaps found on the Files-Changed-table axis. Note: C1's fix (the `agent.py` whitelist change) is currently **absent** from both the Files Changed table and task.md — this is exactly the kind of gap Pass 9 exists to catch, but since C1 itself is already raised above as a Critical Gap (which blocks PASS regardless), it is not double-counted here as a separate traceability finding; fixing C1 must include adding the `agent.py` row to both tables.

### [O2] Pass 10: Behavioral DoD Challenge — coverage confirmed structurally, blocked practically by C1

Every story in `requirement.md` has a Purpose section and at least one `[behavioral]`-tagged AC exercised through `axiom-cli` (OR-1, OR-3, OR-4, OR-6 explicitly; OR-9 aggregates them). Structurally, the requirement document satisfies Pass 10's bar. However, as traced in C1, the design as currently written cannot actually reach the interface path (`axiom-cli --provider committee`) needed to demonstrate any of those behavioral ACs — this is the practical instance of the exact risk Pass 10 exists to catch, surfaced here via direct code trace rather than requirement-document inspection alone. Resolved once C1 is fixed.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 1        | 2        | 2             |

**Verdict**: FAIL — needs revision (C1 must be fixed; W1/W2 recommended but non-blocking)
