"""
Canvas routing — M10 (design.md D8, D9, D13): decides what counts as
"canvas-worthy" and converts it into a CanvasBlock the frontend renders in
its read-only Generative UI pane, separate from plain chat text.

Two sources feed this, both consumed from agui_bridge.stream_turn() (never
from axiom.agent — a core module must not import this interface-layer
module, dryrun-design-3 C1):
  1. KIND-A tool output (write_file/run_shell), via from_tool_result().
  2. Long fenced code blocks in the assistant's response text, via
     split_for_canvas().
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from axiom.tools.port import ToolResult

# D8 -- starting default, not empirically tuned (design.md Future Work).
_CANVAS_LINE_THRESHOLD = 15

_FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


@dataclass
class CanvasBlock:
    language: str
    content: str
    source: str  # "response_text" | "tool_output"

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "content": self.content,
            "source": self.source,
        }

    @classmethod
    def from_tool_result(cls, tool_name: str, result: ToolResult) -> "CanvasBlock":
        """D13 -- write_file/run_shell only. Caller (stream_turn()) is
        responsible for filtering to those two names and to
        `not result.denied and result.error is None` before calling this --
        this constructor does not re-check either, so it can also be reused
        directly in tests without needing a full ToolResult permutation."""
        language = "diff" if tool_name == "write_file" else "shell-output"
        return cls(language=language, content=result.output, source="tool_output")


def split_for_canvas(response: str) -> tuple[str, list[CanvasBlock]]:
    """D8's response-text rule. Returns (remaining_chat_text, canvas_blocks).

    A fenced block at or above _CANVAS_LINE_THRESHOLD lines is extracted to
    a CanvasBlock and replaced in the chat text with a short pointer; a
    shorter block is left inline, unchanged.
    """
    canvas_blocks: list[CanvasBlock] = []

    def _extract(match: re.Match) -> str:
        language = match.group(1) or "text"
        # The regex captures the trailing "\n" right before the closing
        # fence (standard markdown shape: ```lang\ncode\n```) -- counting
        # on the raw capture gives the correct "N lines" semantics (N lines
        # joined by N-1 "\n"s + 1 trailing "\n" = N), but that trailing
        # newline is a capture artifact, not part of the code -- stripped
        # from the stored/displayed content below.
        raw = match.group(2)
        if raw.count("\n") >= _CANVAS_LINE_THRESHOLD:
            canvas_blocks.append(
                CanvasBlock(
                    language=language, content=raw.rstrip("\n"), source="response_text"
                )
            )
            return f"[see canvas: {language} block]"
        return match.group(0)

    chat_text = _FENCE_RE.sub(_extract, response)
    return chat_text, canvas_blocks
