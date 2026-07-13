"""
Spike: probe claude_agent_sdk message types and their fields.

Does NOT make any live API call — purely static introspection.
Prints all event types yielded by sdk_query(), their fields, and
which gen_ai.* attributes each event can populate.
"""

from __future__ import annotations


import claude_agent_sdk


def _fields(cls) -> dict[str, str]:
    """Return {field_name: type_str} for a dataclass."""
    if hasattr(cls, "__dataclass_fields__"):
        return {k: str(v.type) for k, v in cls.__dataclass_fields__.items()}
    return {k: str(v) for k, v in getattr(cls, "__annotations__", {}).items()}


# ---------------------------------------------------------------------------
# 1. All exported names
# ---------------------------------------------------------------------------
print("=" * 70)
print("claude_agent_sdk.__version__:", getattr(claude_agent_sdk, "__version__", "?"))
print()

# ---------------------------------------------------------------------------
# 2. Message types yielded by sdk_query()
# ---------------------------------------------------------------------------
MESSAGE_TYPES = [
    "AssistantMessage",
    "UserMessage",
    "SystemMessage",
    "ResultMessage",
    "TaskStartedMessage",
    "TaskProgressMessage",
    "TaskNotificationMessage",
    "RateLimitEvent",
    "Message",
]

CONTENT_BLOCK_TYPES = [
    "TextBlock",
    "ThinkingBlock",
    "ToolUseBlock",
    "ToolResultBlock",
]

MISC_TYPES = [
    "TaskUsage",
    "RateLimitInfo",
    "ClaudeAgentOptions",
]

print("=" * 70)
print("MESSAGE TYPES (yielded by sdk_query async generator)")
print("=" * 70)
for name in MESSAGE_TYPES:
    cls = getattr(claude_agent_sdk, name, None)
    if cls is None:
        print(f"  {name}: NOT FOUND")
        continue
    fields = _fields(cls)
    print(f"\n{name}:")
    for f, t in fields.items():
        print(f"  .{f}: {t}")

print()
print("=" * 70)
print("CONTENT BLOCK TYPES (inside AssistantMessage.content list)")
print("=" * 70)
for name in CONTENT_BLOCK_TYPES:
    cls = getattr(claude_agent_sdk, name, None)
    if cls is None:
        print(f"  {name}: NOT FOUND")
        continue
    fields = _fields(cls)
    print(f"\n{name}:")
    for f, t in fields.items():
        print(f"  .{f}: {t}")

print()
print("=" * 70)
print("MISC TYPES")
print("=" * 70)
for name in MISC_TYPES:
    cls = getattr(claude_agent_sdk, name, None)
    if cls is None:
        print(f"  {name}: NOT FOUND")
        continue
    fields = _fields(cls)
    print(f"\n{name}:")
    for f, t in fields.items():
        print(f"  .{f}: {t}")

# ---------------------------------------------------------------------------
# 3. gen_ai.* attribute mapping assessment
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("gen_ai.* ATTRIBUTE MAPPING ASSESSMENT")
print("=" * 70)
print("""
AssistantMessage:
  gen_ai.response.model        <- .model (str, always present)
  gen_ai.usage.input_tokens    <- .usage dict, key 'input_tokens' (may be None)
  gen_ai.usage.output_tokens   <- .usage dict, key 'output_tokens' (may be None)
  gen_ai.system                <- hardcode 'claude' (KIND_B constant)
  axiom.stop_reason            <- .stop_reason (str | None)

  content blocks:
    TextBlock.text             -> axiom.assistant_text (assistant turn text)
    ToolUseBlock.name          -> span name 'gen_ai.tool_call.<name>'
    ToolUseBlock.id            -> axiom.tool_use_id
    ToolResultBlock.tool_use_id-> axiom.tool_use_id (on user message side)

ResultMessage:
  axiom.cost_usd               <- .total_cost_usd (float | None)
  gen_ai.usage.input_tokens    <- .usage dict 'input_tokens' (aggregate, may be None)
  gen_ai.usage.output_tokens   <- .usage dict 'output_tokens' (aggregate, may be None)
  gen_ai.response.model        <- NOT present on ResultMessage directly
  axiom.num_turns              <- .num_turns (int)
  axiom.duration_ms            <- .duration_ms (int)

TaskProgressMessage:
  axiom.last_tool_name         <- .last_tool_name (str | None)
  axiom.task_progress_tokens   <- .usage.total_tokens (int)
  axiom.task_progress_tool_uses<- .usage.tool_uses (int)

RateLimitEvent:
  NOT a span — rate-limit metadata only, no gen_ai.* mapping needed

NOT AVAILABLE (null in all records):
  gen_ai.request.model         <- ClaudeAgentOptions has no .model field to read
                                  (model is selected by CLI configuration, not SDK)
""")

# ---------------------------------------------------------------------------
# 4. Span strategy summary
# ---------------------------------------------------------------------------
print("=" * 70)
print("CHILD SPAN STRATEGY (KIND-B under Act)")
print("=" * 70)
print("""
Events that warrant a child span under axiom.loop.act:

  1. AssistantMessage with ToolUseBlock(s) in content
     -> For EACH ToolUseBlock: open span 'gen_ai.tool_call.<tool_name>'
        tag: gen_ai.system='claude', axiom.tool_use_id=block.id
        Close span immediately after processing that message
        (the SDK does not stream tool-result back separately in a way
         we can pair; ToolResultBlock comes in a later UserMessage)

  2. AssistantMessage (any turn, including final)
     -> span 'gen_ai.assistant_turn'
        tag: gen_ai.response.model=msg.model
             gen_ai.usage.input_tokens from msg.usage if available
             gen_ai.usage.output_tokens from msg.usage if available
             span_source='provider-streamed'

  3. ResultMessage (terminal)
     -> NOT a child span; attributes are SET on the parent Act span
        (cost, total tokens go on the Act span itself)

  4. TaskProgressMessage
     -> NOT a span (progress only); attrs could be set on Act span
        but this is noisy — skip for M2.

All child spans:
  axiom.span_source = 'provider-streamed'
  axiom.provider_kind = 'KIND_B'
  parent = current Act span (OTel context propagation, same thread)
""")

print("Spike complete — no live API call made.")
