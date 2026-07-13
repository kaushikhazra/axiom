"""
Unit tests — KIND-A local adapter gen_ai span enrichment (M2 observability).

Verifies that _enrich_current_span_gen_ai() (called from reason() and act()) sets
the correct gen_ai OTel attributes on the active span using the same attribute keys
as ClaudeAdapter (claude_adapter.py) so schema.py serialize_span_end() maps them to
the gen_ai_* record fields.

Tested behaviours:
  - gen_ai.system = "ollama" is set on the span
  - gen_ai.request.model = model_id is set on the span
  - gen_ai.response.model = model_id is set on the span
  - axiom.cost_usd = 0.0 is set on the span
  - gen_ai.usage.input_tokens from ChatMessage.token_usage.input_tokens when present
  - gen_ai.usage.output_tokens from ChatMessage.token_usage.output_tokens when present
  - Fallback: token counts from ChatMessage.raw.usage.prompt_tokens/.completion_tokens
  - Null-safe: when token counts are None, token attrs are NOT set (null in record)
  - Null-safe: when ChatMessage has no token_usage attr, no crash + token attrs null
  - is_recording() gate: no set_attribute calls when span is not recording
  - Zero-overhead: exception inside OTel block is silently swallowed (main path safe)

Mocking strategy (mirrors test_local_adapter.py):
  - smolagents is injected into sys.modules before LocalAdapter import so that
    `from smolagents import CodeAgent, LiteLLMModel` inside __init__ resolves to mocks.
  - _make_chat_message_mock() builds a ChatMessage-like object carrying the real
    token_usage shape (token_usage.input_tokens / token_usage.output_tokens) that
    smolagents 1.26 actually returns — proven by probe_local_tokens.py against
    real qwen2.5:7b.  Tests assert tokens come from THAT object, not from any
    fictional model attribute.
  - Real TracerProvider + processors + CaptureSink (same pattern as
    test_claude_adapter_spans.py) give end-to-end confidence that the span attributes
    flow through to the serialized span_end record.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider

# ---------------------------------------------------------------------------
# Inject mock smolagents BEFORE importing LocalAdapter so the deferred import
# inside __init__ resolves to mocks.  setdefault leaves an existing mock alone
# if test_local_adapter.py already registered one in the same process.
# ---------------------------------------------------------------------------
_mock_smolagents = MagicMock()
_mock_litellm_instance = MagicMock()
_mock_smolagents.LiteLLMModel.return_value = _mock_litellm_instance
_mock_smolagents.CodeAgent = MagicMock()
sys.modules.setdefault("smolagents", _mock_smolagents)

from axiom.providers.local_adapter import LocalAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------


class CaptureSink:
    def __init__(self) -> None:
        self.received: list[dict] = []

    def put(self, record: dict) -> None:
        self.received.append(record)

    def shutdown(self) -> None:
        pass


def _make_provider_with_capture() -> tuple[TracerProvider, CaptureSink]:
    """Create a TracerProvider wired to a CaptureSink via the real processors.

    Same factory as test_claude_adapter_spans.py — ensures end-to-end fidelity.
    The TracerProvider is NOT set as the global provider; the current-span context
    propagation works independently of the global provider.
    """
    from axiom.observability.processors import (
        JsonlExportProcessor,
        LiveNotificationProcessor,
    )
    from axiom.observability.registry import SinkRegistry

    registry = SinkRegistry()
    sink = CaptureSink()
    registry.register("trace", sink)
    tp = TracerProvider()
    tp.add_span_processor(LiveNotificationProcessor(registry=registry))
    tp.add_span_processor(JsonlExportProcessor(registry=registry))
    return tp, sink


def _make_adapter(model_id: str = "ollama_chat/qwen2.5:7b") -> LocalAdapter:
    """Construct a LocalAdapter with the mocked smolagents."""
    return LocalAdapter(persona="test-persona", model_id=model_id)


def _make_chat_message_mock(
    input_tokens: int | None = 50,
    output_tokens: int | None = 30,
    content: str = '{"intent": "RESPOND", "text": "ok"}',
) -> MagicMock:
    """Return a ChatMessage-like mock carrying token_usage — the real shape returned
    by smolagents 1.26's LiteLLMModel on a real qwen2.5:7b call.

    Proven shape (probe_local_tokens.py):
        resp.token_usage = TokenUsage(input_tokens=35, output_tokens=4, total_tokens=39)
        resp.raw.usage   = Usage(prompt_tokens=35, completion_tokens=4, total_tokens=39)
    """
    token_usage = MagicMock()
    token_usage.input_tokens = input_tokens
    token_usage.output_tokens = output_tokens

    msg = MagicMock()
    msg.content = content
    msg.token_usage = token_usage
    return msg


def _make_model_returning(chat_message: MagicMock) -> MagicMock:
    """Return a model callable mock that returns chat_message when called."""
    mock = MagicMock()
    mock.return_value = chat_message
    return mock


# ---------------------------------------------------------------------------
# Tests — _enrich_current_span_gen_ai() sets correct gen_ai attrs
# (direct call with explicit token params — tests the enrichment helper in isolation)
# ---------------------------------------------------------------------------


class TestEnrichCurrentSpanGenAiAttrs:
    """Verify the full set of gen_ai attributes appears in the serialized span_end."""

    def test_gen_ai_system_is_ollama(self):
        """gen_ai.system attribute must be 'ollama' — consistent with OTel semconv and litellm prefix."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=35, output_tokens=4)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_system"] == "ollama"

    def test_gen_ai_response_model_equals_model_id(self):
        """gen_ai.response.model must equal the adapter's model_id."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter(model_id="ollama_chat/qwen2.5:7b")

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=35, output_tokens=4)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_response_model"] == "ollama_chat/qwen2.5:7b"

    def test_gen_ai_request_model_equals_model_id(self):
        """gen_ai.request.model must equal the adapter's model_id.
        KIND-A knows the model at construction time — unlike KIND-B where SDK hides it."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter(model_id="ollama_chat/qwen2.5:7b")

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=35, output_tokens=4)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_request_model"] == "ollama_chat/qwen2.5:7b"

    def test_cost_usd_is_zero(self):
        """axiom.cost_usd must be 0.0 — local Ollama has no API billing."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=35, output_tokens=4)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["cost_usd"] == 0.0

    def test_input_tokens_populated_from_explicit_param(self):
        """gen_ai.usage.input_tokens reflects the value passed via input_tokens param."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=123, output_tokens=45)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_input_tokens"] == 123

    def test_output_tokens_populated_from_explicit_param(self):
        """gen_ai.usage.output_tokens reflects the value passed via output_tokens param."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=123, output_tokens=45)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_output_tokens"] == 45

    def test_enrichment_works_on_act_span_too(self):
        """Same enrichment applies to act-phase spans — call site is act() as well."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.act", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=200, output_tokens=80)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.act")
        assert span_end["gen_ai_response_model"] == "ollama_chat/qwen2.5:7b"
        assert span_end["gen_ai_system"] == "ollama"
        assert span_end["cost_usd"] == 0.0
        assert span_end["gen_ai_usage_input_tokens"] == 200
        assert span_end["gen_ai_usage_output_tokens"] == 80


