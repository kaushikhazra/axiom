# M4 · Tools — Implementation Tasks

**Spec:** `006-m4-tools`
**Status:** Skeleton (design-phase) — fleshed out at implementation time

---

- [x] **Implementer** creates `src/axiom/tools/port.py` — `ToolSpec`, `ToolResult`, `ToolsPort` Protocol. _AC-01.1, AC-01.2, AC-01.3_
- [x] **Implementer** creates `src/axiom/tools/guardrails.py` — `Classification`, `DESTRUCTIVE_TOOL_NAMES`, `GuardrailsGate`, CLI approval prompt. _AC-02.1, AC-02.2, AC-02.3, AC-02.4, AC-02.5, AC-03.1, AC-03.2, AC-03.5, AC-07.1, AC-07.2, AC-07.3, AC-07.4_
- [x] **Implementer** creates `src/axiom/tools/filesystem.py` — `ToolError`, `_resolve_scoped`, `read_file`, `write_file`, `list_dir`. _AC-04.1, AC-04.6_
- [x] **Implementer** creates `src/axiom/tools/shell.py` — `run_shell`, timeout + output cap. _AC-04.2, AC-05.1, AC-05.2, AC-05.3_
- [x] **Implementer** creates `src/axiom/tools/registry.py` — `ToolRegistry` concrete `ToolsPort`. _AC-01.4, AC-02.4_
- [x] **Implementer** creates `src/axiom/tools/smolagents_tools.py` — `ReadFileTool`, `WriteFileTool`, `ListDirTool`, `RunShellTool`. _AC-04.4, AC-04.5, AC-03.3_
- [x] **Implementer** creates `tests/test_tools_smolagents_wrappers.py` — direct `forward()` calls per wrapper against a real `ToolRegistry`. _AC-04.4, AC-04.5 (design.md D8) <!-- ⚠ not in Pass 9 skeleton — mocked act() tests in test_local_adapter.py patch CodeAgent entirely and never exercise these forward() methods, so this file is needed for real coverage -->_
- [x] **Implementer** updates `src/axiom/providers/local_adapter.py` — working_dir/gate constructor params, drop raw `open`/`subprocess` escape hatch, wire new tools into `act()`. _AC-04.3, AC-04.4, AC-05.4_
- [x] **Implementer** updates `src/axiom/providers/claude_adapter.py` — gate constructor param, `PreToolUse` hook via `ClaudeAgentOptions.hooks`, `_gate_hook`. _AC-06.1, AC-06.2, AC-06.4, AC-06.5, AC-06.6, AC-03.3, AC-03.4_
- [x] **Implementer** updates `src/axiom/interface/cli.py` — `--auto-approve-tools` and `--working-dir` flags. _AC-07.1_
- [x] **Implementer** creates `tests/test_tools_registry.py` — dispatch, unknown-tool guard, denial path, missing-required-argument path. _DoD item 6_
- [x] **Implementer** creates `tests/test_tools_filesystem.py` — read/write/list, path-traversal rejection, read-truncation cap, an OSError path surfacing as `ToolError`. _DoD item 6_
- [x] **Implementer** creates `tests/test_tools_shell.py` — success, timeout, output truncation. _DoD item 6_
- [x] **Implementer** creates `tests/test_tools_guardrails.py` — classify table, approval/denial, auto-approve bypass. _DoD item 6_
- [x] **Implementer** updates `tests/test_local_adapter.py` — add `working_dir`/`gate` to `_make_adapter()` and the direct `LocalAdapter(persona="Test")` call; rewrite `test_default_authorized_imports_includes_subprocess` to assert `subprocess` is absent. _AC-04.3, AC-04.4, AC-05.4 (design.md D11)_
- [x] **Implementer** updates `tests/test_local_adapter_spans.py` — add `working_dir`/`gate` to `_make_adapter()`. _AC-04.3, AC-04.4 (design.md D11)_
- [x] **Implementer** updates `tests/test_local_e2e.py` — add `working_dir`/`gate=GuardrailsGate(auto_approve=True)` to the direct `LocalAdapter(...)` construction in `test_e2e_create_and_run_python_file`. _AC-04.3, AC-04.4 (design.md D11)_
- [x] **Implementer** updates `e2e/m2_observability/test_e2e_observability.py` — add `gate=GuardrailsGate(auto_approve=True)` to its direct `ClaudeAdapter(...)` construction (best-effort, not a DoD blocker — see design.md Files Changed note). _AC-06.1_
- [x] **Implementer** updates `src/axiom/agent.py` — rename `M1_ALLOWED_TOOLS` to `CLAUDE_SAFE_TOOLS`, construct `GuardrailsGate`, thread `working_dir`/`auto_approve_tools`. _AC-06.3, AC-07.1_
- [x] **Implementer** creates `spikes/m4-tools/probe_can_use_tool.py`, `probe_pretooluse_hook.py`, `spike-result.md` — empirical evidence for design decision D3 (why the gate uses a `PreToolUse` hook, not `can_use_tool`). _design.md D3 (no AC — design-record only, mirrors the M2 spike precedent)_
- [x] **Implementer** fixes `src/axiom/tools/registry.py` — `execute()` now catches `TypeError` (wrong-argument-type) alongside `KeyError`, and wraps `self._gate.check(...)` in its own try/except (approval-step failures fail closed instead of propagating). _AC-01.1 <!-- ⚠ not in Pass 9 skeleton — found during dryrun-code-1 (findings B1, B2): the "never raises" port contract had two real gaps -->_
- [x] **Implementer** fixes `src/axiom/providers/claude_adapter.py` — `_gate_hook` wraps the approval call in try/except, failing closed (deny) instead of propagating (KIND-B half of dryrun-code-1 finding B2). _AC-03.4 <!-- ⚠ not in Pass 9 skeleton — found during dryrun-code-1 -->_
- [x] **Implementer** updates `tests/test_tools_registry.py` — adds `TestWrongArgumentType` and two approval-exception tests; updates error-message assertions from "missing required argument" to "invalid arguments". _AC-01.1 (dryrun-code-1 B1/B2)_
- [x] **Implementer** creates `tests/test_claude_adapter_gate.py` — direct `_gate_hook` tests: SAFE/DESTRUCTIVE classification, approve/deny, auto-approve, approval-exception fail-closed. _AC-06.2, AC-03.4 <!-- ⚠ not in Pass 9 skeleton — no existing test constructed ClaudeAdapter or exercised the gate hook at all -->_
- [x] **Implementer** fixes `src/axiom/providers/claude_adapter.py` — `act()` sets `permission_mode="bypassPermissions"` on `ClaudeAgentOptions`. _AC-06.6 (design.md D5, corrected) <!-- ⚠ not in Pass 9 skeleton — found during live-CLI verification: a hook-approved DESTRUCTIVE call silently failed to execute under the SDK's default permission_mode; see spikes/m4-tools/spike-result.md addendum -->_
- [x] **Implementer** creates `spikes/m4-tools/probe_permission_mode.py` — empirical evidence that `permission_mode="bypassPermissions"` is required for a hook-approved call to execute (not merely permissive). _design.md D5 addendum (no AC — design-record only)_
- [x] **Implementer** adds a regression test asserting `act()` constructs `ClaudeAgentOptions(permission_mode="bypassPermissions")`. _AC-06.6_

