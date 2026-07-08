"""
Claude adapter — implements all four PRAO port Protocols via claude_agent_sdk.

Bridges synchronous port contracts to the async SDK via anyio.run() per call.
All port methods are synchronous (def, not async def); async is contained here.

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

import json
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
    ActIntent,
    AdapterError,
    FinishIntent,
    Intent,
    RespondIntent,
    RunState,
)

logger = logging.getLogger("axiom.providers")

PER_QUERY_TIMEOUT_SECS: int = 120  # 2 minutes; CLI process can hang if unauthenticated

# ---------------------------------------------------------------------------
# Intent format instructions — injected verbatim into every reason() prompt
# (§4.1 wire format)
# ---------------------------------------------------------------------------
_INTENT_FORMAT_INSTRUCTIONS = """\
---
RESPONSE FORMAT INSTRUCTIONS (mandatory):
Reply with EXACTLY ONE JSON object on a single line. No markdown. No code fences.
No explanation before or after. Only the JSON object.

Choose ONE of:
  {"intent": "RESPOND", "text": "<your response to the user>"}
  {"intent": "ACT", "instruction": "<one bounded instruction for the executor>"}
  {"intent": "FINISH"}

Rules:
- "intent" must be exactly "RESPOND", "ACT", or "FINISH" (case-sensitive).
- "RESPOND" requires a "text" field (string). Use ONLY for requests answerable from
  the conversation context or established general knowledge — no tools needed.
- "ACT" requires an "instruction" field (string). You MUST use ACT (never RESPOND)
  whenever the request requires: web search, real-time or current data, file access,
  running commands, or any side effect. Do NOT attempt to answer such requests from
  memory or training data — you have zero tools; route to ACT so the executor can act.
- STALENESS RULE: Your training knowledge may be months or years out of date. For ANY
  fact that changes over time — software/library versions, prices, who currently holds
  a role or record, news, standings, or anything phrased "latest / current / newest /
  today / now / as of" — assume your stored answer is OUTDATED and route to ACT, even
  if you feel certain. Do not answer time-varying questions from memory.
- TOOL-LESS-MEANS-DELEGATE: You (the reasoning step) have NO tools by design. This does
  not mean you cannot get live data — an executor with web search, bash, and file access
  runs whatever instruction you return in an ACT. NEVER refuse or answer directly because
  you "lack a tool"; instead route to ACT and the executor will use its tools.
- "FINISH" has no additional fields. Use it only when the task is fully complete with no response needed.
- The entire response must be parseable as a single JSON object.

Examples:
  User: "What's the capital of France?"
  → {"intent": "RESPOND", "text": "Paris."} (stable fact, no tool needed)

  User: "What's the latest stable Python version?"
  → {"intent": "ACT", "instruction": "Search the web for the latest stable Python release version."} (time-varying; stored version is likely stale)

  User: "What files are in this directory?"
  → {"intent": "ACT", "instruction": "List the files in the current directory."} (requires a tool)
---"""


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


class ClaudeAdapter:
    """Concrete adapter implementing all four PRAO port Protocols via claude_agent_sdk."""

    def __init__(self, persona: str, allowed_tools: list[str]) -> None:
        self._persona = persona
        self._allowed_tools = allowed_tools

    # ------------------------------------------------------------------
    # PerceivePort
    # ------------------------------------------------------------------

    def perceive(self, run_state: RunState) -> str:
        """Assemble the reasoning context prompt per §7.1."""
        sections: list[str] = []

        sections.append(f"[PERSONA]\n{self._persona}")

        if run_state.history:
            history_lines = [
                f"Step {i + 1}: {result}" for i, result in enumerate(run_state.history)
            ]
            sections.append("[CONVERSATION HISTORY]\n" + "\n".join(history_lines))

        sections.append(f"[CURRENT REQUEST]\n{run_state.user_input}")
        sections.append(_INTENT_FORMAT_INSTRUCTIONS)

        return "\n\n".join(sections)

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
    # ObservePort
    # ------------------------------------------------------------------

    def observe(self, result: str, run_state: RunState) -> RunState:
        """Capture act() result and update run-state (§7.4). Mutate-and-return."""
        run_state.history.append(result)
        run_state.cycle_count += 1
        return run_state

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


# ---------------------------------------------------------------------------
# Intent parse helper (module-level, used by reason() and retry path)
# ---------------------------------------------------------------------------


def _parse_intent(raw: str) -> tuple[Intent | None, str | None]:
    """Parse a raw model response string into an Intent dataclass.

    Implements the §4.1 parse rules (JSON envelope, strict field validation).

    Returns:
        (intent, None) on success.
        (None, error_message) on any parse or validation failure.
    """
    text = raw.strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, str(exc)

    if not isinstance(data, dict):
        return None, f"expected JSON object, got {type(data).__name__}"

    intent_str = data.get("intent")

    if intent_str == "RESPOND":
        t = data.get("text")
        if not isinstance(t, str):
            return None, f"RESPOND missing or invalid 'text' field: {data!r}"
        return RespondIntent(text=t), None

    if intent_str == "ACT":
        instr = data.get("instruction")
        if not isinstance(instr, str):
            return None, f"ACT missing or invalid 'instruction' field: {data!r}"
        return ActIntent(instruction=instr), None

    if intent_str == "FINISH":
        return FinishIntent(), None

    return None, f"unknown intent value: {intent_str!r}"
