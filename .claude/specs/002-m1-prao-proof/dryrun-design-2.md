# Design Dry-Run Report #2

**Document**: `.claude/specs/002-m1-prao-proof/design.md` (revised, 727 lines)
**Reviewed**: 2026-07-08
**Also read**: `requirement.md` (same spec, updated), `task.md` (same spec — now populated, 15 tasks), `dryrun-design-1.md` (prior findings), `.claude/specs/001-agent-core/architecture.md`
**Scope**: (a) Regression check of all dryrun-design-1 findings (C1–C8, W1–W6, O1–O4); (b) fresh full-pass dry-run of the revised design.

---

## Part A — Regression Check (dryrun-design-1 findings)

| # | Prior finding | Status | Evidence in revised design |
|---|--------------|--------|---------------------------|
| C1 | Intent wire format unspecified | **RESOLVED** | §4.1 locks strict single-line JSON envelope: verbatim model instruction text, 7 numbered parse rules (case-sensitive intent values, per-kind required fields, typed-field validation), explicit multi-line payload handling (`\n` escapes; `json.loads()` tolerates whitespace), preamble failure mode routed to §7.2. Nothing left to invent. |
| C2 | Parse-failure fallback contradicts "strict parsing" / silent | **RESOLVED** | §7.2 step 5 specifies: `WARNING [INTENT_PARSE_FAILURE]` log with raw response + error, one bounded retry with correction notice, then `WARNING [INTENT_FALLBACK]` (distinct marker) + `RespondIntent("[FALLBACK_RESPOND] {raw}")`. Fallback is now logged, bounded, and distinguishable — no longer a silent failure. |
| C3 | No SDK/subprocess failure path | **RESOLVED** | §7.5 defines a 120s per-query timeout (`anyio.fail_after`, `PER_QUERY_TIMEOUT_SECS`); §7.6 gives a 7-row scenario table (CLI not found, auth fail, process crash, JSON decode, generic SDK error, timeout, empty result) each with a distinct `ERROR [ADAPTER_*]` marker and `AdapterError` re-raise, plus an explicit propagation path adapter → loop (uncaught) → agent.py (caught → `"[Error: ...]"`) → CLI print. Empty-result behaviour is explicitly decided (valid empty response, not an error). |
| C4 | `spawn_count` had no owner / no path to timing.py | **RESOLVED** | §5 adds `spawn_count` to `RunState` with defined semantics ("Hello"=1, one-cycle task=3); §6.1/§6.2 make the loop increment it before each dispatch; `loop.run()` returns `tuple[str, RunState]`; §10 shows agent.py unpacking it for the timing utility. Consistent across §5, §6.2 flow, §10, §12 diagram, and §13 (MPP-5 row). *(But see new [C1] below — the transport breaks on the exception path.)* |
| C5 | `loop.run()` / constructor contract undefined | **RESOLVED** | §6.1 specifies the full `PraoLoop` API: four port-typed constructor params + `max_cycles` (default via module constant, agent.py may override), `run(user_input) -> tuple[str, RunState]`, initial `RunState` constructed inside `run()`, caller does not pre-populate. Four-slot rationale (partial adapters) recorded. |
| C6 | Terminal-path return contracts undefined | **RESOLVED** | §6.2 exit-contracts table covers all four exits (RESPOND/FINISH/MAX_CYCLES/AdapterError) at all three layers (loop → agent → CLI), incl. FINISH → `""` → `if response: print(response)` prints nothing. `final_response` is deleted from `RunState` (§5) — ownership question dissolved. MAX_CYCLES delivery = typed `MaxCyclesExceededError` (defined in `interfaces.py` per §11), caught in agent.py, converted to error string; CLI needs no exception import. |
| C7 | Sync ports vs async SDK bridge undesigned; §7 call shape wrong | **RESOLVED** | §7 header verifies SDK v0.1.55: tool scoping via `ClaudeAgentOptions(allowed_tools=...)` (the invalid kwarg form is explicitly called out); §7.5 decides: ports stay sync, adapter bridges via `anyio.run()` per call, chunk collection stops at first `ResultMessage`, per-call event-loop overhead explicitly folded into the measured latency, `anyio` confirmed as an existing SDK dependency. The architectural decision the implementer was forced to make is now made. *(One residual verification item — see new [O1].)* |
| C8 | task.md empty — §11 prescriptions untraced | **RESOLVED** | task.md now has 15 actor/action/target tasks covering every §11 module incl. `tests/fake_adapter.py`, `tests/test_contracts.py`, and `pyproject.toml`, each tagged to MPPs. requirement.md gained matching ACs: MPP-4 now requires the fake adapter in the test suite; MPP-5 now specifies the `AXIOM_DEBUG`/`--debug` stderr logger. Full Pass 9 re-run below — all prescriptions trace. |
| W1 | `observe()` docstring contradicted §7.4 | **RESOLVED** | §3 `ObservePort` docstring now states it does NOT decide continue-vs-stop and records the deliberate M1 deviation from architecture.md's Observer/Evaluator role. §7.4 agrees. task.md's interfaces task explicitly requires the corrected docstring. |
| W2 | Call-point wiring stubs silently dropped | **RESOLVED** | §6.3 explicitly supersedes the architecture.md M1 table row, with rationale (avoid locking wrong call signatures before contracts exist), defers to M8, and notes the phase-boundary seams. Also restated in §15. |
| W3 | perceive/observe in adapter undermines drop-in story | **RESOLVED** | §3 design note acknowledges the deviation, marks it intentional for M1, and commits perceive/observe to migrate to a shared base/core at adapter #2 — exactly the acknowledgement dryrun-1 asked for. |
| W4 | DEBUG-log capture mechanism unspecified | **RESOLVED** | §10 specifies: `axiom` logger + stderr `StreamHandler` at DEBUG, configured by agent.py, opt-in via `AXIOM_DEBUG=1` or `--debug`; `timing.py` uses child logger `axiom.observability` (inherits handler); sign-off retrieval command given. Mirrored by a new MPP-5 AC in requirement.md. |
| W5 | `allowed_tools` had no source of truth | **RESOLVED** | §7.3: `M1_ALLOWED_TOOLS: list[str] = ["Bash"]` as a named constant in agent.py, passed into `ClaudeAdapter.__init__()`, stored as `self._allowed_tools`; "Bash" covers the MPP-3 exemplar; expansion path tracked as OQ-1. |
| W6 | RunState mutability ambiguous; cycle_count skew | **RESOLVED** | §5 locks mutate-and-return semantics (documented rationale); `cycle_count` defined as "completed act→observe cycles" with the "Hello" `0 cycle(s), 1 spawn(s)` reading explicitly declared intentional; §10 example log line matches. |
| O1 | Fallback-RESPOND made MPP-2 unfalsifiable | **RESOLVED** | `[INTENT_FALLBACK]` log marker + `[FALLBACK_RESPOND]` text prefix (§7.2) make fallback distinguishable in both logs and CLI output; §13 MPP-2 row states measurement honesty explicitly. |
| O2 | No test strategy for contract tests | **RESOLVED** | §11 test-strategy paragraph: scripted in-memory `FakeAdapter` (all four Protocols, no SDK imports) doubles as second-adapter existence proof + fast deterministic tests; task.md specifies four concrete test cases with expected spawn/cycle counts. |
| O3 | Unbounded history growth stance | **RESOLVED** | §5: "No history truncation in M1 — deliberate", with the latency-pollution risk acknowledged and the decision deferred to M2 with rationale. |
| O4 | Router stub naming mismatch | **RESOLVED** | §15: "agent.py's fixed wiring of a single ClaudeAdapter IS the M1 Router stub. The Router grows into a full policy engine at M6." Exact closing note requested. |

