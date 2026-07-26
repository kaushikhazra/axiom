# M4 · Tools — Design

**Spec:** `006-m4-tools`
**Milestone:** M4 — "Structured tools + a code escape-hatch, working-dir-scoped, with an approval gate"
**Author:** Nira — 2026-07-23
**Status:** DRAFT
**Inputs:** `requirement.md` (this spec); `001-agent-core/architecture.md` (Guardrails GATE call-point, KIND-A/B control-level table); `001-agent-core-roadmap.md` (M4 line); installed `claude_agent_sdk` package (`types.py`) — read directly, not assumed; installed `smolagents` package (`tools.py`, `DuckDuckGoSearchTool`) — read directly; live docs fetch of `code.claude.com/docs/en/agent-sdk/permissions` (2026-07-23) — the permission-evaluation order below is taken verbatim from that page, not guessed; `spikes/m4-tools/spike-result.md` (2026-07-23) — an empirical probe against the live SDK that overturned this design's first draft (see §1, D3).

---

## 1. Overview

M4 turns the Guardrails GATE — named in `architecture.md` as a call-point, not a port, and stubbed through M1–M3 as static `allowed_tools` pre-run scoping — into a real per-call approval gate that both provider adapters route through. It adds a small Tools port (`axiom.tools`) with four working-directory-scoped structured tools for the local provider, and wires the same classification table into the Claude provider via a `PreToolUse` hook (`ClaudeAgentOptions.hooks`) — the mechanism an empirical probe confirmed actually fires, after `can_use_tool` (the initially obvious choice) was probed and found unreliable (see §1, D3, and `spikes/m4-tools/`).

Three design facts, confirmed by reading source/docs and by direct empirical probing rather than assuming, shape everything below:

1. **The Claude Agent SDK exposes a real per-call veto point**, not just pre-run scoping. `architecture.md`'s KIND-B row ("no per-action mid-run veto") predates this finding — this design records the correction but does not rewrite `architecture.md` (out of scope for a milestone design doc).
2. **`ClaudeAgentOptions.can_use_tool` — the callback that looked like the obvious mechanism for that veto — does not reliably fire.** A first design draft planned to use it (matching its type signature in `claude_agent_sdk/types.py`: `CanUseTool = Callable[[str, dict, ToolPermissionContext], Awaitable[PermissionResult]]`). A live probe (`spikes/m4-tools/probe_can_use_tool.py`) proved otherwise: across four configurations — including one where `can_use_tool` was set to unconditionally deny *every* tool call with no `allowed_tools` at all — the callback never fired once, and Bash executed unconditionally every time. **`ClaudeAgentOptions.hooks` with a `PreToolUse` `HookMatcher` fires reliably instead** (`spikes/m4-tools/probe_pretooluse_hook.py` — hook fires, denies, and the query completes gracefully with `is_error=False`). This is also the SDK's own documented recommendation for this exact requirement ("For checks that must run on every tool call, use a `PreToolUse` hook instead" — `code.claude.com/docs/en/agent-sdk/permissions`). §9 below uses hooks, not `can_use_tool`. See `spikes/m4-tools/spike-result.md` for the full writeup — this is a genuine correction the spike forced, not a stylistic preference (D3).
3. **A tool listed in `allowed_tools` by bare name (e.g. `"Bash"`) skips later evaluation steps that would otherwise ask** — but a `PreToolUse` hook runs *before* the allow-rule step and can veto regardless (confirmed via `code.claude.com/docs/en/agent-sdk/permissions`, "How permissions are evaluated": hooks run first; "a hook deny applies even in `bypassPermissions` mode"). This means, unlike the original `can_use_tool`-based plan, M4's hook-based gate does not depend on keeping destructive tools off the `allowed_tools` list — §5/§9 keep them off anyway, as defense-in-depth and minimal-privilege practice, not because it is load-bearing for the gate to function.

---

## 2. Component Map

```
╔═══════════════════════════════════════════════════════════════════════╗
║  ADAPTERS (act() phase only — Tools is an adapter-side concern)        ║
║                                                                        ║
║  ┌─────────────────────────┐        ┌──────────────────────────────┐ ║
║  │  LocalAdapter (KIND-A)   │        │  ClaudeAdapter (KIND-B)      │ ║
║  │                          │        │                              │ ║
║  │  CodeAgent.tools=[       │        │  ClaudeAgentOptions(         │ ║
║  │    ReadFileTool,         │        │    allowed_tools=["WebSearch"]│ ║
║  │    WriteFileTool,        │        │    hooks={"PreToolUse": [     │ ║
║  │    ListDirTool,          │        │      HookMatcher(hooks=       │ ║
║  │    RunShellTool,         │        │        [_gate_hook])],       │ ║
║  │    DuckDuckGoSearchTool  │        │  )                            │ ║
║  │  ]                       │        │  -- hook fires for EVERY tool │ ║
║  │  each Tool.forward()     │        │     call, before allow-rules; │ ║
║  │  calls registry.execute()│        │     can_use_tool NOT used     │ ║
║  │                          │        │     (confirmed unreliable —  │ ║
║  │                          │        │     see spikes/m4-tools/)     │ ║
║  └────────────┬─────────────┘        └──────────────┬───────────────┘ ║
║               │  ToolRegistry.execute(name, args)     │                ║
║               ▼                                        │                ║
║  ┌──────────────────────────────────────┐              │                ║
║  │  ToolRegistry (ToolsPort impl)        │              │                ║
║  │  src/axiom/tools/registry.py          │              │                ║
║  │    read_file / write_file / list_dir  │              │                ║
║  │      (filesystem.py, scoped)          │              │                ║
║  │    run_shell (shell.py, scoped)       │              │                ║
║  │  -- KIND-A's 4 Axiom-owned tools ONLY;│              │                ║
║  │     ClaudeAdapter never calls this --  │              │                ║
║  │     Claude's Bash/Write/Edit are its   │              │                ║
║  │     OWN native tools, not registered   │              │                ║
║  │     here (Non-Goal: no Axiom MCP       │              │                ║
║  │     server exposing these to Claude)   │              │                ║
║  └────────────────────┬───────────────────┘              │                ║
║                        │  gate.check(name, args)          │  gate.classify/║
║                        │  (classify + approve if needed)  │  request_approval║
║                        ▼                                  ▼                ║
║  ┌──────────────────────────────────────────────────────────────────┐ ║
║  │  GuardrailsGate — src/axiom/tools/guardrails.py                  │ ║
║  │  Single classification table (SAFE | DESTRUCTIVE), shared by     │ ║
║  │  both adapters -- called BY ToolRegistry for KIND-A, and         │ ║
║  │  DIRECTLY by ClaudeAdapter's hook for KIND-B (no ToolRegistry    │ ║
║  │  in that path -- Claude's native tools aren't Axiom tools).      │ ║
║  │  CLI approval prompt or --auto-approve-tools.                    │ ║
║  └──────────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════════╝
```

