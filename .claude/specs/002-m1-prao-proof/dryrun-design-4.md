# Design Dry-Run Report #4 — Final Confirmation Pass

**Document**: `.claude/specs/002-m1-prao-proof/design.md` (750 lines)
**Reviewed**: 2026-07-08
**Also read**: `requirement.md`, `task.md` (15 tasks), `dryrun-design-3.md`, `.claude/specs/001-agent-core/architecture.md`
**Scope**: (a) Confirmation that the 4 dryrun-design-3 Observations are resolved or closed-by-decision; (b) fresh full-pass dry-run (Passes 1–9) for any remaining or newly-introduced findings. This is the final confirmation pass — dryrun-3 already returned PASS (0C/0W).

---

## Part A — Confirmation of the 4 Dryrun-3 Observations

| # | Prior observation | Status | Evidence in current documents |
|---|-------------------|--------|-------------------------------|
| O1 | Residual "try/finally" shorthand in §11/§12 for agent.py's timing wrap | **RESOLVED** (with one residual instance — see [O1] below, closed) | §11's agent.py bullet now reads "wraps loop.run() via the observability timing utility (timing.timed_run)". §12's agent.py box now reads "wraps loop.run() via timing.timed_run" and "(response, run_state) = timed_run (success)" — the direct-unpack and try/finally phrasings dryrun-3 cited are gone. Both instances named in dryrun-3's O1 (the agent.py bullet and the §12 agent.py box) are fixed. One uncited residual remains on the §11 *timing.py* annotation line — same cosmetic class, closed below. |
| O2 | requirement.md MPP-5 AC still named `AXIOM_DEBUG=1` alongside `--debug` | **RESOLVED** | requirement.md MPP-5's logger AC now reads: "An `axiom`-namespaced logger is configured at DEBUG level, writing to stderr, enabled via the `--debug` CLI flag (configured by `agent.py`); the latency record is retrievable from this stream at sign-off by running `python -m axiom.interface.cli --debug`." The string `AXIOM_DEBUG` appears nowhere in requirement.md; the example command matches §10's sign-off command exactly. Requirement, design, and task now specify one mechanism with one reading. |
| O3 | task.md's `timed_run` return annotation names `RunState`, unimportable in stdlib-only timing.py | **RESOLVED** (with a literal-completeness nit — see [O2] below, closed) | task.md's Observability task now prescribes: "Resolve the `RunState` return annotation with a `typing.TYPE_CHECKING` guard: place `from axiom.interfaces import RunState` under `if TYPE_CHECKING:` only (stdlib `typing` module; zero runtime import cost) so the type intent survives in static analysis without causing a `NameError` at import time." This is the exact resolution dryrun-3 recommended. |
| O4 | OQ-1/OQ-2 deferral should be formally documented | **RESOLVED** | §14 now carries an explicit deferral-status paragraph: "OQ-1 and OQ-2 are ACCEPTED design-time deferrals — each is verified at implementation, fails loudly on the first live call, and is contained to a single function (`agent.py` constant and `_collect_query_result()` respectively). Closed-by-decision, not open gaps." Both rows retain their resolve-at-sign-off / confirm-during-implementation status. This is a formal closure record, not a silent omission. |

**Confirmation result: 4 / 4 dryrun-3 Observations resolved or closed-by-decision.**

---

## Part B — Fresh Pass Findings (Passes 1–9)

## Critical Gaps (must fix before implementation)

*None found.*

Full re-trace performed. Pass 1: all six MPP stories map to design sections (§13 traceability table verified row-by-row against requirement.md ACs; no orphan requirements, no scope creep). Pass 2: `RunState`, `Intent`, context string, raw response, result text, and the timing tuple all have a named creator, transformer, and consumer; `final_response` remains deleted; the abort path is explicitly counts-free by design, not by omission. Pass 3: the four `Protocol` contracts, the `loop.run() -> tuple[str, RunState]` contract, the `timed_run` two-variant contract, and the `Agent.run() -> str` contract agree at every boundary; format strings for both latency variants are byte-identical across §6.2, §10, §12, §13, and task.md. Pass 4: the four-exit table (§6.2) is exhaustive — RESPOND, FINISH, MAX_CYCLES, AdapterError — with `cycle_count < max` / `>= max` semantics consistent across §6.2, §12, and task.md test (c). Pass 5: the §7.6 seven-row error table covers all SDK exception classes plus timeout and empty-result; the propagation chain (adapter → loop [uncaught] → timed_run [bare-`Exception` catch, abort log, re-raise] → agent.py [typed catch → error string] → CLI print) is import-boundary-legal at every hop; `KeyboardInterrupt` is `BaseException` and passes through untouched. Pass 6: fully synchronous design, one `anyio.run()` event loop per call, no shared mutable state across calls — no concurrency hazards. Pass 7: empty `ResultMessage` text, model preamble before JSON, retry failure, unauthenticated CLI hang (120s timeout), and missing `persona.txt` (loader raises) are all specified. Pass 8: all 15 tasks name actor (Developer), action, and target module; no task is readable as a shortcut against the architecture.

