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
from pathlib import Path
from typing import Callable

from axiom.interfaces import (
    AdapterError,
    Intent,
    RespondIntent,
)
from axiom.providers.base import PraoAdapterBase, _parse_intent
from axiom.tools.guardrails import GuardrailsGate
from axiom.tools.port import ToolResult
from axiom.tools.registry import ToolRegistry

logger = logging.getLogger("axiom.providers")

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

PER_QUERY_TIMEOUT_SECS: int = 60  # local model; shorter than Claude's 120s

# gen_ai.system constant for all KIND-A local (Ollama) spans.
# OTel GenAI semconv does not formally define "ollama" as a registered provider string
# (only "anthropic", "openai", etc. are registered), but "ollama" is the conventional
# value used by OTel GenAI instrumentation for Ollama-backed models — consistent with
# the litellm "ollama_chat/" prefix and smolagents' provider naming.
_GEN_AI_SYSTEM_LOCAL: str = "ollama"


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

    control_level: str = (
        "KIND_A"  # M6 RT-7: our loop can inspect and veto each action step
    )

    def __init__(
        self,
        persona: str,
        working_dir: Path,
        gate: GuardrailsGate,
        model_id: str = "ollama_chat/qwen2.5:7b",
        ollama_api_base: str = "http://localhost:11434",
        max_steps: int = 5,
        additional_authorized_imports: list[str] | None = None,
        on_result: Callable[[str, ToolResult], None] | None = None,
    ) -> None:
        super().__init__(persona=persona)

        # M4: working_dir/gate are required (no defaults) -- a default here
        # would silently construct an unscoped/ungated ToolRegistry, exactly
        # the "silent auto-approve" failure mode M4 exists to remove
        # (design.md D6, D11).
        self._working_dir = working_dir
        self._gate = gate
        # M10 (design.md D13): on_result threaded straight through to
        # ToolRegistry -- LocalAdapter has no logic of its own here, it's
        # purely a passthrough from Agent's constructor.
        self._registry = ToolRegistry(
            working_dir=working_dir, gate=gate, on_result=on_result
        )

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
            # M4: "subprocess" removed (design.md AC-05.4). The only sanctioned
            # way to run a shell command is now the gated RunShellTool -- raw
            # Python subprocess access was the unscoped escape hatch M4 closes
            # (design.md Purpose, D6). Writing/executing files (formerly E2E
            # #3's reason for needing "subprocess") now goes through
            # WriteFileTool + RunShellTool instead.
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

        M5 live-verification fix — skill-reactivation-loop forcing:
        Live-CLI verification on --provider local (SK-7) found qwen-class local models
        will repeatedly re-emit USE_SKILL for a skill that is already active — 10
        consecutive USE_SKILL cycles observed for the same skill name in one run,
        exhausting MAX_CYCLES without ever reaching ACT or RESPOND. FakeAdapter-based
        unit tests (test_contracts.py) could not surface this: they script intents
        directly rather than exercising an actual model's reasoning, so the dedup
        check (design.md D6a) working correctly at the RunState level says nothing
        about whether a real weak model actually stops requesting the skill again.
        Same root cause and same fix shape as Defect-A: a plain informational
        "[SKILL ALREADY ACTIVE]" note is not forceful enough for this model class.
        """
        # Defect-A: detect post-act context (history present) and prepend a strong
        # RESPOND-forcing framing block for qwen2.5:7b.
        #
        # M5 / dryrun-code-1 B2: history (and therefore this sentinel) never
        # clears once populated -- so without the second check below, this
        # would still hard-force RESPOND on the cycle immediately after a
        # skill activation that happens to follow an earlier ACT in the same
        # run, silently re-triggering the exact failure class
        # dryrun-design-1's C3 fixed (Conductor pushed to respond instead of
        # using the skill it just activated) via this LocalAdapter-only code
        # path. [SKILL ACTIVATION] is one-shot (design.md D5a) -- its
        # presence means "something new just happened that the Conductor
        # should act on," so the forcing is suppressed for that one cycle.
        _POST_ACT_SENTINEL = "[TOOL EXECUTION RESULTS"
        _SKILL_ACTIVATION_SENTINEL = "[SKILL ACTIVATION]"
        _SKILL_ALREADY_ACTIVE_SENTINEL = "[SKILL ALREADY ACTIVE]"

        framings: list[str] = []

        if _SKILL_ALREADY_ACTIVE_SENTINEL in context:
            # Live-verification fix (see docstring): stop the re-activation loop.
            # [SKILL ALREADY ACTIVE] always appears inside a [SKILL ACTIVATION]
            # section, so the Defect-A post-act block below is naturally
            # suppressed too (its own _SKILL_ACTIVATION_SENTINEL check) --
            # deliberately not stacked: post-act's "your ONLY valid response is
            # RESPOND" would contradict this block's "choose ACT or RESPOND."
            framings.append(
                "SYSTEM INSTRUCTION (highest priority — read before anything else):\n"
                "You already activated this skill — its full instructions are shown "
                "above under [ACTIVE SKILL: ...]. Do NOT emit another USE_SKILL for "
                "the same skill. Use its instructions now: choose ACT if you still "
                "need more information, or RESPOND if you can already answer.\n"
                "---\n\n"
            )

        if _POST_ACT_SENTINEL in context and _SKILL_ACTIVATION_SENTINEL not in context:
            # Extract the act result(s) from the context for an explicit summary.
            # The perceive() format is:
            #   [TOOL EXECUTION RESULTS — read these carefully]
            #   Step 1: <result>
            #   ...
            #   [NOTE: ...]
            # We reproduce it verbatim in the framing — no re-parsing needed.
            framings.append(
                "SYSTEM INSTRUCTION (highest priority — read before anything else):\n"
                "The executor has ALREADY completed the delegated task. The tool "
                "execution results shown below are the REAL, FINAL output of that "
                "execution. Your ONLY valid response is:\n"
                '  {"intent": "RESPOND", "text": "<surface the result to the user>"}\n'
                "Do NOT issue another ACT. The task is done. Surface the result now.\n"
                "---\n\n"
            )

        augmented_context = "".join(framings) + context

        raw_text, input_tokens, output_tokens = self._query_model(augmented_context)
        # M2: populate gen_ai attrs after model call; tokens from ChatMessage.token_usage.
        self._enrich_current_span_gen_ai(
            input_tokens=input_tokens, output_tokens=output_tokens
        )

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
        retry_text, _, _ = self._query_model(retry_context)
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
        from smolagents import CodeAgent, DuckDuckGoSearchTool, LocalPythonExecutor  # noqa: PLC0415 -- Python import cache: free after first __init__ load

        from axiom.tools.smolagents_tools import (  # noqa: PLC0415 -- lazy, matches smolagents-deferred rule
            ListDirTool,
            ReadFileTool,
            RunShellTool,
            WriteFileTool,
        )

        # G2: CodeAgent constructor is inside the try/except so that construction
        # failures are also wrapped in AdapterError, not raw exceptions.
        try:
            # M4: the raw `open` escape hatch is removed (design.md AC-04.4) --
            # file access now goes through the gated, working-dir-scoped
            # ReadFileTool/WriteFileTool below, not bare Python builtins.
            # Tool-set fix: pre-populate `re` in the executor namespace.
            # qwen2.5:7b routinely generates re.search(...) without writing `import re`
            # first. additional_authorized_imports only permits the import statement --
            # it does NOT pre-inject the module. Pre-populating via additional_functions
            # means `re` is in scope even when the model omits the import, eliminating
            # InterpreterError: The variable 're' is not defined.
            import re as _re  # noqa: PLC0415

            executor = LocalPythonExecutor(
                additional_authorized_imports=self._authorized_imports,
                additional_functions={"re": _re},
            )
            # Tool-set fix (tool-provisioning pass): explicit minimal tool list replaces
            # add_base_tools=True. Rationale:
            # (1) add_base_tools=True includes VisitWebpageTool which requires markdownify
            #     + requests (not installed) -> ImportError when qwen calls visit_webpage().
            # (2) add_base_tools=True includes PythonInterpreterTool which confuses qwen:
            #     it called python_interpreter('hello.py') treating it like a shell
            #     executor and got InterpreterError: 'python_interpreter' not allowed.
            #     In CodeAct, Python execution is the agent's own code block -- no
            #     PythonInterpreterTool needed; LocalPythonExecutor handles it natively.
            # (3) Fewer, clearer tools = less flailing for a weak model (qwen2.5:7b).
            # DuckDuckGoSearchTool is smolagents-provided (SAFE, ungated). The other
            # four are Axiom's own working-dir-scoped, gated tools (design.md §8) --
            # read_file/list_dir are SAFE; write_file/run_shell are DESTRUCTIVE and
            # route through self._gate on every call (design.md AC-04.5).
            agent = CodeAgent(
                model=self._model,
                tools=[
                    DuckDuckGoSearchTool(),
                    ReadFileTool(self._registry),
                    WriteFileTool(self._registry),
                    ListDirTool(self._registry),
                    RunShellTool(self._registry),
                ],
                max_steps=self._max_steps,
                executor=executor,
                verbosity_level=0,  # Defect-B: suppress rich console logging;
                # prevents UnicodeEncodeError on Windows (cp1252) when smolagents/rich
                # tries to print emoji-containing DuckDuckGo search results.
                # No custom system_prompt: relies on smolagents' built-in default (O2).
            )
            result = agent.run(instruction)
            # M2: populate gen_ai attrs after CodeAgent loop. Token counts are left null
            # here because smolagents CodeAgent's agent.run() does not expose an aggregate
            # token_usage on its return value — the multi-step loop makes N internal model
            # calls and there is no clean post-run accessor for the total. Honest null is
            # correct; do not fabricate. model/system/cost are still populated.
            self._enrich_current_span_gen_ai()
            return str(result)
        except Exception as e:
            logger.error("[LOCAL_ADAPTER_ACT_ERROR] %s", e)
            raise AdapterError(f"CodeAgent execution error: {e}") from e

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enrich_current_span_gen_ai(
        self,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Set gen_ai OTel attributes on the current span if it is recording.

        Mirrors the ClaudeAdapter is_recording() gate pattern
        (claude_adapter.py:369-377): lazy OTel import, is_recording() guard,
        then set_attribute() calls using the exact attribute keys that
        schema.py serialize_span_end() maps to the gen_ai_* record fields:
          gen_ai.system            -> gen_ai_system
          gen_ai.request.model     -> gen_ai_request_model
          gen_ai.response.model    -> gen_ai_response_model
          gen_ai.usage.input_tokens  -> gen_ai_usage_input_tokens
          gen_ai.usage.output_tokens -> gen_ai_usage_output_tokens
          axiom.cost_usd           -> cost_usd

        Unlike KIND-B (Claude), KIND-A knows its model at construction time so
        both gen_ai.request.model and gen_ai.response.model are populated.
        cost_usd = 0.0 always: local Ollama has no API billing.

        Token counts are passed explicitly by the caller (extracted from the
        ChatMessage returned by the model call) rather than read from model
        attributes — smolagents 1.26's LiteLLMModel has no last_*_token_count
        attrs; the real counts live on ChatMessage.token_usage (see _query_model).
        Only sets the token attributes when the value is not None (null-safe).

        Zero OTel overhead when not recording: is_recording() is False for the
        no-op INVALID span that OTel returns when no span context is active or
        when observability is not initialized.
        """
        try:
            from opentelemetry import trace  # noqa: PLC0415

            span = trace.get_current_span()
            if not span.is_recording():
                return
            span.set_attribute("gen_ai.system", _GEN_AI_SYSTEM_LOCAL)
            span.set_attribute("gen_ai.request.model", self._model_id)
            span.set_attribute("gen_ai.response.model", self._model_id)
            span.set_attribute("axiom.cost_usd", 0.0)
            if input_tokens is not None:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            if output_tokens is not None:
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        except Exception:
            # Observability must never break the main reasoning/acting path.
            pass

    def _query_model(self, prompt: str) -> tuple[str, int | None, int | None]:
        """Call the local model via smolagents LiteLLMModel for a tool-less completion.

        Returns a 3-tuple: (text, input_tokens, output_tokens).
        text           -- the model's text response (never None; empty string on None content).
        input_tokens   -- prompt token count from ChatMessage.token_usage, or None if absent.
        output_tokens  -- completion token count from ChatMessage.token_usage, or None if absent.

        Raises AdapterError on failure.

        Token extraction (confirmed against real qwen2.5:7b via probe_local_tokens.py):
          Primary:  ChatMessage.token_usage.input_tokens / .output_tokens
          Fallback: ChatMessage.raw.usage.prompt_tokens / .completion_tokens
          Both paths are null-safe via getattr; if neither is present tokens are None.

        Note: smolagents 1.26's LiteLLMModel has NO last_input/output_token_count
        attributes — reading from the model object always yields None. The ChatMessage
        returned by self._model(...) is the only reliable token source.

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
                return str(response), None, None
            text = response.content if response.content is not None else ""

            # Extract token counts from ChatMessage.token_usage (primary source).
            # smolagents 1.26 sets token_usage on the ChatMessage returned by the model
            # call; the model object itself has no last_*_token_count attrs.
            input_tokens: int | None = None
            output_tokens: int | None = None
            token_usage = getattr(response, "token_usage", None)
            if token_usage is not None:
                input_tokens = getattr(token_usage, "input_tokens", None)
                output_tokens = getattr(token_usage, "output_tokens", None)
            # Fallback: raw.usage.prompt_tokens / completion_tokens (litellm response).
            if input_tokens is None or output_tokens is None:
                raw_usage = getattr(getattr(response, "raw", None), "usage", None)
                if raw_usage is not None:
                    if input_tokens is None:
                        input_tokens = getattr(raw_usage, "prompt_tokens", None)
                    if output_tokens is None:
                        output_tokens = getattr(raw_usage, "completion_tokens", None)

            return text, input_tokens, output_tokens
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