`loop.py` and `interfaces.py` are untouched — the Tools port is adapter-side, exactly like the smolagents/Claude SDK dependency itself. This mirrors the existing precedent that not every faculty is loop-visible: `MemoryPort` is loop-level (the loop calls it directly at Perceive/Observe), but Tools is not — `ActPort.act()` remains the loop's only Act-phase contract, and what an adapter does inside `act()` (including calling a `ToolsPort`) is the adapter's business, same as it already was for `claude_agent_sdk` or `smolagents` themselves.

---

## 3. Decisions Log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Tools is adapter-side, not loop-level. `loop.py`/`interfaces.py` import nothing from `axiom.tools`. | Matches AC-01.5. The loop's contract is the four PRAO ports; Tools is a dependency of the *adapters*, the same relationship `claude_agent_sdk` and `smolagents` already have to their adapters. Keeps the port-adapter seam (M1's core proof) intact — no provider-shaped leakage into the loop. |
| D2 | One classification table (`DESTRUCTIVE_TOOL_NAMES`, a module-level `frozenset[str]` in `guardrails.py`), read by both adapters. | AC-02.4. A per-adapter copy would drift; a single source of truth is grep-able and testable once. |
| D3 | KIND-B gating uses a **`PreToolUse` hook** (`ClaudeAgentOptions.hooks`), **not** `can_use_tool`. | A first draft of this design planned `can_use_tool` — it matches the "Handle approvals and user input" use case by name and by type signature. An empirical probe (`spikes/m4-tools/probe_can_use_tool.py`) proved it does not fire in practice, in the exact environment M4's own live-CLI verification (US-08) runs in: across four configurations, including one denying every tool call with no `allowed_tools` at all, the callback was never invoked and the tool call executed regardless. A `PreToolUse` hook (`spikes/m4-tools/probe_pretooluse_hook.py`), by contrast, fired reliably, denied the call, and the query completed gracefully (`is_error=False`). This is also the SDK docs' own recommendation: "For checks that must run on every tool call, use a `PreToolUse` hook instead." This decision is evidence-driven, not a style preference — see `spikes/m4-tools/spike-result.md`. |
| D4 | `allowed_tools` for `ClaudeAdapter.act()` lists **only SAFE tools** (`WebSearch`). Destructive tools (`Bash`, `Write`, `Edit`) are **not** bare-listed anywhere (not in `allowed_tools`, not in `disallowed_tools`). | Kept as defense-in-depth / minimal-privilege practice, not because it is load-bearing for the gate (D3's hook fires and can deny regardless of `allowed_tools` content — hooks run before the allow-rule evaluation step). Listing only what's actually meant to be auto-approved keeps the adapter's intent legible without relying on the hook alone. |
| D5 | `permission_mode="bypassPermissions"` is set explicitly on `ClaudeAgentOptions`, alongside the `PreToolUse` hook. | **Corrected during live-CLI verification (superseding an earlier, wrong version of this row).** The hook firing and returning `{}` ("no objection, fall through to normal evaluation") is not sufficient on its own — under the SDK's default `permission_mode`, a hook-approved `Bash`/`Write` call was observed live to silently fail to execute (Claude's own text response described it as blocked by "the environment," not by our hook — the hook had already said yes). Isolated spikes confirmed the mechanism: with default `permission_mode`, `{}` from the hook does **not** result in execution; with `permission_mode="bypassPermissions"`, `{}` **does** result in execution, and a hook `deny` still correctly blocks the call either way (confirmed both directions empirically, twice). This matches the SDK docs' own statement that hook denials apply "even in `bypassPermissions` mode" — but the docs did not make clear that `bypassPermissions` is *required* (not merely permissive) for a hook's affirmative "no objection" to actually take effect under this SDK version. See `spikes/m4-tools/spike-result.md` §"permission_mode is load-bearing" for the full empirical trail. `bypassPermissions` is safe here specifically *because* the hook is the enforcement point and hook-deny overrides it — this is not "turn off safety," it's "let the hook be the only gate, instead of stacking on top of an unrelated and looser ambient default." |
| D6 | Local provider's raw `open`/`subprocess` escape hatch is removed outright, not left as a fallback alongside the new tools. | Requirement's Purpose section identifies this as the actual security gap M4 exists to close (AC-04.4, AC-05.4, DoD item 3). Leaving it in place as a parallel path would make the new gate cosmetic. |
| D7 | `run_shell` uses `subprocess.run(command, shell=True, cwd=working_dir, ...)` — a single shell string, not an argv list. | This is Axiom's own analogue of Claude Code's own `Bash` tool (a shell string, not a restricted argv). Consistent with the "code escape-hatch" framing (roadmap) — it is deliberately general-purpose, which is exactly why it is `DESTRUCTIVE` and gated (D2), and why it is `cwd`-pinned (working-dir scope) rather than sandboxed further (Non-Goal: full sandboxing is later-phase Guardrails/Safety). |
| D8 | Four separate smolagents `Tool` subclasses (`ReadFileTool`, `WriteFileTool`, `ListDirTool`, `RunShellTool`), each with class-level `name`/`description`/`inputs`/`output_type`, rather than one parameterized wrapper class. | Matches smolagents' own convention (`DuckDuckGoSearchTool` defines these as class attributes). A single generic wrapper would need to set `name`/`inputs` per-instance before/alongside `Tool.__init__`, which works in current smolagents but is not the library's own pattern and risks breaking on a smolagents upgrade that adds class-level validation. Four small classes cost little and stay idiomatic. |
| D9 | Tool denial returns a `"DENIED: ..."` **string**, not a raised exception; a scoping/execution error returns an `"ERROR: ..."` **string**, also not a raised exception. | AC-04.6 and AC-03.4 both require "no crash." A raised exception from `Tool.forward()` still gets caught by smolagents' step-execution error handling and surfaces as an error observation (same mechanism `DuckDuckGoSearchTool` relies on for "no results found") — but a plain string return is simpler to reason about for both KIND-A (smolagents observes the return value directly) and keeps `ToolRegistry.execute()`'s contract (always returns a `ToolResult`, never raises) uniform for future non-smolagents callers. |
| D10 | The CLI approval prompt runs on a worker thread via `anyio.to_thread.run_sync`, from both the KIND-A dispatch path (already sync, no change needed) and the KIND-B `PreToolUse` hook callback (async, needs the bridge). | AC-06.4. The hook callback is awaited inside the same asyncio loop `anyio.run()` drives in `_run_query`/`_collect_query_result`; a blocking `input()` call directly inside that coroutine would stall the event loop for the duration of the prompt. `anyio.to_thread.run_sync` moves the blocking call off the loop thread without changing the CLI prompt's own (synchronous, simple) implementation. Confirmed safe in the probe: the hook callback in `probe_pretooluse_hook.py` runs inside the SDK's own async control-request handling (`_internal/query.py::_handle_control_request`), the same execution context `can_use_tool` would have used. |
| D11 | `LocalAdapter.__init__`'s new `working_dir`/`gate` parameters stay **required, no defaults** — even though this is a breaking change to three existing test files that construct `LocalAdapter` directly. | Consistent with D6: a default that silently constructs an unscoped/ungated `ToolRegistry` (e.g. `gate: GuardrailsGate \| None = None` quietly falling back to some permissive default) would smuggle back exactly the "silent auto-approve" failure mode M4 exists to remove. Grepped and confirmed the actual blast radius before accepting the break: `tests/test_local_adapter.py` (a `_make_adapter()` helper used across 28 call sites in that file, fixed in one place, plus one direct `LocalAdapter(persona="Test")` in `test_smolagents_import_failure_raises_helpful_error`), `tests/test_local_adapter_spans.py` (its own separate `_make_adapter()` helper), and `tests/test_local_e2e.py` (one direct construction in `test_e2e_create_and_run_python_file`, guarded by `_SKIP_NO_OLLAMA` so it doesn't run in this environment but must still be source-correct) all construct `LocalAdapter` without `working_dir`/`gate` today and must be updated as part of this milestone's implementation, not left for a later cleanup — added to §12 Files Changed. Also found (grepping `LocalAdapter(` / `ClaudeAdapter(` across the whole tree, not just `tests/`): `e2e/m2_observability/test_e2e_observability.py` directly constructs `ClaudeAdapter` too — added to §12 as a best-effort (non-blocking) fix since that directory sits outside `pytest`'s `testpaths`. `tests/test_local_adapter.py::test_default_authorized_imports_includes_subprocess` additionally asserts the literal opposite of AC-05.4 (`"subprocess" in adapter._authorized_imports`) and must be rewritten, not just re-parameterized. |

