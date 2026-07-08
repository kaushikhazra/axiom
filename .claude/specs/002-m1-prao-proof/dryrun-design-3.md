# Design Dry-Run Report #3

**Document**: `.claude/specs/002-m1-prao-proof/design.md` (revised, 748 lines)
**Reviewed**: 2026-07-08
**Also read**: `requirement.md`, `task.md` (15 tasks), `dryrun-design-1.md`, `dryrun-design-2.md`, `.claude/specs/001-agent-core/architecture.md`
**Scope**: (a) Regression check of the 4 dryrun-design-2 findings (New C1, W1, O1, O2); (b) spot-check that the 18 dryrun-design-1 findings remain resolved in the sections the latest fix touched (§5/§6/§7.6/§10/§12/§13, task.md); (c) fresh full-pass dry-run of the revised design.

---

## Part A — Regression Check (dryrun-design-2 findings)

| # | Prior finding | Status | Evidence in revised design |
|---|--------------|--------|---------------------------|
| New C1 | Exception-path timing log couldn't reach `RunState` | **RESOLVED** | The chosen mechanism (elapsed-only abort log in `timing.timed_run`) is specified consistently everywhere it matters: §6.1 `run()` docstring ("Both raised exceptions propagate to agent.py where timing.timed_run fires the abort-path log (elapsed only, no counts) in its except block before re-raising"); §6.2 flow diagram now says "timing abort-log fires in timing.timed_run — **not here**" (the dryrun-2 diagram ambiguity that put the log inside `loop.py` is gone); §6.2 defines the two log variants explicitly (success full: `"[M1 Latency] %.3fs  (%d cycle(s), %d SDK spawn(s))"`; abort elapsed-only: `"[M1 Latency] %.3fs (aborted: %s)"`); §6.2/task.md state `timing.py` catches **bare `Exception`** and does not import `interfaces.py` — the import boundary (§11: timing.py = stdlib only) is preserved; §7.6 propagation path now includes `timed_run` in the chain (adapter → loop → timed_run [log + re-raise] → agent.py [catch → error string] → CLI); §5 `spawn_count` ownership paragraph acknowledges the abort path omits counts; §10 specifies both variants with the abort rationale; §12 timing box shows both variants + re-raise; §13 MPP-5 row states the abort variant. task.md's Observability task prescribes `timed_run` with both exact format strings, bare-`Exception` catch, and the stdlib-only constraint. No `RunState` is needed on the abort path — the unimplementable contract is dissolved, not papered over. |
| W1 | `spawn_count` comment overclaimed on retry runs | **RESOLVED** | §5 field comment now reads "loop-dispatched query() calls (adapter-internal retries excluded — see §7.2)" — exactly the suggested reword. §10 adds the "Note on retry spawns (W1)" paragraph: runs emitting `[INTENT_PARSE_FAILURE]` carry one additional unlogged spawn; sign-off readers are told to cross-check the WARNING log. The MPP-5 datum is no longer silently distorted — the reconciliation rule is written down. |
| O1 | OQ-2 wording should cover the `query()` call shape too | **RESOLVED** | §14 OQ-2 now reads "Confirm, against the installed SDK source, the exact `query()` call shape (`await`-then-iterate vs direct `async for`) AND the `ResultMessage` result attribute name" — both verification items in one step, contained to `_collect_query_result()`, fail-loudly noted. §7.5's helper remains marked "illustrative — not final". |
| O2 | `--debug` plumbing specified with an "or" | **RESOLVED** | The "or" is gone: §10 locks the **constructor parameter** (`Agent(debug=True)`, "not a process-global mutation"); the code comment states "cli.py passes Agent(debug=True) when --debug flag is set"; task.md's cli.py task says "passes it as `Agent(debug=True)` constructor parameter (no env-var mutation)" and adds the `if __name__ == "__main__": main()` guard the sign-off command needs (also noted in §10's retrieval line). One reading only. *(Residual doc-sync nit in requirement.md — see [O2] below, pre-closed.)* |

**Regression result: 4 / 4 dryrun-2 findings fully RESOLVED.**

### Spot-check — original 18 (dryrun-1) in the sections the latest fix touched