**Regression result: 18 / 18 prior findings fully RESOLVED** (8 Critical, 6 Warnings, 4 Observations). None partial, none regressed — though the C4 fix exposes one new gap on the exception path, below.

---

## Part B — Fresh Pass Findings (new issues in the revised design)

## Critical Gaps (must fix before implementation)

### [C1] Exception-path timing log cannot access `RunState` — the promised counts are unreachable when `loop.run()` raises
- **Pass**: Pass 5 (Failure Path Analysis) / Pass 2 (Data Flow Trace)
- **What**: §6.2 and §10 promise the timing log fires (via agent.py's `try/finally`) even when `loop.run()` raises `MaxCyclesExceededError` or `AdapterError`, and the log format (§10, task.md's `timed_run` task) requires `run_state.cycle_count` and `run_state.spawn_count`. But `RunState` is constructed *inside* `loop.run()` (§6.1) and is only exposed via the **return value** `tuple[str, RunState]` — which does not exist when `run()` raises. On both error exits, the `finally` block in `timing.py`/agent.py has no `RunState` to read. Neither exception is specified to carry the run state. (The §6.2 flow diagram's "timing log fires; raise MaxCyclesExceededError" line inside the loop box compounds the ambiguity — read literally it puts the timing log in `loop.py`, which the import rules in §11 forbid, `timing.py`/`loop.py` being mutually unaware.)
- **Risk**: The implementer must invent a contract on the loop↔agent seam: attach `run_state` to the exceptions, hold a state reference outside `run()` (impossible as designed), or emit a count-less error log — each changes a specified contract (`interfaces.py` exception classes, or the §10 log format). Naive implementation of the design as written raises `NameError`/`UnboundLocalError` in the `finally` block, masking the original error. MPP-1's "never hangs, error delivered to CLI" path is exactly where this fires.
- **Fix**: Decide and document one mechanism. Recommended: `MaxCyclesExceededError` and the loop's re-raise path carry the `RunState` (e.g. `MaxCyclesExceededError(run_state=...)`; for `AdapterError`, either the loop wraps/annotates it with the current `run_state` before propagating, or the error-path log emits an elapsed-only variant (`"[M1 Latency] %.3fs (aborted: %s)"`). Update §6.2 (incl. the diagram wording), §10, and the `timed_run` task in task.md to match.

---

## Warnings (should fix, may cause issues)

### [W1] `spawn_count` field comment overclaims: retries mean actual subprocess spawns can exceed the logged count
- **Pass**: Pass 3 (Interface Contract Validation)
- **What**: §5's dataclass comment defines `spawn_count` as "total SDK query() calls dispatched", and the §10 DEBUG line labels it "SDK spawn(s)" — but §7.2 explicitly excludes the parse-failure retry query from `spawn_count` ("retries are adapter-internal, not loop-dispatched spawns"). On a retry run, actual subprocesses = spawn_count + 1, so the MPP-5 latency line reports elapsed time that includes a spawn the count doesn't show — a run could log "1 SDK spawn(s)" with 2-spawn latency.
- **Risk**: The milestone's key empirical datum (spawn-vs-latency correlation) is quietly distorted on exactly the runs where the model misformats — and the sign-off reader has no arithmetic way to reconcile the numbers without cross-referencing WARNING logs.
- **Suggestion**: Two-line fix: reword the §5 comment to "loop-dispatched query() calls (adapter-internal retries excluded — see §7.2)", and note in §10 that runs containing `[INTENT_PARSE_FAILURE]` warnings carry one extra unlogged spawn (or have the adapter expose a retry counter that agent.py adds to the log line).

---

## Observations (worth discussing)

### [O1] Illustrative bridge call shape (`await sdk_query(...)`) should be verified together with OQ-2 — and OQ-2's deferral is acceptable
§7.5's illustrative helper writes `async for message in await sdk_query(prompt=..., options=...)`. Whether `query()` must be awaited to obtain the iterator or iterated directly (`async for m in sdk_query(...)`) depends on the SDK's exact definition — the same single-function, verify-at-implementation concern as OQ-2's `ResultMessage.result` attribute name. **Deferring OQ-2 to implementation is acceptable**: it is contained to `_collect_query_result()`, fails loudly on the first live call, and the code is explicitly marked "illustrative — not final". Suggest widening OQ-2's wording to "confirm the exact `query()` call shape (await vs direct iteration) and the `ResultMessage` result attribute against the installed SDK source" so both land in the same verification step.

### [O2] `--debug` plumbing is specified with an "or" in task.md
task.md's cli.py task says `--debug` "passes to Agent constructor **or** sets `AXIOM_DEBUG` env var before constructing Agent"; §10 similarly allows either. Both respect the import boundary (cli → agent only), so this is not architecturally risky, but per the task-spec rules a two-way-readable task should pick one (recommend: constructor parameter — no process-global mutation). Related nit: §10's sign-off command `python -m axiom.interface.cli` requires cli.py to have a `if __name__ == "__main__": main()` guard (or use the `axiom-cli` entry point task.md defines) — worth one line in the cli task.

---

### Pass 9: Design-to-Task-to-AC Traceability

No "Files Changed" table exists; §11 (File Layout) body prescriptions were checked on both axes against the now-populated task.md and updated requirement.md.

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| Body §11: `src/axiom/interfaces.py` — ports + Intent + RunState + exceptions | Core Contracts task | MPP-4 AC-1 (port interface), MPP-1 AC-3 |
| Body §11: `src/axiom/loop.py` — PraoLoop | Master PRAO Loop task | MPP-1 AC-1/AC-2, MPP-2, MPP-3 |
| Body §11: `src/axiom/agent.py` — composition root, M1_ALLOWED_TOOLS, debug logging | Core Assembly task | MPP-5 AC-5 (logger config), MPP-6 AC-2 |
| Body §11: `src/axiom/persona/__init__.py` + `persona.txt` | Persona Package tasks (×2) | MPP-6 AC-1/AC-5 |
| Body §11: `src/axiom/providers/claude_adapter.py` — ClaudeAdapter + bridge + errors | Claude Adapter tasks (×6) | MPP-1 AC-3, MPP-2, MPP-3 |
| Body §11: `src/axiom/observability/timing.py` | Observability task | MPP-5 AC-1/AC-4 |
| Body §11: `src/axiom/interface/cli.py` | CLI Entry Point task | MPP-2 AC-4, MPP-6 AC-2, MPP-5 AC-5 |
| Body §11: `tests/fake_adapter.py` — FakeAdapter | Tests task 1 | MPP-4 AC-5 (fake in-memory adapter — new AC) |
| Body §11: `tests/test_contracts.py` — contract tests | Tests task 2 | MPP-4 AC-3/AC-5 (Tier 2: "confirmed by code inspection" + fake-adapter AC) |
| Body §11: `pyproject.toml` — package metadata + deps | Package Scaffold task 1 | Tier 2: requirement.md Infrastructure Dependencies — "`src/axiom` package layout — to be created in M1" |

**Result**: All 10 file-level prescriptions traced to tasks and ACs. No traceability gaps. (The two gaps from dryrun-1 — tests and pyproject — are closed by the new MPP-4 AC-5 and the Package Scaffold task + infra-dependency row respectively.)

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 1        | 1        | 2            |

**Regression**: 18/18 prior findings RESOLVED (C1–C8, W1–W6, O1–O4 — all fully resolved, none partial).

**Verdict**: **NEEDS-REVISION (narrow)** — FAIL on one item only.

The revision is genuine and thorough: every dryrun-1 finding is resolved with actual contract text, not hand-waving, and task.md/requirement.md were updated in lockstep. The design is otherwise implementable end-to-end — the wire format, the loop API, all four exit paths, the async bridge, the error table, and the spawn-count flow are internally consistent across §4/§5/§6/§7/§10/§12/§13 and task.md. The single blocker is new [C1]: the exception-path timing log is promised twice (§6.2, §10) but has no way to reach `RunState` when `loop.run()` raises — an unimplementable contract introduced by the (otherwise correct) C4/C6 fixes. It is a surgical specification fix (decide whether exceptions carry the run state or the error log drops the counts), not a redesign. Fix [C1], optionally the two-line [W1] reword, and dryrun-design-3 should PASS.