---

## 4. Tools Port Contract

`src/axiom/tools/port.py` — no changes to `loop.py`/`interfaces.py` (D1).

```python
"""
Tools port contract — the adapter-side seam for Axiom's structured tools.

Not a loop-level port: loop.py and interfaces.py import nothing from this
package. ToolsPort is consumed by provider adapters, the same relationship
they already have with claude_agent_sdk / smolagents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    destructive: bool  # mirrors GuardrailsGate.classify(name) at registration time


@dataclass
class ToolResult:
    output: str
    error: str | None = None
    denied: bool = False


class ToolsPort(Protocol):
    def list_tools(self) -> list[ToolSpec]:
        """Return the specs of every tool this registry exposes."""
        ...

    def execute(self, name: str, arguments: dict) -> ToolResult:
        """Run a tool by name. Never raises — failures and denials are
        encoded in the returned ToolResult (error / denied fields)."""
        ...
```

---

## 5. GuardrailsGate — single classification table, shared approval seam

`src/axiom/tools/guardrails.py`

```python
"""
Guardrails GATE — the cross-cutting call-point named in architecture.md
("Before Act ... approval gate on consequential actions"), implemented here
as a plain, provider-agnostic component. Not a port: both adapters import
this module directly, the same way both would import a shared utility.

Single source of truth for SAFE vs DESTRUCTIVE classification (D2) --
read by ToolRegistry (KIND-A dispatch) and by ClaudeAdapter's PreToolUse
hook callback (KIND-B dispatch). Never duplicated per adapter.
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Callable

logger = logging.getLogger("axiom.tools")

# Axiom's own tools (KIND-A, registry.py) + Claude's native tools (KIND-B).
# A tool name not in this set is SAFE by default -- deliberately: the set
# names what's dangerous, not what's permitted, so adding a new SAFE tool
# (e.g. a future read-only Axiom tool) requires no change here.
DESTRUCTIVE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "write_file",
        "run_shell",
        "Bash",
        "Write",
        "Edit",
    }
)


class Classification(Enum):
    SAFE = auto()
    DESTRUCTIVE = auto()


def _cli_prompt_approval(tool_name: str, arguments: dict) -> bool:
    """Default approval UX: print the call, read a y/n from stdin.

    Mirrors Claude Code's own permission-prompt shape. Writes to stderr so
    it never pollutes stdout the way CLI response text does (interface/cli.py
    prints only agent.run()'s return value to stdout).
    """
    import sys

    print(f"\n[axiom] approval required -- tool: {tool_name}", file=sys.stderr)
    print(f"[axiom] arguments: {arguments!r}", file=sys.stderr)
    print("[axiom] allow? [y/N] ", end="", file=sys.stderr, flush=True)
    answer = sys.stdin.readline().strip().lower()
    return answer in ("y", "yes")


class GuardrailsGate:
    """Classify a tool call and, for DESTRUCTIVE calls, gate it on approval.

    auto_approve=True (wired from --auto-approve-tools) skips the *prompt*,
    not the *classification* or the *audit log* -- every DESTRUCTIVE call is
    still logged at DEBUG (AC-07.4).
    """

    def __init__(
        self,
        auto_approve: bool = False,
        approval_fn: Callable[[str, dict], bool] = _cli_prompt_approval,
    ) -> None:
        self._auto_approve = auto_approve
        self._approval_fn = approval_fn

    def classify(self, tool_name: str) -> Classification:
        return (
            Classification.DESTRUCTIVE
            if tool_name in DESTRUCTIVE_TOOL_NAMES
            else Classification.SAFE
        )

    def request_approval(self, tool_name: str, arguments: dict) -> bool:
        """Blocking call -- the caller is responsible for thread-bridging
        (D10) when invoked from async context."""
        if self._auto_approve:
            logger.debug(
                "[GUARDRAILS_AUTO_APPROVE] tool=%s args=%r", tool_name, arguments
            )
            return True

        approved = self._approval_fn(tool_name, arguments)
        logger.debug(
            "[GUARDRAILS_%s] tool=%s args=%r",
            "APPROVED" if approved else "DENIED",
            tool_name,
            arguments,
        )
        return approved

    def check(self, tool_name: str, arguments: dict) -> bool:
        """Convenience for KIND-A dispatch: classify, then approve if needed.
        Returns True iff execution may proceed."""
        if self.classify(tool_name) is Classification.SAFE:
            return True
        return self.request_approval(tool_name, arguments)
```

