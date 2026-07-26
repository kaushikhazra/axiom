"""
Spike: is ClaudeAgentOptions.permission_mode load-bearing for a PreToolUse
hook's "no objection" ({}) decision to actually let the tool call execute?

Background: live-CLI verification of the M4 Guardrails GATE found that a
hook-approved Bash/Write call sometimes silently failed to execute even
though the hook logged an APPROVE decision -- Claude's own text response
described it as blocked by "the environment", not by the hook (the hook had
already said yes). This probe isolates the mechanism.

Result (2026-07-24, same environment as the other probes in this directory):
  - Default permission_mode + hook returning {} -> tool call does NOT execute.
  - permission_mode="bypassPermissions" + hook returning {} -> tool call DOES execute.
  - permission_mode="bypassPermissions" + hook returning a deny payload ->
    tool call is still blocked (hook deny overrides bypassPermissions, as
    documented).

Consequence: ClaudeAdapter.act() sets permission_mode="bypassPermissions"
alongside the PreToolUse hook (design.md D5, corrected). This supersedes an
earlier version of D5 that assumed permission_mode was not load-bearing.
"""

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    query as sdk_query,
)


async def approve_hook(input_data, tool_use_id, context):
    print(
        f"[hook] fired for {input_data.get('tool_name')} -- returning {{}} (approved)"
    )
    return {}


async def run_probe(label: str, permission_mode, marker_file: str) -> None:
    print(f"\n=== {label} (permission_mode={permission_mode!r}) ===")
    options = ClaudeAgentOptions(
        permission_mode=permission_mode,
        hooks={"PreToolUse": [HookMatcher(hooks=[approve_hook])]},
    )
    prompt = f"Run exactly this bash command: echo -n ok > {marker_file}"
    async for message in sdk_query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print("TEXT:", block.text[:200])
        if isinstance(message, ResultMessage):
            print("is_error=", message.is_error)

    try:
        with open(marker_file, encoding="utf-8") as f:
            print(f"FILE CREATED, contents={f.read()!r}")
    except FileNotFoundError:
        print("FILE NOT CREATED")


async def main():
    await run_probe("default permission_mode", None, "probe_default_mode.txt")
    await run_probe("bypassPermissions", "bypassPermissions", "probe_bypass_mode.txt")


anyio.run(main)
