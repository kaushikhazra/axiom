"""
Claude adapter — implements all four PRAO port Protocols via claude_agent_sdk.

Bridges synchronous port contracts to the async SDK via anyio.run() per call.
All port methods are synchronous (def, not async def); async is contained here.

perceive() and observe() are inherited from PraoAdapterBase (providers/base.py).
reason() and act() are Claude-specific (SDK query calls).

OQ-2 confirmed:
  - query() is an async generator (NOT a coroutine) — iterate with
    'async for message in sdk_query(...)' — no 'await' before sdk_query.
  - ResultMessage.result is str | None — access as message.result.
  - ClaudeAgentOptions(tools=[]) is the correct kwarg for tool-less queries.
    NOTE: allowed_tools=[] does NOT disable tools — empty list is falsy,
    so subprocess_cli.py skips the --allowedTools flag entirely, leaving all
    CLI defaults active. Use tools=[] instead: subprocess_cli.py has an
    explicit None-check (not truthiness) and emits --tools "" for empty list.

M2 KIND-B streaming spans:
  act() passes the current OTel context into the async helper so that child
  spans minted inside the async generator correctly nest under the Act span.
  anyio.run() is synchronous and runs on the calling thread, so OTel context
  is inherited automatically — no manual context attachment is required.

  Child spans minted per SDK event:
    AssistantMessage  -> 'axiom.provider.assistant_turn'
                         attributes: gen_ai.system, gen_ai.response.model,
                         gen_ai.usage.input_tokens, gen_ai.usage.output_tokens
    ToolUseBlock(s)   -> one span per block: 'gen_ai.tool_call.<tool_name>'
                         attributes: gen_ai.system, axiom.tool_use_id
    ResultMessage     -> no child span; cost+aggregate tokens set on Act span
                         via the act_span Span reference passed in

  NOT exposed by SDK (null in all records):
    gen_ai.request.model — model is CLI-configured; ClaudeAgentOptions.model
                           is only set when the caller explicitly chooses one.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ClaudeAgentOptions,
    ClaudeSDKError,
    HookMatcher,
    ProcessError,
    ResultMessage,
    ToolUseBlock,
    query as sdk_query,
)

from axiom.interfaces import (
    AdapterError,
    Intent,
)
from axiom.providers.base import PraoAdapterBase, _parse_intent
from axiom.tools.guardrails import Classification, GuardrailsGate

if TYPE_CHECKING:
    from opentelemetry.trace import Span

logger = logging.getLogger("axiom.providers")

PER_QUERY_TIMEOUT_SECS: int = 120  # 2 minutes; CLI process can hang if unauthenticated

# gen_ai.system constant for all KIND-B Claude spans.
# OTel GenAI semconv (v1.28.0) defines "anthropic" as the correct provider-system
# value for Anthropic's Claude — not the model-family name "claude".
_GEN_AI_SYSTEM: str = "anthropic"


# ---------------------------------------------------------------------------
# Child-span helpers (module-level so they have no adapter state dependency)
# ---------------------------------------------------------------------------


def _open_child_span(
    tracer,
    name: str,
    run_id: str,
    provider_kind: str,
    extra_attributes: dict | None = None,
):
    """Start and return an OTel span as a direct child of the current context.

    The caller is responsible for calling span.end() when the event is complete.
    Precondition: tracer must not be None. The guard 'if tracer is not None'
    in _collect_query_result ensures this precondition is never violated at runtime.
    """
    attributes: dict = {
        "axiom.run_id": run_id,
        "axiom.span_source": "provider-streamed",
        "axiom.provider_kind": provider_kind,
        "gen_ai.system": _GEN_AI_SYSTEM,
    }
    if extra_attributes:
        attributes.update(extra_attributes)
    return tracer.start_span(name, attributes=attributes)


def _end_span_ok(span) -> None:
    """Set OK status and end an OTel span."""
    from opentelemetry.trace import StatusCode  # local — OTel confined to observability

    span.set_status(StatusCode.OK)
    span.end()


# ---------------------------------------------------------------------------
# Async helper (module-level so anyio.run() can accept it as a callable)
# ---------------------------------------------------------------------------


async def _collect_query_result(
    prompt: str,
    options: ClaudeAgentOptions,
    tracer=None,
    run_id: str | None = None,
    provider_kind: str = "KIND_B",
    act_span: "Span | None" = None,
) -> str:
    """Async helper: run one sdk_query() call and collect the ResultMessage text.

    query() is an async generator function (confirmed via inspect.isasyncgenfunction).
    Iterate directly — no 'await' before sdk_query().
    Wraps iteration in anyio.fail_after() for the per-query timeout.
    Explicitly closes the generator in a finally block for deterministic cleanup
    (prevents lingering subprocess on the is_error and timeout exit paths).
    ResultMessage is terminal — no break on the success path; the generator
    exhausts naturally, making aclose() a no-op on that path.

    When tracer, run_id, and act_span are provided (KIND-B observability active),
    mints child spans under the Act span for each AssistantMessage and its
    ToolUseBlock entries. ResultMessage cost/token attributes are set on act_span.
    """
    result_text = ""
    gen = sdk_query(prompt=prompt, options=options)
    try:
        with anyio.fail_after(PER_QUERY_TIMEOUT_SECS):
            async for message in gen:
                # -- KIND-B child span minting --
                if tracer is not None and run_id is not None:
                    _handle_sdk_event_spans(
                        message, tracer, run_id, provider_kind, act_span
                    )

                if isinstance(message, ResultMessage):
                    if message.is_error:
                        subtype = getattr(message, "subtype", None)
                        errors = getattr(message, "errors", None)
                        detail = f"subtype={subtype!r}"
                        if errors:
                            detail += f", errors={errors!r}"
                        logger.error("[ADAPTER_SDK_IS_ERROR] %s", detail)
                        raise AdapterError(f"SDK run failed ({detail})")
                    result_text = message.result or ""
                    # No break — ResultMessage is terminal; iterating to exhaustion
                    # ensures deterministic generator cleanup on the success path.
    finally:
        with anyio.move_on_after(5):  # best-effort: don't let teardown hang
            await gen.aclose()
    return result_text


def _handle_sdk_event_spans(
    message,
    tracer,
    run_id: str,
    provider_kind: str,
    act_span: "Span | None",
) -> None:
    """Mint child OTel spans for a single SDK message event.

    Called synchronously from within the async generator loop.
    OTel context is inherited from the calling coroutine's thread — no manual
    context attachment needed because anyio.run() runs on the same thread as
    the act() caller (which holds the Act span as the current context).

    Span lifetime policy:
      - AssistantMessage -> one 'axiom.provider.assistant_turn' span, closed immediately
      - ToolUseBlock     -> one 'gen_ai.tool_call.<name>' span per block, closed immediately
      - ResultMessage    -> no span; cost+tokens SET on act_span attributes
    """
    if isinstance(message, AssistantMessage):
        _mint_assistant_turn_span(message, tracer, run_id, provider_kind)
        _mint_tool_use_spans(message, tracer, run_id, provider_kind)

    elif isinstance(message, ResultMessage) and act_span is not None:
        _set_result_attrs_on_act_span(message, act_span)


def _mint_assistant_turn_span(
    message: AssistantMessage,
    tracer,
    run_id: str,
    provider_kind: str,
) -> None:
    """Open and immediately close an 'axiom.provider.assistant_turn' child span."""
    extra: dict = {
        "axiom.phase": "act",
        "gen_ai.operation.name": "assistant_turn",
        "gen_ai.response.model": message.model,
    }
    usage = message.usage or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is not None:
        extra["gen_ai.usage.input_tokens"] = input_tokens
    if output_tokens is not None:
        extra["gen_ai.usage.output_tokens"] = output_tokens
    if message.stop_reason is not None:
        extra["axiom.stop_reason"] = message.stop_reason

    span = _open_child_span(
        tracer,
        name="axiom.provider.assistant_turn",
        run_id=run_id,
        provider_kind=provider_kind,
        extra_attributes=extra,
    )
    _end_span_ok(span)


def _mint_tool_use_spans(
    message: AssistantMessage,
    tracer,
    run_id: str,
    provider_kind: str,
) -> None:
    """Open and immediately close one child span per ToolUseBlock in the message."""
    for block in message.content:
        if not isinstance(block, ToolUseBlock):
            continue
        span = _open_child_span(
            tracer,
            name=f"gen_ai.tool_call.{block.name}",
            run_id=run_id,
            provider_kind=provider_kind,
            extra_attributes={
                "axiom.phase": "act",
                "gen_ai.operation.name": "tool_call",
                "axiom.tool_name": block.name,
                "axiom.tool_use_id": block.id,
            },
        )
        _end_span_ok(span)


def _set_result_attrs_on_act_span(
    message: ResultMessage,
    act_span: "Span",
) -> None:
    """Set aggregate cost and token attributes from ResultMessage onto the Act span."""
    if message.total_cost_usd is not None:
        act_span.set_attribute("axiom.cost_usd", message.total_cost_usd)

    usage = message.usage or {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is not None:
        act_span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
    if output_tokens is not None:
        act_span.set_attribute("gen_ai.usage.output_tokens", output_tokens)

    act_span.set_attribute("axiom.num_turns", message.num_turns)


# ---------------------------------------------------------------------------
# ClaudeAdapter
# ---------------------------------------------------------------------------


class ClaudeAdapter(PraoAdapterBase):
    """Concrete adapter implementing all four PRAO port Protocols via claude_agent_sdk.

    perceive() and observe() are inherited from PraoAdapterBase.
    reason() and act() are implemented here using the Claude SDK.
    """

    def __init__(
        self, persona: str, allowed_tools: list[str], gate: GuardrailsGate
    ) -> None:
        super().__init__(persona=persona)
        self._allowed_tools = allowed_tools
        # M4: gate is required (no default) -- same fail-loud rationale as
        # LocalAdapter's working_dir/gate params (design.md D6, D11).
        self._gate = gate

    # ------------------------------------------------------------------
    # Guardrails GATE (M4)
    # ------------------------------------------------------------------

    async def _gate_hook(
        self, input_data: dict, tool_use_id: str | None, context
    ) -> dict:
        """PreToolUse hook -- fires for every tool call (no matcher restriction).

        Uses a PreToolUse hook, not ClaudeAgentOptions.can_use_tool -- an
        empirical probe (spikes/m4-tools/probe_can_use_tool.py) found
        can_use_tool does not reliably fire, while a PreToolUse hook does
        (spikes/m4-tools/probe_pretooluse_hook.py). See design.md D3.

        Returns {} to let the call fall through to normal evaluation (SAFE
        tools, or an approved DESTRUCTIVE call), or a deny hookSpecificOutput
        for a refused DESTRUCTIVE call. There is no corresponding "force
        allow" -- a hook 'allow' decision does not skip later evaluation
        steps (confirmed via SDK docs), so SAFE tools are left to
        allowed_tools / default evaluation instead of being explicitly
        allowed here.
        """
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        if self._gate.classify(tool_name) is Classification.SAFE:
            return {}

        try:
            # D10: the blocking CLI prompt runs off the event-loop thread so
            # it doesn't stall the SDK's async control-request handling.
            approved = await anyio.to_thread.run_sync(
                self._gate.request_approval, tool_name, tool_input
            )
        except Exception as exc:
            # The approval step itself failed (e.g. a custom approval_fn
            # raised, or stdin was closed for the default CLI prompt). Fails
            # closed -- deny rather than let the exception propagate out of
            # the hook (mirrors ToolRegistry.execute()'s equivalent guard on
            # the KIND-A side; dryrun-code-1 finding B2).
            logger.error("[GATE_HOOK_APPROVAL_ERROR] %s", exc)
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"approval check failed: {exc}",
                }
            }

        if approved:
            return {}

        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "denied by user",
            }
        }

    # ------------------------------------------------------------------
    # ReasonPort
    # ------------------------------------------------------------------

    def reason(self, context: str) -> Intent:
        """Tool-less query -> parse JSON intent -> return Intent (§7.2).

        On parse failure: logs [INTENT_PARSE_FAILURE] and retries once with a
        correction notice. On retry failure: logs [INTENT_FALLBACK] and returns
        RespondIntent(text='[FALLBACK_RESPOND] {raw}').
        """
        options = ClaudeAgentOptions(
            tools=[]
        )  # tools=[] sends --tools "" to CLI (truly tool-less)
        raw_text = self._run_query(context, options)

        intent, error = _parse_intent(raw_text)
        if intent is not None:
            return intent

        # Parse failure — log and retry once
        logger.warning(
            "[INTENT_PARSE_FAILURE] failed to parse intent JSON. error=%s raw=%r",
            error,
            raw_text,
        )
        retry_context = (
            context + "\n\nYour previous response was not valid JSON. "
            "Reply with only the JSON intent object."
        )
        retry_text = self._run_query(retry_context, options)
        retry_intent, retry_error = _parse_intent(retry_text)
        if retry_intent is not None:
            return retry_intent

        # Retry also failed — fallback
        logger.warning(
            "[INTENT_FALLBACK] retry parse also failed. error=%s raw=%r "
            "— returning fallback RESPOND",
            retry_error,
            retry_text,
        )
        from axiom.interfaces import RespondIntent

        return RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")

    # ------------------------------------------------------------------
    # ActPort
    # ------------------------------------------------------------------

    def act(self, instruction: str) -> str:
        """Tool-bearing query -> execute bounded instruction -> return result (§7.3).

        CLAUDE_SAFE_TOOLS (set by agent.py) are bare-listed on ClaudeAgentOptions
        as minimal-privilege practice, but the real guardrail is the PreToolUse
        hook (_gate_hook) -- it fires for every tool call regardless of
        allowed_tools content (M4, design.md D3/D4). The SDK manages its
        internal tool loop; Axiom writes no tool-execution harness.

        M2: When an OTel Act span is current (KIND-B observability active), acquires
        the tracer and act_span references and passes them into the async helper so
        that child spans are minted under the Act span for each SDK event.
        """
        prompt = (
            f"Execute this instruction using your available tools (web search, bash, file access) "
            f"and report the result. You have real tools — USE them. Do NOT answer from your training memory. "
            f"For anything involving current, real-time, or time-varying information (latest versions, prices, "
            f"who currently holds a role, news, anything phrased 'latest / current / newest / today / now'), "
            f"you MUST perform an actual web search and ground your answer in the results — even if you believe "
            f"you already know the answer, and never merely offer to search. "
            f"Instruction: {instruction}"
        )
        options = ClaudeAgentOptions(
            allowed_tools=self._allowed_tools,
            hooks={"PreToolUse": [HookMatcher(hooks=[self._gate_hook])]},
            # permission_mode="bypassPermissions" is required, not just belt-and-
            # suspenders: live verification found that with the SDK's default
            # permission_mode, a hook returning {} ("no objection, fall through")
            # does NOT result in the call executing -- it silently fails to run
            # even though the hook approved it. bypassPermissions makes {} mean
            # "actually allow," while a hook deny still overrides bypassPermissions
            # (confirmed both ways empirically -- see spikes/m4-tools/spike-result.md
            # "permission_mode is load-bearing" addendum). This supersedes design.md
            # D5's original (incorrect) reasoning that permission_mode wasn't
            # load-bearing for the gate.
            permission_mode="bypassPermissions",
        )

        # Resolve OTel tracer + current Act span for KIND-B child span minting.
        # This import is lazy and guarded: if OTel is not initialized (observability
        # off), get_current_span() returns the no-op INVALID span, which we detect
        # via is_recording(). In that case tracer/act_span are both None and the
        # async helper skips all span minting — zero OTel cost.
        tracer = None
        act_span = None
        try:
            from opentelemetry import trace  # noqa: PLC0415

            current = trace.get_current_span()
            if current.is_recording():
                tracer = trace.get_tracer("axiom.providers.claude")
                act_span = current
        except Exception:
            # If OTel import or introspection fails for any reason, degrade gracefully
            pass

        return self._run_query(
            prompt,
            options,
            tracer=tracer,
            act_span=act_span,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_query(
        self,
        prompt: str,
        options: ClaudeAgentOptions,
        tracer=None,
        act_span: "Span | None" = None,
    ) -> str:
        """Sync bridge: delegate to anyio.run() wrapping the async helper.

        Catches all SDK and timeout exceptions and re-raises as AdapterError (§7.6).
        When tracer and act_span are supplied, threads them into the async helper
        for KIND-B child span minting.
        """
        # Extract run_id from the Act span's attributes so child spans carry the
        # same axiom.run_id as their parent (set by record_phase in loop.py).
        run_id: str | None = None
        if act_span is not None:
            attrs = getattr(act_span, "attributes", None) or {}
            run_id = attrs.get("axiom.run_id")

        try:
            return anyio.run(
                _collect_query_result,
                prompt,
                options,
                tracer,
                run_id,
                "KIND_B",
                act_span,
            )
        except CLINotFoundError as e:
            logger.error("[ADAPTER_CLI_NOT_FOUND] %s", e)
            raise AdapterError(
                "claude-code CLI not found: install and authenticate first"
            ) from e
        except CLIConnectionError as e:
            logger.error("[ADAPTER_CLI_AUTH_FAIL] %s", e)
            raise AdapterError(
                "claude-code CLI connection failed: check authentication"
            ) from e
        except ProcessError as e:
            exit_code = getattr(e, "exit_code", "?")
            logger.error("[ADAPTER_PROCESS_ERROR] exit_code=%s %s", exit_code, e)
            raise AdapterError(f"subprocess error (exit {exit_code}): {e}") from e
        except CLIJSONDecodeError as e:
            logger.error("[ADAPTER_JSON_ERROR] %s", e)
            raise AdapterError(f"JSON decode error from subprocess: {e}") from e
        except ClaudeSDKError as e:
            logger.error("[ADAPTER_SDK_ERROR] %s", e)
            raise AdapterError(str(e)) from e
        except TimeoutError as e:
            logger.error(
                "[ADAPTER_TIMEOUT] query timed out after %ds", PER_QUERY_TIMEOUT_SECS
            )
            raise AdapterError(
                f"query timed out after {PER_QUERY_TIMEOUT_SECS}s"
            ) from e
        except Exception as e:
            if isinstance(e, AdapterError):
                raise
            logger.error("[ADAPTER_UNEXPECTED] %s", e)
            raise AdapterError(f"unexpected error: {e}") from e
