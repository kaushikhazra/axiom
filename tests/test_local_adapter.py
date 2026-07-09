"""
Unit tests for LocalAdapter (reason, act, constructor).

PraoAdapterBase and _parse_intent tests live in test_shared_base.py (design §8/§11.2).

All tests use MagicMock to stub litellm — no live model, no network.
litellm is injected into sys.modules at module load time, before LocalAdapter
is ever constructed, so that the deferred `import litellm` inside
LocalAdapter.__init__ resolves to the mock rather than a real package install.

After construction, each test replaces adapter._litellm with its own fresh
MagicMock so tests are fully independent.
"""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Inject mock litellm into sys.modules BEFORE importing LocalAdapter so that
# `import litellm as _litellm_mod` inside __init__ doesn't raise ModuleNotFoundError
# (litellm may not be installed in the test environment — only in production).
# ---------------------------------------------------------------------------
_module_level_mock_litellm = MagicMock()
sys.modules.setdefault("litellm", _module_level_mock_litellm)

from axiom.interfaces import (  # noqa: E402
    ActIntent,
    AdapterError,
    FinishIntent,
    RespondIntent,
)
from axiom.providers.local_adapter import LocalAdapter, MAX_TOOL_ITERATIONS  # noqa: E402


# ============================================================
# Test helpers
# ============================================================


def _make_adapter(
    max_tool_iterations: int = MAX_TOOL_ITERATIONS,
) -> tuple[LocalAdapter, MagicMock]:
    """Build a LocalAdapter and return (adapter, fresh_mock_litellm).

    The adapter._litellm is replaced with a fresh MagicMock so every test
    can configure side_effects independently without cross-contamination.
    """
    adapter = LocalAdapter(
        persona="Test persona", max_tool_iterations=max_tool_iterations
    )
    mock_lt = MagicMock()
    adapter._litellm = mock_lt
    return adapter, mock_lt


def _text_resp(content: str) -> MagicMock:
    """Mock litellm response: plain text content, no tool calls."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = None  # falsy → loop treats this as a final answer
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _tool_call_resp(
    tool_name: str,
    tool_args: dict,
    call_id: str = "call_1",
) -> MagicMock:
    """Mock litellm response: a single tool call with no text content."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(tool_args)

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_args),
                },
            }
        ],
    }
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _tool_call_resp_with_text(
    tool_name: str,
    tool_args: dict,
    text_content: str,
    call_id: str = "call_1",
) -> MagicMock:
    """Mock litellm response: a tool call whose model_dump() includes text content.

    Used to test the exhaustion backward-scan branch: the serialised assistant
    message has a non-empty 'content' field, so the backward scan returns it
    rather than the exhaustion-summary string.
    """
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(tool_args)

    msg = MagicMock()
    msg.content = None  # falsy at call time — loop continues to execute tool
    msg.tool_calls = [tc]
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": text_content,  # present in serialised form for backward scan
        "tool_calls": [
            {
                "id": call_id,
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(tool_args),
                },
            }
        ],
    }
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _malformed_tool_call_resp(call_id: str = "call_bad") -> MagicMock:
    """Mock litellm response: tool call with non-JSON arguments string."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = "run_shell_command"
    tc.function.arguments = "NOT JSON {{{"  # will trigger json.JSONDecodeError

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "function": {
                    "name": "run_shell_command",
                    "arguments": "NOT JSON {{{",
                },
            }
        ],
    }
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _unknown_tool_call_resp(call_id: str = "call_u") -> MagicMock:
    """Mock litellm response: tool call for a tool not in the registry."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = "nonexistent_tool"
    tc.function.arguments = json.dumps({"x": 1})

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]
    msg.model_dump.return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "function": {
                    "name": "nonexistent_tool",
                    "arguments": json.dumps({"x": 1}),
                },
            }
        ],
    }
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


# ============================================================
# LocalAdapter — constructor
# ============================================================


