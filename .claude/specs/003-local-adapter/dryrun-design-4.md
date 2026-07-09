# Design Dry-Run Report #4

**Document**: `.claude/specs/003-local-adapter/design.md` (661 lines, revised 2026-07-09)
**Reviewed**: 2026-07-09
**Reviewer**: Velasari
**Purpose**: CONFIRMING pass. Dryrun-design-3 returned 0 Critical / 3 Warnings / 5 Observations; a design-fix worker (19458a64) resolved all 8. This review confirms those resolutions are genuine and that the revision introduced no new gaps or inconsistencies.

**Inputs read:**
- `.claude/specs/003-local-adapter/dryrun-design-3.md` (prior findings, 209 lines)
- `.claude/specs/003-local-adapter/requirement.md` (163 lines, revised)
- `.claude/specs/003-local-adapter/design.md` (661 lines, revised)
- `.claude/specs/003-local-adapter/task.md` (72 lines, revised)
- `.claude/specs/002-m1-prao-proof/design.md` (M1 port contract, 789 lines)
- `.claude/research/004-local-model-tool-sdk-landscape-2026-07-09.md` (decision doc, 202 lines)

---

## Prior Findings Confirmation

### W1 -- LiteLLMModel Standalone API: RESOLVED

**What dryrun-3 found:** `_query_model()` assumes `self._model(messages, stop_sequences=None)` calling convention and `response.content` return attribute -- unverified against the installed smolagents version. If wrong, `reason()` is 100% broken.

**What the fix did:** (a) Marked the calling convention and return type PROVISIONAL with inline comments in SS4.3 code. (b) Added `hasattr(response, 'content') else str(response)` guard on the return value. (c) Added a mandatory "Implementation Step 0" instruction in SS4.3: verify `LiteLLMModel.__call__` signature against installed smolagents **before** writing `_query_model()`. (d) OQ-1 in SS15 updated to RESOLVED with the same detail.

**Confirmation:** Genuine resolution. The risk was that the implementer would write `_query_model()` blindly and discover the API mismatch only at test time. The fix makes API verification a **blocking first step** (task.md item 3 Step 0 says "mandatory first"), not post-hoc cleanup. The `hasattr` guard is a secondary defence that prevents a hard crash even if the attribute name is wrong -- the fallback `str(response)` produces something parseable by `_parse_intent()` or triggers the retry/fallback path gracefully. Both the design (SS4.3) and task.md (item 3 Step 0) are consistent on this. **Closed.**

### W2 -- CodeAgent Statefulness Across act() Calls: RESOLVED

**What dryrun-3 found:** Design defaulted to reusing a single `CodeAgent` instance across `act()` calls. If `CodeAgent.run()` accumulates history between runs, multi-cycle PRAO loops would exhibit stale-context contamination.

**What the fix did:** Changed the design default to **fresh CodeAgent per `act()` call**. Removed `self._agent` from the constructor; stored `self._max_steps` and `self._authorized_imports` instead. `act()` constructs a new `CodeAgent` before each delegation.

**Confirmation -- cross-checked four locations:**
1. SS4.1 (line 102): "The CodeAgent is created **fresh on every `act()` call** -- this is the safe design default." Explicit, unambiguous.
2. SS4.4 (line 217): `act()` code creates `CodeAgent(model=self._model, ...)` inside the method body, not from `self._agent`. Comment says "W2 -- safe default: no cross-call state leakage."
3. SS6 (line 348-349): Constructor stores `self._max_steps` and `self._authorized_imports` with comment "CodeAgent is created FRESH per act() call (W2 resolution). No self._agent here."
4. task.md item 3: "Does NOT create `self._agent` in `__init__` (W2 -- fresh-per-call default)" and "act() (W2): Developer creates a fresh `CodeAgent(...)` at the start of each `act()` call."

All four locations are internally consistent. No residual `self._agent` reference anywhere in the design. Reuse is explicitly labelled a "performance optimisation deferred until statefulness is explicitly confirmed by test." **Closed.**

### W3 -- E2E #3 Literal File-Creation-and-Execution Requirement: RESOLVED

**What dryrun-3 found:** Design was ambiguous about whether E2E #3 ("Create a Python script") meant in-memory code execution (sandbox-friendly) or actual file written to disk + executed (which might hit sandbox restrictions). The requirement from Kaushik is literal: real file creation + real execution.

