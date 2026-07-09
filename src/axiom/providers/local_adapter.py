"""
Local adapter — implements all four PRAO port Protocols via smolagents + Ollama.

perceive() and observe() are inherited from PraoAdapterBase (providers/base.py).
reason() uses a tool-less smolagents LiteLLMModel call + shared _parse_intent().
act() creates a fresh smolagents CodeAgent per call and delegates to CodeAgent.run().

Import boundary:
  axiom.interfaces, axiom.providers.base, smolagents (deferred — imported inside
  __init__, not at module top-level), logging, stdlib.
  NO litellm direct import. NO subprocess import at module level.

smolagents is imported inside __init__ (deferred) so that Claude-only installs do
not pay the smolagents import cost. See design §4.1 / §11.
"""

from __future__ import annotations

import logging

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

PER_QUERY_TIMEOUT_SECS: int = 60  # local model; shorter than Claude's 120s


# ---------------------------------------------------------------------------
# LocalAdapter
# ---------------------------------------------------------------------------


class LocalAdapter(PraoAdapterBase):
    """Local adapter: reason() + act() via smolagents LiteLLMModel + CodeAgent.

    perceive() and observe() are inherited from PraoAdapterBase.
    reason() queries the local model tool-lessly and parses the JSON intent.
    act() creates a fresh CodeAgent per call and delegates to CodeAgent.run()
    (KIND-B delegation -- smolagents owns its internal multi-step loop).

    smolagents is imported in __init__ (deferred) so that Claude-only installs
    never pay the import cost.
    """

    def __init__(
        self,
        persona: str,
        model_id: str = "ollama_chat/qwen2.5:7b",
        ollama_api_base: str = "http://localhost:11434",
        max_steps: int = 5,
        additional_authorized_imports: list[str] | None = None,
    ) -> None:
        super().__init__(persona=persona)

        # Deferred import: pay smolagents import cost only when LocalAdapter is used.
        try:
            from smolagents import CodeAgent, LiteLLMModel  # noqa: PLC0415
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "LocalAdapter requires smolagents -- install with: pip install smolagents"
            ) from exc

        self._model = LiteLLMModel(
            model_id=model_id,
            api_base=ollama_api_base,
        )

        authorized_imports = additional_authorized_imports or [
            "math",
            "statistics",
            "datetime",
            "json",
            "re",
            "subprocess",  # required: E2E #3 writes hello.py to disk + executes it (W3)
        ]

        # Store CodeAgent config -- CodeAgent is created FRESH per act() call (W2 resolution).
        # No self._agent here: instantiating once and reusing across act() calls risks
        # cross-call state leakage if CodeAgent accumulates history between runs.
        # act() creates a new CodeAgent from these stored params before each delegation.
        self._max_steps = max_steps
        self._authorized_imports = authorized_imports

        # Stored for test introspection and error messages
        self._model_id = model_id
        self._ollama_api_base = ollama_api_base

    # ------------------------------------------------------------------
    # ReasonPort
    # ------------------------------------------------------------------

    def reason(self, context: str) -> Intent:
        """Tool-less query to local model -> parse JSON intent -> return Intent.

        Uses the same JSON wire format as M1 §4.1 (injected by perceive()).
        Same parse-retry + fallback strategy as ClaudeAdapter §7.2.
        Enhanced _parse_intent pre-processing handles code-fence-wrapped JSON.

        Defect-A fix — post-act RESPOND forcing:
        When the context already contains [TOOL EXECUTION RESULTS] (i.e. at least one
        act() cycle has completed and its result is in run_state.history), local weak
        models (qwen2.5:7b) frequently re-issue ACT despite perceive()'s RESPOND-nudge.
        This is because the KIND-B CodeAgent already ran the ENTIRE delegated task
        internally — one act() call = one complete multi-step tool loop with a final
        answer. Re-issuing ACT would duplicate that work and stall the loop.

        Fix: prepend a LOCAL-ADAPTER-ONLY system framing block ahead of the perceive()
        context when history is present. This block explicitly tells the model that the
        executor has ALREADY COMPLETED the task and that the ONLY valid response is a
        RESPOND intent containing the result. The block is prepended (not appended) so
        it appears before the lengthy tool-output section and is seen first.

        Design constraint: this sentinel check uses the literal substring
        '[TOOL EXECUTION RESULTS' which is the label produced by PraoAdapterBase.perceive()
        — it does NOT parse run_state directly (reason() only receives the assembled
        context string). The sentinel is stable: it is the only place this label is
        produced (providers/base.py perceive()). Any perceive() output that contains this
        label guarantees at least one act() result is in history.
        """
        # Defect-A: detect post-act context (history present) and prepend a strong
        # RESPOND-forcing framing block for qwen2.5:7b.
        _POST_ACT_SENTINEL = "[TOOL EXECUTION RESULTS"
        if _POST_ACT_SENTINEL in context:
            # Extract the act result(s) from the context for an explicit summary.
            # The perceive() format is:
            #   [TOOL EXECUTION RESULTS — read these carefully]
            #   Step 1: <result>
            #   ...
            #   [NOTE: ...]
            # We reproduce it verbatim in the framing — no re-parsing needed.
            framing = (
                "SYSTEM INSTRUCTION (highest priority — read before anything else):\n"
                "The executor has ALREADY completed the delegated task. The tool "
                "execution results shown below are the REAL, FINAL output of that "
                "execution. Your ONLY valid response is:\n"
                '  {"intent": "RESPOND", "text": "<surface the result to the user>"}\n'
                "Do NOT issue another ACT. The task is done. Surface the result now.\n"
                "---\n\n"
            )
            augmented_context = framing + context
        else:
            augmented_context = context

        raw_text = self._query_model(augmented_context)

        intent, error = _parse_intent(raw_text)
        if intent is not None:
            return intent

        # Parse failure -- log and retry once (same strategy as M1 §7.2)
        logger.warning(
            "[INTENT_PARSE_FAILURE] local model failed to produce valid intent JSON. "
            "error=%s raw=%r",
            error,
            raw_text,
        )
        # Retry uses augmented_context (which already includes the post-act framing
        # block when history is present) so the RESPOND-forcing instruction is retained.
        retry_context = (
            augmented_context + "\n\nYour previous response was not valid JSON. "
            "Reply with only the JSON intent object."
        )
        retry_text = self._query_model(retry_context)
        retry_intent, retry_error = _parse_intent(retry_text)
        if retry_intent is not None:
            return retry_intent

        # Retry also failed -- fallback
        logger.warning(
            "[INTENT_FALLBACK] local model retry parse also failed. error=%s raw=%r "
            "-- returning fallback RESPOND",
            retry_error,
            retry_text,
        )
        return RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")

    # ------------------------------------------------------------------
    # ActPort
    # ------------------------------------------------------------------

    def act(self, instruction: str) -> str:
        """Execute a bounded instruction via smolagents CodeAgent.

        Creates a FRESH CodeAgent per call (W2 -- safe default: no cross-call
        state leakage). The CodeAgent owns its internal multi-step loop
        (KIND-B delegation): generates Python code -> executes via tools ->
        observes -> iterates until done or max_steps reached. Returns the
        final result string.
        """
        from smolagents import CodeAgent, LocalPythonExecutor  # noqa: PLC0415 -- Python import cache: free after first __init__ load

        # G2: CodeAgent constructor is inside the try/except so that construction
        # failures are also wrapped in AdapterError, not raw exceptions.
        try:
            # smolagents 1.26.0: open() is not in BASE_PYTHON_TOOLS and the sandbox
            # blocks it as an unnamed builtin. Inject it explicitly via additional_functions
            # so the CodeAgent's generated code can write real files to disk (E2E #3 / W3).
            import builtins  # noqa: PLC0415

            executor = LocalPythonExecutor(
                additional_authorized_imports=self._authorized_imports,
                additional_functions={"open": builtins.open},
            )
            agent = CodeAgent(
                model=self._model,
                tools=[],
                add_base_tools=True,
                max_steps=self._max_steps,
                executor=executor,
                verbosity_level=0,  # Defect-B: suppress rich console logging;
                # prevents UnicodeEncodeError on Windows (cp1252) when smolagents/rich
                # tries to print emoji-containing DuckDuckGo search results.
                # No custom system_prompt: relies on smolagents' built-in default (O2).
            )
            result = agent.run(instruction)
            return str(result)
        except Exception as e:
            logger.error("[LOCAL_ADAPTER_ACT_ERROR] %s", e)
            raise AdapterError(f"CodeAgent execution error: {e}") from e

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_model(self, prompt: str) -> str:
        """Call the local model via smolagents LiteLLMModel for a tool-less completion.

        Returns the model's text response. Raises AdapterError on failure.

        VERIFIED (Step 0): smolagents 1.26.0 confirms:
          - LiteLLMModel.__call__ delegates to LiteLLMModel.generate().
          - generate(messages, stop_sequences=None, **kwargs) -> ChatMessage.
          - **kwargs are forwarded to litellm.completion(), so timeout= is honoured (G1).
          - Raw dicts {"role": ..., "content": ...} are accepted alongside ChatMessage objects.
          - The returned ChatMessage has a .content attribute containing the text response.

        G1 -- timeout: PER_QUERY_TIMEOUT_SECS is passed as timeout= to self._model() so
          litellm.completion() enforces a 60 s wall-clock limit on the LiteLLMModel call.
          CodeAgent.run() in act() does NOT have a wall-clock timeout parameter; its
          internal loop is bounded by max_steps instead (design SS4.4).

        W2 -- hasattr guard: restored per design SS4.3. .content is verified present on
          ChatMessage (Step 0), but the guard future-proofs against smolagents API changes.
          None content returns "" so _parse_intent receives a string (fallback path).
        """
        # smolagents 1.26.0: LiteLLMModel sets flatten_messages_as_text=True for
        # ollama/* models. get_clean_message_list then calls content[0]["text"],
        # which fails if content is a plain string. Content must be a list of
        # {"type": "text", "text": ...} dicts so the flatten path works correctly.
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        try:
            response = self._model(
                messages,
                stop_sequences=None,
                timeout=PER_QUERY_TIMEOUT_SECS,  # G1: enforce per-query timeout.
            )
            # W2: defensive hasattr guard + None-content -> "" for _parse_intent safety.
            if not hasattr(response, "content"):
                return str(response)
            return response.content if response.content is not None else ""
        except Exception as e:
            # W1: differentiated log tags per design SS4.5 error table.
            exc_name = type(e).__name__
            exc_msg = str(e).lower()
            if "Connection" in exc_name or "ServiceUnavailable" in exc_name:
                tag = "[LOCAL_ADAPTER_OLLAMA_DOWN]"
                msg = f"Ollama not reachable at {self._ollama_api_base}: {e}"
            elif "NotFound" in exc_name or "404" in exc_msg:
                tag = "[LOCAL_ADAPTER_MODEL_NOT_FOUND]"
                msg = f"model {self._model_id} not found in Ollama: {e}"
            elif "Timeout" in exc_name or "timeout" in exc_msg:
                tag = "[LOCAL_ADAPTER_TIMEOUT]"
                msg = f"local model timeout after {PER_QUERY_TIMEOUT_SECS}s: {e}"
            else:
                tag = "[LOCAL_ADAPTER_UNEXPECTED]"
                msg = f"local model error: {e}"
            logger.error("%s %s", tag, e)
            raise AdapterError(msg) from e