---

## Warnings (should fix, may cause issues)

*None found.*

---

## Observations (worth discussing — all closed, none blocking)

### [O1] One residual "try/finally" phrase on the §11 timing.py annotation line — closed as cosmetic
§11's file-tree annotation for `observability/timing.py` still reads "Wall-clock timer utility; try/finally around loop.run(); emits DEBUG log". This instance was not among the two dryrun-3 O1 cited (agent.py bullet, §12 box — both now fixed); it is the same cosmetic-shorthand class. The mechanism is catch-log-re-raise (try/*except*), specified unambiguously in §6.1, §6.2, §7.6, §10, §12, and — decisively — the task.md Observability task the implementer executes ("on abort (`loop_fn` raises any exception), emit ... then re-raise"). A file-tree comment cannot override five authoritative specifications plus the executed task text; no wrong implementation can result. **Closed-by-analysis** — worth the same two-word tidy next time §11 is touched; not a blocker and not grounds to reopen the design.

### [O2] The TYPE_CHECKING guard prescription is directionally correct but literally incomplete — closed as fail-loud build-time detail
Python evaluates function annotations at definition time by default, so a `TYPE_CHECKING`-guarded import alone still leaves `-> tuple[str, RunState]` raising `NameError` at import unless paired with `from __future__ import annotations` or a quoted annotation — the standard idiom pairing, which the task text does not spell out. **Closed-by-analysis**: identical containment profile to the original O3 — fails loudly on the very first `import` of `timing.py` (cannot ship broken), the fix is one standard line, no contract is affected, and any implementer applying the TYPE_CHECKING idiom (or any type checker / first test run) resolves it immediately. Recommend the implementer add `from __future__ import annotations` alongside the guard. Build-time detail, not a design gap.

### [O3] design.md header status line is stale — closed as doc hygiene
The header still reads "Status: Revised draft — ready for dryrun-design-3" and carries no revision line for the post-dryrun-3 observation fixes (§11/§12 wording, §14 deferral paragraph). Purely a bookkeeping line with zero normative content; no section of the design depends on it. **Closed-by-analysis** — update the status line to "Approved — build ready" when this report is accepted; not a blocker.

---

### Pass 9: Design-to-Task-to-AC Traceability

No "Files Changed" table exists; §11 (File Layout) body prescriptions were re-checked on both axes. File coverage is unchanged since dryrun-3; requirement.md's only change (O2 fix) touched an AC's wording, not its file references; task.md's only change (O3 fix) extended the Observability task text without altering its target.

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
| 0        | 0        | 3            |

**Confirmation**: 4/4 dryrun-3 Observations resolved or closed-by-decision (O1 wording fixed in §11/§12; O2 `AXIOM_DEBUG` removed from requirement.md MPP-5; O3 TYPE_CHECKING guard prescribed in task.md; O4 OQ-1/OQ-2 formally recorded as accepted deferrals in §14).

**New findings**: 3 Observations, each judged and **closed** above — [O1] one uncited residual "try/finally" comment (cosmetic; overridden by five authoritative specifications plus the executed task text), [O2] the TYPE_CHECKING idiom's standard `from __future__ import annotations` pairing left implicit (fails loudly at first import; one-line build-time detail), [O3] stale header status line (zero normative content). None is a Critical Gap, none is a Warning, and none reopens any contract, flow, or boundary.

**Verdict**: **PASS — BUILD READY**

Four review iterations converged: dryrun-1 FAIL (8C/6W/4O) → dryrun-2 (18/18 resolved) → dryrun-3 PASS (0C/0W) → dryrun-4 confirms all observations resolved or closed-by-decision. Every remaining item is a documented, contained, fail-loud build-time detail or a cosmetic comment with no normative force. The design's contracts, data flows, error paths, import boundaries, and task/AC traceability are internally consistent end-to-end. Implementation may begin.
