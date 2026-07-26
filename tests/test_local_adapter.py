"""
Unit tests for LocalAdapter (reason, act, constructor) -- smolagents implementation.

PraoAdapterBase and _parse_intent tests live in test_shared_base.py (design §8/§11.2).

All tests use unittest.mock to stub smolagents components -- no live Ollama, no network.
smolagents (CodeAgent, LiteLLMModel) is injected into sys.modules before LocalAdapter
is imported so that the deferred `from smolagents import ...` inside LocalAdapter.__init__
resolves to mocks rather than the real package.

Key mocking strategy (design §12.1):
  - reason() tests: mock self._model directly after construction (it's the LiteLLMModel
    instance stored in __init__). _query_model() calls self._model(messages, stop_sequences=None),
    which returns a ChatMessage-like object with a .content attribute.
  - act() tests: patch 'axiom.providers.local_adapter.CodeAgent' (the name imported inside
    act()) so the freshly-constructed CodeAgent instance returns a controlled .run() value.
    Since act() creates a FRESH CodeAgent per call, we patch the constructor, not an instance.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Inject mock smolagents into sys.modules BEFORE importing LocalAdapter so that
# `from smolagents import CodeAgent, LiteLLMModel` inside __init__ resolves to
# mocks (isolates from live model/network calls -- smolagents is a required
# dependency per pyproject.toml, so a real import to seed Tool below is safe).
#
# M4: axiom.tools.smolagents_tools does `class ReadFileTool(Tool): ...` at
# import time (lazily, on the first act() call). A bare MagicMock
# auto-attribute is not usable as a base class -- it doesn't raise, it just
# silently produces a broken mock object in place of a real class. Tool is
# seeded from the real smolagents module so subclassing behaves normally;
# CodeAgent/LiteLLMModel stay mocked to avoid any live model/network work.
# ---------------------------------------------------------------------------
import smolagents as _real_smolagents_module  # noqa: E402 -- real import, captures Tool before the mock replaces sys.modules["smolagents"]

_mock_smolagents = MagicMock()
_mock_LiteLLMModel_instance = MagicMock()
_mock_smolagents.LiteLLMModel.return_value = _mock_LiteLLMModel_instance
_mock_smolagents.CodeAgent = MagicMock()
_mock_smolagents.Tool = _real_smolagents_module.Tool

sys.modules["smolagents"] = _mock_smolagents

from axiom.interfaces import (  # noqa: E402
    ActIntent,
    AdapterError,
    FinishIntent,
    RespondIntent,
)
from axiom.providers.local_adapter import LocalAdapter  # noqa: E402
from axiom.tools.guardrails import GuardrailsGate  # noqa: E402

_TEST_WORKING_DIR = Path(tempfile.gettempdir())


# ============================================================
# Test helpers
# ============================================================


def _make_model_response(content: str) -> MagicMock:
    """Build a mock ChatMessage-like response with .content attribute."""
    resp = MagicMock()
    resp.content = content
    return resp


def _make_adapter(
    max_steps: int = 5,
    additional_authorized_imports: list[str] | None = None,
) -> tuple[LocalAdapter, MagicMock]:
    """Build a LocalAdapter with a fresh mock _model, return (adapter, mock_model).

    Replaces adapter._model with a fresh MagicMock so every test configures
    side_effects independently without cross-contamination.
    """
    kwargs: dict = {
        "persona": "Test persona",
        "working_dir": _TEST_WORKING_DIR,
        "gate": GuardrailsGate(auto_approve=True),
        "max_steps": max_steps,
    }
    if additional_authorized_imports is not None:
        kwargs["additional_authorized_imports"] = additional_authorized_imports

    adapter = LocalAdapter(**kwargs)
    mock_model = MagicMock()
    adapter._model = mock_model
    return adapter, mock_model


# ============================================================
# LocalAdapter — constructor
# ============================================================


class TestLocalAdapterConstructor:
    def test_default_model_id(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter._model_id == "ollama_chat/qwen2.5:7b"

    def test_default_ollama_api_base(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter._ollama_api_base == "http://localhost:11434"

    def test_default_max_steps(self) -> None:
        adapter, _ = _make_adapter()
        assert adapter._max_steps == 5

    def test_custom_max_steps(self) -> None:
        adapter, _ = _make_adapter(max_steps=3)
        assert adapter._max_steps == 3

    def test_default_authorized_imports_excludes_subprocess(self) -> None:
        """M4: raw subprocess access is removed -- run_shell (gated, working-dir-
        scoped) is now the only sanctioned way to run a shell command
        (design.md AC-05.4)."""
        adapter, _ = _make_adapter()
        assert "subprocess" not in adapter._authorized_imports

    def test_custom_authorized_imports(self) -> None:
        adapter, _ = _make_adapter(additional_authorized_imports=["math"])
        assert adapter._authorized_imports == ["math"]

    def test_no_agent_stored_on_instance(self) -> None:
        """act() creates CodeAgent fresh per call -- no self._agent stored (W2)."""
        adapter, _ = _make_adapter()
        assert not hasattr(adapter, "_agent")

    def test_smolagents_import_failure_raises_helpful_error(self) -> None:
        """If smolagents is not installed, constructor raises ModuleNotFoundError with guidance."""
        # Setting a module to None in sys.modules causes `import smolagents` to raise ImportError.
        with patch.dict(sys.modules, {"smolagents": None}):
            with pytest.raises((ModuleNotFoundError, ImportError), match="smolagents"):
                LocalAdapter(
                    persona="Test",
                    working_dir=_TEST_WORKING_DIR,
                    gate=GuardrailsGate(auto_approve=True),
                )


# ============================================================
# LocalAdapter — reason()
# ============================================================


class TestLocalAdapterReason:
    def test_valid_respond_intent(self) -> None:
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "RESPOND", "text": "Hi"}'
        )
        result = adapter.reason("some context")
        assert isinstance(result, RespondIntent)
        assert result.text == "Hi"
        assert mock_model.call_count == 1

    def test_valid_act_intent(self) -> None:
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "ACT", "instruction": "do it"}'
        )
        result = adapter.reason("some context")
        assert isinstance(result, ActIntent)
        assert result.instruction == "do it"

    def test_valid_finish_intent(self) -> None:
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response('{"intent": "FINISH"}')
        result = adapter.reason("context")
        assert isinstance(result, FinishIntent)

    def test_malformed_first_call_retry_succeeds(self) -> None:
        """First call returns bad JSON; retry call returns valid JSON -> Intent returned."""
        adapter, mock_model = _make_adapter()
        mock_model.side_effect = [
            _make_model_response("not json at all"),
            _make_model_response('{"intent": "RESPOND", "text": "retry worked"}'),
        ]
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert result.text == "retry worked"
        assert mock_model.call_count == 2

    def test_malformed_both_attempts_returns_fallback_respond(self) -> None:
        """Both first and retry calls return bad JSON -> [FALLBACK_RESPOND] returned."""
        adapter, mock_model = _make_adapter()
        mock_model.side_effect = [
            _make_model_response("garbage1"),
            _make_model_response("garbage2"),
        ]
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert "[FALLBACK_RESPOND]" in result.text
        assert mock_model.call_count == 2

    def test_json_in_code_fence_resolved_without_retry(self) -> None:
        """Pre-processing recovers JSON from code fence -- no retry needed."""
        adapter, mock_model = _make_adapter()
        fenced = '```json\n{"intent": "RESPOND", "text": "From fence"}\n```'
        mock_model.return_value = _make_model_response(fenced)
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert result.text == "From fence"
        assert mock_model.call_count == 1  # pre-processing resolved it, no retry

    def test_reason_model_error_raises_adapter_error(self) -> None:
        """Model raises in _query_model() -> AdapterError propagated.

        Uses RuntimeError so the exception class name doesn't match any
        differentiated tag (Connection/NotFound/Timeout), hitting the
        [LOCAL_ADAPTER_UNEXPECTED] branch with message 'local model error: ...'.
        """
        adapter, mock_model = _make_adapter()
        mock_model.side_effect = RuntimeError("something crashed")
        with pytest.raises(AdapterError, match="local model error"):
            adapter.reason("context")

    def test_none_content_returned_as_empty_string(self) -> None:
        """If model response .content is None, _query_model returns '' -> fallback RESPOND."""
        adapter, mock_model = _make_adapter()
        # First and retry both return None content -> both parse fail -> fallback
        mock_model.side_effect = [
            _make_model_response(None),  # type: ignore[arg-type]
            _make_model_response(None),  # type: ignore[arg-type]
        ]
        result = adapter.reason("context")
        assert isinstance(result, RespondIntent)
        assert "[FALLBACK_RESPOND]" in result.text

    # ----------------------------------------------------------------
    # Defect-A tests: RESPOND-forcing when history is present
    # ----------------------------------------------------------------

    def test_post_act_context_prepends_framing_block(self) -> None:
        """Defect-A: when context contains [TOOL EXECUTION RESULTS, model is called
        with a prepended SYSTEM INSTRUCTION framing block — not the bare context."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "RESPOND", "text": "done"}'
        )
        # Simulate a context that perceive() would produce after one act() cycle.
        post_act_context = (
            "[PERSONA]\nTest persona\n\n"
            "[TOOL EXECUTION RESULTS — read these carefully]\n"
            "Step 1: hello\n\n"
            "[NOTE: The above are REAL outputs...]\n\n"
            "[CURRENT REQUEST]\nRun the script"
        )
        adapter.reason(post_act_context)
        # Verify the actual prompt sent to the model includes the framing block.
        call_args = mock_model.call_args
        # _query_model wraps in messages list: [{"role": "user", "content": [{...}]}]
        sent_text = call_args[0][0][0]["content"][0]["text"]
        assert "SYSTEM INSTRUCTION (highest priority" in sent_text
        assert "ALREADY completed" in sent_text
        # Original context is still present (appended after framing)
        assert "[TOOL EXECUTION RESULTS" in sent_text

    def test_no_framing_block_without_history(self) -> None:
        """Defect-A: when context has NO [TOOL EXECUTION RESULTS, no framing is prepended."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "ACT", "instruction": "do it"}'
        )
        plain_context = "[PERSONA]\nTest persona\n\n[CURRENT REQUEST]\nDo something"
        adapter.reason(plain_context)
        call_args = mock_model.call_args
        sent_text = call_args[0][0][0]["content"][0]["text"]
        assert "SYSTEM INSTRUCTION (highest priority" not in sent_text
        assert sent_text == plain_context

    def test_no_framing_block_when_skill_activation_present(self) -> None:
        """M5 / dryrun-code-1 B2 regression: [TOOL EXECUTION RESULTS from an
        earlier ACT is still present (history never clears), but a skill was
        JUST activated -- the hard RESPOND-forcing framing must be suppressed
        so the Conductor can actually use the skill instead of being pushed
        to respond immediately (the exact failure class dryrun-design-1's C3
        fixed, reproduced here via LocalAdapter's own Defect-A mechanism)."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "ACT", "instruction": "use the skill instructions"}'
        )
        post_act_and_skill_context = (
            "[PERSONA]\nTest persona\n\n"
            "[ACTIVE SKILL: csv-summarizer]\nStep 1: read the CSV.\n\n"
            "[TOOL EXECUTION RESULTS — read these carefully]\n"
            "Step 1: file1.csv\n\n"
            "[SKILL ACTIVATION]\n[SKILL ACTIVATED] csv-summarizer\n\n"
            "[CURRENT REQUEST]\nSummarize the csv"
        )
        adapter.reason(post_act_and_skill_context)
        call_args = mock_model.call_args
        sent_text = call_args[0][0][0]["content"][0]["text"]
        assert "SYSTEM INSTRUCTION (highest priority" not in sent_text
        assert sent_text == post_act_and_skill_context

    def test_framing_block_returns_after_skill_activation_note_clears(self) -> None:
        """Once skill_activation_note is cleared (the cycle after activation,
        per design.md D5a's one-shot rendering), [TOOL EXECUTION RESULTS
        alone is enough to re-trigger the forcing -- suppression is scoped
        to exactly the one cycle the note is visible for."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "RESPOND", "text": "done"}'
        )
        post_act_context_no_skill_note = (
            "[PERSONA]\nTest persona\n\n"
            "[ACTIVE SKILL: csv-summarizer]\nStep 1: read the CSV.\n\n"
            "[TOOL EXECUTION RESULTS — read these carefully]\n"
            "Step 1: file1.csv\n\n"
            "[CURRENT REQUEST]\nSummarize the csv"
        )
        adapter.reason(post_act_context_no_skill_note)
        call_args = mock_model.call_args
        sent_text = call_args[0][0][0]["content"][0]["text"]
        assert "SYSTEM INSTRUCTION (highest priority" in sent_text

    def test_framing_block_prepended_for_already_active_skill(self) -> None:
        """Live-CLI verification (SK-7) regression: a real local model repeatedly
        re-emitted USE_SKILL for an already-active skill and exhausted MAX_CYCLES.
        A [SKILL ALREADY ACTIVE] note must trigger a hard forcing block telling
        the model to stop re-requesting and use ACT/RESPOND instead."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "RESPOND", "text": "done"}'
        )
        already_active_context = (
            "[PERSONA]\nTest persona\n\n"
            "[ACTIVE SKILL: csv-summarizer]\nStep 1: read the CSV.\n\n"
            "[SKILL ACTIVATION]\n[SKILL ALREADY ACTIVE] csv-summarizer\n\n"
            "[CURRENT REQUEST]\nSummarize the csv"
        )
        adapter.reason(already_active_context)
        call_args = mock_model.call_args
        sent_text = call_args[0][0][0]["content"][0]["text"]
        assert "SYSTEM INSTRUCTION (highest priority" in sent_text
        assert "Do NOT emit another USE_SKILL" in sent_text

    def test_already_active_forcing_does_not_stack_with_contradictory_post_act_forcing(
        self,
    ) -> None:
        """Both sentinels can co-occur (an earlier ACT, then a re-requested
        already-active skill in the same run). The post-act block's "your
        ONLY valid response is RESPOND, do NOT ACT" instruction would
        contradict the already-active block's "choose ACT or RESPOND" --
        so only the already-active framing fires, matching the existing
        [SKILL ACTIVATION]-suppresses-post-act rule (dryrun-code-1 B2)."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "RESPOND", "text": "done"}'
        )
        both_context = (
            "[PERSONA]\nTest persona\n\n"
            "[TOOL EXECUTION RESULTS — read these carefully]\n"
            "Step 1: file1.csv\n\n"
            "[SKILL ACTIVATION]\n[SKILL ALREADY ACTIVE] csv-summarizer\n\n"
            "[CURRENT REQUEST]\nSummarize the csv"
        )
        adapter.reason(both_context)
        call_args = mock_model.call_args
        sent_text = call_args[0][0][0]["content"][0]["text"]
        assert "Do NOT emit another USE_SKILL" in sent_text
        assert "The executor has ALREADY completed the delegated task" not in sent_text

    def test_post_act_context_returns_respond_intent(self) -> None:
        """Defect-A integration: reason() returns RESPOND when history is present
        and model correctly returns RESPOND intent (main scenario for loop termination)."""
        adapter, mock_model = _make_adapter()
        mock_model.return_value = _make_model_response(
            '{"intent": "RESPOND", "text": "The output was: hello"}'
        )
        post_act_context = (
            "[PERSONA]\nTest persona\n\n"
            "[TOOL EXECUTION RESULTS — read these carefully]\n"
            "Step 1: hello\n\n"
            "[CURRENT REQUEST]\nRun the script"
        )
        result = adapter.reason(post_act_context)
        assert isinstance(result, RespondIntent)
        assert result.text == "The output was: hello"

    def test_post_act_retry_also_uses_framing(self) -> None:
        """Defect-A: when retry is needed in a post-act context, the retry prompt
        also contains the RESPOND-forcing framing block (not just the bare context)."""
        adapter, mock_model = _make_adapter()
        mock_model.side_effect = [
            _make_model_response("not json"),
            _make_model_response('{"intent": "RESPOND", "text": "retry worked"}'),
        ]
        post_act_context = (
            "[PERSONA]\nTest persona\n\n"
            "[TOOL EXECUTION RESULTS — read these carefully]\n"
            "Step 1: output\n\n"
            "[CURRENT REQUEST]\nRun script"
        )
        result = adapter.reason(post_act_context)
        assert isinstance(result, RespondIntent)
        assert result.text == "retry worked"
        # Verify the retry call also included the framing block
        retry_call_args = mock_model.call_args_list[1]
        retry_text = retry_call_args[0][0][0]["content"][0]["text"]
        assert "SYSTEM INSTRUCTION (highest priority" in retry_text


# ============================================================
# LocalAdapter — act()
# ============================================================


class TestLocalAdapterAct:
    def test_happy_path_returns_result_string(self) -> None:
        """CodeAgent.run() returns a string -> act() returns that string."""
        adapter, _ = _make_adapter()
        with patch("smolagents.CodeAgent") as MockCodeAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.return_value = "The answer is 42"
            MockCodeAgent.return_value = mock_agent_instance

            result = adapter.act("What is 6 times 7?")

        assert result == "The answer is 42"
        MockCodeAgent.assert_called_once()
        mock_agent_instance.run.assert_called_once_with("What is 6 times 7?")

    def test_act_creates_fresh_codeagent_per_call(self) -> None:
        """Each act() call creates a new CodeAgent (W2 -- no cross-call state)."""
        adapter, _ = _make_adapter()
        with patch("smolagents.CodeAgent") as MockCodeAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.return_value = "result"
            MockCodeAgent.return_value = mock_agent_instance

            adapter.act("first call")
            adapter.act("second call")

        # Constructor called twice -> two fresh instances
        assert MockCodeAgent.call_count == 2

    def test_act_passes_correct_constructor_args(self) -> None:
        """CodeAgent is constructed with the right model, tools, max_steps, executor.

        Tool-set fix: add_base_tools is NOT passed (explicit minimal tool list is
        used instead). CodeAgent receives tools=[DuckDuckGoSearchTool(), <4 Axiom
        tools>], max_steps, executor, verbosity_level.

        Since smolagents 1.26.0: additional_authorized_imports is passed to a
        LocalPythonExecutor, not directly to CodeAgent. CodeAgent receives an
        executor= kwarg instead.

        M4: the Axiom tools (ReadFileTool/WriteFileTool/ListDirTool/RunShellTool)
        are imported from axiom.tools.smolagents_tools, not from the smolagents
        package itself, so patch("smolagents.DuckDuckGoSearchTool") mocks only
        that one tool -- the other four are real (but harmless: their __init__
        just stores a ToolRegistry reference, no I/O).
        """
        from axiom.tools.smolagents_tools import (
            ListDirTool,
            ReadFileTool,
            RunShellTool,
            WriteFileTool,
        )

        adapter, _ = _make_adapter(max_steps=3)
        with (
            patch("smolagents.CodeAgent") as MockCodeAgent,
            patch("smolagents.LocalPythonExecutor") as MockExecutor,
            patch("smolagents.DuckDuckGoSearchTool") as MockDDGTool,
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.return_value = "ok"
            MockCodeAgent.return_value = mock_agent_instance
            mock_executor_instance = MagicMock()
            MockExecutor.return_value = mock_executor_instance
            mock_ddg_instance = MagicMock()
            MockDDGTool.return_value = mock_ddg_instance

            adapter.act("do something")

        # CodeAgent receives model, tools=[DuckDuckGoSearchTool(), <4 Axiom tools>],
        # max_steps, executor, verbosity_level. add_base_tools is NOT passed (tool-set fix).
        call_kwargs = MockCodeAgent.call_args[1]
        assert call_kwargs["model"] is adapter._model
        tools = call_kwargs["tools"]
        assert len(tools) == 5
        assert tools[0] is mock_ddg_instance
        assert isinstance(tools[1], ReadFileTool)
        assert isinstance(tools[2], WriteFileTool)
        assert isinstance(tools[3], ListDirTool)
        assert isinstance(tools[4], RunShellTool)
        assert "add_base_tools" not in call_kwargs, (
            "add_base_tools must NOT be passed -- explicit tool list replaces it"
        )
        assert call_kwargs["max_steps"] == 3
        assert call_kwargs["executor"] is mock_executor_instance
        # Defect-B: verbosity_level=0 must be present to suppress rich console logging
        assert call_kwargs["verbosity_level"] == 0

        # LocalPythonExecutor: M4 removed "subprocess" (AC-05.4) and "open" from
        # additional_functions (AC-04.4) -- run_shell/write_file are the gated
        # replacements. 're' is still pre-populated (tool-set fix, unrelated to M4).
        executor_kwargs = MockExecutor.call_args[1]
        assert "subprocess" not in executor_kwargs["additional_authorized_imports"]
        assert "open" not in executor_kwargs["additional_functions"]
        assert "re" in executor_kwargs["additional_functions"], (
            "re module must be pre-populated in executor namespace (tool-set fix)"
        )
        import re as _re_check

        assert executor_kwargs["additional_functions"]["re"] is _re_check

    def test_act_verbosity_level_zero_suppresses_console_logging(self) -> None:
        """Defect-B: CodeAgent is constructed with verbosity_level=0.

        Prevents UnicodeEncodeError on Windows (cp1252) when smolagents/rich
        tries to print emoji-containing content (e.g. DuckDuckGo search results).
        verbosity_level=0 suppresses all rich console output from the CodeAgent.
        """
        adapter, _ = _make_adapter()
        with (
            patch("smolagents.CodeAgent") as MockCodeAgent,
            patch("smolagents.LocalPythonExecutor"),
        ):
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.return_value = "result"
            MockCodeAgent.return_value = mock_agent_instance

            adapter.act("do something")

        call_kwargs = MockCodeAgent.call_args[1]
        assert "verbosity_level" in call_kwargs, (
            "CodeAgent must be constructed with verbosity_level kwarg (Defect-B fix)"
        )
        assert call_kwargs["verbosity_level"] == 0, (
            "verbosity_level must be 0 to suppress rich console logging on Windows"
        )

    def test_act_result_non_string_converted_to_str(self) -> None:
        """If CodeAgent.run() returns a non-string (e.g. int), str() is applied."""
        adapter, _ = _make_adapter()
        with patch("smolagents.CodeAgent") as MockCodeAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.return_value = 42  # int, not str
            MockCodeAgent.return_value = mock_agent_instance

            result = adapter.act("what is 6*7")

        assert result == "42"
        assert isinstance(result, str)

    def test_act_codeagent_error_raises_adapter_error(self) -> None:
        """CodeAgent.run() raises -> AdapterError propagated."""
        adapter, _ = _make_adapter()
        with patch("smolagents.CodeAgent") as MockCodeAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.side_effect = RuntimeError("model refused")
            MockCodeAgent.return_value = mock_agent_instance

            with pytest.raises(AdapterError, match="CodeAgent execution error"):
                adapter.act("do something")

    def test_act_error_message_contains_original_exception(self) -> None:
        """AdapterError message wraps the original exception text."""
        adapter, _ = _make_adapter()
        with patch("smolagents.CodeAgent") as MockCodeAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.run.side_effect = ValueError("quota exceeded")
            MockCodeAgent.return_value = mock_agent_instance

            with pytest.raises(AdapterError, match="quota exceeded"):
                adapter.act("do something")

    def test_act_codeagent_constructor_failure_raises_adapter_error(self) -> None:
        """CodeAgent constructor raises -> AdapterError propagated (G2 fix).

        Before G2, the constructor was outside the try/except so raw exceptions
        escaped the adapter boundary. Now the whole block is guarded.
        """
        adapter, _ = _make_adapter()
        with patch("smolagents.CodeAgent") as MockCodeAgent:
            MockCodeAgent.side_effect = RuntimeError("model config invalid")

            with pytest.raises(AdapterError, match="CodeAgent execution error"):
                adapter.act("do something")
