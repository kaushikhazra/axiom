# M4 · Tools — Requirements

**Spec:** `006-m4-tools`
**Milestone:** M4 — "Structured tools + a code escape-hatch, working-dir-scoped, with an approval gate"
**Author:** Nira — 2026-07-23
**Status:** DRAFT

---

## Purpose

M4 gives Axiom a real **Guardrails GATE** — the cross-cutting call-point already named in `architecture.md` ("Before Act ... Guardrails GATE — approval gate on consequential actions; may veto or redirect the intent") but, as of M1–M3, only stubbed as pre-run `allowed_tools` scoping. M4 upgrades that stub into a genuine per-call approval gate, applied uniformly across both provider adapters, plus a small Axiom-owned structured-tool surface for the local provider.

**Baseline gap this milestone closes.** Today, the two adapters' `act()` phases have very different — and in one case genuinely unguarded — tool surfaces:

- **`ClaudeAdapter`** delegates entirely to the Claude Agent SDK's own tool loop, scoped only by a static `allowed_tools=["Bash", "WebSearch"]` pre-run allowlist (`agent.py::M1_ALLOWED_TOOLS`). Once a tool is on that list, every call to it is silently permitted — there is no per-call visibility or veto.
- **`LocalAdapter`** hands its smolagents `CodeAgent` raw, unscoped capabilities: `additional_functions={"open": builtins.open, ...}` and `subprocess` in `additional_authorized_imports` (`local_adapter.py`). This means the local provider can read, write, or delete **any file the OS user can reach**, and run **arbitrary shell commands**, with zero working-directory scoping and zero approval step. This is a real gap against the roadmap's explicit M4 promise ("the escape-hatch runs working-dir-scoped + an approval gate for destructive ops") and against `architecture.md`'s KIND-A guarantee ("our loop can inspect and veto each action step").

**What M4 builds:**
1. A small **Tools port** (`axiom.tools`) — `ToolSpec` / `ToolResult` / `ToolsPort` — and a `ToolRegistry` with four working-directory-scoped structured tools: `read_file`, `write_file`, `list_dir`, `run_shell` (the code escape-hatch).
2. A **Guardrails GATE** (`axiom.tools.guardrails`) that classifies every tool call about to run in the Act phase as `SAFE` or `DESTRUCTIVE`, and requires explicit approval for `DESTRUCTIVE` calls before they execute.
3. **Provider wiring for both adapters**, so the gate has real teeth on both sides of the port, not just one:
   - **KIND-A (`LocalAdapter`)**: the raw `open`/`subprocess` escape hatch is replaced by Axiom's own tools (wrapped as smolagents `Tool` subclasses) — working-dir-scoped, gated.
   - **KIND-B (`ClaudeAdapter`)**: the gate is wired via a `PreToolUse` hook (`ClaudeAgentOptions.hooks`) — a real per-tool-call `Allow`/`Deny` veto point, empirically confirmed to fire reliably (`spikes/m4-tools/probe_pretooluse_hook.py`). An earlier candidate, the SDK's `can_use_tool` permission callback, looked like the obvious mechanism by its type signature (`claude_agent_sdk/types.py`) but was probed and found **not** to fire in practice (`spikes/m4-tools/probe_can_use_tool.py`) — see `design.md` D3 for the full account. Either way, this is a genuine upgrade over the M1-era belief (recorded in `architecture.md`'s KIND-B row) that delegated providers only support "pre-run scope, no per-action mid-run veto" — the SDK does expose a working per-action veto point, and M4 uses it.
4. **Approval UX** at the CLI: a destructive call prints the tool name + arguments and prompts for confirmation (Claude-Code-style), with an `--auto-approve-tools` flag for headless/scripted runs (needed for the same kind of CLI-driven verification M1/M3 already used).

**Not full sandboxing.** Per the roadmap, M4 is working-directory scope + an approval gate — not container/VM isolation. Full isolation is later-phase Guardrails/Safety work, triggered by untrusted input (connectors) or multi-user deployment.

---

## User Stories

---

### US-01 — Tools port contract: structured, swappable, testable in isolation