---

## Live Verification (US-08, AC-08.1–AC-08.5)

Run 2026-07-24 via `axiom-cli`, not pytest — per the milestone's own DoD item 8.

| # | Scenario | Provider | Result |
|---|---|---|---|
| AC-08.4 | SAFE task (WebSearch), expect no prompt | claude | ✅ No `[axiom] approval required` line; completed cleanly. |
| AC-08.1 | DESTRUCTIVE task, interactive approve (`y`) | claude | ✅ Prompt fired; file created with exact content after approval. |
| AC-03.3/AC-03.4 | DESTRUCTIVE task, interactive deny (`n`/EOF) | claude | ✅ Prompt fired; file NOT created; graceful text response, no crash. |
| AC-08.1 | DESTRUCTIVE task, `--auto-approve-tools` | claude | ✅ File created, no prompt (only the DEBUG auto-approve log line). |
| AC-08.4 | SAFE task (`list_dir`), expect no prompt | local | ✅ No prompt; correct file list returned (model narration added one hallucinated filename — a qwen2.5:7b quality quirk, not a gate defect). |
| AC-08.2 | DESTRUCTIVE write+execute task, `--auto-approve-tools` | local | ✅ Model's first attempt used raw `open()` — correctly **rejected** by `LocalPythonExecutor`'s sandbox (`open` no longer pre-injected, AC-04.4). Model self-corrected to the gated `run_shell` tool; each call auto-approved and logged; `greet.py` created and executed successfully. Directly confirms the dryrun-code-1 note about needing live confirmation of local-model tool-selection after the `open`/`subprocess` removal. |
| AC-08.3/AC-04.6 | Path-traversal write (`../escape_attempt.txt`), `--auto-approve-tools` | local | ✅ First attempt (approved by the gate, since approval and scoping are separate concerns) was rejected by `_resolve_scoped`'s containment check; model self-corrected to a relative path inside `working_dir`; confirmed via filesystem check that no file was created outside `working_dir`. |

**Bug found only by this pass (not by dryrun-design, dryrun-code, or the pytest suite):** a hook-approved (`{}`) DESTRUCTIVE call on the `claude` provider silently failed to execute under the SDK's default `permission_mode` — Claude's own text response attributed the failure to "the environment"/"the sandbox," not to our gate, even though the Guardrails GATE's own debug log showed `[GUARDRAILS_APPROVED]`. Root-caused via `spikes/m4-tools/probe_permission_mode.py`: `permission_mode="bypassPermissions"` is required for a hook's "no objection" decision to actually take effect (a hook `deny` already overrides it regardless, confirmed both directions). Fixed in `claude_adapter.py::act()`; `design.md` D5 and `requirement.md` AC-06.6 corrected to match; full suite re-run green (402 passed, 4 skipped) after the fix; all AC-08 scenarios above were run **after** this fix was applied.