class TestLocalAdapterConstructor:
    def test_default_model_name(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter._model_name == "ollama_chat/qwen2.5:7b"

    def test_default_ollama_api_base(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter._ollama_api_base == "http://localhost:11434"

    def test_default_max_tool_iterations(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter._max_tool_iterations == MAX_TOOL_ITERATIONS

    def test_custom_max_tool_iterations(self) -> None:
        adapter, _ = _make_adapter(max_tool_iterations=2)
        assert adapter._max_tool_iterations == 2

    def test_tool_registry_contains_shell_tool(self) -> None:
        adapter, _ = _make_adapter()
        assert "run_shell_command" in adapter._tool_executors


# ============================================================
# LocalAdapter — reason()
# ============================================================


class TestLocalAdapterReason:
    def test_valid_respond_intent(self) -> None:
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.return_value = _text_resp(
            '{"intent": "RESPOND", "text": "Hi"}'
        )
        result = adapter.reason("some context")
        assert isinstance(result, RespondIntent)
        assert result.text == "Hi"
        assert mock_lt.completion.call_count == 1

    def test_valid_act_intent(self) -> None:
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.return_value = _text_resp(
            '{"intent": "ACT", "instruction": "do it"}'
        )
        result = adapter.reason("some context")
        assert isinstance(result, ActIntent)
        assert result.instruction == "do it"

    def test_valid_finish_intent(self) -> None:
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.return_value = _text_resp('{"intent": "FINISH"}')
        result = adapter.reason("context")
        assert isinstance(result, FinishIntent)

    def test_malformed_first_call_retry_succeeds(self) -> None:
        """First call returns bad JSON; retry call returns valid JSON → Intent returned."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _text_resp("not json at all"),
            _text_resp('{"intent": "RESPOND", "text": "retry worked"}'),
        ]
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert result.text == "retry worked"
        assert mock_lt.completion.call_count == 2

    def test_malformed_both_attempts_returns_fallback_respond(self) -> None:
        """Both first and retry calls return bad JSON → [FALLBACK_RESPOND] returned."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _text_resp("garbage1"),
            _text_resp("garbage2"),
        ]
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert "[FALLBACK_RESPOND]" in result.text
        assert mock_lt.completion.call_count == 2

    def test_json_in_code_fence_resolved_without_retry(self) -> None:
        """Pre-processing recovers JSON from code fence — no retry needed."""
        adapter, mock_lt = _make_adapter()
        fenced = '```json\n{"intent": "RESPOND", "text": "From fence"}\n```'
        mock_lt.completion.return_value = _text_resp(fenced)
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert result.text == "From fence"
        assert (
            mock_lt.completion.call_count == 1
        )  # pre-processing resolved it, no retry

    def test_reason_model_error_raises_adapter_error(self) -> None:
        """litellm.completion raises in reason() → AdapterError propagated."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = Exception("timeout")
        with pytest.raises(AdapterError, match="local model error"):
            adapter.reason("context")


# ============================================================
# LocalAdapter — act() / _run_tool_loop()
# ============================================================


class TestLocalAdapterAct:
    def test_happy_path_single_tool_call(self) -> None:
        """Model proposes run_shell_command → harness executes → final text returned."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _tool_call_resp("run_shell_command", {"command": "echo hello"}),
            _text_resp("The output was: hello"),
        ]
        # Stub the executor — no subprocess spawned
        adapter._tool_executors["run_shell_command"] = lambda args: "hello"

        result = adapter.act("Echo hello and report")
        assert result == "The output was: hello"
        assert mock_lt.completion.call_count == 2

    def test_multi_step_tool_loop(self) -> None:
        """G3: Model calls tools on iterations 1 and 2, then returns final text on 3.

        Verifies that _run_tool_loop correctly accumulates tool results across
        multiple iterations and passes them all back before the model's final answer.
        """
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _tool_call_resp("run_shell_command", {"command": "ls"}, call_id="c1"),
            _tool_call_resp("run_shell_command", {"command": "pwd"}, call_id="c2"),
            _text_resp("Done: ls and pwd both ran"),
        ]
        execution_log: list[str] = []

        def recording_executor(args: dict) -> str:
            execution_log.append(args["command"])
            return f"output of {args['command']}"

        adapter._tool_executors["run_shell_command"] = recording_executor

        result = adapter.act("List files and current dir")

        assert result == "Done: ls and pwd both ran"
        assert mock_lt.completion.call_count == 3
        assert execution_log == ["ls", "pwd"], (
            f"Tools should have run in order [ls, pwd]; got {execution_log}"
        )

    def test_malformed_tool_args_feeds_error_back_does_not_crash(self) -> None:
        """Malformed tool arguments → error string fed back to model; no exception raised."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _malformed_tool_call_resp(),
            _text_resp("Got an error but recovered"),
        ]
        result = adapter.act("do something")
        assert result == "Got an error but recovered"
        # Verify error was fed back in the tool message of the second call
        second_call_msgs = mock_lt.completion.call_args_list[1][1]["messages"]
        tool_msgs = [
            m
            for m in second_call_msgs
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        assert len(tool_msgs) == 1
        assert "[error]" in tool_msgs[0]["content"]

    def test_tool_execution_error_fed_back_as_string(self) -> None:
        """Executor raises → error string fed back to model; exception never re-raised."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _tool_call_resp("run_shell_command", {"command": "bad cmd"}),
            _text_resp("Error handled gracefully"),
        ]

        def raising_executor(args: dict) -> str:
            raise RuntimeError("disk full")

        adapter._tool_executors["run_shell_command"] = raising_executor

        result = adapter.act("run bad cmd")
        assert result == "Error handled gracefully"
        # The second completion call must have received the error as a tool message
        second_call_msgs = mock_lt.completion.call_args_list[1][1]["messages"]
        tool_msgs = [
            m
            for m in second_call_msgs
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        assert len(tool_msgs) == 1
        assert "[error]" in tool_msgs[0]["content"]
        assert "disk full" in tool_msgs[0]["content"]

    def test_unknown_tool_feeds_error_back_does_not_crash(self) -> None:
        """Model proposes unknown tool → error string fed back; no crash."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = [
            _unknown_tool_call_resp(),
            _text_resp("Unknown tool noted"),
        ]
        result = adapter.act("use unknown tool")
        assert result == "Unknown tool noted"
        # Verify error was fed back
        second_call_msgs = mock_lt.completion.call_args_list[1][1]["messages"]
        tool_msgs = [
            m
            for m in second_call_msgs
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        assert len(tool_msgs) == 1
        assert "unknown tool" in tool_msgs[0]["content"]

    def test_max_tool_iterations_exhaustion_returns_summary_string(self) -> None:
        """Loop exhausts MAX_TOOL_ITERATIONS → returns explicit summary; never raises."""
        adapter, mock_lt = _make_adapter(max_tool_iterations=2)
        # Both responses are tool-calls → loop never gets a final text answer
        mock_lt.completion.side_effect = [
            _tool_call_resp("run_shell_command", {"command": "ls"}, call_id="c1"),
            _tool_call_resp("run_shell_command", {"command": "ls"}, call_id="c2"),
        ]
        # Stub executor to avoid subprocess
        adapter._tool_executors["run_shell_command"] = lambda args: "ls output"

        result = adapter.act("keep looping")
        # Must not raise; must return a non-empty string
        assert isinstance(result, str) and len(result) > 0
        # No assistant text was produced → exhaustion summary is returned
        assert "exhausted" in result or "iterations" in result
        assert mock_lt.completion.call_count == 2

    def test_exhaustion_backward_scan_returns_assistant_text(self) -> None:
        """G4: Exhaustion scan finds earlier assistant text and returns it (not raw tool result).

        Design §5.4 / dryrun-code-1 G4: when the loop exhausts MAX_TOOL_ITERATIONS
        and an earlier assistant message has non-empty 'content' in its model_dump(),
        the backward scan must return that text rather than the generic exhaustion string.
        """
        adapter, mock_lt = _make_adapter(max_tool_iterations=2)
        # Iteration 1: tool call whose model_dump() includes text content
        # Iteration 2: tool call with no text content — loop exhausts after this
        mock_lt.completion.side_effect = [
            _tool_call_resp_with_text(
                "run_shell_command",
                {"command": "ls"},
                text_content="Partial result: I found the files",
                call_id="c1",
            ),
            _tool_call_resp("run_shell_command", {"command": "pwd"}, call_id="c2"),
        ]
        adapter._tool_executors["run_shell_command"] = lambda args: "some output"

        result = adapter.act("find files")

        # The backward scan should find the text from the first assistant message
        assert result == "Partial result: I found the files", (
            f"Expected assistant text from backward scan; got {result!r}"
        )
        assert mock_lt.completion.call_count == 2

    def test_act_model_error_raises_adapter_error(self) -> None:
        """litellm.completion raises inside _run_tool_loop → AdapterError raised."""
        adapter, mock_lt = _make_adapter()
        mock_lt.completion.side_effect = Exception("connection refused")
        with pytest.raises(AdapterError, match="local model error"):
            adapter.act("anything")
