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
"""

from __future__ import annotations

import logging

import anyio
from claude_agent_sdk import (
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ClaudeAgentOptions,
    ClaudeSDKError,
    ProcessError,
    ResultMessage,
    query as sdk_query,
)

from axiom.interfaces import (
    AdapterError,
    Intent,
)
from axiom.providers.base import PraoAdapterBase, _parse_intent

logger = logging.getLogger("axiom.providers")

PER_QUERY_TIMEOUT_SECS: int = 120  # 2 minutes; CLI process can hang if unauthenticated


# ---------------------------------------------------------------------------
# Async helper (module-level so anyio.run() can accept it as a callable)
# ---------------------------------------------------------------------------


async def _collect_query_result(prompt: str, options: ClaudeAgentOptions) -> str:
    """Async helper: run one sdk_query() call and collect the ResultMessage text.

    query() is an async generator function (confirmed via inspect.isasyncgenfunction).
    Iterate directly — no 'await' before sdk_query().
    Wraps iteration in anyio.fail_after() for the per-query timeout.
    Explicitly closes the generator in a finally block for deterministic cleanup
    (prevents lingering subprocess on the is_error and timeout exit paths).
    ResultMessage is terminal — no break on the success path; the generator
    exhausts naturally, making aclose() a no-op on that path.
    """
    result_text = ""
    gen = sdk_query(prompt=prompt, options=options)
    try:
        with anyio.fail_after(PER_QUERY_TIMEOUT_SECS):
            async for message in gen:
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


# ---------------------------------------------------------------------------
# ClaudeAdapter
# ---------------------------------------------------------------------------


class ClaudeAdapter(PraoAdapterBase):
    """Concrete adapter implementing all four PRAO port Protocols via claude_agent_sdk.

    perceive() and observe() are inherited from PraoAdapterBase.
    reason() and act() are implemented here using the Claude SDK.
    """

    def __init__(self, persona: str, allowed_tools: list[str]) -> None:
        super().__init__(persona=persona)
        self._allowed_tools = allowed_tools

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

        M1_ALLOWED_TOOLS (set by agent.py) are scoped here via ClaudeAgentOptions.
        The SDK manages its internal tool loop; Axiom writes no tool-execution harness.
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
        options = ClaudeAgentOptions(allowed_tools=self._allowed_tools)
        return self._run_query(prompt, options)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_query(self, prompt: str, options: ClaudeAgentOptions) -> str:
        """Sync bridge: delegate to anyio.run() wrapping the async helper.

        Catches all SDK and timeout exceptions and re-raises as AdapterError (§7.6).
        """
        try:
            return anyio.run(_collect_query_result, prompt, options)
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