**What the fix did:** (a) E2E #3 design updated to specify: write real `hello.py` via `open('hello.py', 'w')`, execute via `subprocess.run(['python', 'hello.py'], capture_output=True, text=True)`, capture stdout. (b) `"subprocess"` added to `additional_authorized_imports` as the minimum addition needed. (c) Security tradeoff documented in SS5.2. (d) requirement.md MLA-5 E2E #3 updated with bold emphasis: "This is a real file written to disk and really executed -- NOT merely running `print('hello world')` inline in the interpreter's memory."

**Confirmation -- cross-checked five locations:**
1. requirement.md MLA-5 E2E #3 (line 109): Literal phrasing preserved, bold clarification added. Explicitly says "subprocess is included in additional_authorized_imports for this purpose."
2. SS5.2 (lines 287-298): Documents `open()` as a builtin (no import needed), `subprocess` as explicitly authorized, security tradeoff stated and accepted for M3 dev-machine proof.
3. SS6 constructor (line 341): Default `authorized_imports` list includes `"subprocess"`.
4. SS12.4 E2E #3 (line 531): Test description specifies the literal file-write + subprocess-exec path. Test assertion checks output contains "hello world" regardless of exact execution path.
5. task.md item 9 (line 71): "Test input MUST use Kaushik's literal phrasing (file creation + execution), NOT a rephrased 'code execution only' variant."

The requirement has NOT been watered down. The design explicitly requires real disk I/O + real process execution, not an in-memory shortcut. **Closed.**

### O1 -- Sandbox Trust Without Independent Verification: RESOLVED (accepted)

SS5.2 (line 296): "M3 trusts smolagents' PythonInterpreterTool sandbox enforcement without independent verification. Acceptable for a dev-machine proof where the developer controls the environment. Production deployments must independently verify sandbox claims or adopt E2B/Docker execution before granting subprocess to model-generated code." Explicit acceptance with scoped applicability. **Closed.**

### O2 -- No Custom system_prompt for CodeAgent: RESOLVED (decided)

SS4.4 (lines 247): Decision documented with three-part rationale: (a) smolagents' default is designed for CodeAct, (b) the qwen2.5:7b ACT-loop fix was in `perceive()` not the CodeAgent's prompt scope, (c) override is the named escape hatch if E2E testing reveals issues. **Closed.**

### O3 -- max_steps=5 Preserves Parity: RESOLVED (accepted)

SS6 (line 359): "max_steps defaults to 5, preserving behavioural parity with the prior design's MAX_TOOL_ITERATIONS=5 (O3 -- accepted: intentional continuity)." **Closed.**

### O4 -- Import Boundary and Frozen-File Constraints Honoured: RESOLVED (positive finding)

SS11 (lines 493): Explicit note clarifies that `subprocess` in `additional_authorized_imports` grants subprocess to model-generated code inside the PythonInterpreterTool sandbox -- "it is NOT an import in `local_adapter.py` itself." The frozen-file constraint is fully honoured. `local_adapter.py` import boundary: `axiom.interfaces`, `axiom.providers.base`, `smolagents` (deferred), `logging`, stdlib. NO `subprocess` import. NO `litellm` direct import. **Closed.**

### O5 -- additional_authorized_imports Configurable by Caller: RESOLVED (scoped)

SS5.2 and SS6 document: default set is `["math", "statistics", "datetime", "json", "re", "subprocess"]`. Caller MAY override; "production callers should restrict, not expand." Risk is acknowledged and bounded. **Closed.**

---

## Invariant Re-Verification (Regression Check)