# ---------------------------------------------------------------------------
# Tests — tokens flow from ChatMessage.token_usage through _query_model → span
# (integration path: model returns real ChatMessage shape → reason() enriches span)
# ---------------------------------------------------------------------------


class TestTokensFromChatMessageTokenUsage:
    """Verify the real token-extraction chain: model call → ChatMessage.token_usage
    → _query_model tuple → _enrich_current_span_gen_ai → span attributes.

    This is the must-fix path confirmed by probe_local_tokens.py:
      resp.token_usage.input_tokens  (primary source)
      resp.token_usage.output_tokens (primary source)
    """

    def test_reason_populates_input_tokens_from_chat_message_token_usage(self):
        """reason() must land input_tokens on the span from ChatMessage.token_usage."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()
        chat_msg = _make_chat_message_mock(input_tokens=35, output_tokens=4)
        adapter._model = _make_model_returning(chat_msg)

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter.reason("some context")

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_input_tokens"] == 35

    def test_reason_populates_output_tokens_from_chat_message_token_usage(self):
        """reason() must land output_tokens on the span from ChatMessage.token_usage."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()
        chat_msg = _make_chat_message_mock(input_tokens=35, output_tokens=4)
        adapter._model = _make_model_returning(chat_msg)

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter.reason("some context")

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_output_tokens"] == 4

    def test_reason_tokens_not_from_model_object_attrs(self):
        """Tokens must NOT come from any attribute on self._model itself — the model
        object has no last_*_token_count in smolagents 1.26. Confirm the ChatMessage
        is the source by giving the model object contradictory attrs and asserting
        the ChatMessage values win."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()
        chat_msg = _make_chat_message_mock(input_tokens=99, output_tokens=7)
        model_mock = _make_model_returning(chat_msg)
        # Deliberately add contradictory attrs on the model object itself.
        # If the code reads these instead of ChatMessage.token_usage, the assertion fails.
        model_mock.last_input_token_count = 999
        model_mock.last_output_token_count = 777
        adapter._model = model_mock

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter.reason("some context")

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        # Must be ChatMessage values (99, 7), NOT model-object values (999, 777).
        assert span_end["gen_ai_usage_input_tokens"] == 99
        assert span_end["gen_ai_usage_output_tokens"] == 7


class TestTokensFallbackToRawUsage:
    """Verify the raw.usage fallback path when token_usage is absent."""

    def test_query_model_falls_back_to_raw_usage_when_token_usage_absent(self):
        """When ChatMessage.token_usage is absent, _query_model falls back to
        raw.usage.prompt_tokens / completion_tokens."""
        adapter = _make_adapter()

        raw_usage = MagicMock()
        raw_usage.prompt_tokens = 41
        raw_usage.completion_tokens = 6
        raw = MagicMock()
        raw.usage = raw_usage

        msg = MagicMock()
        msg.content = '{"intent": "RESPOND", "text": "ok"}'
        # No token_usage attribute — simulate absence via spec=[...] subset.
        del msg.token_usage  # remove the auto-created MagicMock attr
        msg.raw = raw

        adapter._model = _make_model_returning(msg)
        _text, input_tokens, output_tokens = adapter._query_model("prompt")

        assert input_tokens == 41
        assert output_tokens == 6

    def test_query_model_returns_none_tokens_when_both_sources_absent(self):
        """When neither token_usage nor raw.usage is present, tokens are None (no crash)."""
        adapter = _make_adapter()

        msg = MagicMock(spec=["content"])
        msg.content = '{"intent": "RESPOND", "text": "ok"}'
        adapter._model = _make_model_returning(msg)

        _text, input_tokens, output_tokens = adapter._query_model("prompt")
        assert input_tokens is None
        assert output_tokens is None


# ---------------------------------------------------------------------------
# Tests — null-safety when token counts are absent
# ---------------------------------------------------------------------------


class TestEnrichCurrentSpanNullSafety:
    """Verify graceful degradation when token counts are None or absent."""

    def test_input_tokens_null_when_param_is_none(self):
        """When input_tokens=None, gen_ai_usage_input_tokens must be null in the
        serialized record — not fabricated as 0 or any other value."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=None, output_tokens=30)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_input_tokens"] is None

    def test_output_tokens_null_when_param_is_none(self):
        """When output_tokens=None, gen_ai_usage_output_tokens must be null."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=50, output_tokens=None)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_output_tokens"] is None

    def test_both_tokens_null_when_both_params_none(self):
        """Both token attrs null when both params are None — no partial fabrication."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter()

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=None, output_tokens=None)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_usage_input_tokens"] is None
        assert span_end["gen_ai_usage_output_tokens"] is None

    def test_null_safe_when_chat_message_has_no_token_usage(self):
        """When ChatMessage has no token_usage attr at all, no crash + tokens null."""
        adapter = _make_adapter()
        # spec=["content"] means the mock only has .content — no token_usage.
        msg = MagicMock(spec=["content"])
        msg.content = '{"intent": "RESPOND", "text": "ok"}'
        adapter._model = _make_model_returning(msg)

        _text, input_tokens, output_tokens = adapter._query_model("prompt")
        assert input_tokens is None
        assert output_tokens is None

    def test_other_attrs_still_set_even_when_tokens_absent(self):
        """model, system, cost attrs are set even when token counts are absent."""
        tp, sink = _make_provider_with_capture()
        tracer = tp.get_tracer("test")
        adapter = _make_adapter(model_id="ollama_chat/qwen2.5:7b")

        with tracer.start_as_current_span("axiom.loop.reason", attributes={}):
            adapter._enrich_current_span_gen_ai(input_tokens=None, output_tokens=None)

        ends = [r for r in sink.received if r["record_type"] == "span_end"]
        span_end = next(r for r in ends if r["span_name"] == "axiom.loop.reason")
        assert span_end["gen_ai_system"] == "ollama"
        assert span_end["gen_ai_response_model"] == "ollama_chat/qwen2.5:7b"
        assert span_end["gen_ai_request_model"] == "ollama_chat/qwen2.5:7b"
        assert span_end["cost_usd"] == 0.0


