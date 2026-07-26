# Design Dry-Run Report #1

**Document**: `.claude/specs/006-m4-tools/design.md` (+ `requirement.md`, `task.md`)
**Reviewed**: 2026-07-23

---

## Issues found and corrected during this review

Per project convention (`.claude/specs/002-m1-prao-proof/dryrun-design-*.md`, `004-m2-observability/dryrun-design-*.md`), this section records what a first read of the design surfaced. Unlike those specs' multi-iteration history, the issues below were corrected in-place during this single pass rather than deferred to a `dryrun-design-2.md` — the sections after this one assess the **resulting, corrected** document, which is what carries the PASS verdict.

1. **`can_use_tool` does not fire (empirical, not theoretical).** The design's first draft planned to gate the Claude provider via `ClaudeAgentOptions.can_use_tool`. Before trusting that plan, it was probed live against the real SDK (`spikes/m4-tools/probe_can_use_tool.py`) — across four configurations, including one denying every tool call with no `allowed_tools` at all, the callback never fired once and Bash executed unconditionally. A `PreToolUse` hook (`spikes/m4-tools/probe_pretooluse_hook.py`) fired reliably and denied gracefully (`is_error=False`, no crash). The design (D3, §9) was rewritten around hooks. This is the single largest correction in this pass — it changes the entire KIND-B wiring mechanism.
2. **Component Map diagram was structurally wrong.** The original ASCII diagram showed both adapters' arrows converging into `ToolRegistry` before reaching `GuardrailsGate`. The actual design has `ClaudeAdapter`'s `PreToolUse` hook calling `GuardrailsGate` directly — `ToolRegistry` only implements Axiom's four KIND-A tools, never Claude's native `Bash`/`Write`/`Edit`. Fixed (§2).
3. **`ToolsPort.execute()`'s "never raises" contract was violated by its own implementation.** `ToolRegistry._dispatch()` indexed `arguments["path"]` etc. directly — a `KeyError` on a missing argument would have propagated uncaught. Fixed: `execute()` now also catches `KeyError` (§7).
4. **`filesystem.py` had no `OSError` handling**, unlike `shell.py` (which already caught `OSError`/`TimeoutExpired` around `subprocess.run`). A permission error or disk-full condition in `read_file`/`write_file`/`list_dir` would have raised uncaught, again violating the "never raises" port contract. Fixed: all three functions now wrap their I/O in `try/except OSError → ToolError` (§6). `read_file` also gained a size cap (`MAX_READ_CHARS`), matching `run_shell`'s existing output cap — an uncapped `read_file` on a large file would flood the reasoning prompt the same way uncapped shell output would.
5. **Making `working_dir`/`gate` required constructor parameters (correctly, per D6's "no silent-insecure defaults" principle) breaks existing tests that were never updated for it.** Grepped `LocalAdapter(` / `ClaudeAdapter(` across the whole tree (not just `tests/`) and found real, current call sites that construct these adapters directly without the new parameters: `tests/test_local_adapter.py` (a `_make_adapter()` helper used across 28 call sites, plus one direct call), `tests/test_local_adapter_spans.py` (its own `_make_adapter()` helper), `tests/test_local_e2e.py` (one direct call, skip-gated but must stay source-correct), and `e2e/m2_observability/test_e2e_observability.py` (one direct `ClaudeAdapter(...)` call, outside `pytest`'s `testpaths` so non-blocking but still fixed for consistency). One of these tests — `test_default_authorized_imports_includes_subprocess` — asserts the **literal opposite** of what AC-05.4 requires and must be rewritten, not just re-parameterized. All four files added to §12 Files Changed and to `task.md` (D11).
6. **Concurrent-approval-prompt edge case was undefended and undocumented.** Claude can issue parallel tool calls within one assistant turn; if more than one is `DESTRUCTIVE`, two concurrent `GuardrailsGate.request_approval()` calls could interleave garbled stdin/stderr prompts. Not a crash risk and disproportionate to redesign for at M4's scope, but was silently unhandled — now recorded as an accepted limitation in §11's Error Handling table rather than left invisible.

---

## Critical Gaps (must fix before implementation)

None remaining. (See "Issues found and corrected" above — all were resolved in this pass.)

---

## Warnings (should fix, may cause issues)

None.

---

## Observations (worth discussing)

None.

---

### Pass 9: Design-to-Task-to-AC Traceability

#### Traceability Matrix

