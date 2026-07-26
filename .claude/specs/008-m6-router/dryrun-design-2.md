# Design Dry-Run Report #2

**Document**: `.claude/specs/008-m6-router/design.md`
**Reviewed**: 2026-07-26

Full 10-pass re-review after `dryrun-design-1`'s 3 Critical / 1 Warning were addressed (commit `a3691c6`).

- **C1 (unreachable policy engine)**: confirmed fixed — `cli.py`'s `--provider` no longer has `default="claude"`, `Agent.__init__`'s `provider` parameter now defaults to `None`, and `forced_provider = provider` correctly propagates that distinction into `Router`.
- **C2 (fallback observability misreport)**: confirmed fixed — `_maybe_record()` now yields the `Span`; the ACT branch sets `axiom.control_level`/`axiom.router.provider` from `final_selection` (whichever of `selection`/`fallback` actually produced `result`), after the dispatch completes.
- **C3 (spawn_count undercounting)**: confirmed fixed — `run_state.spawn_count += 1` now appears on both the primary and fallback dispatch paths.

Re-ran all 10 passes against the full current document, not just the diff.

---

## Critical Gaps (must fix before implementation)

### [C1] `Router` never exposes which provider it picked for the Conductor — `agent.py`'s own prose claim about deriving `self._provider_kind` from it is unimplementable as designed
- **Pass**: Pass 3 (Interface Contract Validation) — checked whether §6's prose claim about `agent.py` has a corresponding, callable interface on `Router`.
- **What**: §6 states: *"`self._provider_kind`... is now derived from `router`'s chosen Conductor rather than the raw `provider` string, via the existing `_PROVIDER_KIND` mapping."* But `Router.select_conductor()` (§3) returns only the bare `RoutableAdapter` — the provider name it picked (`"claude"` or `"local"`) is stored in `self._conductor_provider`, a **private** attribute (leading underscore, no public property exposing it). `agent.py` — a different module — cannot read a private attribute of a `Router` instance it doesn't own the internals of (and shouldn't, by the same encapsulation discipline this design applies everywhere else, e.g. `Router._cache`, `Router._factories`). There is no method or property anywhere in §3's `Router` class that returns the conductor's provider name.
- **Risk**: This isn't a hypothetical — `self._provider_kind` is **existing, pre-M6 functionality** (`Agent.run()` already threads it into `loop.run(user_input, run_id=run_id, provider_kind=provider_kind)` for every observed run, predating this milestone). As designed, implementing §6's own described behavior is impossible — the implementer hits a dead end and either (a) invents an undocumented private-attribute reach-around (breaking encapsulation the rest of this design otherwise respects), or (b) silently drops the derivation and hardcodes/guesses `provider_kind`, quietly breaking observability's run-level `provider_kind` attribute for every session where the Conductor wasn't explicitly forced via `--provider`. Either outcome is a real regression in already-shipped M2 observability behavior, introduced by this milestone.
- **Fix**: Add a public read-only property to `Router`: `conductor_provider: str | None` (returns `self._conductor_provider`, `None` before `select_conductor()` has been called). `agent.py`'s §6 code becomes concrete: `self._provider_kind = _PROVIDER_KIND.get(router.conductor_provider, "KIND_A")` (matching the existing `_PROVIDER_KIND.get(provider, "KIND_A")` fallback pattern already in `agent.py`, unchanged by this design). Add this property alongside `Router`'s other public surface in §3, and mention it explicitly in §6's code sample rather than leaving it as unbacked prose.

---

## Warnings (should fix, may cause issues)

### [W1] The ACT span records no routing attribution at all when the dispatch fails without a fallback (or the fallback itself fails)
- **Pass**: Pass 5 (Failure Path Analysis) — traced the ACT branch's exception paths against the `act_span.set_attribute(...)` calls added to fix C2.
- **What**: §5's corrected code only calls `act_span.set_attribute("axiom.control_level", ...)` / `(..."axiom.router.provider", ...)` **after** the `try/except` block completes successfully (`final_selection` is only assigned inside the `try` or the fallback branch, both success paths). On a hard failure — `selection.fallback_allowed` is `False` and `AdapterError` propagates, or the fallback dispatch itself also raises `AdapterError` — the function exits via `raise` before reaching the `if act_span is not None:` lines. `record_phase()`'s own `except Exception` handler (in `observability/record.py`, unchanged) sets the span's status to `ERROR`, but never touches `axiom.control_level`/`axiom.router.provider` — those attributes are simply absent from the span for every failed ACT dispatch.
- **Risk**: Lower severity than C1/C2/C3 (doesn't violate a specific `requirement.md` AC — RT-7's AC only names the successful "Claude-routed"/"local-routed" cases), but weakens exactly the scenario observability exists to help with: debugging a *failure*. A future engineer looking at a failed run's trace to answer "which provider was it even trying to use when this broke?" would find the `act` span present (status `ERROR`) but silent on routing — the one piece of context that would most help triage a provider-specific failure.
- **Suggestion**: Set `act_span.set_attribute(...)` from `selection` (the pre-dispatch, "what was attempted" value) immediately after `selection = self._router.select_worker(...)`, before the `try` block — then, on success, optionally overwrite with `final_selection` if a fallback occurred. This guarantees the span always carries *some* routing attribution, upgraded to the accurate post-fallback value only when dispatch actually succeeds via fallback.

---

## Observations (worth discussing)

### [O1] Minor stale cross-reference: the Error Handling table's row for "`select_worker()` called before `select_conductor()`" cites "D6 in §6," but D6 is actually §4's `control_level`-as-class-attribute decision
- Pre-existing (not introduced by the C1-C3 fix pass) — the wiring-order guarantee described in that row is really just "§6's code happens to call `select_conductor()` before constructing `PraoLoop`," which has no dedicated D-number. Not blocking (the row's substance is correct, only the citation is off), but worth a one-line correction — either add a decision entry for the wiring-order guarantee or drop the "(D6 in §6)" parenthetical and just say "per §6's wiring order."

---

### Pass 9: Design-to-Task-to-AC Traceability

No new files introduced by this iteration's C1 fix (the new `conductor_provider` property lands inside the already-traced `src/axiom/router/router.py` row). Re-confirmed the full matrix from iteration 1 still holds — all 12 file-level prescriptions (11 original + `cli.py` added during the C1 fix, already re-traced last iteration) remain traced to tasks and ACs.

**Result**: No new traceability gaps.

---

### Pass 10: Behavioral DoD Challenge

Unaffected by this iteration's findings — C1 (this report) is an interface-contract gap that would surface at implementation time as an `AttributeError`-shaped dead end, not a behavioral-AC gap; RT-2's own behavioral AC (same-provider-across-turns, observable via `--observe` trace) still depends on `self._provider_kind` being correctly derived, which is exactly what C1 fixes.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 1        | 1        | 1             |

**Verdict**: FAIL — needs revision
