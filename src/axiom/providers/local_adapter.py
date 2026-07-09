"""
Local adapter — implements all four PRAO port Protocols via LiteLLM + Ollama.

perceive() and observe() are inherited from PraoAdapterBase (providers/base.py).
reason() uses a tool-less LiteLLM completion call + shared _parse_intent().
act() runs a bounded tool-calling loop (harness built here; no SDK-internal loop).

Import boundary:
  axiom.interfaces, axiom.providers.base, litellm (deferred), json, subprocess,
  logging, stdlib — zero Claude SDK imports.

litellm is imported inside __init__ (deferred) so that Claude-only installs do
not pay the litellm import cost. See design §4.3 / O1.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Callable

from axiom.interfaces import (
    AdapterError,
    Intent,
    RespondIntent,
)
from axiom.providers.base import PraoAdapterBase, _parse_intent

logger = logging.getLogger("axiom.providers")

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

MAX_TOOL_ITERATIONS: int = 5  # default; overridable via constructor
PER_QUERY_TIMEOUT_SECS: int = 60  # local model; shorter than Claude's 120s
TOOL_COMMAND_TIMEOUT_SECS: int = 30  # per-command subprocess timeout

# ---------------------------------------------------------------------------
# Shell tool schema (OpenAI function-calling format, as expected by LiteLLM)
# ---------------------------------------------------------------------------

SHELL_TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "run_shell_command",
        "description": (
            "Execute a shell command on the local machine. "
            "Returns stdout and stderr. Use for file listing, "
            "directory exploration, and system commands."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute (e.g. 'ls -la /tmp')",
                },
            },
            "required": ["command"],
        },
    },
}


# ---------------------------------------------------------------------------
# Shell tool executor (module-level pure function; easy to unit-test)
# ---------------------------------------------------------------------------


def _execute_shell_tool(command: str) -> str:
    """Run a shell command and return combined stdout+stderr.

    Bounded by TOOL_COMMAND_TIMEOUT_SECS. On timeout or subprocess error,
    returns an error string rather than raising — the model receives the error
    as a tool result and can retry or adjust (per MLA-3 AC).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,  # nosec — accepted per design §5.2.1: dev-machine proof only, not production
            capture_output=True,
            text=True,
            timeout=TOOL_COMMAND_TIMEOUT_SECS,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code]: {result.returncode}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[error]: command timed out after {TOOL_COMMAND_TIMEOUT_SECS}s"
    except Exception as e:
        return f"[error]: {e}"


# ---------------------------------------------------------------------------
# LocalAdapter
# ---------------------------------------------------------------------------