| File/Prescription | Task Reference | AC Reference |
|---|---|---|
| `src/axiom/tools/port.py` | task.md line 8 | AC-01.1, AC-01.2, AC-01.3 |
| `src/axiom/tools/guardrails.py` | task.md line 9 | AC-02.1–AC-02.5, AC-03.1, AC-03.2, AC-03.5, AC-07.1–AC-07.4 |
| `src/axiom/tools/filesystem.py` | task.md line 10 | AC-04.1, AC-04.6 |
| `src/axiom/tools/shell.py` | task.md line 11 | AC-04.2, AC-05.1–AC-05.3 |
| `src/axiom/tools/registry.py` | task.md line 12 | AC-01.4, AC-02.4 |
| `src/axiom/tools/smolagents_tools.py` | task.md line 13 | AC-04.4, AC-04.5, AC-03.3 |
| `src/axiom/providers/local_adapter.py` | task.md line 14 | AC-04.3, AC-04.4, AC-05.4 |
| `src/axiom/providers/claude_adapter.py` | task.md line 15 | AC-06.1, AC-06.2, AC-06.4–AC-06.6, AC-03.3, AC-03.4 |
| `src/axiom/agent.py` | task.md line 16 | AC-06.3, AC-07.1 |
| `src/axiom/interface/cli.py` | task.md line 17 | AC-07.1 |
| `tests/test_tools_registry.py` | task.md line 18 | DoD item 6 |
| `tests/test_tools_filesystem.py` | task.md line 19 | DoD item 6 |
| `tests/test_tools_shell.py` | task.md line 20 | DoD item 6 |
| `tests/test_tools_guardrails.py` | task.md line 21 | DoD item 6 |
| `tests/test_local_adapter.py` | task.md line 22 | AC-04.3, AC-04.4, AC-05.4 (design.md D11) |
| `tests/test_local_adapter_spans.py` | task.md line 23 | AC-04.3, AC-04.4 (design.md D11) |
| `tests/test_local_e2e.py` | task.md line 24 | AC-04.3, AC-04.4 (design.md D11) |
| `e2e/m2_observability/test_e2e_observability.py` | task.md line 25 | AC-06.1 (best-effort, non-blocking) |
| `spikes/m4-tools/probe_can_use_tool.py`, `probe_pretooluse_hook.py`, `spike-result.md` | task.md line 26 (marked done — files exist on disk) | design.md D3 (design-record only, no AC — mirrors the M2 spike precedent) |

**Result**: All 18 Files Changed prescriptions traced to tasks and ACs (or explicitly marked design-record-only, consistent with the M2 precedent for spike files). No traceability gaps. `requirement.md` and `task.md` both exist; no missing-file fallback triggered.

---

## Other passes (1–8) — summary

- **Pass 1 (Completeness)**: All eight user stories (US-01–US-08) have corresponding design sections. AC-08.* (live verification) has no design *artifact* by nature — it's a verification activity performed post-implementation — which is correct, not a gap. No scope creep found: the one item beyond a literal AC (`--working-dir` CLI flag) is explicitly sanctioned by the requirement's own Non-Goals wording ("included only if trivial").
- **Pass 2 (Data Flow)**: Traced tool-call arguments from creation (smolagents `Tool.forward()` kwargs / Claude's `tool_input`) through to `ToolResult`. One diagram defect found and fixed (see above, item 2). `working_dir` resolution (`Agent.__init__` → adapter constructor, always via keyword args) traced clean — parameter *ordering* inside `LocalAdapter.__init__` is left to the implementer (any ordering with non-default params before defaulted ones works; all call sites use keyword arguments), which is a reasonable, low-stakes implementation detail rather than a design ambiguity.
- **Pass 3 (Interface Contracts)**: `ToolsPort.execute()`'s "never raises" contract — two violations found and fixed (see above, items 3–4). `GuardrailsGate`'s classify/approve seam is used identically (structurally) by both adapters, satisfying AC-02.5.
- **Pass 4 (State Machines)**: `GuardrailsGate` and `ToolRegistry` are effectively stateless after construction (immutable config only) — no state-machine risk.
- **Pass 5 (Failure Paths)**: `can_use_tool` failure (item 1), missing-argument (item 3), OS-level I/O failure (item 4) all found and fixed. Timeout paths (`run_shell`, the existing `PER_QUERY_TIMEOUT_SECS` interaction with a pending approval prompt) were already documented and are accepted as-is (§9's "Timeout interaction" note) — proportionate for M4, not a gap.
- **Pass 6 (Concurrency)**: Concurrent-approval-prompt edge case found and documented as an accepted limitation (item 6). No other concurrency hazards — KIND-A's smolagents `CodeAgent` calls tools sequentially within its own generated code; KIND-B's hook fires per tool-call event from the SDK's own control protocol, independent of Axiom's threading model.
- **Pass 7 (Edge Cases)**: Symlink escape already correctly handled by `Path.resolve()` (resolves symlinks before the containment check — verified against the existing docstring, not just assumed). Large-file `read_file` flooding the prompt — found and fixed (item 4, the `MAX_READ_CHARS` cap). Empty `run_shell` command — harmless no-op, not a real edge case. Nonexistent `working_dir` — `write_file`'s `mkdir(parents=True, exist_ok=True)` reasonably auto-creates it; not a gap.
- **Pass 8 (Task Spec Alignment)**: Every `task.md` item names actor ("Implementer"), action, and target file unambiguously — no task readable two ways.

---

## Summary

| Critical | Warnings | Observations |
|----------|----------|---------------|
| 0        | 0        | 0             |

**Verdict**: PASS

Six substantive issues (one of them, item 1, load-bearing enough to change the entire KIND-B wiring mechanism) were found and corrected during this review — see "Issues found and corrected during this review" above for the full account. The design as it now stands has zero open critical, warning, or observation findings.