| Invariant | Status | Evidence |
|-----------|--------|----------|
| Zero axiom-authored tool code | Honoured | SS5.1: `tools=[]`, `add_base_tools=True`. No SHELL_TOOL_SCHEMA, no _execute_shell_tool, no _run_tool_loop anywhere in design. |
| base.py / claude_adapter.py / loop.py / interfaces.py untouched | Honoured | SS9 file layout: all four marked [UNCHANGED]. SS17 out-of-scope restates "Changes to loop.py, interfaces.py, base.py, or claude_adapter.py -- hard constraint; frozen." |
| M1's 26 tests stay green | Honoured | SS12.3: "All 26 existing tests must pass without modification. Already confirmed -- no files they depend on are changing." task.md items 1-2 (shared base + ClaudeAdapter refactor) both marked [x] done with "M1's 26 tests must pass without modification." |
| PRAO port mapping coherent | Honoured | SS4.2 table: perceive/observe inherited (PraoAdapterBase, outer loop); reason = tool-less LiteLLMModel direct call (outer loop); act = CodeAgent.run delegation (KIND-B inner worker). Matches M1 contract exactly -- port signatures verbatim from interfaces.py. |
| subprocess authorized-import is sandbox-scoped only | Honoured | SS11 end-note (line 493): "`subprocess` addition in `additional_authorized_imports` grants subprocess to **model-generated code** executing inside smolagents' PythonInterpreterTool sandbox -- it is NOT an import in `local_adapter.py` itself." Module-level import boundary for local_adapter.py explicitly says "NO `subprocess` import." |
| FakeAdapter unchanged | Honoured | SS9: fake_adapter.py [UNCHANGED]. SS3.2: "FakeAdapter does not (it has its own tracking logic)." |

No regressions detected from the revision.

---

## Full 9-Pass Review (New Gaps Check)

### Pass 1: Completeness Check

| Requirement Story | Design Coverage | Task Coverage |
|-------------------|----------------|---------------|
| MLA-1 (four Protocols, zero loop changes) | SS4, SS6, SS9, SS11, SS14 | Task 3, Task 4 (done), Task 5 (done) |
| MLA-2 (shared perceive/observe, W3 debt) | SS3 (already implemented) | Task 1 (done), Task 2 (done) |
| MLA-3 (act() via CodeAgent) | SS4.4, SS5 | Task 3 |
| MLA-4 (fast unit tests) | SS12.1 | Task 7 (done), Task 8 |
| MLA-5 (live E2E, 3 scenarios) | SS12.4 | Task 9 |
| MLA-6 (M1 26 tests green) | SS12.3 | Task 1-2 (done; constraint restated) |

All requirements have corresponding design elements. No design elements lack corresponding requirements. No scope creep detected.

### Pass 2: Data Flow Trace

- **User input** -> cli.py -> agent.py -> PraoLoop.run() -> RunState constructed internally -> perceive(RunState) -> context string -> reason(context) -> _query_model(prompt) -> LiteLLMModel(messages) -> response -> _parse_intent(raw) -> Intent
- **If ACT:** act(instruction) -> fresh CodeAgent -> CodeAgent.run(instruction) -> [internal CodeAct loop: Python code gen -> PythonInterpreterTool/DuckDuckGoSearchTool execution -> observe -> iterate] -> result -> str(result) -> observe(result, RunState) -> RunState mutated -> loop back to perceive
- **If RESPOND:** return (intent.text, RunState) -> agent.py -> cli.py -> print

All data created is consumed. All data consumed is created. No orphaned flows. `_model` (LiteLLMModel) is created in `__init__` and consumed by both `_query_model()` (reason path) and `CodeAgent` constructor (act path) -- shared correctly.

### Pass 3: Interface Contract Validation

All boundaries explicitly defined:
- **LocalAdapter <-> PraoLoop:** Four Protocol signatures from interfaces.py. Verbatim match confirmed against M1 design SS3.
- **LocalAdapter <-> LiteLLMModel:** PROVISIONAL but defended (hasattr guard + Step 0 verification). Contract violation produces AdapterError, not silent failure.
- **LocalAdapter <-> CodeAgent:** `CodeAgent.run(instruction) -> result`, wrapped in `str()`. Contract violation (exception) produces AdapterError.
- **LocalAdapter <-> PraoAdapterBase:** Inheritance. perceive()/observe()/_parse_intent() contracts unchanged from M1.

No implicit interfaces found.

### Pass 4: State Machine & Transitions

- **PraoLoop state machine:** Unchanged from M1. States: initial -> perceive -> reason -> {RESPOND: return, ACT: act -> observe -> cycle check -> perceive, FINISH: return, MAX_CYCLES: raise}. No unreachable states, no states without exit.
- **CodeAgent:** Created fresh per act() call (W2 resolved). No cross-call state. Internal state machine is smolagents' concern, bounded by max_steps.
- **RunState:** Mutate-and-return semantics documented (M1 SS5). Single owner (PraoLoop).

