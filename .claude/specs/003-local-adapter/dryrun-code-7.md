# Code Dry-Run Report #7 — POST-E2E DEFECT FIX CONFIRMATION

**Scope**: `src/axiom/providers/local_adapter.py` (288 lines), `tests/test_local_adapter.py` (434 lines)
**Design**: `.claude/specs/003-local-adapter/design.md` (746 lines, SS18 added)
**Task**: `.claude/specs/003-local-adapter/task.md` (SS9 added)
**Research**: `.claude/research/004-local-model-tool-sdk-landscape-2026-07-09.md`
**Prior report**: `dryrun-code-6.md` — 0/0/0/0, verdict PASS (READY-FOR-E2E)
**Fix commit**: `ed946658` (worker applied Defect A + Defect B fixes)
**Reviewed**: 2026-07-09
**Purpose**: Confirm both post-E2E defect fixes are sound, new tests are non-vacuous, prior clean findings did not regress, and frozen-file invariants hold.

---

## 1. Defect A Fix — RESPOND-Forcing Framing (reason())

### Sentinel reliability

The sentinel `[TOOL EXECUTION RESULTS` is checked at `local_adapter.py` line 132. Its single source is `base.py` line 232 (`perceive()` emits it when `run_state.history` is non-empty). Verified by reading `base.py` (257 lines): no other code path produces this label. **Single source, stable.**

### Framing block correctness

Lines 140-148: prepends a "SYSTEM INSTRUCTION (highest priority)" block ahead of the perceive() context. The block states the task is ALREADY COMPLETED and the ONLY valid response is RESPOND. Prepend placement (line 149: `framing + context`) means the model sees the instruction before the lengthy tool-output section. **Correct.**

### Multi-cycle trade-off assessment

**Question**: Does forcing RESPOND after any `[TOOL EXECUTION RESULTS` presence block legitimate multi-cycle ACT?

**Answer**: No, this is acceptable for the local adapter's KIND-B semantics. One `act()` call = one complete CodeAgent run (multi-step internal loop + final answer). The CodeAgent handles all tool iterations internally. If the task genuinely needed more work, the CodeAgent should have handled it within its `max_steps`-bounded loop. A second outer-loop ACT would duplicate the delegation. The design (SS4.2) explicitly documents this: "one act() call = one complete multi-step tool loop with a Final answer." The framing is specific to the local adapter (not applied to ClaudeAdapter, which handles its own nudge correctly). **Trade-off is sound for KIND-B.**

### Retry path

Lines 168-171: `retry_context` is built from `augmented_context` (not bare `context`), so the RESPOND-forcing framing is retained on retry. **Correct.**

### Design consistency

Design SS18.1 documents the fix, root cause, sentinel source, scope limitation (local_adapter.py only), and retry retention. Code matches. **Consistent.**

---

## 2. Defect B Fix — verbosity_level=0 (act())

### Kwarg validity