**As** a developer extending Axiom's tool surface,
**I want** a `ToolsPort` protocol with a small `ToolSpec`/`ToolResult` value-object contract,
**so that** tool implementations are swappable and testable independent of any provider adapter, the same way `MemoryPort` and the four PRAO ports are.

#### Acceptance criteria

- AC-01.1: `axiom/tools/port.py` defines a `ToolsPort` Protocol with `list_tools() -> list[ToolSpec]` and `execute(name: str, arguments: dict) -> ToolResult`.
- AC-01.2: `ToolSpec` carries at minimum: `name`, `description`, `destructive: bool` (the classification the Guardrails GATE reads — see US-02).
- AC-01.3: `ToolResult` carries at minimum: `output: str`, `error: str | None`, `denied: bool` (set when the Guardrails GATE refused execution — see US-02).
- AC-01.4: `axiom/tools/registry.py` implements `ToolRegistry(ToolsPort)` — a concrete, in-process registry of the four built-in tools (US-04).
- AC-01.5: `loop.py` and `interfaces.py` import nothing from `axiom.tools` — the Tools port is consumed by adapters, not by the core loop (the loop's `ActPort` contract is unchanged; Tools is an adapter-side concern, matching how `MemoryPort` is loop-level but `ToolsPort` is adapter-level).

---

### US-02 — Guardrails GATE: classify every act-phase tool call as SAFE or DESTRUCTIVE

**As** the Axiom system,
**I want** every tool call made during the Act phase — on either provider — to be classified as `SAFE` or `DESTRUCTIVE` before it runs,
**so that** consequential operations (writing files, running shell commands) are never silently auto-approved the way `allowed_tools` scoping silently auto-approved them through M1–M3.

#### Acceptance criteria

- AC-02.1: `axiom/tools/guardrails.py` defines a `GuardrailsGate` with a `classify(tool_name: str) -> Classification` method (`SAFE` | `DESTRUCTIVE`), driven by a static classification table, not a per-call heuristic.
- AC-02.2: For Axiom's own tools (US-04): `read_file` and `list_dir` are `SAFE`; `write_file` and `run_shell` are `DESTRUCTIVE`.
- AC-02.3: For Claude's native tools (US-06): `WebSearch` is `SAFE`; `Bash`, `Write`, `Edit` are `DESTRUCTIVE`.
- AC-02.4: The classification table is a single source of truth (one module-level constant), read by both the KIND-A tool wrappers (US-05) and the KIND-B `PreToolUse` hook callback (US-06) — not duplicated per adapter.
- AC-02.5: `GuardrailsGate` has no provider-specific code — it is a plain classify+approve component, reusable by both adapters (mirrors the "Guardrails GATE" cross-cutting call-point named in `architecture.md`, not a port).

---

### US-03 — Destructive calls require approval; denial surfaces cleanly, no crash

**As** a user running Axiom interactively,
**I want** a `DESTRUCTIVE` tool call to pause and ask for my approval before it executes, and my decision to be respected without crashing the run,
**so that** I retain control over consequential actions the same way Claude Code's own permission prompts work.

#### Acceptance criteria

- AC-03.1: `GuardrailsGate.request_approval(tool_name: str, arguments: dict) -> bool` is the single approval seam. Both adapters call through it (directly for KIND-A, via the `PreToolUse` hook callback for KIND-B) — no adapter re-implements its own approval UX.
- AC-03.2: The default approval implementation is CLI-based: prints the tool name and a readable rendering of its arguments to stderr, then reads a y/n confirmation from stdin.
- AC-03.3: On denial, the tool call does **not** execute. For KIND-A, `ToolResult(denied=True, error="denied by user")` is returned to the calling `Tool.forward()`, which surfaces it back into the smolagents step as a normal (non-crashing) observation. For KIND-B, the `PreToolUse` hook callback returns a `permissionDecision: "deny"` payload, which the SDK surfaces back into Claude's own loop as a normal denied-tool observation — empirically confirmed (not just type-inferred): `spikes/m4-tools/probe_pretooluse_hook.py` shows the query completing with `is_error=False` and Claude's own response explaining the denial.
- AC-03.4: A denial never raises an uncaught exception and never terminates the PRAO loop early — `reason()` gets a chance to see the denial (via the next cycle's tool-result/history) and respond accordingly (e.g. explain to the user that the action was declined).
- AC-03.5: `SAFE`-classified calls never invoke the approval seam — only `DESTRUCTIVE` calls do (US-02).

---

### US-04 — Axiom-owned structured tools for the local provider, working-directory-scoped

**As** the local (KIND-A) provider,
**I want** `read_file`, `write_file`, `list_dir`, and `run_shell` to be Axiom's own tool implementations rather than raw `open`/`subprocess` access,
**so that** every file or shell operation is resolved against a configured working directory and cannot escape it — closing the gap described in Purpose.

#### Acceptance criteria

- AC-04.1: `axiom/tools/filesystem.py` implements `read_file(path)`, `write_file(path, content)`, `list_dir(path=".")`. Each resolves `path` against a configured `working_dir` root (`Path.resolve()` + a containment check) and raises/returns an error result — never executes — when the resolved path falls outside `working_dir`.
- AC-04.2: `axiom/tools/shell.py` implements `run_shell(command)`, executing via `subprocess.run(..., cwd=working_dir, timeout=<bounded>)`. The subprocess's working directory is pinned to `working_dir` regardless of what the command itself references.
- AC-04.3: `working_dir` defaults to the process's current working directory at `Agent.__init__` time and is configurable (constructor parameter, threaded from a future CLI flag — CLI flag itself is out of scope for M4 unless trivial to add; see Non-Goals if deferred).
- AC-04.4: `LocalAdapter.act()` no longer passes `additional_functions={"open": builtins.open}` or `"subprocess"` in `additional_authorized_imports`. Instead, the four tools are wrapped as smolagents `Tool` subclasses and passed via `tools=[...]` to `CodeAgent`, alongside the existing `DuckDuckGoSearchTool`.
- AC-04.5: Each smolagents `Tool` wrapper's `forward()` method classifies itself via `GuardrailsGate.classify()` and, for `DESTRUCTIVE` tools, calls `GuardrailsGate.request_approval()` before performing the real operation (US-03).
- AC-04.6: A path-traversal attempt (e.g. `read_file("../../etc/passwd")` relative to `working_dir`) is rejected with a clear error result, not a raised exception that crashes the CodeAgent step.

---

### US-05 — `run_shell` is the code escape-hatch

**As** the local provider's executor,
**I want** `run_shell` to be the single sanctioned way to run arbitrary commands,
**so that** the "hybrid action space" (structured tools + code escape-hatch) named in the roadmap is explicit and auditable, rather than implicit via bare Python `subprocess` access.

#### Acceptance criteria

- AC-05.1: `run_shell` is classified `DESTRUCTIVE` (US-02) — every invocation requires approval unless `--auto-approve-tools` is set (US-07).
- AC-05.2: `run_shell` has a bounded execution timeout (module-level constant, consistent in spirit with `PER_QUERY_TIMEOUT_SECS` elsewhere in the codebase) so a hanging command cannot stall the Act phase indefinitely.
- AC-05.3: `run_shell`'s output (stdout + stderr, truncated to a reasonable cap) is returned as the tool result text, so the reasoning step can see what happened.
- AC-05.4: `additional_authorized_imports` for the `LocalPythonExecutor` no longer includes `"subprocess"` (AC-04.4) — the only way to run a shell command is through the gated `run_shell` tool, not raw Python.

---

### US-06 — KIND-B gate wiring via a `PreToolUse` hook — a real per-call veto, not just pre-run scoping

**As** a user running the Claude provider,
**I want** `Bash`, `Write`, and `Edit` tool calls from the Claude Agent SDK to route through the same Guardrails GATE as the local provider,
**so that** the approval gate is a system-wide guarantee, not a KIND-A-only feature.

**Mechanism note (empirically settled, not a design-time open question):** `ClaudeAgentOptions.can_use_tool` looked like the obvious mechanism by its type signature, but a live probe (`spikes/m4-tools/probe_can_use_tool.py`) proved it does not fire in this SDK/CLI combination, under any of four configurations tried — including one denying every tool call with no `allowed_tools` at all. A `PreToolUse` hook (`ClaudeAgentOptions.hooks`, `spikes/m4-tools/probe_pretooluse_hook.py`) fires reliably instead, and is also the SDK docs' own recommendation for this exact requirement. US-06 below is written against the hook mechanism.

#### Acceptance criteria

- AC-06.1: `ClaudeAdapter.act()` passes `hooks={"PreToolUse": [HookMatcher(hooks=[<gate hook>])]}` on `ClaudeAgentOptions` (no `matcher` restriction — the hook fires for every tool call and does its own classify/approve dispatch). The callback signature matches the SDK's `HookCallback` type: `async def (input: HookInput, tool_use_id: str | None, context: HookContext) -> HookJSONOutput`.
- AC-06.2: The callback reads `tool_name` from the hook input, calls `GuardrailsGate.classify(tool_name)`. `SAFE` tools return `{}` (no decision — falls through to normal evaluation), no prompt. `DESTRUCTIVE` tools call `GuardrailsGate.request_approval(tool_name, tool_input)`; on approval, return `{}`; on denial, return a `hookSpecificOutput` payload with `permissionDecision: "deny"`.
- AC-06.3: `M1_ALLOWED_TOOLS` (`agent.py`) is renamed `CLAUDE_SAFE_TOOLS` and holds only `SAFE`-classified tools (`WebSearch`) — this is defense-in-depth / minimal-privilege practice, not load-bearing for the gate: the `PreToolUse` hook denies `DESTRUCTIVE` calls regardless of `allowed_tools` content, since hooks are evaluated before allow-rules (confirmed via SDK docs and the probe).
- AC-06.4: Because the hook callback is async and the adapter's public methods are sync (bridged via `anyio.run` — see `claude_adapter.py` header comment), the CLI approval prompt (US-03, currently a blocking `input()` call) must not deadlock the anyio event loop. `anyio.to_thread.run_sync` bridges the blocking prompt call — confirmed safe by the probe (no deadlock observed).
- AC-06.5: A denial response is empirically confirmed (not just type-inferred) to surface back into the SDK's normal message stream rather than raising — `spikes/m4-tools/probe_pretooluse_hook.py` shows the query completing with `is_error=False`, and Claude's own reasoning explaining the denial to the user, consistent with AC-03.4's cross-provider guarantee.
- AC-06.6: `ClaudeAgentOptions.permission_mode` is pinned to `"bypassPermissions"`. **Corrected during live-CLI verification** (superseding an earlier version of this AC that claimed the opposite): a hook `deny` decision does apply regardless of permission mode, as the SDK docs state — but live testing found that under the SDK's *default* permission mode, a hook's `{}` ("no objection") response does **not** result in the call actually executing; `bypassPermissions` is required for that. Confirmed both directions empirically (deny still blocks under `bypassPermissions`; `{}` only executes with `bypassPermissions` set) — see `spikes/m4-tools/spike-result.md`.

---

### US-07 — `--auto-approve-tools` CLI flag for headless verification

**As** a developer verifying Axiom end-to-end via the CLI (the same way M1/M3 were verified),
**I want** an `--auto-approve-tools` flag that answers every approval prompt "yes" automatically,
**so that** I can drive scripted or headless runs (including this milestone's own live-CLI verification, per Definition of Done) without blocking on stdin.

#### Acceptance criteria

- AC-07.1: `axiom-cli --auto-approve-tools` threads a flag through `Agent.__init__` down to `GuardrailsGate`, causing `request_approval()` to return `True` unconditionally without prompting.
- AC-07.2: Without the flag, `request_approval()` uses the interactive CLI prompt (US-03).
- AC-07.3: The flag is off by default — the safe, prompting behavior is the default, matching Claude Code's own default permission posture.
- AC-07.4: Every `DESTRUCTIVE` call still passes through `GuardrailsGate.classify()` and is logged (DEBUG level, consistent with the M1 logging pattern) even when auto-approved — auto-approve skips the *prompt*, not the *audit trail*.

---

### US-08 — M4 verified live via CLI on both providers

**As** a developer signing off M4,
**I want** the milestone verified by actually running `axiom-cli` against both providers — not just unit tests — the same way M1's walking skeleton and M3's memory recall were verified live,
**so that** the Guardrails GATE demonstrably works end-to-end, not just in isolation.

#### Acceptance criteria

- AC-08.1: A live CLI run on `--provider claude` with a prompt that requires a `DESTRUCTIVE` tool (e.g. writing a file) demonstrates the approval prompt firing, and (with `--auto-approve-tools`) completing successfully with the file actually written inside `working_dir`.
- AC-08.2: A live CLI run on `--provider local` with the same kind of prompt demonstrates the same behavior via the smolagents `Tool` wrappers.
- AC-08.3: A live CLI run attempting a path-traversal write (e.g. asking the agent to write outside the working directory) is rejected by the working-dir scope check (AC-04.1) on both providers, without crashing the run.
- AC-08.4: A live CLI run with a `SAFE`-only task (e.g. "read this file back to me") completes with no approval prompt at all, on both providers.
- AC-08.5: Results of AC-08.1–AC-08.4 are recorded as part of the M4 sign-off (this milestone's equivalent of M1's MPP-5 latency log / M3's cross-session recall proof).

---

## Non-Goals (M4 scope fence)

| Non-Goal | Notes |
|----------|-------|
| Full sandboxing (container/VM isolation) | Later-phase Guardrails/Safety component, triggered by untrusted input (connectors) or multi-user deployment. M4 is working-dir scope + approval gate only. |
| Tool registry exposed to Skills (M5) | M5 builds on top of M4's registry; M4 does not implement skill authoring or progressive disclosure. |
| MCP server / custom tool exposure to Claude | Claude's own native tools (Bash, Write, Edit, WebSearch) are gated in place; M4 does not stand up an Axiom MCP server to give Claude Axiom's own `read_file`/`write_file` implementations. |
| Fine-grained per-argument approval policy (e.g. allow `rm` but not `rm -rf`) | M4's classification is per-tool-name, not per-argument. Argument-level policy is a future Guardrails refinement. |
| Persisted/remembered approval decisions ("always allow this command") | Every `DESTRUCTIVE` call is gated fresh each time (or bypassed wholesale via `--auto-approve-tools`) — no partial/remembered-choice UX in M4. |
| Working-dir CLI flag | `working_dir` is configurable at the constructor level (AC-04.3); wiring a `--working-dir` CLI flag is included only if trivial, otherwise deferred — not a blocking M4 requirement. |
| Router / multi-provider tool policy | M6 concern. M4's gate applies uniformly, not per-Router-policy. |

---

## Definition of Done (M4 complete when ALL of these pass)

1. **Spec gate:** `requirement.md`, `design.md`, `task.md` exist; `dryrun-design-N.md`'s latest verdict has zero critical, zero warning, zero observation findings.
2. **Code dryrun gate:** the latest `dryrun-code-N.md` verdict has zero critical, zero warning, zero observation findings.
3. **Gap closed:** `grep -rn "additional_functions.*open\|\"subprocess\"" src/axiom/providers/local_adapter.py` returns nothing — the raw escape hatch described in Purpose no longer exists.
4. **Port contract:** `ToolsPort` Protocol exists in `axiom/tools/port.py`; `ToolRegistry` implements it without `loop.py`/`interfaces.py` importing anything from `axiom.tools`.
5. **Gate is shared, not duplicated:** exactly one classification table (US-02, AC-02.4) is referenced by both adapters — no second copy of the SAFE/DESTRUCTIVE list.
6. **Unit tests green:** new `tests/test_tools_*.py` files cover the registry, working-dir scoping (including a path-traversal rejection case), and the Guardrails GATE's classify/approve behavior — including both approval and denial paths — with no skips.
7. **Full suite green:** the whole `pytest` suite (pre-existing + new) passes.
8. **Live verification:** AC-08.1 through AC-08.4 all demonstrated and recorded, on both `--provider claude` and `--provider local`.