---

## 6. Working-directory-scoped filesystem and shell tools

`src/axiom/tools/filesystem.py`

```python
"""
Working-directory-scoped file tools. Every path is resolved against a
configured working_dir root; anything that resolves outside it is rejected.
Functions raise ToolError -- ToolRegistry.execute() converts that into a
ToolResult(error=...) string, never letting it propagate as a raw exception
into a caller (D9).
"""

from __future__ import annotations

from pathlib import Path


class ToolError(Exception):
    """Raised by any tool function on a scoping violation or execution
    failure. Caught exclusively by ToolRegistry.execute()."""


def _resolve_scoped(working_dir: Path, path: str) -> Path:
    """Resolve `path` relative to working_dir; reject any escape.

    Path.resolve() collapses '..' segments and symlinks before the
    containment check, so 'a/../../etc/passwd' and an absolute path outside
    working_dir are both caught the same way.
    """
    root = working_dir.resolve()
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ToolError(
            f"path {path!r} resolves outside the working directory ({root})"
        ) from exc
    return candidate


MAX_READ_CHARS: int = 8000  # bounds prompt size the same way shell.py bounds run_shell output


def read_file(working_dir: Path, path: str) -> str:
    target = _resolve_scoped(working_dir, path)
    if not target.is_file():
        raise ToolError(f"not a file: {path}")
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ToolError(f"failed to read {path!r}: {exc}") from exc
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + f"\n... [truncated {len(text) - MAX_READ_CHARS} chars]"
    return text


def write_file(working_dir: Path, path: str, content: str) -> str:
    target = _resolve_scoped(working_dir, path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"failed to write {path!r}: {exc}") from exc
    return f"wrote {len(content)} bytes to {path}"


def list_dir(working_dir: Path, path: str = ".") -> str:
    target = _resolve_scoped(working_dir, path)
    if not target.is_dir():
        raise ToolError(f"not a directory: {path}")
    try:
        entries = sorted(
            p.name + ("/" if p.is_dir() else "") for p in target.iterdir()
        )
    except OSError as exc:
        raise ToolError(f"failed to list {path!r}: {exc}") from exc
    return "\n".join(entries) if entries else "(empty)"
```

`read_file`/`write_file`/`list_dir` now wrap their actual filesystem calls in `except OSError` — matching the pattern `shell.py::run_shell` already uses for `subprocess.run` (permission errors, disk-full, and similar OS-level failures were previously unguarded here and would have escaped as raw exceptions, violating `ToolsPort.execute()`'s "never raises" contract; see §7's matching `except (ToolError, KeyError)` fix). `read_file` also gets an output cap (`MAX_READ_CHARS`), mirroring `run_shell`'s `MAX_OUTPUT_CHARS` — an uncapped `read_file` on a large file would flood the reasoning prompt the same way uncapped shell output would.

`src/axiom/tools/shell.py`