# ---------------------------------------------------------------------------
# Tests — is_recording() gate (zero OTel overhead when observability is off)
# ---------------------------------------------------------------------------


class TestEnrichCurrentSpanIsRecordingGate:
    """Verify the is_recording() guard: zero set_attribute calls when not recording."""

    def test_noop_when_span_not_recording(self):
        """When span.is_recording() is False, set_attribute must never be called.
        Mirrors ClaudeAdapter.act() pattern (claude_adapter.py:369-377)."""
        adapter = _make_adapter()

        with patch("opentelemetry.trace.get_current_span") as mock_get_span:
            mock_span = MagicMock()
            mock_span.is_recording.return_value = False
            mock_get_span.return_value = mock_span

            adapter._enrich_current_span_gen_ai(input_tokens=10, output_tokens=5)

        mock_span.set_attribute.assert_not_called()

    def test_recording_check_happens_before_any_set_attribute(self):
        """is_recording() is checked first — set_attribute is conditional, not always called."""
        adapter = _make_adapter()

        with patch("opentelemetry.trace.get_current_span") as mock_get_span:
            mock_span = MagicMock()
            mock_span.is_recording.return_value = False
            mock_get_span.return_value = mock_span

            adapter._enrich_current_span_gen_ai(input_tokens=10, output_tokens=5)

        # is_recording() called exactly once; set_attribute never
        mock_span.is_recording.assert_called_once()
        mock_span.set_attribute.assert_not_called()

    def test_attributes_set_when_recording(self):
        """Inverse: when is_recording() is True, set_attribute IS called."""
        adapter = _make_adapter()

        with patch("opentelemetry.trace.get_current_span") as mock_get_span:
            mock_span = MagicMock()
            mock_span.is_recording.return_value = True
            mock_get_span.return_value = mock_span

            adapter._enrich_current_span_gen_ai(input_tokens=10, output_tokens=5)

        # At minimum, model, system, cost, and token attributes must be set
        called_keys = {call.args[0] for call in mock_span.set_attribute.call_args_list}
        assert "gen_ai.system" in called_keys
        assert "gen_ai.request.model" in called_keys
        assert "gen_ai.response.model" in called_keys
        assert "axiom.cost_usd" in called_keys
        assert "gen_ai.usage.input_tokens" in called_keys
        assert "gen_ai.usage.output_tokens" in called_keys


