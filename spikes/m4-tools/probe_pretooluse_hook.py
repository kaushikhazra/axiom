"""
Spike: does a PreToolUse hook (ClaudeAgentOptions.hooks) intercept and deny
a tool call, where can_use_tool (probe_can_use_tool.py) could not?

Result (2026-07-23, same environment as probe_can_use_tool.py): YES. The
hook fired, denied the Bash call, and the query completed successfully
(is_error=False) with Claude explaining the tool was blocked -- no crash,
no uncaught exception, graceful continuation. This is the mechanism M4's
GuardrailsGate uses for the Claude (KIND-B) adapter -- see design.md D3.
"""

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query as sdk_query,
)

LOG_PATH = "hook_log.txt"


def log(line: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def deny_bash_hook(input_data, tool_use_id, context):
    log(f"[hook] FIRED input={input_data}")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "denied by probe hook",
        }
    }


async def main():
    open(LOG_PATH, "w").close()
    options = ClaudeAgentOptions(
        hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[deny_bash_hook])]},
    )
    prompt_text = (
        "Run the shell command 'echo AXIOM_SPIKE_MARKER_HOOK_77216' using your "
        "Bash tool right now and report back the EXACT output. Do not guess."
    )

    async def prompt_stream():
        yield {
            "type": "user",
            "message": {"role": "user", "content": prompt_text},
            "parent_tool_use_id": None,
            "session_id": "probe-session-2",
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
    print("\n--- hook_log.txt contents ---")
    with open(LOG_PATH, encoding="utf-8") as f:
        print(f.read() or "(empty -- hook never fired)")


anyio.run(main)