```python
"""
run_shell -- Axiom's code escape-hatch (D7). Working-dir-scoped by pinning
subprocess cwd; bounded by a wall-clock timeout (AC-05.2); output capped to
keep the reasoning prompt bounded (AC-05.3).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from axiom.tools.filesystem import ToolError

RUN_SHELL_TIMEOUT_SECS: int = 30
MAX_OUTPUT_CHARS: int = 4000


def run_shell(working_dir: Path, command: str) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,  # deliberate: the escape-hatch takes a shell string,
            # same shape as Claude Code's own Bash tool (D7) -- gated by
            # GuardrailsGate.check(), not sandboxed further (Non-Goal).
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=RUN_SHELL_TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(
            f"command timed out after {RUN_SHELL_TIMEOUT_SECS}s"
        ) from exc
    except OSError as exc:
        raise ToolError(f"failed to run command: {exc}") from exc

    combined = (proc.stdout or "") + (proc.stderr or "")
    truncated = combined[:MAX_OUTPUT_CHARS]
    if len(combined) > MAX_OUTPUT_CHARS:
        truncated += f"\n... [truncated {len(combined) - MAX_OUTPUT_CHARS} chars]"
    return f"exit={proc.returncode}\n{truncated}"
```

---

## 7. ToolRegistry — the concrete `ToolsPort`

`src/axiom/tools/registry.py`

```python
"""
ToolRegistry -- the concrete ToolsPort. Owns the working_dir root and the
GuardrailsGate; dispatches by name to filesystem.py / shell.py functions.
"""

from __future__ import annotations

from pathlib import Path

from axiom.tools.filesystem import ToolError, list_dir, read_file, write_file
from axiom.tools.guardrails import Classification, GuardrailsGate
from axiom.tools.port import ToolResult, ToolSpec
from axiom.tools.shell import run_shell

_SPECS: dict[str, str] = {
    "read_file": "Read a UTF-8 text file. Path is resolved relative to the working directory.",
    "write_file": "Write UTF-8 text to a file. DESTRUCTIVE: requires approval. Path is resolved relative to the working directory.",
    "list_dir": "List entries in a directory. Path is resolved relative to the working directory.",
    "run_shell": "Run a shell command in the working directory (the code escape-hatch). DESTRUCTIVE: requires approval.",
}


class ToolRegistry:
    """Implements ToolsPort (structurally -- Protocol, no explicit inheritance)."""

    def __init__(self, working_dir: Path, gate: GuardrailsGate) -> None:
        self._working_dir = working_dir
        self._gate = gate

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=name,
                description=desc,
                destructive=self._gate.classify(name) is Classification.DESTRUCTIVE,
            )
            for name, desc in _SPECS.items()
        ]

    def execute(self, name: str, arguments: dict) -> ToolResult:
        if name not in _SPECS:
            return ToolResult(output="", error=f"unknown tool: {name}")

        if not self._gate.check(name, arguments):
            return ToolResult(output="", denied=True, error="denied by user")

        try:
            output = self._dispatch(name, arguments)
            return ToolResult(output=output)
        except ToolError as exc:
            return ToolResult(output="", error=str(exc))
        except KeyError as exc:
            # A required argument was missing from `arguments` -- e.g. a
            # direct execute() call (bypassing smolagents' own argument
            # validation) omitting "path". Converted to a ToolResult, not
            # left to propagate, so the "never raises" port contract
            # (ToolsPort.execute docstring, AC-01.1) holds for every caller,
            # not just ones that happen to go through a smolagents Tool.
            return ToolResult(output="", error=f"missing required argument: {exc}")

    def _dispatch(self, name: str, arguments: dict) -> str:
        if name == "read_file":
            return read_file(self._working_dir, arguments["path"])
        if name == "write_file":
            return write_file(
                self._working_dir, arguments["path"], arguments["content"]
            )
        if name == "list_dir":
            return list_dir(self._working_dir, arguments.get("path", "."))
        if name == "run_shell":
            return run_shell(self._working_dir, arguments["command"])
        raise AssertionError(f"unreachable: {name!r} passed the _SPECS guard")
```

---

## 8. KIND-A wiring — smolagents `Tool` wrappers replace the raw escape hatch