No state disagreements possible.

### Pass 5: Failure Path Analysis

| Failure | Handler | Blast Radius | Cascades? |
|---------|---------|--------------|-----------|
| Ollama down | AdapterError (SS4.5) | Turn terminates | No |
| Model not found | AdapterError (SS4.5) | Turn terminates | No |
| Query timeout | AdapterError (SS4.5) | Turn terminates | No |
| CodeAgent internal error | AdapterError (SS4.5) | Turn terminates | No |
| Malformed intent JSON | Retry once -> fallback RESPOND (SS4.3) | Graceful degradation | No |
| smolagents not installed | ModuleNotFoundError at __init__ (SS6) | Construction fails | No |
| max_steps exhausted | CodeAgent returns partial; act() wraps in str() | Degraded result, not crash | No |

All failure paths terminate cleanly. No silent failures. No cascading failures. retry strategy in reason() is appropriate (single bounded retry, then fallback -- no infinite retry loop).

### Pass 6: Concurrency & Ordering

Entirely synchronous. smolagents/litellm is synchronous (SS8: "None -- smolagents/litellm is synchronous"). No async bridge needed (unlike ClaudeAdapter). No shared mutable state across threads. No concurrency concerns.

### Pass 7: Edge Cases & Boundaries

- **Empty input:** perceive() assembles context with empty user_input; reason() receives it; model produces an intent (likely RESPOND). No crash path.
- **Cold start:** Pre-warming specified (SS8, SS12.4). First inference after model load is slow (~10-30s); pre-warm separates cold-load from inference latency.
- **Maximum-size input:** No truncation in M3 (same as M1 -- deliberate deferral, acceptable at MAX_CYCLES=10).
- **Partial deployment:** Not applicable -- single-process, single-machine. No distributed components.
- **smolagents upgrade breaking API:** Step 0 mandatory verification catches this at implementation time, not silently at runtime.

### Pass 8: Task Spec Alignment

| Task | Actor | Action | Target | Ambiguity? |
|------|-------|--------|--------|------------|
| Task 1 (shared base) | Developer | creates | base.py | [x] done, unambiguous |
| Task 2 (ClaudeAdapter refactor) | Developer | refactors | claude_adapter.py | [x] done, unambiguous |
| Task 3 (LocalAdapter rewrite) | Developer | rewrites | local_adapter.py | Clear. Step 0 specified. W2 act() specified. |
| Task 4 (agent.py) | Developer | updates (no-op) | agent.py | [x] done, unambiguous |
| Task 5 (CLI) | Developer | updates (no-op) | cli.py | [x] done, unambiguous |
| Task 6 (dependencies) | Developer | updates | pyproject.toml | Clear: replaces litellm -> smolagents |
| Task 7 (shared base tests) | Developer | creates (already exists) | test_shared_base.py | [x] done, unambiguous |
| Task 8 (unit tests) | Developer | rewrites | test_local_adapter.py | Clear. Mocking strategy specified (patch CodeAgent constructor). |
| Task 9 (E2E tests) | Developer | rewrites | test_local_e2e.py | Clear. Three scenarios specified. Literal phrasing mandated. |

No task can be read two ways. Each specifies actor, action, and target. Design decisions in SS4.1 (fresh-per-call), SS4.3 (Step 0), SS5.2 (subprocess authorization) all have corresponding task items.

### Pass 9: Design-to-Task-to-AC Traceability

#### Files Changed from SS9

| File | Change | Task Match | AC Match |
|------|--------|------------|----------|
| `local_adapter.py` [CHANGED] | Rewritten: smolagents replaces litellm hand-rolled tool harness | Task 3 (explicit) | MLA-1 (adapter implements Protocols), MLA-3 (act via CodeAgent) |
| `test_local_adapter.py` [CHANGED] | Rewritten for smolagents mocking | Task 8 (explicit) | MLA-4 (fast unit tests) |
| `test_local_e2e.py` [CHANGED] | Rewritten: 3 E2E scenarios | Task 9 (explicit) | MLA-5 (live E2E) |
| `pyproject.toml` [CHANGED] | Swaps litellm -> smolagents | Task 6 (explicit) | MLA-1 (smolagents as backend) |

#### Body Prescriptions (outside Files Changed table)

