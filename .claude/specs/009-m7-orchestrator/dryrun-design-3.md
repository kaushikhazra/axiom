# Design Dry-Run Report #3

**Document**: `.claude/specs/009-m7-orchestrator/design.md`
**Reviewed**: 2026-07-27

---

## Context for this iteration

Triggered by a real finding surfaced during live-verification prep (after dryrun-code-2's PASS): OR-3's original AC required "one `act` span per configured provider... each carrying its own `axiom.router.provider` value" — a mechanism the implemented design (D10) deliberately did not build (one aggregate span with `committee_size`/`providers` attributes instead). Neither dryrun-design-1 nor dryrun-design-2 caught this AC/design conflict — a genuine miss in both prior passes' Pass 1 (Completeness) and Pass 10 (Behavioral DoD Challenge). `requirement.md`'s OR-3 has been revised (not the code) to match D10's actual mechanism, with the correction reasoned through and recorded inline in OR-3 itself. This iteration re-sweeps to confirm requirement.md and design.md now realign.

---

## Pass 1: Completeness Check (re-run, focused)

OR-3's AC now describes exactly what `select_committee()` + the loop's committee branch actually do: same-instruction dispatch to every member (unchanged, already correct), independent per-member result capture (unchanged), and a single committee-mode `act` span carrying `axiom.router.committee_size`/`axiom.router.providers` (now matches D10 exactly, not the old N-span requirement). No design element is now undescribed by an AC, and no AC now describes a mechanism the design doesn't build. Traced directly against the live `router.py`/`loop.py` source (not just design.md prose) — `select_committee()`'s `logger.debug` (dryrun-code-1 G1 fix) uses `RoutingDecision.CONSORTIUM`, and `loop.py`'s committee branch sets exactly `axiom.router.committee_size` / `axiom.router.providers` on the one wrapping `act` span, exactly as OR-3's revised AC now states.

## Pass 10: Behavioral DoD Challenge (re-run, focused)

Re-asked the falsification question for OR-3 specifically: *"If every AC passes, is OR-3's Purpose (each provider genuinely, independently invoked with the identical instruction) actually served?"* OR-3's own ACs are now structural (same-instruction-string, independent capture, span attributes) — by themselves they would NOT prove real independent invocation (a hypothetical bug that dispatches once and duplicates the result into `parts` twice could satisfy them). This is why OR-3's revised behavioral AC explicitly delegates its live proof to OR-4's marker test rather than inventing a redundant one: OR-4's AC can only pass if genuinely distinct per-provider answers reach the final synthesized response — which is impossible unless every member was actually, independently dispatched. Confirmed this reasoning holds: OR-4 remains fully self-contained (has its own Purpose, its own behavioral AC, unaffected by this revision) and does not depend on OR-3 for its own validity — the delegation is sound, not circular. No Critical Gap.

## Full fresh sweep (Passes 2-9)

No changes to data flow, interfaces, state machines, failure paths, concurrency, edge cases, task alignment, or Files-Changed traceability since dryrun-design-2 (PASS 0/0/0) — this revision touched only `requirement.md`'s OR-3 AC text, not `design.md` or `task.md`. Re-verified `task.md`'s existing skeleton still covers everything (no new file-level prescription was introduced by this revision — `loop.py`'s row already traces to OR-3 via task.md §3). No new findings.

---

## Critical Gaps

None.

## Warnings

None.

## Observations

None.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 0        | 0        | 0             |

**Verdict**: PASS

---

*Process note (not a counted finding — retrospective commentary only): both dryrun-design-1 and dryrun-design-2 should have caught the OR-3/D10 mismatch this iteration resolves — Pass 1 (Completeness) and Pass 10 (Behavioral DoD) are both meant to check exactly this kind of AC-vs-mechanism conflict, and neither pass's execution went deep enough into OR-3's specific wording against D10's specific wording to catch it before code was written. No process change follows from this; recorded here for honesty, per this session's practice of surfacing genuine misses rather than smoothing over them.*