`src/axiom/tools/smolagents_tools.py` (new file — deliberately **not** imported by `axiom/tools/__init__.py` or any other module in this package, so importing `axiom.tools` never pays the `smolagents` import cost; only `local_adapter.py`'s lazy import block reaches it, preserving the existing lazy-import boundary).

```python
"""
smolagents Tool wrappers over ToolRegistry -- KIND-A wiring for M4.

Four small classes (D8), each delegating forward() to
ToolRegistry.execute(). Denial and error results return as plain strings
(D9) so the CodeAgent step observes them as normal tool output, never as a
crash.

Import boundary: smolagents only. No claude_agent_sdk. Imported lazily by
local_adapter.py, matching the existing smolagents-is-deferred rule.
"""

from __future__ import annotations

from smolagents import Tool

from axiom.tools.registry import ToolRegistry


def _dispatch(registry: ToolRegistry, name: str, arguments: dict) -> str:
    result = registry.execute(name, arguments)
    if result.denied:
        return f"DENIED: {result.error}"
    if result.error:
        return f"ERROR: {result.error}"
    return result.output


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read a UTF-8 text file's contents. Path is resolved relative to "
        "the working directory; paths outside it are rejected."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "File path, relative to the working directory.",
        }
    }
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, path: str) -> str:
        return _dispatch(self._registry, "read_file", {"path": path})


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write UTF-8 text content to a file. DESTRUCTIVE: requires approval. "
        "Path is resolved relative to the working directory; paths outside "
        "it are rejected."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "File path, relative to the working directory.",
        },
        "content": {"type": "string", "description": "Text content to write."},
    }
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, path: str, content: str) -> str:
        return _dispatch(
            self._registry, "write_file", {"path": path, "content": content}
        )


class ListDirTool(Tool):
    name = "list_dir"
    description = (
        "List entries in a directory. Path is resolved relative to the "
        "working directory; paths outside it are rejected."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "Directory path, relative to the working directory.",
            "nullable": True,
        }
    }
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, path: str = ".") -> str:
        return _dispatch(self._registry, "list_dir", {"path": path})


class RunShellTool(Tool):
    name = "run_shell"
    description = (
        "Run a shell command in the working directory (the code "
        "escape-hatch). DESTRUCTIVE: requires approval."
    )
    inputs = {"command": {"type": "string", "description": "Shell command to execute."}}
    output_type = "string"

    def __init__(self, registry: ToolRegistry) -> None:
        super().__init__()
        self._registry = registry

    def forward(self, command: str) -> str:
        return _dispatch(self._registry, "run_shell", {"command": command})
```

### `local_adapter.py` changes

- `__init__` gains `working_dir: Path` and `gate: GuardrailsGate` parameters (both required — no defaults that would silently construct an unscoped/ungated registry), and constructs `self._registry = ToolRegistry(working_dir, gate)`.
- `additional_authorized_imports` default list **drops `"subprocess"`** (AC-05.4).
- `additional_functions={"open": builtins.open, "re": _re}` becomes `additional_functions={"re": _re}` — `open` is removed (AC-04.4); `re` pre-injection is unrelated to this milestone and stays.
- Inside `act()`, the `CodeAgent(...)` construction's `tools=[DuckDuckGoSearchTool()]` becomes:

  ```python
  from axiom.tools.smolagents_tools import (
      ListDirTool,
      ReadFileTool,
      RunShellTool,
      WriteFileTool,
  )

  tools = [
      DuckDuckGoSearchTool(),
      ReadFileTool(self._registry),
      WriteFileTool(self._registry),
      ListDirTool(self._registry),
      RunShellTool(self._registry),
  ]
  ```

---

## 9. KIND-B wiring — `PreToolUse` hook

Uses `ClaudeAgentOptions.hooks`, not `can_use_tool` (D3 — `can_use_tool` was probed and does not fire in practice; see `spikes/m4-tools/spike-result.md`). Confirmed by a follow-up probe that hooks, unlike `can_use_tool`, impose **no streaming-mode requirement** — a plain string `prompt` (what `act()` already passes to `sdk_query`) works unchanged; only `can_use_tool` requires the prompt to be an `AsyncIterable` (`claude_agent_sdk/_internal/client.py::process_query`, `if options.can_use_tool: ... raise ValueError`). No change is needed to how `act()` constructs its prompt.

### `claude_adapter.py` changes

- `ClaudeAdapter.__init__` gains a `gate: GuardrailsGate` parameter, stored as `self._gate`.
- `M1_ALLOWED_TOOLS` (`agent.py`) is renamed `CLAUDE_SAFE_TOOLS = ["WebSearch"]` (D4) — only SAFE tools are bare-listed, as minimal-privilege practice (not load-bearing for the gate itself — see D4).
- `act()`'s `ClaudeAgentOptions` construction adds `hooks={"PreToolUse": [HookMatcher(hooks=[self._gate_hook])]}` — no `matcher` value, so the hook fires for **every** tool call, and the callback itself does the classify/approve dispatch — **and** `permission_mode="bypassPermissions"` (D5, corrected during live-CLI verification: required for a hook-approved call to actually execute, not merely permissive):

  ```python
  options = ClaudeAgentOptions(
      allowed_tools=self._allowed_tools,  # CLAUDE_SAFE_TOOLS = ["WebSearch"]
      hooks={"PreToolUse": [HookMatcher(hooks=[self._gate_hook])]},
      permission_mode="bypassPermissions",
  )
  ```

- New method on `ClaudeAdapter`:

  ```python
  async def _gate_hook(self, input_data: dict, tool_use_id: str | None, context) -> dict:
      """PreToolUse hook -- fires for every tool call (no matcher restriction).

      Returns {} to let the call fall through to normal evaluation (SAFE tools,
      or nothing to say), or a deny hookSpecificOutput for a refused DESTRUCTIVE
      call. There is no corresponding "force allow" -- hook 'allow' does not
      skip later evaluation steps (confirmed via SDK docs), so SAFE tools are
      left to allowed_tools / default evaluation instead of being explicitly
      allowed here.
      """
      tool_name = input_data.get("tool_name", "")
      tool_input = input_data.get("tool_input", {})

      from axiom.tools.guardrails import Classification

      if self._gate.classify(tool_name) is Classification.SAFE:
          return {}

      approved = await anyio.to_thread.run_sync(
          self._gate.request_approval, tool_name, tool_input
      )
      if approved:
          return {}

      return {
          "hookSpecificOutput": {
              "hookEventName": "PreToolUse",
              "permissionDecision": "deny",
              "permissionDecisionReason": "denied by user",
          }
      }
  ```

  (D10 — the blocking CLI prompt inside `request_approval` runs off the event-loop thread via `anyio.to_thread.run_sync`. Confirmed safe: the probe's hook callback ran inside the SDK's own async control-request handling with no deadlock.)

- Import addition at module top: `HookMatcher` from `claude_agent_sdk`. `Classification` is imported lazily inside `_gate_hook`, consistent with the existing lazy-`opentelemetry`-import pattern elsewhere in this file.

### Timeout interaction (AC-06.4, follow-up note)

`PER_QUERY_TIMEOUT_SECS = 120` wraps the whole `act()` query via `anyio.fail_after`. While the gate is waiting on a human's y/n, that wall clock keeps running. This is accepted as-is for M4 (120s is generous for a prompt; `--auto-approve-tools` exists precisely for runs where no human is present to answer). No change to the timeout constant.

---

## 10. `Agent` / CLI wiring

### `agent.py` changes

- `Agent.__init__` gains `working_dir: str | Path | None = None` and `auto_approve_tools: bool = False`.
- Constructs, before building either adapter:

  ```python
  from pathlib import Path
  from axiom.tools.guardrails import GuardrailsGate

  resolved_working_dir = Path(working_dir) if working_dir is not None else Path.cwd()
  gate = GuardrailsGate(auto_approve=auto_approve_tools)
  ```

- Passes `gate=gate` (and, for `LocalAdapter`, `working_dir=resolved_working_dir`) into whichever adapter is constructed. `ClaudeAdapter` does not need `working_dir` directly — its file/shell operations run through Claude Code's own built-in tools, which are already cwd-scoped by the Claude Code CLI subprocess's own working directory (unchanged by M4; Claude's native tools are not re-implemented, only gated, per Non-Goals).

### `interface/cli.py` changes

- New flag: `--auto-approve-tools` (`action="store_true"`, default `False`) → `Agent(..., auto_approve_tools=args.auto_approve_tools)`.
- New flag: `--working-dir` (default `None`, meaning "current directory") → `Agent(..., working_dir=args.working_dir)`. Included because it is trivial given `Agent.__init__` already needs the parameter (Non-Goals allowed this "only if trivial").

---

## 11. Error Handling

| Failure | Where caught | Behavior |
|---|---|---|
| Path resolves outside `working_dir` | `filesystem.py::_resolve_scoped` raises `ToolError` | `ToolRegistry.execute()` catches it, returns `ToolResult(error=...)`. KIND-A: surfaces as `"ERROR: ..."` string, observed by CodeAgent, no crash. KIND-B: not applicable — Claude's native file tools are gated (approve/deny), not re-scoped by Axiom; working-dir scoping applies to Axiom's own tools only (US-04 is explicitly a KIND-A requirement). |
| `run_shell` exceeds `RUN_SHELL_TIMEOUT_SECS` | `shell.py::run_shell` catches `subprocess.TimeoutExpired`, raises `ToolError` | Same propagation as above — `"ERROR: command timed out after 30s"`. |
| User denies a `DESTRUCTIVE` call | `GuardrailsGate.request_approval` returns `False` | KIND-A: `ToolRegistry.execute()` returns `ToolResult(denied=True)` → `"DENIED: ..."` string. KIND-B: `_gate_hook` returns a `PreToolUse` `permissionDecision: "deny"` payload → the SDK blocks the call and Claude's own next turn sees the denial and explains it to the user — empirically confirmed by `spikes/m4-tools/probe_pretooluse_hook.py`: the query completed with `is_error=False`, no crash, no uncaught exception. |
| Unknown tool name reaches `ToolRegistry.execute` | Guard clause in `execute()` | Returns `ToolResult(error="unknown tool: ...")` — should not happen in practice (only the four registered names are ever wired to a smolagents `Tool`), but keeps the contract total rather than partial. |
| Required argument missing (e.g. `execute("read_file", {})` with no `"path"`) | `ToolRegistry.execute()` catches `KeyError` from `_dispatch()` | Returns `ToolResult(error="missing required argument: ...")` — same "never raises" guarantee as the `ToolError` path. In practice smolagents' own `Tool.validate_arguments()` already rejects an incomplete call before `forward()` runs, so this is a defense-in-depth backstop for any caller that bypasses that validation (e.g. a direct `ToolRegistry.execute()` call in a test). |
| Filesystem OS-level failure (permission denied, disk full, etc.) in `read_file`/`write_file`/`list_dir` | Each function now catches `OSError` around its actual I/O call, raises `ToolError` (matching the pattern `shell.py::run_shell` already used for `subprocess.run`) | Same propagation as the path-traversal row — `ToolRegistry.execute()`'s existing `except ToolError` catches it, returns `ToolResult(error=...)`, no crash. |
| CLI approval prompt reads EOF (non-interactive stdin, no `--auto-approve-tools`) | `_cli_prompt_approval`'s `sys.stdin.readline()` returns `""` | `"".strip().lower()` is `""`, which is not in `("y", "yes")` → treated as denial (fail-closed), not a hang or crash. Documented behavior: headless runs **must** pass `--auto-approve-tools` or `DESTRUCTIVE` calls will always be denied. |
| Two `DESTRUCTIVE` tool calls need approval concurrently (KIND-B only — Claude can issue parallel tool calls in one assistant turn; smolagents' `CodeAgent` calls tools sequentially within its own generated code, so this does not arise for KIND-A) | Not defended against | `GuardrailsGate.request_approval`'s default CLI prompt (`sys.stdin`/`stderr`) is not safe for concurrent invocation — two simultaneous prompts could interleave garbled output. Accepted limitation for M4: parallel Claude tool calls where more than one is `DESTRUCTIVE` in the same turn are uncommon, and `--auto-approve-tools` sidesteps the scenario entirely for headless/scripted runs. Not a crash risk (each `request_approval` call still returns a valid bool; worst case is a confusing prompt, not incorrect behavior) — noted here rather than silently unhandled. Revisit only if this proves disruptive in practice. |

---

## 12. Files Changed

| File | Change | AC Trace |
|---|---|---|
| `src/axiom/tools/port.py` | New. `ToolSpec`, `ToolResult`, `ToolsPort` Protocol. | AC-01.1, AC-01.2, AC-01.3 |
| `src/axiom/tools/guardrails.py` | New. `Classification`, `DESTRUCTIVE_TOOL_NAMES`, `GuardrailsGate`, CLI approval prompt. | AC-02.1, AC-02.2, AC-02.3, AC-02.4, AC-02.5, AC-03.1, AC-03.2, AC-03.5, AC-07.1, AC-07.2, AC-07.3, AC-07.4 |
| `src/axiom/tools/filesystem.py` | New. `ToolError`, `_resolve_scoped`, `read_file`, `write_file`, `list_dir`. | AC-04.1, AC-04.6 |
| `src/axiom/tools/shell.py` | New. `run_shell`, timeout + output cap. | AC-04.2, AC-05.1, AC-05.2, AC-05.3 |
| `src/axiom/tools/registry.py` | New. `ToolRegistry` — concrete `ToolsPort`, dispatch + gate check. | AC-01.4, AC-02.4 |
| `src/axiom/tools/smolagents_tools.py` | New. `ReadFileTool`, `WriteFileTool`, `ListDirTool`, `RunShellTool` — smolagents `Tool` wrappers. | AC-04.4, AC-04.5, AC-03.3 (KIND-A half) |
| `src/axiom/providers/local_adapter.py` | Modified. Constructor gains `working_dir`/`gate`; drops `additional_functions={"open": ...}` and `"subprocess"` from authorized imports; `act()` wires the four new `Tool` wrappers alongside `DuckDuckGoSearchTool`. | AC-04.3, AC-04.4, AC-05.4 |
| `src/axiom/providers/claude_adapter.py` | Modified. Constructor gains `gate`; `act()` adds a `PreToolUse` hook via `ClaudeAgentOptions.hooks`; new `_gate_hook` method; `act()`'s docstring comment ("M1_ALLOWED_TOOLS (set by agent.py) are scoped here...") updated to reference `CLAUDE_SAFE_TOOLS` and the hook. | AC-06.1, AC-06.2, AC-06.4, AC-06.5, AC-06.6, AC-03.3 (KIND-B half), AC-03.4 (KIND-B half) |
| `spikes/m4-tools/probe_can_use_tool.py`, `probe_pretooluse_hook.py`, `spike-result.md` | New. Empirical evidence for D3 (why the gate uses a `PreToolUse` hook, not `can_use_tool`). | D3 (design-record only — no AC; mirrors the M2 precedent of recording load-bearing spikes) |
| `src/axiom/agent.py` | Modified. `M1_ALLOWED_TOOLS` renamed `CLAUDE_SAFE_TOOLS = ["WebSearch"]`; constructs `GuardrailsGate`; new `working_dir`/`auto_approve_tools` constructor params threaded to both adapters. | AC-06.3, AC-07.1 |
| `src/axiom/interface/cli.py` | Modified. New `--auto-approve-tools` and `--working-dir` flags. | AC-07.1 |
| `tests/test_tools_registry.py` | New. `ToolRegistry` dispatch, unknown-tool guard, denial path, missing-required-argument path (`execute()` with an incomplete `arguments` dict returns a `ToolResult(error=...)`, never raises). | DoD item 6 |
| `tests/test_tools_filesystem.py` | New. `read_file`/`write_file`/`list_dir`, path-traversal rejection, `read_file` truncation at `MAX_READ_CHARS`, an `OSError` path (e.g. `write_file` into a location `mkdir`/`write_text` can't reach) surfacing as `ToolError` rather than raising. | DoD item 6 |
| `tests/test_tools_shell.py` | New. `run_shell` success, timeout, output truncation. | DoD item 6 |
| `tests/test_tools_guardrails.py` | New. `classify()` table, `request_approval()` with a stub `approval_fn`, auto-approve bypass. | DoD item 6 |
| `tests/test_local_adapter.py` | Modified (D11 — breaking change, not optional). `_make_adapter()` helper gains `working_dir=tmp_path`/`gate=GuardrailsGate(auto_approve=True)`; `test_smolagents_import_failure_raises_helpful_error`'s direct `LocalAdapter(persona="Test")` call gets the same two args added; `test_default_authorized_imports_includes_subprocess` is rewritten to assert `"subprocess" not in adapter._authorized_imports` (renamed accordingly). | AC-04.3, AC-04.4, AC-05.4 |
| `tests/test_local_adapter_spans.py` | Modified (D11). `_make_adapter()` helper gains the same `working_dir`/`gate` arguments. | AC-04.3, AC-04.4 |
| `tests/test_local_e2e.py` | Modified (D11). `test_e2e_create_and_run_python_file`'s direct `LocalAdapter(persona=persona_text, max_steps=8)` call gains `working_dir=Path(cwd)` and `gate=GuardrailsGate(auto_approve=True)` — this test's entire point is verifying a real write+execute happens, so it must auto-approve rather than hang/deny on non-interactive stdin. Skip-gated by `_SKIP_NO_OLLAMA`; does not run in the environment this design was verified in, but must stay source-correct. | AC-04.3, AC-04.4 |
| `e2e/m2_observability/test_e2e_observability.py` | Modified, best-effort (not a DoD blocker). Its `ClaudeAdapter(persona=persona_text, allowed_tools=M1_ALLOWED_TOOLS)` call (line ~554) gains `gate=GuardrailsGate(auto_approve=True)`. Outside `pytest`'s `testpaths = ["tests"]` (confirmed in `pyproject.toml`), so this file is not part of DoD item 7's "full suite green" gate — and its `PraoLoop(...)` call already omits M3's required `memory=` parameter, a pre-existing defect from before M4 that this milestone does not take on fixing. Updated for `gate=` consistency so it isn't left silently more broken than it already was; not blocking. | AC-06.1 (best-effort — not gated on it) |

---

## 13. Future Work (Out of Scope)

- **Full sandboxing** (container/VM isolation of `run_shell`) — later-phase Guardrails/Safety component (Non-Goal).
- **Per-argument policy** (e.g. allow `git status` but gate `git push`) — M4's classification is per-tool-name only (Non-Goal).
- **Remembered approval decisions** ("always allow `run_shell` for this session") — every call is gated fresh, or bypassed wholesale via `--auto-approve-tools` (Non-Goal).
- **Axiom MCP server exposing `read_file`/`write_file`/`run_shell` to Claude** so KIND-B uses Axiom's own tool implementations instead of Claude's native ones — would let both providers share literally the same tool code, not just the same gate. Deferred; M4 gates Claude's native tools in place (Non-Goal).
- **Root-causing why `can_use_tool` never fired** in the probed environment (most likely `skipDangerousModePermissionPrompt` in this machine's global `~/.claude/settings.json`, per `spikes/m4-tools/spike-result.md` — not confirmed as the sole cause). Not needed for M4: the `PreToolUse` hook is proven to work regardless of the root cause. Worth revisiting only if a future milestone needs `can_use_tool` specifically (e.g. for its `updated_input` field, which hooks don't offer).