| Prescription | Source Section | Task Match | AC Match |
|-------------|---------------|------------|----------|
| `_query_model()` PROVISIONAL + Step 0 verification | SS4.3 | Task 3 Step 0 | MLA-1 (smolagents as model backend) |
| Fresh `CodeAgent` per `act()` call | SS4.1, SS4.4, SS6 | Task 3 act() subsection | MLA-3 (CodeAgent delegation) |
| `"subprocess"` in `additional_authorized_imports` | SS5.2, SS6 | Task 3 (authorized imports in constructor) | MLA-5 E2E #3 (file creation + execution) |
| `add_base_tools=True` on CodeAgent | SS4.1, SS5.1 | Task 3 (CodeAgent construction) | MLA-1 (zero axiom-authored tool code), MLA-3 |

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|-------------------|---------------|--------------|
| `local_adapter.py` -- smolagents rewrite | Task 3 | MLA-1, MLA-3 |
| `test_local_adapter.py` -- smolagents mocking | Task 8 | MLA-4 |
| `test_local_e2e.py` -- 3 E2E scenarios | Task 9 | MLA-5 |
| `pyproject.toml` -- litellm -> smolagents | Task 6 | MLA-1 |
| Body SS4.3: `_query_model()` Step 0 | Task 3 Step 0 | MLA-1 |
| Body SS4.1/4.4/6: fresh CodeAgent per act() | Task 3 act() | MLA-3 |
| Body SS5.2/6: subprocess in authorized_imports | Task 3 constructor | MLA-5 E2E #3 |
| Body SS4.1/5.1: add_base_tools=True | Task 3 CodeAgent | MLA-1, MLA-3 |

**Result**: All 8 file-level prescriptions traced to tasks and ACs. No traceability gaps.

---

## Architectural Consistency Check (unchanged from dryrun-3 + re-verified)

| Constraint | Status |
|------------|--------|
| PraoLoop drives outer cycle; CodeAgent owns inner worker loop (KIND-B) | Honoured |
| Port signatures match M1 contract verbatim | Honoured |
| loop.py imports zero provider code | Honoured |
| interfaces.py has zero diff from M1 | Honoured |
| base.py has zero diff (already extracted) | Honoured |
| claude_adapter.py has zero diff (already refactored) | Honoured |
| Zero axiom-authored tool code | Honoured |
| AdapterError error contract consistent with M1 | Honoured |
| M1's 26 tests unaffected | Honoured |
| FakeAdapter unchanged | Honoured |
| subprocess authorized-import is sandbox-scoped, NOT a module-level import | Honoured |

---

## Critical Gaps (must fix before implementation)

None.

---

## Warnings (should fix, may cause issues)

None.

---

## Observations (worth noting)

### [O1] SS16 resolution record is a positive pattern

The new SS16 (Design Review Resolutions) provides an explicit resolution record for each dryrun-3 finding, with the design location cross-referenced. This makes the design self-documenting about its review history and ensures future readers can trace why specific decisions were made. Worth adopting as a standard practice for post-dryrun revisions.

### [O2] CodeAgent import redundancy in constructor is intentional fail-fast

SS6 constructor imports `from smolagents import CodeAgent, LiteLLMModel` but only uses `LiteLLMModel` in `__init__`. `CodeAgent` is imported again inside `act()` (SS4.4 line 222). The constructor import serves as a fail-fast check: if smolagents is installed but `CodeAgent` is missing (broken installation), `__init__` fails immediately rather than succeeding and then crashing on the first `act()` call. The `act()` re-import is a free dict lookup after the first load. This is defensive design, not redundancy.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|--------------|
| 0        | 0        | 2            |

**Verdict**: **PASS**

All 3 Warnings and 5 Observations from dryrun-design-3 are confirmed genuinely resolved. Each resolution was verified against multiple locations in the design for internal consistency. The revision introduced no new Critical gaps, no new Warnings, and no regressions against M1 invariants. The design is ready for implementation.

---

*Reviewed by Velasari, 2026-07-09. This is review iteration 4 -- the confirming pass after dryrun-design-3's findings were resolved by the design-fix worker (19458a64). Iterations 1-2 reviewed the superseded litellm-era design; iteration 3 was the first review of the smolagents-migrated design; iteration 4 confirms all iteration-3 findings are closed.*
