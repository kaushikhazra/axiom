"""
run_shell -- Axiom's code escape-hatch (design.md D7). Working-dir-scoped by
pinning subprocess cwd; bounded by a wall-clock timeout (AC-05.2); output
capped to keep the reasoning prompt bounded (AC-05.3).
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
            # same shape as Claude Code's own Bash tool (design.md D7) --
            # gated by GuardrailsGate.check(), not sandboxed further (Non-Goal).
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=RUN_SHELL_TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"command timed out after {RUN_SHELL_TIMEOUT_SECS}s") from exc
    except OSError as exc:
        raise ToolError(f"failed to run command: {exc}") from exc

    combined = (proc.stdout or "") + (proc.stderr or "")
    truncated = combined[:MAX_OUTPUT_CHARS]
    if len(combined) > MAX_OUTPUT_CHARS:
        truncated += f"\n... [truncated {len(combined) - MAX_OUTPUT_CHARS} chars]"
    return f"exit={proc.returncode}\n{truncated}"
