# M3 -- Local Adapter: Design

**Spec:** `003-local-adapter`
**Authored:** 2026-07-09 (Velasari)
**Status:** Draft -- ready for review + /dryrun-design

---

## 1. Purpose

This document translates the M3 requirements (`requirement.md`) into concrete structural decisions: the shared perceive/observe extraction (resolving M1's W3 debt), the LocalAdapter class and its direct LiteLLM wiring to Ollama, the act() tool-execution harness, and the file-layout deltas from M1. It references `interfaces.py` port contracts verbatim -- those files are frozen and not redefined here.

M3 proves exactly one thing:

> **Open/closed extensibility is real** -- a second provider adapter, backed by a completely different model stack (local Ollama vs cloud Claude), plugs into the same PraoLoop with zero changes to `loop.py` or `interfaces.py`.

---

## 2. Architecture Style

Same as M1: **Ports-and-Adapters (Hexagonal), hand-wired in Python.** The four PRAO phases remain four `Protocol` types in `interfaces.py`. M3 adds a second concrete adapter (`LocalAdapter`) alongside the existing `ClaudeAdapter`. Both adapters satisfy the same four Protocols. The loop is oblivious to which adapter is plugged in.

**What changes from M1:** The provider-independent `perceive()` and `observe()` logic -- previously duplicated inside `ClaudeAdapter` -- is extracted into a shared base class (`PraoAdapterBase`) in `src/axiom/providers/base.py`. Both `ClaudeAdapter` and `LocalAdapter` inherit from it. The Protocols in `interfaces.py` are untouched; `PraoAdapterBase` is an implementation convenience, not a new contract.

**What does NOT change:** `loop.py`, `interfaces.py`, `tests/fake_adapter.py`, `tests/test_contracts.py`.

---

## 3. W3 Resolution -- Shared perceive()/observe() Extraction

### 3.1 The Problem

M1's design note W3 (section 3) anticipated that `perceive()` (context assembly) and `observe()` (state bookkeeping) are provider-independent -- they contain zero SDK calls, zero model-specific logic. In M1, both lived inside `ClaudeAdapter` as a pragmatic shortcut. With adapter #2, duplicating them would violate DRY and create a maintenance hazard.

### 3.2 The Decision: Shared Base Class in `providers/base.py`

**Extract into:** `src/axiom/providers/base.py` -- a new module containing `PraoAdapterBase`.

**Why a base class (not a mixin, not a core module):**
- `perceive()` and `observe()` need access to instance state (`self._persona` for perceive; no instance state for observe, but it is natural to co-locate with perceive).
- A base class in `providers/` keeps the shared logic within the adapter layer -- it does not leak upward into core (`interfaces.py`, `loop.py`). The Protocols stay lean; the base class is an adapter-side implementation detail.
- A mixin would work equally well structurally, but a base class is simpler (single inheritance, no MRO complexity) and communicates intent clearly: "all adapters share this foundation."
- A core helper module (e.g. `src/axiom/context.py`) would work but would blur the boundary -- perceive/observe are adapter responsibilities per the M1 design, even though their logic is provider-independent. Keeping them in `providers/` preserves the M1 architectural intent.

### 3.3 `PraoAdapterBase` Specification

```python
# src/axiom/providers/base.py  (illustrative -- not final code)

from axiom.interfaces import RunState

# Intent format instructions -- same string as in M1's claude_adapter.py (section 4.1)
# Moved here so both adapters inject the identical wire format.
INTENT_FORMAT_INSTRUCTIONS: str = """..."""  # exact text from M1 section 4.1, unchanged

class PraoAdapterBase:
    """Shared base for all PRAO adapters.

    Provides provider-independent perceive() and observe() implementations.
    Subclasses must implement reason() and act() (provider-specific).
    """

    def __init__(self, persona: str) -> None:
        self._persona = persona

    # PerceivePort implementation
    def perceive(self, run_state: RunState) -> str:
        """Assemble the reasoning context prompt -- identical to M1 section 7.1."""
        sections: list[str] = []
        sections.append(f"[PERSONA]\n{self._persona}")

        if run_state.history:
            history_lines = [
                f"Step {i + 1}: {result}"
                for i, result in enumerate(run_state.history)
            ]
            sections.append("[CONVERSATION HISTORY]\n" + "\n".join(history_lines))

        sections.append(f"[CURRENT REQUEST]\n{run_state.user_input}")
        sections.append(INTENT_FORMAT_INSTRUCTIONS)

        return "\n\n".join(sections)

    # ObservePort implementation
    def observe(self, result: str, run_state: RunState) -> RunState:
        """Capture act() result and update run-state -- identical to M1 section 7.4.
        Mutate-and-return semantics."""
        run_state.history.append(result)
        run_state.cycle_count += 1
        return run_state
```

**Key points:**
- `INTENT_FORMAT_INSTRUCTIONS` is the _exact same string_ from M1's `claude_adapter.py` -- moved to `base.py` so both adapters reference a single source of truth. The constant is module-level, not a method, so it can also be referenced by tests.
- `perceive()` history section label: **E2E-discovered refinement.** When `run_state.history` is non-empty, the section header is `[TOOL EXECUTION RESULTS — read these carefully]` (not `[CONVERSATION HISTORY]`). The section also appends an explicit nudge: `[NOTE: The above are REAL outputs from tool executions. The task has been partially or fully completed. You now have the data you need. Use RESPOND to deliver the answer to the user — do NOT request another ACT unless there is clearly something missing.]` This change was discovered during live E2E with qwen2.5:7b, which repeatedly emitted ACT intents after tool output when the label was generic. The explicit instruction to RESPOND (not loop ACT) was the fix that made E2E pass. Both the label and the nudge are required behaviour -- not cosmetic.
- `observe()` semantics are identical to M1's `ClaudeAdapter.observe()` -- append to history, increment cycle_count, return self.
- `PraoAdapterBase.__init__` takes `persona: str` as the only shared parameter. Subclass `__init__` methods call `super().__init__(persona=persona)` and then add their own parameters (e.g. `allowed_tools` for Claude, `model_name` for Local).

### 3.4 ClaudeAdapter Refactor

`ClaudeAdapter` changes:

1. **Inherits from `PraoAdapterBase`** instead of being standalone.
2. **Removes its own `perceive()` and `observe()` methods** -- inherited from the base.
3. **Removes `_INTENT_FORMAT_INSTRUCTIONS`** from `claude_adapter.py` -- imports it from `base.py` (only needed if reason() references it directly; in practice, perceive() handles injection and reason() does not need the constant).
4. **`__init__` calls `super().__init__(persona=persona)`** and keeps `self._allowed_tools = allowed_tools`.
5. **`reason()` and `act()` remain unchanged** -- they are Claude-specific (SDK query calls).
6. **`_run_query()` and all error handling remain unchanged.**

**Net diff to `claude_adapter.py`:** ~98 lines removed (perceive ~16 lines, observe ~5 lines, `_INTENT_FORMAT_INSTRUCTIONS` ~41 lines, `_parse_intent` ~36 lines), ~5–8 lines added (import base, class declaration change, super().__init__, _parse_intent import). **Zero behavioural change.** The 26 M1 tests pass without modification because:
- `perceive()` output is identical (same logic, same constant).
- `observe()` mutations are identical.
- `reason()` and `act()` are untouched.
- `FakeAdapter` does not inherit from the base (it has its own tracking logic) -- no change required.
- `test_contracts.py` imports from `axiom.interfaces` and `axiom.loop` only -- never imports `ClaudeAdapter` directly.

### 3.5 What Stays Separate (NOT Extracted)

- **`reason()`** -- provider-specific. ClaudeAdapter uses `claude_agent_sdk.query()` with `tools=[]`. LocalAdapter uses LiteLLM.
- **`act()`** -- provider-specific. ClaudeAdapter delegates to the SDK's internal tool loop. LocalAdapter runs its own tool-execution harness.
- **`_run_query()` / sync bridge** -- Claude-specific (`anyio.run` over async SDK). LocalAdapter has its own `_query_model()` (synchronous via `litellm.completion()`).
- **Error handling details** -- each adapter wraps its own SDK's exceptions into `AdapterError`.
- **Intent parsing (`_parse_intent`)** -- currently a module-level function in `claude_adapter.py`. Decision: **extract `_parse_intent` to `base.py`** as well, since both adapters parse the identical JSON wire format. This is a pure function (no instance state) so it fits naturally at module level in `base.py`.

---

## 4. The LocalAdapter Class

Defined in `src/axiom/providers/local_adapter.py`. Inherits from `PraoAdapterBase`. Implements `reason()` and `act()` using LiteLLM to reach qwen2.5:7b via Ollama.

### 4.1 LiteLLM Wiring (Direct — No ADK)

**SDK choice:** LiteLLM (`litellm` package) is used directly to call Ollama. No Google ADK wrapper — see section 4.3 rationale.

**Model instantiation:**

```python
# src/axiom/providers/local_adapter.py  (illustrative)

class LocalAdapter(PraoAdapterBase):
    def __init__(
        self,
        persona: str,
        model_name: str = "ollama_chat/qwen2.5:7b",
        ollama_api_base: str = "http://localhost:11434",
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        super().__init__(persona=persona)
        self._model_name = model_name
        self._ollama_api_base = ollama_api_base
        self._max_tool_iterations = max_tool_iterations
```

**Ollama base URL configuration:** LiteLLM reads `OLLAMA_API_BASE` from process-level configuration. The adapter sets this in `__init__` using `setdefault` on the process config so that LiteLLM can locate the Ollama server. This is a process-level setting, not a global config mutation.

**Tool schema format:** Tool schemas are plain Python dicts in OpenAI function-calling format (see section 5.2.1). No ADK `FunctionTool` class is used — the schema is a straightforward dict literal. LiteLLM passes these schemas directly to Ollama, which supports OpenAI-compatible tool calling.

### 4.2 `reason()` -- Tool-Less Local Query + Intent Parsing

Structurally mirrors ClaudeAdapter's `reason()` but uses LiteLLM instead of `claude_agent_sdk`.

```python
def reason(self, context: str) -> Intent:
    """Tool-less query to local model -> parse JSON intent -> return Intent.

    Uses the same JSON wire format as M1 section 4.1 (injected by perceive()).
    Same parse-retry + fallback strategy as ClaudeAdapter section 7.2.
    """
    raw_text = self._query_model(context, tools=[])

    intent, error = _parse_intent(raw_text)
    if intent is not None:
        return intent

    # Parse failure -- log and retry once (same strategy as M1 section 7.2)
    logger.warning(
        "[INTENT_PARSE_FAILURE] local model failed to produce valid intent JSON. "
        "error=%s raw=%r",
        error, raw_text,
    )
    retry_context = (
        context + "\n\nYour previous response was not valid JSON. "
        "Reply with only the JSON intent object."
    )
    retry_text = self._query_model(retry_context, tools=[])
    retry_intent, retry_error = _parse_intent(retry_text)
    if retry_intent is not None:
        return retry_intent

    # Retry also failed -- fallback
    logger.warning(
        "[INTENT_FALLBACK] local model retry parse also failed. error=%s raw=%r "
        "-- returning fallback RESPOND",
        retry_error, retry_text,
    )
    return RespondIntent(text=f"[FALLBACK_RESPOND] {raw_text}")
```

**Why the same parse-retry + fallback:** qwen2.5:7b is a weaker model than Claude -- it is _more_ likely to emit malformed JSON, not less. The retry-then-fallback strategy from M1 section 7.2 is essential. The `[FALLBACK_RESPOND]` prefix makes fallback responses distinguishable.

**Enhanced JSON extraction for weak models:** The `_parse_intent` function (shared in `base.py`) gains a pre-processing step: if `json.loads()` fails on the raw text, attempt to extract a JSON object from within the text (e.g. strip markdown code fences, find the first `{...}` substring). This handles the common local-model failure mode of wrapping JSON in explanation text. The pre-processing is additive -- it does not change the happy-path behaviour for well-formed JSON (ClaudeAdapter is unaffected).

### 4.3 `_query_model()` -- Sync Model Call

The internal helper that calls the local model. Unlike ClaudeAdapter's `_run_query()` (which bridges async via `anyio.run`), this is synchronous end-to-end -- LiteLLM's Ollama integration supports synchronous calls.

```python
# litellm is imported at construction or first use (deferred), not at module
# top-level, so that Claude-only installs do not pay the litellm import cost.
# See O1 in dryrun-design-1.md.

PER_QUERY_TIMEOUT_SECS: int = 60  # local model; shorter than Claude's 120s

def _query_model(
    self,
    prompt: str,
    tools: list[dict] | None = None,
) -> str:
    """Call the local model via LiteLLM. Returns the model's text response.

    Args:
        prompt: The full prompt string.
        tools: Tool schemas in OpenAI function-calling format (or None/[] for tool-less).

    Returns:
        The model's response text.

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
        response = litellm.completion(**kwargs)
        message = response.choices[0].message
        return message.content or ""
    except Exception as e:
        logger.error("[LOCAL_ADAPTER_ERROR] %s", e)
        raise AdapterError(f"local model error: {e}") from e
```

**Design note -- direct LiteLLM (no ADK):** `litellm.completion()` is called directly for both `reason()` (tool-less) and `act()` (tool-bearing). Tool schemas are plain dicts in OpenAI function-calling format — no ADK classes involved. Direct LiteLLM gives full control over the tool-calling loop, which is exactly what the harness needs. **Decision: use `litellm.completion()` directly for both reason() and act(). Google ADK is not a dependency of this milestone.**

**Sync call -- no async bridge needed:** Unlike `claude_agent_sdk.query()` (async generator), `litellm.completion()` is synchronous. No `anyio.run()` wrapper is needed. This eliminates the per-call event-loop overhead that M1 measured -- a structural advantage of the local adapter.

### 4.4 `act()` -- Tool-Bearing Query with Local Tool-Execution Harness

This is the core design problem unique to LocalAdapter. Claude's SDK has its own internal tool loop; a local completion model does not. LocalAdapter must build one.

**See section 5 for the full tool-execution harness design.**

```python
def act(self, instruction: str) -> str:
    """Execute a bounded instruction using the local model + tool harness.

    Runs a tool-calling loop: model proposes tool calls -> harness executes ->
    results fed back -> repeat until model produces a final text answer or
    MAX_TOOL_ITERATIONS is reached.
    """
    return self._run_tool_loop(instruction)
```

### 4.5 Error Handling

All errors from the local model stack are caught and raised as `AdapterError` -- same contract as ClaudeAdapter.

| Scenario | Exception source | Adapter action |
|----------|-----------------|----------------|
| Ollama not running | `litellm` ServiceUnavailableError or `ConnectionError` | Log `ERROR [LOCAL_ADAPTER_OLLAMA_DOWN]`; raise `AdapterError("Ollama not reachable at {api_base}")` |
| Model not loaded | `litellm` error with 404 | Log `ERROR [LOCAL_ADAPTER_MODEL_NOT_FOUND]`; raise `AdapterError("model {model_name} not found in Ollama")` |
| Query timeout | `litellm.Timeout` | Log `ERROR [LOCAL_ADAPTER_TIMEOUT]`; raise `AdapterError("local model query timed out after {timeout}s")` |
| Malformed response (not JSON-parseable as intent) | (handled in reason() retry/fallback) | See section 4.2 -- not an AdapterError, handled gracefully |
| Any other exception | Any `Exception` | Log `ERROR [LOCAL_ADAPTER_UNEXPECTED]`; raise `AdapterError(f"unexpected error: {e}")` |

---

## 5. The act() Tool-Execution Harness

### 5.1 Problem Statement

ClaudeAdapter's `act()` sends a prompt with `allowed_tools` to the Claude SDK, which internally runs its own tool loop (model proposes tool call, SDK executes, feed result back, repeat). Axiom writes no tool-execution harness for Claude -- the SDK handles it.

A local model (qwen2.5:7b via LiteLLM) has no such internal loop. When the model "calls a tool," it returns a response with `tool_calls` in the message -- but nobody executes those calls. LocalAdapter must:

1. Declare tool schemas to the model (so it knows what tools exist).
2. Parse tool-call responses from the model.
3. Execute the tool locally.
4. Feed the result back to the model.
5. Repeat until the model produces a final text answer (no tool calls).
6. Bound the loop to prevent infinite iteration.

### 5.2 Tool Declarations

M3 ships with one self-contained tool. A web-search tool is optional/stretch.

#### 5.2.1 Shell Tool -- `run_shell_command`

**Purpose:** Execute a shell command on the local machine and return stdout/stderr. This mirrors M1's MPP-3 exemplar ("list files in a directory and summarise") and is the primary tool for the E2E test.

**Schema (OpenAI function-calling format, as expected by LiteLLM):**

```python
SHELL_TOOL_SCHEMA = {
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
```

**Execution implementation:**

```python
import subprocess

TOOL_COMMAND_TIMEOUT_SECS: int = 30  # per-command timeout

def _execute_shell_tool(command: str) -> str:
    """Run a shell command and return combined stdout+stderr.

    Bounded by TOOL_COMMAND_TIMEOUT_SECS. On timeout or error,
    returns an error string (not raises) -- the model gets the error
    as a tool result and can retry or adjust.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
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
```

**Security note:** The shell tool executes arbitrary commands -- same risk profile as M1's `Bash` tool in `allowed_tools`. M3 is a dev-machine proof, not a production deployment. Guardrail policy is a later milestone concern.

#### 5.2.2 Tool Registry (Internal)

Tools are registered as a list of `(schema, executor)` tuples within LocalAdapter:

```python
# Inside LocalAdapter.__init__
self._tools: list[tuple[dict, Callable[[dict], str]]] = [
    (SHELL_TOOL_SCHEMA, lambda args: _execute_shell_tool(args["command"])),
]
self._tool_schemas = [t[0] for t in self._tools]
self._tool_executors = {t[0]["function"]["name"]: t[1] for t in self._tools}
```

This is a simple internal registry -- not an Axiom-wide tools registry (that is a later milestone). It is just enough to wire tool schemas to executors for the harness loop.

### 5.3 The Tool-Calling Loop

```python
MAX_TOOL_ITERATIONS: int = 5  # module-level constant; overridable via constructor

def _run_tool_loop(self, instruction: str) -> str:
    """Execute the tool-calling loop for act().

    Flow:
    1. Send instruction + tool schemas to model.
    2. If model response contains tool_calls -> execute each, collect results.
    3. Feed tool results back to model as tool-role messages.
    4. Repeat until model produces a text response (no tool_calls) or
       MAX_TOOL_ITERATIONS is reached.
    5. Return the final text response.
    """
    messages = [
        {
            "role": "user",
            "content": (
                f"Execute this instruction using your available tools and report the result. "
                f"You have real tools -- USE them. Do NOT answer from memory. "
                f"Instruction: {instruction}"
            ),
        }
    ]

    for iteration in range(self._max_tool_iterations):
        try:
            response = litellm.completion(
                model=self._model_name,
                messages=messages,
                tools=self._tool_schemas,
                tool_choice="auto",
                timeout=PER_QUERY_TIMEOUT_SECS,
                api_base=self._ollama_api_base,
            )
        except Exception as e:
            logger.error("[LOCAL_ADAPTER_TOOL_LOOP_ERROR] iteration=%d %s", iteration, e)
            raise AdapterError(f"local model error during tool loop: {e}") from e

        message = response.choices[0].message

        # Case 1: Model produced a final text answer (no tool calls)
        if not message.tool_calls:
            return message.content or ""

        # Case 2: Model proposed tool calls -- execute them
        # Append the assistant's tool-call message to conversation.
        # NOTE (O4): message.model_dump() assumes the LiteLLM response
        # message is a Pydantic model. Verify at implementation that
        # response.choices[0].message.model_dump() produces a dict
        # compatible with the messages list format expected by subsequent
        # litellm.completion() calls. If the LiteLLM version changes the
        # response type, this will fail loudly on the first live call.
        messages.append(message.model_dump())

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            try:
                fn_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                # Malformed arguments — do NOT call the executor.
                # Feed an error string back to the model as the tool result
                # so it can retry with well-formed arguments.
                tool_result = "[error]: could not parse tool arguments"
                logger.warning(
                    "[LOCAL_ADAPTER_TOOL_ARGS_PARSE_FAIL] tool=%s raw=%r",
                    fn_name, tool_call.function.arguments,
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                })
                continue

            executor = self._tool_executors.get(fn_name)
            if executor:
                try:
                    tool_result = executor(fn_args)
                except Exception as exec_err:
                    # Any executor exception (KeyError, subprocess failure,
                    # timeout, etc.) is converted to an error string — never
                    # raised out of act(). Consistent with MLA-3 AC:
                    # "tool-execution errors are caught and fed back to the
                    # model as error results."
                    tool_result = f"[error]: tool execution failed: {exec_err}"
                    logger.warning(
                        "[LOCAL_ADAPTER_TOOL_EXEC_ERROR] tool=%s error=%s",
                        fn_name, exec_err,
                    )
            else:
                tool_result = f"[error]: unknown tool '{fn_name}'"
                logger.warning("[LOCAL_ADAPTER_UNKNOWN_TOOL] %s", fn_name)

            # Feed tool result back to model
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

        logger.debug(
            "[LOCAL_ADAPTER_TOOL_ITERATION] iteration=%d tool_calls=%d",
            iteration, len(message.tool_calls),
        )

    # MAX_TOOL_ITERATIONS reached -- return best partial result
    logger.warning(
        "[LOCAL_ADAPTER_MAX_TOOL_ITERATIONS] reached %d iterations without final answer",
        self._max_tool_iterations,
    )
    # Scan backward for the last ASSISTANT message's text content.
    # At exhaustion, messages[-1] is a tool-result (role: "tool"), NOT
    # model text. We must find the last assistant-role message instead.
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            text = msg.get("content") or ""
            if text.strip():
                return text
    # No assistant text found at all — return explicit exhaustion summary
    return f"[tool loop exhausted after {self._max_tool_iterations} iterations]"
```

### 5.4 Tool Loop Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Message format** | OpenAI function-calling format (`tool_calls`, `tool` role) | LiteLLM standardises on OpenAI format regardless of underlying provider. Ollama's Qwen support follows this. |
| **Tool choice** | `"auto"` | Let the model decide whether to call a tool or respond directly. |
| **Multiple tool calls per turn** | Supported | Some models batch multiple tool calls in one response. The loop iterates over all `tool_calls` in a single response. |
| **Max iterations** | 5 (default) | Generous enough for multi-step tasks (e.g. list then read then summarise), tight enough to prevent runaway loops. Overridable via constructor. |
| **Exhaustion behaviour** | Return partial result or error string | NOT an `AdapterError` -- the loop did work, it just did not converge. The result is returned to `observe()` and the outer PRAO loop can try again or stop. |
| **Tool errors** | Fed back as tool-result strings | The model sees the error and can adjust (e.g. fix a typo in a command). This is more robust than raising. |
| **Conversation accumulation** | Full message history within the tool loop | Each iteration sees all prior tool calls and results. This gives the model context to make informed follow-up calls. |

### 5.5 reason() Stays Tool-Less

`reason()` receives the context from `perceive()` (which already contains the intent format instructions) and queries the model with `tools=[]` (or `tools=None`). The model must return a single-line JSON intent -- no tool calls allowed.

This is identical to ClaudeAdapter's `reason()` design (M1 section 7.2). The wire format, parse rules, retry strategy, and fallback are all reused. The only difference is the model backend.

**Weak-model mitigation:** qwen2.5:7b may struggle more with strict JSON output than Claude. The enhanced `_parse_intent` pre-processing (section 4.2 -- strip code fences, extract first `{...}`) mitigates this. If the model consistently fails, the `[FALLBACK_RESPOND]` path catches it. E2E tests will validate this empirically.

---

## 6. Intent Wire Format -- Reused Verbatim

The JSON intent wire format from M1 section 4.1 is reused without modification. The `INTENT_FORMAT_INSTRUCTIONS` string is now defined in `providers/base.py` (section 3.3) and injected into every `reason()` prompt via the shared `perceive()`.

The `_parse_intent()` function is also shared (moved to `base.py`). Both adapters parse the same JSON envelope with the same rules. The enhanced pre-processing for weak models (section 4.2) is additive -- it does not change happy-path behaviour.

Parse rules (unchanged from M1 section 4.1):
1. Strip leading/trailing whitespace.
2. (NEW) If `json.loads()` fails, attempt to extract JSON from within the text (strip markdown code fences, find first `{...}` via regex). Retry `json.loads()` on extracted substring.
3. Parse with `json.loads()`. On failure: parse failure.
4. Validate `intent` field: `"RESPOND"`, `"ACT"`, `"FINISH"` (case-sensitive).
5. For `"RESPOND"`: require `text` field (str).
6. For `"ACT"`: require `instruction` field (str).
7. For `"FINISH"`: no additional fields required.
8. On success: construct and return the corresponding `Intent` dataclass.

---

## 7. Latency Note -- Local vs Claude Model Loading

The latency profile of `LocalAdapter` is fundamentally different from `ClaudeAdapter`:

| Aspect | ClaudeAdapter | LocalAdapter |
|--------|--------------|--------------|
| **Per-call overhead** | Subprocess spawn (`claude-code` CLI) -- ~2-5s per query | No subprocess. Direct API call to Ollama -- ~0.1s overhead |
| **Cold start** | Each `query()` spawns a fresh subprocess | First inference after Ollama loads the model is slow (~10-30s for 7B on GPU); subsequent calls are warm-fast (~1-3s) |
| **Model loading** | N/A (cloud) | Ollama loads the model into VRAM/RAM on first request; stays loaded via `keep_alive` |
| **Async bridge** | `anyio.run()` per call (event loop overhead) | None -- `litellm.completion()` is synchronous |
| **Token generation** | Cloud-fast (~50-100 tok/s) | Local-GPU-bound (~20-40 tok/s on RTX 3060 4GB with 7B quantised) |

**E2E pre-warming:** To get meaningful latency numbers (not polluted by model-load time), E2E tests pre-warm the model before timing:

```python
import httpx

def _prewarm_ollama(model: str = "qwen2.5:7b", base: str = "http://localhost:11434"):
    """Send a trivial generate request to ensure the model is loaded in memory."""
    httpx.post(
        f"{base}/api/generate",
        json={"model": model, "prompt": "hi", "stream": False},
        timeout=120,  # generous timeout for cold load
    )
```

**Latency logging:** Uses the same `observability/timing.py` utility as M1. The `timed_run` wrapper measures wall-clock elapsed for the full `loop.run()` call. DEBUG log format is identical: `"[M1 Latency] %.3fs  (%d cycle(s), %d SDK spawn(s))"` -- the "SDK spawn(s)" label is slightly misleading for local (there are no SDK spawns), but keeping the format identical avoids changes to `timing.py`. A label update is a cosmetic M2 concern.

---

## 8. File Layout -- Deltas from M1

New and changed files marked with `[NEW]` and `[CHANGED]`:

```
axiom/
  src/
    axiom/
      __init__.py
      interfaces.py              # [UNCHANGED] -- frozen
      loop.py                    # [UNCHANGED] -- frozen
      agent.py                   # [CHANGED] -- adds LocalAdapter wiring option
      persona/
        __init__.py              # [UNCHANGED]
        persona.txt              # [UNCHANGED]
      providers/
        __init__.py              # [UNCHANGED]
        base.py                  # [NEW] -- PraoAdapterBase (shared perceive/observe)
                                 #   + INTENT_FORMAT_INSTRUCTIONS constant
                                 #   + _parse_intent() shared function
        claude_adapter.py        # [CHANGED] -- inherits PraoAdapterBase;
                                 #   removes perceive(), observe(), _INTENT_FORMAT_INSTRUCTIONS;
                                 #   imports _parse_intent from base
        local_adapter.py         # [NEW] -- LocalAdapter: reason() + act() via LiteLLM
                                 #   + _query_model() sync model call
                                 #   + _run_tool_loop() tool-execution harness
                                 #   + _execute_shell_tool() tool implementation
                                 #   + SHELL_TOOL_SCHEMA, MAX_TOOL_ITERATIONS,
                                 #     PER_QUERY_TIMEOUT_SECS, TOOL_COMMAND_TIMEOUT_SECS
      observability/
        __init__.py              # [UNCHANGED]
        timing.py                # [UNCHANGED]
      interface/
        __init__.py              # [UNCHANGED]
        cli.py                   # [CHANGED] -- gains --provider flag (claude|local) passed to Agent(provider=...)
  tests/
    __init__.py                  # [UNCHANGED]
    fake_adapter.py              # [UNCHANGED]
    test_contracts.py            # [UNCHANGED] -- M1's 26 tests
    test_local_adapter.py        # [NEW] -- unit tests for LocalAdapter (stubbed model)
    test_shared_base.py          # [NEW] -- unit tests for PraoAdapterBase
    test_local_e2e.py            # [NEW] -- live E2E tests on qwen2.5:7b
                                 #   (marked @pytest.mark.e2e_local; skipped if no Ollama)
  pyproject.toml                 # [CHANGED] -- adds litellm dependency
  .claude/
    specs/003-local-adapter/
      requirement.md
      design.md                  # <-- this document
      task.md
```

### 8.1 `agent.py` Changes

`agent.py` gains a `LocalAdapter` import and an alternative wiring path. M3 does NOT implement a runtime router -- the adapter choice is a code-level decision:

```python
# src/axiom/agent.py  (M3 delta -- illustrative)
# NOTE: LocalAdapter is imported lazily inside the provider=="local" branch
# so that Claude-only installs do not pay the litellm import cost.

class Agent:
    def __init__(self, debug: bool = False, provider: str = "claude") -> None:
        if debug:
            _configure_debug_logging()

        persona_text = persona_pkg.load()

        if provider == "local":
            from axiom.providers.local_adapter import LocalAdapter  # lazy import
            adapter = LocalAdapter(persona=persona_text)
        else:
            adapter = ClaudeAdapter(persona=persona_text, allowed_tools=M1_ALLOWED_TOOLS)

        self._loop = PraoLoop(
            perceive=adapter,
            reason=adapter,
            act=adapter,
            observe=adapter,
            max_cycles=10,
        )
```

**CLI flag:** `cli.py` gains a `--provider` flag (`claude` or `local`) passed to `Agent(provider=...)`. Default is `claude` -- M1 behaviour preserved.

---

## 9. Dependency Additions

| Package | Version | Purpose | Install |
|---------|---------|---------|---------|
| `litellm` | latest stable | LLM gateway -- routes to Ollama for local models via `litellm.completion()` | `pip install litellm` |
| `httpx` | latest stable | Used for Ollama pre-warming in E2E tests | `pip install httpx` (likely already a transitive dep) |

**pyproject.toml additions:**

```toml
[project]
dependencies = [
    "claude-agent-sdk",
    "anyio",
    "litellm",
]

[project.optional-dependencies]
test = [
    "pytest",
    "httpx",
]
```

---

## 10. Import Boundary Rules

Extended from M1 section 11. New/changed rules in **bold**.

| Module | May import |
|---|---|
| `loop.py` | `axiom.interfaces` only -- zero provider imports (UNCHANGED) |
| **`providers/base.py`** | **`axiom.interfaces` only -- zero SDK imports** |
| `providers/claude_adapter.py` | `axiom.interfaces`, **`axiom.providers.base`**, `claude_agent_sdk`, `anyio` |
| **`providers/local_adapter.py`** | **`axiom.interfaces`, `axiom.providers.base`, `litellm` (deferred — imported at construction or first use, not at module top-level), `json`, `subprocess`, `logging`, stdlib** |
| `persona/__init__.py` | stdlib only (UNCHANGED) |
| `observability/timing.py` | stdlib only (UNCHANGED) |
| `agent.py` | `axiom.loop`, `axiom.providers.claude_adapter`, **`axiom.providers.local_adapter` (lazy — imported inside `provider=="local"` branch only)**, `axiom.persona`, `axiom.observability.timing`, `axiom.interfaces`, stdlib |
| `interface/cli.py` | `axiom.agent` only (UNCHANGED) |
| `tests/fake_adapter.py` | `axiom.interfaces` only (UNCHANGED) |
| `tests/test_contracts.py` | `axiom.interfaces`, `axiom.loop`, `tests.fake_adapter` (UNCHANGED) |
| **`tests/test_local_adapter.py`** | **`axiom.interfaces`, `axiom.loop`, `axiom.providers.local_adapter`, `axiom.providers.base`, `unittest.mock`** |
| **`tests/test_shared_base.py`** | **`axiom.interfaces`, `axiom.providers.base`** |
| **`tests/test_local_e2e.py`** | **`axiom.interfaces`, `axiom.loop`, `axiom.providers.local_adapter`, `axiom.persona`, `httpx`, `pytest`** |

No circular imports. The port-adapter proof is confirmed by `loop.py` importing zero provider code -- unchanged from M1.

---

## 11. Test Strategy

### 11.1 Unit Tests -- `test_local_adapter.py`

Test the LocalAdapter with a **mocked `litellm.completion`** (via `unittest.mock.patch`). No live Ollama. No network.

| Test case | What it verifies |
|-----------|-----------------|
| reason() with valid JSON intent | `_query_model` called with tools=None/[]; correct Intent returned |
| reason() with malformed JSON then retry succeeds | First call returns garbage; retry returns valid JSON; correct Intent returned |
| reason() with malformed JSON then fallback | Both calls return garbage; `[FALLBACK_RESPOND]` returned |
| reason() with JSON wrapped in code fences | Pre-processing strips fences; correct Intent returned |
| act() tool loop -- single tool call | Model proposes `run_shell_command`; harness executes; model returns final text |
| act() tool loop -- multi-step | Model calls tool twice across 2 iterations; final text returned |
| act() tool loop -- max iterations | Model always proposes tool calls; loop stops at MAX_TOOL_ITERATIONS |
| act() tool loop -- unknown tool | Model proposes a tool not in registry; error fed back to model |
| act() tool loop -- tool execution error | Shell command fails; error string fed back to model |
| act() model error then AdapterError | `litellm.completion` raises; `AdapterError` propagated |
| Constructor defaults | model_name, api_base, max_tool_iterations have correct defaults |

### 11.2 Shared Base Tests -- `test_shared_base.py`

Test `PraoAdapterBase.perceive()` and `PraoAdapterBase.observe()` directly.

| Test case | What it verifies |
|-----------|-----------------|
| perceive() with empty history | Output contains persona + request + intent instructions; no history section |
| perceive() with history | Output contains history section with numbered steps |
| perceive() persona injection | Persona text appears in output |
| observe() appends to history | `run_state.history` gains the result string |
| observe() increments cycle_count | `run_state.cycle_count` increases by 1 |
| observe() returns run_state | Same object returned (mutate-and-return) |

### 11.3 M1 Regression -- `test_contracts.py`

All 26 existing tests must pass without modification. Verified by running `pytest tests/test_contracts.py` -- the refactored `ClaudeAdapter` (now inheriting `PraoAdapterBase`) must produce identical behaviour. These tests never import `ClaudeAdapter` directly -- they use `FakeAdapter` -- so the refactor is structurally invisible to them.

### 11.4 Live E2E -- `test_local_e2e.py`

Requires Ollama running with qwen2.5:7b. Marked `@pytest.mark.e2e_local`.

| Test case | What it verifies |
|-----------|-----------------|
| Trivial RESPOND (e.g. "What is the capital of France?") | `reason()` returns RESPOND; `act()` NOT called; loop returns coherent text |
| Tool task (e.g. "List files in the current directory") | `reason()` returns ACT; `act()` runs tool harness; shell tool executes; `observe()` captures; loop completes |
| Pre-warming | Model loaded before timing; latency logged |
| Ollama unavailable then skip | Test skips gracefully (not fails) if Ollama is unreachable |

**pytest configuration:**

```ini
# pyproject.toml or conftest.py
[tool.pytest.ini_options]
markers = [
    "e2e_local: marks tests requiring local Ollama (deselect with '-m not e2e_local')",
]
```

---

## 12. System Diagram -- M3 Delta

```
  User input             +--------------------------------------------------+
  (stdin / arg) -------->|  interface/cli.py  (pure I/O entry point)        |
                         |  * --provider flag (claude | local)              |
                         +----------------+---------------------------------+
                                          |
                                          v
                         +--------------------------------------------------+
                         |  agent.py  (composition root)                    |
                         |  * provider="claude" -> ClaudeAdapter            |
                         |  * provider="local"  -> LocalAdapter             |
                         |  * constructs PraoLoop(perceive=adapter, ...)    |
                         +------+-------------------------------------------+
                                |
                                v
                         +--------------------------------------------------+
                         |  loop.py -- PraoLoop  [UNCHANGED]                |
                         |  (same control flow as M1 -- section 6.2)        |
                         +----------+---------------------------------------+
                                    |
               +--------------------+--------------------+
               |                    |                    |
               v                    v                    v
  +---------------------+  +------------------+  +--------------------------+
  |  PraoAdapterBase    |  |  ClaudeAdapter    |  |  LocalAdapter            |
  |  [NEW -- base.py]   |  |  [CHANGED]        |  |  [NEW]                   |
  |                     |  |                   |  |                          |
  |  perceive()  <------|--|-- inherits        |  |  inherits -------------->|
  |  observe()   <------|--|-- inherits        |  |  inherits -------------->|
  |  _parse_intent()    |  |                   |  |                          |
  +---------------------+  |  reason() -> SDK  |  |  reason() -> litellm    |
                           |  act()   -> SDK   |  |  act()   -> tool harness|
                           |  _run_query()     |  |  _query_model()          |
                           +------+------------+  |  _run_tool_loop()        |
                                  |               |  _execute_shell_tool()   |
                                  v               +----------+---------------+
                           claude_agent_sdk                  |
                           (async subprocess)                v
                                                  litellm.completion()
                                                  (sync -> Ollama API)
                                                       |
                                                       v
                                                  Ollama (localhost:11434)
                                                  qwen2.5:7b
```

---

## 13. Requirements Traceability

| Story | Satisfied by |
|---|---|
| **MLA-1** -- LocalAdapter satisfies all four Protocols, same PraoLoop, zero loop changes | `LocalAdapter` in `local_adapter.py` inherits `PraoAdapterBase` (perceive/observe) and implements `reason()`/`act()` using `litellm.completion()` against Ollama. `loop.py` + `interfaces.py` have zero diff. `PraoLoop` constructor takes port-typed params -- accepts LocalAdapter identically to ClaudeAdapter. |
| **MLA-2** -- Shared perceive()/observe(), W3 resolved | `PraoAdapterBase` in `base.py` provides shared `perceive()` + `observe()`. `ClaudeAdapter` inherits it with zero behaviour change. `LocalAdapter` inherits it. `INTENT_FORMAT_INSTRUCTIONS` + `_parse_intent()` shared. M1 tests unaffected (they use `FakeAdapter`, which is independent). |
| **MLA-3** -- act() tool-execution harness | `_run_tool_loop()` in `local_adapter.py`: sends instruction + tool schemas, parses tool_calls, executes via `_execute_shell_tool()`, feeds results back, repeats until final text or `MAX_TOOL_ITERATIONS`. Shell tool (`run_shell_command`) is the self-contained local tool. |
| **MLA-4** -- Fast unit tests (stubbed model) | `test_local_adapter.py`: mocked `litellm.completion` covers reason() (valid/malformed/fallback), act() tool loop (single/multi/max-iterations/unknown-tool/error), AdapterError propagation. `test_shared_base.py`: direct tests of perceive() and observe(). No Ollama, no network. |
| **MLA-5** -- Live E2E on qwen2.5:7b | `test_local_e2e.py`: trivial RESPOND + tool task through real PraoLoop + real Ollama. Pre-warmed. Marked `@pytest.mark.e2e_local`. Skips gracefully if Ollama unavailable. |
| **MLA-6** -- M1's 26 tests remain green | `test_contracts.py` is untouched. `FakeAdapter` is untouched. `loop.py` + `interfaces.py` are frozen. ClaudeAdapter refactor is behaviour-preserving (same perceive/observe logic, just inherited). |

---

## 14. Open Questions

| # | Question | Status |
|---|----------|--------|
| OQ-1 | **ADK LiteLlm vs direct litellm.completion():** RESOLVED — direct `litellm.completion()` is the decision. Google ADK is removed from M3 dependencies entirely (see W2/W5 resolution). No ADK fallback. Contained to `_query_model()` and `_run_tool_loop()`. Fails loudly at E2E if litellm+Ollama integration doesn't work. | Resolved — direct LiteLLM. Accepted deferral: loud failure at first E2E call if integration breaks. |
| OQ-2 | **qwen2.5:7b tool-calling reliability:** The model's ability to produce well-formed tool calls (function name + JSON arguments) in LiteLLM's OpenAI format is unverified. If it fails consistently, the E2E tool test may need a different model or a more forgiving tool-call parser. | Validate empirically during E2E testing. |
| OQ-3 | **Enhanced `_parse_intent` backward compatibility:** The JSON-extraction pre-processing (strip code fences, find first `{...}`) is additive, but verify it does not false-positive on ClaudeAdapter's clean JSON output. Add a unit test with clean JSON to confirm no regression. | Verify during implementation of `base.py`. |

---

## 15. Out of Scope (restate for design clarity)

The following are explicitly NOT designed or built in M3:

- **Router / multi-provider selection** -- `agent.py` wires one adapter via a code-level `provider` parameter. No runtime routing policy. Router is M6.
- **Conductor / multi-agent orchestration** -- single master loop only.
- **ADK Runner / agent loop** -- not applicable; ADK is not a dependency of this milestone. PraoLoop is the sole orchestrator.
- **Web-search tool** -- optional/stretch; E2E does not depend on it. Shell tool is sufficient.
- **Memory** -- ephemeral `RunState.history` only; no cross-session recall.
- **Streaming** -- no streaming from local model to CLI.
- **Dynamic persona** -- static file only.
- **YAML / declarative config** -- Python wiring only.
- **Performance tuning** -- qwen2.5:7b runs as-is; no quantisation tuning.
- **Changes to loop.py or interfaces.py** -- hard constraint; these files are frozen.
- **Fused reason+act** -- split design maintained.
- **Axiom-wide tools registry** -- the internal `_tools` list in LocalAdapter is adapter-local, not a system registry.
- **`timing.py` label update** -- "SDK spawn(s)" label is slightly misleading for local; cosmetic fix deferred.