# ---------------------------------------------------------------------------
# Tests — exception safety: OTel errors must never crash the main path
# ---------------------------------------------------------------------------


class TestEnrichCurrentSpanExceptionSafety:
    """Verify the outer try/except swallows OTel-internal exceptions."""

    def test_does_not_raise_on_otel_import_error(self):
        """If opentelemetry is unavailable (patched away), method returns silently."""
        adapter = _make_adapter()

        with patch.dict(
            sys.modules, {"opentelemetry": None, "opentelemetry.trace": None}
        ):
            # ModuleNotFoundError is a subclass of Exception — the outer try/except catches it.
            adapter._enrich_current_span_gen_ai(
                input_tokens=10, output_tokens=5
            )  # must not raise

    def test_does_not_raise_when_set_attribute_throws(self):
        """If set_attribute raises unexpectedly, the main path is unaffected."""
        adapter = _make_adapter()

        with patch("opentelemetry.trace.get_current_span") as mock_get_span:
            mock_span = MagicMock()
            mock_span.is_recording.return_value = True
            mock_span.set_attribute.side_effect = RuntimeError("OTel internal error")
            mock_get_span.return_value = mock_span

            adapter._enrich_current_span_gen_ai(
                input_tokens=10, output_tokens=5
            )  # must not raise