class LocalAdapter(PraoAdapterBase):
    """Local adapter: reason() + act() via LiteLLM -> Ollama.

    perceive() and observe() are inherited from PraoAdapterBase.
    reason() queries the local model tool-lessly and parses the JSON intent.
    act() runs the bounded tool-calling harness (_run_tool_loop).

    litellm is imported in __init__ (deferred) and stored as self._litellm
    so that Claude-only installs never pay the import cost, and so that
    unit tests can replace self._litellm with a mock after construction.
    """

    def __init__(
        self,
        persona: str,
        model_name: str = "ollama_chat/qwen2.5:7b",
        ollama_api_base: str = "http://localhost:11434",
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        super().__init__(persona=persona)

        # Deferred import: pay litellm import cost only when LocalAdapter is used.
        # Unit tests replace self._litellm with a MagicMock after construction.
        try:
            import litellm as _litellm_mod  # noqa: PLC0415
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "LocalAdapter requires litellm — install with: pip install litellm"
            ) from exc

        self._litellm = _litellm_mod

        self._model_name = model_name
        self._ollama_api_base = ollama_api_base
        self._max_tool_iterations = max_tool_iterations

        # Tool registry: list of (schema_dict, executor_callable) tuples.
        # Schema dicts are in OpenAI function-calling format (LiteLLM standard).
        # Executor callables take the parsed args dict and return a result string.
        self._tools: list[tuple[dict, Callable[[dict], str]]] = [
            (
                SHELL_TOOL_SCHEMA,
                lambda args: (
                    _execute_shell_tool(args["command"])
                    if "command" in args
                    else "[error]: tool call missing required 'command' argument"
                ),
            ),
        ]
        self._tool_schemas: list[dict] = [t[0] for t in self._tools]
        self._tool_executors: dict[str, Callable[[dict], str]] = {
            t[0]["function"]["name"]: t[1] for t in self._tools
        }

    # ------------------------------------------------------------------
    # ReasonPort
    # ------------------------------------------------------------------

    def reason(self, context: str) -> Intent:
        """Tool-less query to local model -> parse JSON intent -> return Intent.

        Uses the same JSON wire format as M1 §4.1 (injected by perceive()).
        Same parse-retry + fallback strategy as ClaudeAdapter §7.2.
        Enhanced _parse_intent pre-processing handles code-fence-wrapped JSON.
        """
        raw_text = self._query_model(context, tools=[])

        intent, error = _parse_intent(raw_text)
        if intent is not None:
            return intent

        # Parse failure — log and retry once (same strategy as M1 §7.2)
        logger.warning(
            "[INTENT_PARSE_FAILURE] local model failed to produce valid intent JSON. "
            "error=%s raw=%r",
            error,
            raw_text,
        )
        retry_context = (
            context + "\n\nYour previous response was not valid JSON. "
            "Reply with only the JSON intent object."
        )
        retry_text = self._query_model(retry_context, tools=[])
        retry_intent, retry_error = _parse_intent(retry_text)
        if retry_intent is not None:
            return retry_intent

        # Retry also failed — fallback
        logger.warning(
            "[INTENT_FALLBACK] local model retry parse also failed. error=%s raw=%r "
            "— returning fallback RESPOND",
            retry_error,
            retry_text,
        )
        return RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")

    # ------------------------------------------------------------------
    # ActPort
    # ------------------------------------------------------------------

    def act(self, instruction: str) -> str:
        """Execute a bounded instruction using the local model + tool harness.

        Delegates to _run_tool_loop which handles the full tool-calling cycle:
        model proposes tool calls -> harness executes -> results fed back -> repeat
        until model produces a final text answer or MAX_TOOL_ITERATIONS is reached.
        """
        return self._run_tool_loop(instruction)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_model(
        self,
        prompt: str,
        tools: list[dict] | None = None,
    ) -> str:
        """Call the local model via LiteLLM (synchronous). Returns the model's text.

        Args:
            prompt: The full prompt string (user role).
            tools: Tool schemas in OpenAI format (or None/[] for tool-less queries).

        Returns:
            The model's text response content.

        Raises:
            AdapterError: On any model call failure (Ollama down, timeout, etc.).
        """
        messages = [{"role": "user", "content": prompt}]
        kwargs: dict = {
            "model": self._model_name,
            "messages": messages,
            "timeout": PER_QUERY_TIMEOUT_SECS,
            "api_base": self._ollama_api_base,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self._litellm.completion(**kwargs)
            message = response.choices[0].message
            return message.content or ""
        except Exception as e:
            logger.error("[LOCAL_ADAPTER_ERROR] %s", e)
            raise AdapterError(f"local model error: {e}") from e

    def _run_tool_loop(self, instruction: str) -> str:
        """Execute the bounded tool-calling loop for act().

        Flow:
          1. Send instruction + tool schemas to model.
          2. If model response contains tool_calls -> execute each, collect results.
          3. Feed tool results back to model as tool-role messages.
          4. Repeat until model produces a text response (no tool_calls) or
             MAX_TOOL_ITERATIONS is reached.
          5. Return the final text response.

        Error handling per MLA-3 AC:
          - Malformed tool args (JSON decode error): error string fed back, skip execution.
          - Executor exception: error string fed back, never raised out of act().
          - Unknown tool name: error string fed back.
          - Iteration exhaustion: scan backwards for last assistant text or return
            explicit exhaustion summary (NOT an AdapterError).
        """
        messages: list[dict] = [
            {
                "role": "user",
                "content": (
                    f"Execute this instruction using your available tools and report the result. "
                    f"You have real tools — USE them. Do NOT answer from memory. "
                    f"Instruction: {instruction}"
                ),
            }
        ]

        for iteration in range(self._max_tool_iterations):
            try:
                response = self._litellm.completion(
                    model=self._model_name,
                    messages=messages,
                    tools=self._tool_schemas,
                    tool_choice="auto",
                    timeout=PER_QUERY_TIMEOUT_SECS,
                    api_base=self._ollama_api_base,
                )
            except Exception as e:
                logger.error(
                    "[LOCAL_ADAPTER_TOOL_LOOP_ERROR] iteration=%d %s", iteration, e
                )
                raise AdapterError(f"local model error during tool loop: {e}") from e

            message = response.choices[0].message

            # Case 1: Model produced a final text answer (no tool calls).
            # Returning "" when content is None is intentional — the caller
            # (PraoLoop via act()) treats an empty-string result as a
            # completed (though vacuous) act step; no crash. (W3 accepted)
            if not message.tool_calls:
                return message.content or ""

            # Case 2: Model proposed tool calls — execute them.
            # Append the assistant's tool-call message to conversation history.
            # model_dump() on LiteLLM's Pydantic response message produces a dict
            # compatible with subsequent litellm.completion() messages list.
            messages.append(message.model_dump())

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                try:
                    fn_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    # Malformed args — do NOT call executor. Feed error back.
                    tool_result = "[error]: could not parse tool arguments"
                    logger.warning(
                        "[LOCAL_ADAPTER_TOOL_ARGS_PARSE_FAIL] tool=%s raw=%r",
                        fn_name,
                        tool_call.function.arguments,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        }
                    )
                    continue

                executor = self._tool_executors.get(fn_name)
                if executor is not None:
                    try:
                        tool_result = executor(fn_args)
                    except Exception as exec_err:
                        # Any executor exception is converted to an error string.
                        # Consistent with MLA-3 AC: errors fed back, never raised.
                        tool_result = f"[error]: tool execution failed: {exec_err}"
                        logger.warning(
                            "[LOCAL_ADAPTER_TOOL_EXEC_ERROR] tool=%s error=%s",
                            fn_name,
                            exec_err,
                        )
                else:
                    tool_result = f"[error]: unknown tool '{fn_name}'"
                    logger.warning("[LOCAL_ADAPTER_UNKNOWN_TOOL] %s", fn_name)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

            logger.debug(
                "[LOCAL_ADAPTER_TOOL_ITERATION] iteration=%d tool_calls=%d",
                iteration,
                len(message.tool_calls),
            )

        # MAX_TOOL_ITERATIONS reached — return best partial result.
        # At exhaustion, messages[-1] is a tool-result (role: "tool"), NOT model text.
        # Scan backwards for the last assistant-role message's text content.
        logger.warning(
            "[LOCAL_ADAPTER_MAX_TOOL_ITERATIONS] reached %d iterations without final answer",
            self._max_tool_iterations,
        )
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                text = msg.get("content") or ""
                if text.strip():
                    return text
        # No assistant text found at all — return explicit exhaustion summary
        return f"[tool loop exhausted after {self._max_tool_iterations} iterations]"
