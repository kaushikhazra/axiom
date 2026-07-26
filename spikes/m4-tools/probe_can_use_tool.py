"""
Spike: does ClaudeAgentOptions.can_use_tool actually intercept a tool call
that is NOT pre-approved by allowed_tools?

Result (2026-07-23, claude_agent_sdk 0.1.56, claude CLI 2.1.216): NO.
Across four configurations -- (a) allowed_tools=["WebSearch"] only,
(b) + setting_sources=["project"], (c) with suspect CLAUDE_* env vars
stripped from the parent process, (d) can_use_tool denying EVERY tool with
no allowed_tools at all -- the callback never fired once. Bash executed
unconditionally every time. See spike-result.md for the full writeup and
the fix (a PreToolUse hook instead -- see probe_pretooluse_hook.py).

This file reproduces configuration (d), the strongest case: no allowed_tools,
can_use_tool set to unconditionally deny, setting_sources=[]. Run it and
inspect callback_log.txt -- it stays empty despite Bash executing and
returning the correct (unguessable) marker.
"""

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query as sdk_query,
)

LOG_PATH = "callback_log.txt"


def log(line: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def deny_everything(tool_name, tool_input, context):
    log(f"[callback] FIRED tool={tool_name} input={tool_input}")
    return PermissionResultDeny(message="denied by probe -- deny EVERYTHING")


async def main():
    open(LOG_PATH, "w").close()
    options = ClaudeAgentOptions(
        can_use_tool=deny_everything,
        permission_mode="default",
        setting_sources=[],
    )
    prompt_text = (
        "Run the shell command 'echo AXIOM_SPIKE_MARKER_39182' using your Bash "
        "tool right now and report back the EXACT output. Do not guess -- you "
        "must actually invoke the tool, the marker is not something you could "
        "know without running it."
    )

    async def prompt_stream():
        yield {
            "type": "user",
            "message": {"role": "user", "content": prompt_text},
            "parent_tool_use_id": None,
            "session_id": "probe-session",
        }

    message_count = 0
    try:
        async for message in sdk_query(prompt=prompt_stream(), options=options):
            message_count += 1
            print(f"--- message {message_count}: {type(message).__name__} ---")
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"    ToolUseBlock name={block.name} input={block.input}")
                    elif isinstance(block, TextBlock):
                        print(f"    TextBlock text={block.text!r}")
            if isinstance(message, ResultMessage):
                print(
                    f"is_error={message.is_error} subtype={getattr(message, 'subtype', None)}"
                )
                print(f"result={message.result!r}")
    except Exception as e:
        print(f"EXCEPTION during query: {type(e).__name__}: {e}")
    print(f"\nDONE. message_count={message_count}")
    print("\n--- callback_log.txt contents ---")
    with open(LOG_PATH, encoding="utf-8") as f:
        print(f.read() or "(empty -- callback never fired, as documented above)")


anyio.run(main)