| Area | Status |
|------|--------|
| C4 (spawn_count transport) | Still resolved — §5 ownership paragraph, §6.2 increments, §10 transport all agree; the abort path is now explicitly counts-free rather than contradictory. |
| C6 (exit contracts) | Still resolved — §6.2 four-exit table unchanged and consistent with the new timed_run chain (agent.py catches the two typed exceptions *after* timed_run re-raises; CLI still imports nothing). |
| C3 (§7.6 error table + propagation) | Still resolved — the 7-row table is intact; the propagation paragraph was correctly extended to insert timed_run without changing who catches what. |
| C2/O1-of-1 (parse failure / fallback markers) | Untouched and intact (§7.2). |
| W4 (DEBUG handler) | Still resolved — mechanism narrowed from "env var or flag" to constructor param; handler config, child-logger inheritance, and retrieval command all consistent. |
| W6 (mutability / cycle_count) | Untouched and intact (§5, §7.4); "Hello" = `0 cycle(s), 1 spawn(s)` example in §10 still matches. |
| MAX_CYCLES check semantics | §6.2 ("cycle_count < max? yes→loop / no→raise"), §12 ("cycle_count >= max → raise"), and task.md test (c) ("raises after max_cycles cycles") agree. |
| C8 / traceability | task.md still covers all §11 modules (15 tasks); requirement.md ACs unchanged. Re-verified in Pass 9 below. |

**No regressions found. 18/18 originals hold.**

---

## Part B — Fresh Pass Findings

## Critical Gaps (must fix before implementation)

*None found.*

The two-variant timing contract was traced end-to-end: §6.2, §10, §12, §13, and task.md carry byte-identical format strings for both variants. The exception path was simulated at every hop — `AdapterError` raised in `_run_query()` (adapter may import `interfaces.py` ✓) → uncaught through `loop.py` ✓ → caught as bare `Exception` in `timed_run` (no `interfaces` import needed ✓ import-boundary-legal) → re-raised → caught by type in `agent.py` (§11 permits `interfaces` import "for error types" ✓) → `"[Error: ...]"` string → `print(response)` in cli.py (no exception imports needed ✓). An exception that is neither `AdapterError` nor `MaxCyclesExceededError` (i.e. a genuine bug) gets the abort log then propagates as a raw traceback — acceptable and arguably correct; the design never promises converting arbitrary exceptions. `KeyboardInterrupt` is `BaseException`, not `Exception`, so `timed_run`'s bare catch does not swallow Ctrl-C. The `Agent(debug=True)` thread (cli argparse → constructor → `_configure_debug_logging()` → `"axiom"` stderr handler → `"axiom.observability"` child inherits) is complete and boundary-legal. Contract tests (a)–(d) in task.md were dry-executed against §5/§6.2 semantics: expected counts (1/0, 3/1), MAX_CYCLES raise, and AdapterError propagation all match the design.

---

## Warnings (should fix, may cause issues)

*None found.*

---

## Observations (worth discussing — all pre-closed / acceptable)