`verbosity_level` is a valid `CodeAgent` constructor parameter (inherited from smolagents' `MultiStepAgent` base class). Value `0` suppresses all rich console output. Line 219: `verbosity_level=0`. **Valid kwarg.**

### Error visibility

Suppressing console logging does NOT hide errors the adapter needs. smolagents raises exceptions on CodeAgent failures (e.g., `AgentError`). These propagate through the `try/except` at lines 203-228 and are wrapped as `AdapterError`. Error information flows via exception propagation, not console output. **No error masking.**

### Design consistency

Design SS18.2 documents the fix and scope. Code matches. **Consistent.**

---

## 3. New Tests — Non-Vacuousness Audit (5 new)

| # | Test | What it exercises | Vacuous? |
|---|------|-------------------|----------|
| 1 | `test_post_act_context_prepends_framing_block` (lines 215-238) | Builds a post-act context with sentinel, calls reason(), inspects the actual prompt sent to mock model — asserts "SYSTEM INSTRUCTION" and "ALREADY completed" present, and original context preserved | **NO** — inspects call_args, verifies framing injected |
| 2 | `test_no_framing_block_without_history` (lines 240-251) | Builds a context WITHOUT sentinel, calls reason(), asserts sent_text does NOT contain "SYSTEM INSTRUCTION" and equals the plain context exactly | **NO** — verifies framing is conditional |
| 3 | `test_post_act_context_returns_respond_intent` (lines 253-268) | Post-act context + model returns RESPOND → asserts RespondIntent with correct text | **NO** — integration of framing + parse |
| 4 | `test_post_act_retry_also_uses_framing` (lines 270-290) | Post-act context, first call returns bad JSON, retry succeeds. Inspects retry call's sent_text — asserts framing present in retry prompt | **NO** — verifies retry retains augmented_context |
| 5 | `test_act_verbosity_level_zero_suppresses_console_logging` (lines 361-385) | Calls act(), inspects CodeAgent constructor kwargs — asserts `verbosity_level` key present and value is 0, with descriptive failure messages | **NO** — directly verifies constructor kwarg |

**Updated test**: `test_act_passes_correct_constructor_args` (line 355) now also asserts `verbosity_level == 0` in the constructor kwargs. **Non-vacuous extension.**

**5 new tests, 0 vacuous. All exercise the actual fix mechanisms with meaningful assertions.**

---

## 4. Frozen-File Invariants

| File | Lines | Status | Evidence |
|------|-------|--------|----------|
| `src/axiom/loop.py` | 97 | **UNTOUCHED** | Imports `axiom.interfaces` only; PraoLoop unchanged; no defect-fix code |
| `src/axiom/interfaces.py` | 121 | **UNTOUCHED** | All contracts intact; no new types added |
| `src/axiom/providers/base.py` | 257 | **UNTOUCHED** | `perceive()` sentinel label at line 232 unchanged; `_parse_intent()` unchanged; `strict=False` unchanged |
| `src/axiom/providers/claude_adapter.py` | 214 | **UNTOUCHED** | No defect-A framing, no verbosity_level; completely unrelated to fixes |

**All four frozen files confirmed untouched. Zero diff.**

---

## 5. Prior Clean Findings Regression Check (from dryrun-code-6)

| Finding | Expected state | Current state | Regressed? |
|---------|---------------|---------------|------------|
| G1: timeout kwarg | `timeout=PER_QUERY_TIMEOUT_SECS` in `_query_model()` | Present at line 264 | **NO** |
| G2: constructor-in-try | CodeAgent constructor inside try/except in `act()` | Constructor at line 213, inside try at line 203 | **NO** |
| W1: differentiated error tags | 4 tags (OLLAMA_DOWN, MODEL_NOT_FOUND, TIMEOUT, UNEXPECTED) | Present at lines 274-287 | **NO** |
| W2: hasattr guard | `hasattr(response, "content")` check before `.content` access | Present at lines 267-269 | **NO** |
| strict=False | `json.loads(..., strict=False)` in base.py | Unchanged (base.py untouched) | **NO** |
| Fresh CodeAgent per act() | No `self._agent` stored; CodeAgent created in act() | Constructor at line 213 inside act(); no `self._agent` in `__init__` | **NO** |

**All 6 prior findings remain closed. No regressions.**

---

## 6. Additional Invariants

| Invariant | Status |
|-----------|--------|
| Zero axiom-authored tool code | **PASS** — no tool schemas, executors, or registries in local_adapter.py |
| No module-level subprocess import | **PASS** — `subprocess` appears only as string in authorized_imports (line 83) and as `builtins` import inside act() (line 207) |
| Import boundary clean | **PASS** — local_adapter.py imports: `logging`, `axiom.interfaces`, `axiom.providers.base`, `smolagents` (deferred in __init__ and act()) |
| PRAO port mapping coherent | **PASS** — perceive/observe inherited, reason = tool-less LiteLLMModel, act = fresh CodeAgent |
| Design SS18 documents both fixes | **PASS** — SS18.1 (Defect A) and SS18.2 (Defect B) present and accurate |
| Task SS9 documents fix tasks | **PASS** — three checked items: Defect A, Defect B, new tests |
| Test count | 28 local-adapter tests (23 prior + 5 new) + 26 M1 contracts = 54 minimum; user reports 77 total (includes test_shared_base.py and others) |

---

## Summary

| Bugs | Gaps | Warnings | Style |
|------|------|----------|-------|
| 0 | 0 | 0 | 0 |

**Defect A fix**: Sound. Sentinel is single-source (base.py perceive()). Framing block correctly steers reason() to RESPOND. Trade-off (no second ACT after history) is acceptable for KIND-B one-act-equals-full-delegation semantics. Retry path retains framing. Design SS18.1 consistent.

**Defect B fix**: Sound. `verbosity_level=0` is a valid CodeAgent kwarg. Errors propagate via exceptions, not console output — no masking. Design SS18.2 consistent.

**New tests**: 5 new, 0 vacuous. Cover framing injection, conditional application, retry retention, and verbosity kwarg.

**Frozen files**: loop.py, interfaces.py, base.py, claude_adapter.py — all confirmed untouched.

**Prior findings**: All 6 from dryrun-code-6 remain closed, no regressions.

**Verdict: PASS — READY-FOR-E2E-RERUN**

Goal bar met: 0 bug / 0 gap / 0 warning / 0 style. Both post-E2E defect fixes are structurally sound, well-tested, properly documented, and introduce no regressions. The adapter is ready for E2E re-run against Ollama + qwen2.5:7b to confirm the fixes resolve the live scenarios.
