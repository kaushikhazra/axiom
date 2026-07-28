"""
Unit tests for axiom.interface.web.canvas_routing (M10, design.md D8, D13).
"""

from __future__ import annotations

from axiom.interface.web.canvas_routing import (
    CanvasBlock,
    split_for_canvas,
    _CANVAS_LINE_THRESHOLD,
)
from axiom.tools.port import ToolResult


class TestCanvasBlock:
    def test_to_dict_shape(self) -> None:
        block = CanvasBlock(language="python", content="x = 1", source="response_text")
        assert block.to_dict() == {
            "language": "python",
            "content": "x = 1",
            "source": "response_text",
        }

    def test_from_tool_result_write_file_uses_diff_language(self) -> None:
        result = ToolResult(output="wrote 3 lines")
        block = CanvasBlock.from_tool_result("write_file", result)
        assert block.language == "diff"
        assert block.content == "wrote 3 lines"
        assert block.source == "tool_output"

    def test_from_tool_result_run_shell_uses_shell_output_language(self) -> None:
        result = ToolResult(output="total 0")
        block = CanvasBlock.from_tool_result("run_shell", result)
        assert block.language == "shell-output"


class TestSplitForCanvas:
    def test_short_fence_stays_inline(self) -> None:
        text = "here:\n```python\nx = 1\n```\ndone"
        chat_text, blocks = split_for_canvas(text)
        assert chat_text == text  # unchanged -- below threshold
        assert blocks == []

    def test_long_fence_extracted_to_canvas(self) -> None:
        long_code = "\n".join(f"line{i}" for i in range(_CANVAS_LINE_THRESHOLD + 5))
        text = f"here:\n```python\n{long_code}\n```\ndone"
        chat_text, blocks = split_for_canvas(text)
        assert len(blocks) == 1
        assert blocks[0].language == "python"
        assert blocks[0].content == long_code
        assert blocks[0].source == "response_text"
        assert "[see canvas: python block]" in chat_text
        assert long_code not in chat_text

    def test_exactly_at_threshold_routes_to_canvas(self) -> None:
        """D8's rule is >= threshold, not strictly greater."""
        code = "\n".join(f"line{i}" for i in range(_CANVAS_LINE_THRESHOLD))
        text = f"```text\n{code}\n```"
        _chat_text, blocks = split_for_canvas(text)
        assert len(blocks) == 1

    def test_no_fence_returns_original_text_unchanged(self) -> None:
        text = "just plain prose, no code at all"
        chat_text, blocks = split_for_canvas(text)
        assert chat_text == text
        assert blocks == []

    def test_multiple_fences_mixed_lengths(self) -> None:
        long_code = "\n".join(f"line{i}" for i in range(_CANVAS_LINE_THRESHOLD + 2))
        text = f"```python\nx = 1\n```\nmiddle\n```text\n{long_code}\n```"
        chat_text, blocks = split_for_canvas(text)
        assert len(blocks) == 1
        assert "x = 1" in chat_text  # short block stayed inline
        assert long_code not in chat_text  # long block extracted

    def test_missing_language_defaults_to_text(self) -> None:
        long_code = "\n".join(f"line{i}" for i in range(_CANVAS_LINE_THRESHOLD + 1))
        text = f"```\n{long_code}\n```"
        _chat_text, blocks = split_for_canvas(text)
        assert blocks[0].language == "text"