### [O1] Residual "try/finally" shorthand in §11 and §12 for agent.py's timing wrap
§11's agent.py bullet ("wraps loop.run() with observability timing (try/finally)") and §12's agent.py box ("timing wrapper: try/finally around loop.run()" and the direct `(response, run_state) = loop.run(user_input)` unpack line) predate the `timed_run` mechanism, which is a catch-log-re-raise (try/*except*) inside `timing.py`, invoked as `timing.timed_run(self._loop.run, user_input)`. **Pre-closed**: every authoritative specification of the mechanism (§6.1 docstring, §6.2, §10, §7.6, and — decisively — the task.md tasks the implementer executes) says `timed_run` unambiguously; the §11/§12 phrases are readable as shorthand for "wraps via the timing utility". Cosmetic; cannot produce a wrong implementation. Worth a two-word tidy next time §11/§12 are touched — not a blocker.

### [O2] requirement.md MPP-5 AC still names `AXIOM_DEBUG=1` alongside `--debug`; the design now implements only the constructor-param/`--debug` path
The O2 fix (correctly) picked one mechanism in design.md and task.md, but requirement.md's MPP-5 AC still reads "enabled via the `AXIOM_DEBUG=1` environment variable **or** `--debug` CLI flag" with the example command `AXIOM_DEBUG=1 python -m axiom.interface.cli`. Under the design, setting `AXIOM_DEBUG=1` does nothing. **Pre-closed**: the AC is disjunctive — implementing the `--debug` arm satisfies it — and the example command carries "(or equivalent)", which §10's sign-off command (`python -m axiom.interface.cli --debug`) is. No contract is violated and no implementation ambiguity exists (task.md says "no env-var mutation... not an env-var read"). Residual risk is a sign-off tester running the stale example verbatim and briefly wondering why no latency line appears — a one-line requirement.md cleanup at its next touch removes even that. Acceptable to leave for this review; this report is review-only and does not edit requirement.md.

### [O3] task.md's `timed_run` return annotation names `RunState`, which stdlib-only `timing.py` cannot import
task.md's Observability task prescribes the signature `timed_run(loop_fn, user_input: str) -> tuple[str, RunState]` while the same task (and §11) forbids `timing.py` from importing `interfaces.py`. Written literally, the annotation raises `NameError` at import time. **Pre-closed**: this fails loudly on the very first import (cannot ship broken), the body needs only duck-typed attribute access (`run_state.cycle_count` / `.spawn_count`), and three one-line legal resolutions exist (`typing.TYPE_CHECKING` guard, `-> tuple[str, object]`/`Any`, or `from __future__ import annotations`) — all stdlib, none affecting any contract. Same contained, verify-at-build class as OQ-2. Acceptable to resolve at implementation; recommend the implementer use the `TYPE_CHECKING` guard so the type intent survives.

### [O4] OQ-1 / OQ-2 deferral to build time is acceptable
OQ-1 (`M1_ALLOWED_TOOLS` adequacy) is a one-line constant change in agent.py with a named single source of truth — correctly deferred to sign-off testing. OQ-2 (SDK `query()` call shape + `ResultMessage` attribute) is contained to `_collect_query_result()`, marked illustrative, and fails loudly on the first live call; dryrun-2's O1 asked for the widened wording and §14 now has it. Both deferrals are sound.

---

### Pass 9: Design-to-Task-to-AC Traceability

No "Files Changed" table exists; §11 (File Layout) body prescriptions were re-checked on both axes against task.md (unchanged file coverage since dryrun-2, but task text revised) and requirement.md.

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| Body §11: `src/axiom/interfaces.py` — ports + Intent + RunState + exceptions | Core Contracts task | MPP-4 AC-1, MPP-1 AC-3 |
| Body §11: `src/axiom/loop.py` — PraoLoop + MAX_CYCLES | Master PRAO Loop task | MPP-1 AC-1/AC-2, MPP-2, MPP-3 |
| Body §11: `src/axiom/agent.py` — composition root, M1_ALLOWED_TOOLS, debug logging | Core Assembly task | MPP-5 AC-5 (logger config), MPP-6 AC-2 |
| Body §11: `src/axiom/persona/__init__.py` + `persona.txt` | Persona Package tasks (×2) | MPP-6 AC-1/AC-5 |
| Body §11: `src/axiom/providers/claude_adapter.py` — ClaudeAdapter + bridge + errors | Claude Adapter tasks (×6) | MPP-1 AC-3, MPP-2, MPP-3 |
| Body §11: `src/axiom/observability/timing.py` — timed_run, two log variants | Observability task | MPP-5 AC-1/AC-4 |
| Body §11: `src/axiom/interface/cli.py` — pure I/O, --debug, __main__ guard | CLI Entry Point task | MPP-2 AC-4, MPP-6 AC-2, MPP-5 AC-5 |
| Body §11: `tests/fake_adapter.py` — FakeAdapter | Tests task 1 | MPP-4 AC-5 |
| Body §11: `tests/test_contracts.py` — contract tests (a)–(d) | Tests task 2 | MPP-4 AC-3/AC-5 |
| Body §11: `pyproject.toml` — package metadata + deps + entry point | Package Scaffold task 1 | Tier 2: requirement.md Infrastructure Dependencies ("`src/axiom` package layout — to be created in M1") |

**Result**: All 10 file-level prescriptions traced to tasks and ACs. No traceability gaps.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 0        | 0        | 4            |

**Regression**: 4/4 dryrun-2 findings RESOLVED (New C1, W1, O1, O2). 18/18 dryrun-1 findings spot-checked in the touched sections — all hold, no regressions.

**Verdict**: **PASS**

The New-C1 fix is genuinely resolved, not relocated: choosing the elapsed-only abort variant dissolves the unreachable-`RunState` contract instead of smuggling state through exceptions, keeps `timing.py` stdlib-only, and is specified with identical format strings across §6.1, §6.2, §10, §12, §13, and task.md. The exception path was traced hop-by-hop and is complete and import-boundary-legal; the spawn_count/timing flow is internally consistent now that success and abort paths are explicitly distinct; the `--debug` thread has exactly one reading. The four Observations are documentation-sync and build-time nits, each pre-closed above with rationale — none blocks implementation. **The design is ready to build.**
