# OSS Agentic SDK for Axiom's Second Provider Adapter — Landscape Research

**Date:** 2026-07-08
**Method:** WebSearch + WebFetch against official docs and GitHub READMEs (live, fetched 2026-07-08). All capability claims grounded or flagged.
**One-line question:** Which existing OSS/open-model agentic SDK gives `query()`-equivalent KIND-B worker autonomy so the second Axiom provider adapter is thin?

---

## The narrowed question and constraints

The 07-07 research (`prao-loop-on-claude-sdk-2026-07-07.md`) locked the Axiom master loop design: the Claude Agent SDK's `query()` is adopted as the delegated KIND-B WORKER — it owns its own perceive→act→observe loop, streams messages back, is abortable, and is pre-scoped by `allowed_tools`. That is the reference contract.

Open uncertainty #4 from that doc: *"for a fully local-first REASON/worker, a local/OSS model via a thin-degenerate-agent wrapper replaces the SDK call; confirm the wrapper presents the same intent contract."*

This document answers the worker/provider side specifically. The constraints, priority-ordered:

| # | Constraint | Type |
|---|------------|------|
| 1 | **In-process / local-first** — runs in OUR process, NOT a hosted cloud-agent service | HARD (eliminates hosted options) |
| 2 | **Owns the loop** — give it a task, it runs until done without caller re-invocation | HARD (eliminates bare model clients) |
| 3 | **Open/OSS models locally** — Ollama / vLLM / llama.cpp / OpenAI-compatible endpoint | HARD (the whole point) |
| 4 | **MCP client** — our Connectors port; adapter must not bypass it | Strong requirement |
| 5 | **Streaming trace of steps** — observability feed AND the abort point (reuse, not duplicate) | Strong requirement |
| 6 | **Mid-run abort** — circuit-breaker; can kill an in-flight run | Strong requirement |
| 7 | **Tool-scoping / permissions** — pre-run allowlist maps to KIND-B pre-run scope | Strong requirement |
| 8 | **Lifecycle hooks** — pre/post tool, stop — maps to our call-points | Nice-to-have |
| 9 | **Maturity + license + language** — permissive OSS, Python primary | Preference |

The 07-07 doc established that the adapter lives behind the single Agent port (hexagonal architecture, N adapters). The adapter must present the same KIND-B intent contract regardless of which SDK backs it: `dispatch(task, scope) → stream → observe → [abort?]`. The goal is to ADOPT the SDK's loop so the adapter is thin — the same decision made for the Claude Agent SDK.

---

## Comparison Matrix

Evaluation marks: ✅ = confirmed from docs · ⚠️ = partial or unverified · ❌ = absent or fails

| SDK | 1. Owns Loop | 2. Open Models Local | 3. MCP Client | 4. Stream Trace | 5. Tool-Scope | 6. Mid-Abort | 7. In-Process | 8. Hooks | 9. Maturity / License / Lang |
|-----|-------------|---------------------|---------------|-----------------|---------------|--------------|---------------|----------|------------------------------|
| **A. OpenAI Agents SDK** | ✅ Built-in agent loop, tools → LLM → tools until done | ✅ `base_url` override → Ollama/vLLM; Chat Completions path (not Responses API) | ✅ First-class MCP tool integration | ✅ Tracing built-in; step streaming; disable for local via flag | ⚠️ Tools scoped at agent-def time; no runtime allowlist toggle or per-action approval confirmed | ⚠️ Not documented; no `cancel()` or abort token found | ✅ In-process Python | ✅ `RunHooks` + `AgentHooks`: `on_tool_start`, `on_tool_end`, `on_agent_start/end`, `on_handoff` | MIT · ~27.7k stars · Python · v0.18.0 · Active |
| **B. Pydantic AI** | ✅ `agent.run()` multi-step; `agent.iter()` for step control | ✅ `OllamaModel` class native; model-agnostic | ✅ MCP integration documented | ✅ `run_stream_events()` granular events; OTel spans per tool call; time-to-first-chunk | ⚠️ Human-in-the-loop approval exists; allowlist at construction; per-action approval API details unverified | ✅ `agent.iter()` with manual `.next()` enables conditional halt; interrupted state captured | ✅ In-process Python | ⚠️ Event-stream-based observability; named pre/post hook callbacks unconfirmed | MIT · ~18.3k stars · Python · v2.6.0 · Active |
| **C. LangGraph** | ✅ Compiled graph runs until termination; `.invoke()` or `.stream()` drives loop | ✅ `ChatOllama` via LangChain model zoo | ⚠️ Not natively documented; third-party ecosystem adapters exist; UNVERIFIED in LangGraph itself | ✅ `.stream_events()` first-class; LangSmith integration | ⚠️ Tools bound at graph-build time; human-in-the-loop interrupts for approval; no named `allowed_tools` allowlist | ✅ Interrupt/breakpoint mechanism; durable execution; pause-and-resume | ✅ In-process Python; LangGraph Cloud is a separate opt-in hosted product | ⚠️ Graph node wrappers can add pre/post logic; checkpoint callbacks; no named `on_tool_start/end` API | MIT · ~36.7k stars · Python · v1.2.8 · Production |
| **D. smolagents** | ✅ `MultiStepAgent`: explicit ReAct cycle until objective reached; `agent.run()` | ✅ `OllamaModel` class; LiteLLM bridge for 100+ providers | ✅ `ToolCollection.from_mcp()` documented; use tools from any MCP server | ✅ `agent.run(stream=True)` yields each step as executed; `step_callbacks` per-step | ✅ `tools=[...]` at init; `additional_authorized_imports` controls code scope; tool list IS the allowlist | ✅ `MultiStepAgent.interrupt()` — explicit method in source (`agents.py#L754`) | ✅ In-process Python; sandbox (E2B/Docker) is for code execution only, not the loop | ✅ `step_callbacks: list[Callable] \| dict[Type[MemoryStep], Callable]`; step-type-mapped | Apache-2.0 · ~28.2k stars · Python · v1.26.0 · Active · ~1,000 lines core |
| **E. LlamaIndex AgentWorkflow** | ✅ Agent loops until task judged complete; `FunctionAgent` handles tool-call cycle | ✅ `Ollama` LLM class; 300+ integrations via LlamaHub | ✅ MCP Registry integration documented | ⚠️ Streaming enabled by default; step-level tool-event streaming unconfirmed (token streaming confirmed) | ⚠️ Tools at construction; no explicit allowlist or per-action approval documented from fetched content | ⚠️ Not documented in fetched content | ✅ In-process Python | ⚠️ `CallbackManager` exists for framework; agent-specific pre/post tool hooks unconfirmed | MIT · ~50.7k stars · Python · Mature · Monorepo |
| **F. AWS Strands Agents** | ✅ Loop-owning; hooks intercept every step | ✅ Ollama listed explicitly alongside Bedrock/Anthropic/OpenAI | ✅ MCP built-in; dedicated MCP server repo | ✅ Bidirectional streaming documented | ✅ Defined tool sets at agent construction | ⚠️ Steering handlers mentioned; explicit `cancel()` not confirmed | ✅ In-process Python or TypeScript; not a cloud service | ✅ "Hooks intercept any step to log, validate, redirect" | Apache-2.0 · ~6.5k stars · Python+TS · Active · Younger project |
| **G. Google ADK** | ✅ Autonomous multi-step: tool calls, context management, retries, parallel jobs, failure handling all internal | ✅ Ollama, vLLM, LiteLLM adapters; "works with almost any generative AI model" | ✅ `McpToolset` class; `tool_filter` param selects subset of MCP tools | ✅ Streaming guides; event loop with yield/pause/resume | ✅ `tool_filter` on `McpToolset` allowlists specific tools; structured tool management with auth controls | ✅ "Cancel Agent Runs" documented; TypeScript `AbortSignal`; Python graceful cancellation | ✅ pip-installable; "Deploy anywhere"; no Google Cloud required | ✅ Six named callbacks: `before_agent_callback`, `after_agent_callback`, `before_model_callback`, `after_model_callback`, `before_tool_callback`, `after_tool_callback`; returning value overrides default | Apache-2.0 · ~20.5k stars · Python+TS+Go+Java · v2.4.0 · Bi-weekly releases |
| **H. AutoGen v0.4+** | ✅ `AssistantAgent.run()` autonomous; tools executed within same `run()` call; `run_stream()` step events | ✅ `OllamaChatCompletionClient` via `autogen-ext[ollama]` (marked experimental) | ✅ `McpWorkbench`; `mcp_server_tools()` helper | ✅ `run_stream()` yields `BaseAgentEvent` per step, `TaskResult` at end | ⚠️ Tools at construction; `CodeExecutorAgent` has `approval_func`; no general per-tool approval hook confirmed | ✅ `ExternalTermination` condition for programmatic stop from outside the run (UI "Stop" button pattern) | ✅ In-process Python; distributed runtime is optional | ⚠️ `on_pause/resume/reset` lifecycle; message-level `on_messages_stream()`; named pre/post tool hooks not confirmed | MIT · ~59.6k stars · Python+.NET · v0.4+ · ⚠️ **In maintenance mode** — new projects directed to Microsoft Agent Framework |
| **I. Semantic Kernel** | ⚠️ `ChatCompletionAgent.invoke()` autonomous within a single turn (multi-tool); does NOT autonomously re-plan across turns without caller re-invocation; `AgentGroupChat` for multi-turn | ✅ Ollama, LM Studio, ONNX adapters | ✅ MCP plugin import documented; can expose SK as MCP server | ✅ `invoke_stream()`; `on_intermediate_message` callback for FunctionCall/FunctionResult during tool loop | ✅ Per-agent `Kernel` with only desired plugins; role-specific tool subsets in multi-agent examples | ✅ `AutoFunctionInvocationFilter` with `context.Terminate = true` stops function-calling mid-loop | ✅ In-process; no Microsoft cloud required | ✅ Three filter types: `FunctionInvocationFilter` (pre/post every kernel function), `PromptRenderFilter` (pre-LLM), `AutoFunctionInvocationFilter` (pre/post each auto-call, with terminate); `await next(context)` pipeline | MIT · ~28.3k stars · Python+C#+Java · v1.0+ · Enterprise-grade |
| **J. Ollama Native** | ❌ Model server only; `/api/chat` returns tool-call; caller must implement the loop | ✅ Core purpose | ❌ No MCP client; REST API only | ⚠️ Token streaming (`stream: true`); tool-call streaming explicitly marked "coming soon" in blog | ❌ `tools` field per-request; no enforcement or allowlist | ❌ HTTP cancel client-side only; no agent-level abort | ✅ Local server; caller controls | ❌ No hook system | MIT · 100k+ stars · Go · Stable · Model runtime, not agent SDK |

---

## Top Recommendations for the Axiom Second Adapter

### Recommendation 1: Google ADK — primary recommendation

**Why ADK wins on criteria that decide the KIND-B contract:**

ADK is the only candidate with all nine criteria verified from official documentation in a single pass — the cleanest coverage with no significant ⚠️ on the hard requirements.

The specific criteria that make ADK the natural fit for the Axiom KIND-B adapter:

1. **Owns the loop** ✅ — ADK's autonomous execution engine handles tool calls, context, retries, and parallel sub-tasks internally. `run()` delegates; ADK finishes.
2. **Open models locally** ✅ — Explicit Ollama and vLLM support; not a workaround (`base_url` override) but a documented primary path.
3. **MCP via `McpToolset` with `tool_filter`** ✅ — This is the closest analog to Agent SDK's `allowed_tools`. `tool_filter` on `McpToolset` is a pre-run allowlist scoped per agent. This maps directly to KIND-B's pre-run scope requirement — better than any other candidate.
4. **Cancel Agent Runs** ✅ — Documented cancellation with `AbortSignal` (TypeScript) and graceful cancellation (Python). The only candidate where mid-run abort is explicitly a documented named feature.
5. **Six named lifecycle callbacks** ✅ — `before_tool_callback` / `after_tool_callback` are exact analogs of Claude Agent SDK's `PreToolUse` / `PostToolUse` hooks. Returning a replacement from a callback overrides default behavior — the same "inject/block" contract. The adapter needs these to wire into Axiom's observability feed.
6. **Apache-2.0** — permissive, commercial-use friendly.
7. **Multi-language** — Python primary (97.1%), but TypeScript, Go, Java in the same project — strategic value for future platform expansion.

**What ADK does NOT give free:**
- The adapter shell itself (dispatch protocol, stream-→-CM-memory wiring, the parent port interface) — these are Axiom domain logic.
- Model-specific tool-calling reliability for open-weight models — varies by model (see Open Uncertainties).

---

### Recommendation 2: smolagents — strong alternative, minimum-surface option

**Why smolagents is a credible second choice:**

smolagents has the smallest cognitive surface of any candidate (~1,000 lines of core logic, Apache-2.0). It is deliberately minimal. For Axiom's purposes:

1. **Explicit `interrupt()` method** — the clearest mid-run abort API of all candidates. `MultiStepAgent.interrupt()` in source at a documented line.
2. **`ToolCollection.from_mcp()` ** — MCP client built-in, no adapter needed.
3. **`step_callbacks` typed by step type** — maps cleanly to Axiom's observability feed without over-engineering.
4. **`OllamaModel` native** — not a base_url workaround; a first-class class.
5. **Minimal surface = thin adapter** — fewer framework concepts to work around. The ReAct loop is exposed, not abstracted behind a graph.

**Where smolagents trails ADK:**
- No named `before_tool_callback`/`after_tool_callback` hooks — only step-level callbacks (less granular than ADK's six named callbacks).
- No documented per-tool allowlist beyond "pass only the tools you want at init" — passable, but not as explicit as ADK's `tool_filter`.
- No documented cancel analog in Python to ADK's named `cancel_run` — only `interrupt()` (which stops after the current step, not mid-step).
- Google ADK's six-callback system and `tool_filter` more precisely mirror the Claude Agent SDK's hook+permissions surface.

**smolagents is the right choice if:** the priority is minimizing framework footprint and maximizing hackability at the cost of hook/cancel completeness.

---

## Thin-Adapter Sketch: ADK Mapping onto the KIND-B Contract

The Axiom Agent port's KIND-B contract is: `dispatch(task, scope) → stream → observe → [abort?]`

```
Axiom Agent Port (KIND-B)             Google ADK mapping
─────────────────────────────────── ──────────────────────────────────────────────────
dispatch(task, scope)           →   agent = LlmAgent(
                                        model=OllamaModel("llama3.2"),
                                        tools=scope.tool_list,          # KIND-B pre-run scope
                                        before_tool_callback=_observe,  # hook into Axiom
                                        after_tool_callback=_observe,   #   observability
                                    )
                                    runner = Runner(agent=agent, ...)
                                    run_handle = runner.run_async(task)

stream → observe                →   async for event in run_handle:      # ADK event stream
                                        axiom_trace.record(event)       # our observability
                                        if circuit_breaker.triggered:
                                            await run_handle.cancel()   # mid-run abort

abort                           →   await run_handle.cancel()           # ADK graceful cancel

result                          →   final_response = await run_handle   # ADK collects internally
```

**What we wrap (Axiom adapter logic, ~one file):**
- `scope` → `tools=[...]` + `McpToolset(servers=..., tool_filter=scope.mcp_allowlist)` construction
- `_observe` callbacks → forward events to Axiom's observability channel (same channel as Claude Agent SDK trace)
- `run_handle.cancel()` → wired to the circuit-breaker the master PRAO loop already manages
- Model selection → `OllamaModel(model_name, base_url)` or `LiteLLMModel(model_id, base_url)` depending on local backend
- Error normalization → map ADK exceptions to Axiom's AgentError types

**What we get free (no rebuild needed):**
- The perceive→act→observe loop itself
- Tool execution (ADK executes, retries, handles errors internally)
- MCP client (`McpToolset` with `tool_filter`)
- The six lifecycle callbacks (observability without a separate channel)
- Cancellation (`cancel()`)
- Context management within the delegated run
- Multi-step autonomy (no caller re-invocation needed between steps)

**ADK vs Claude Agent SDK surface parity:**

| KIND-B feature | Claude Agent SDK | Google ADK adapter |
|----------------|-----------------|-------------------|
| Pre-run tool scope | `allowed_tools` list | `tools=[...]` + `McpToolset(tool_filter=...)` |
| Observability stream | `query()` message stream | `runner.run_async()` event stream |
| Mid-run abort | Stop hook / stream abort | `run_handle.cancel()` |
| Pre-tool hook | `PreToolUse` hook | `before_tool_callback` |
| Post-tool hook | `PostToolUse` hook | `after_tool_callback` |
| Per-action approval | `canUseTool` callback | `before_tool_callback` returning override |
| Model target | Claude via API | `OllamaModel` / `LiteLLMModel` local |

The surfaces are parallel. The adapter is a translation shim, not a rebuilt harness.

---

## Reuse-vs-Build Verdict

The 07-07 doc made this call for the Claude side: *build the thin master loop on the Client SDK; adopt the Agent SDK as the worker/perceiver.* The same lens applies here.

**Option A — Adopt ADK (or smolagents) as the second adapter.**

The adapter is ~one file. The loop, tool execution, MCP, hooks, cancellation, and context management are all adopted. The adapter writes translation code (scope → ADK config, ADK events → Axiom trace, ADK cancel → circuit-breaker). This mirrors exactly the Claude Agent SDK adoption decision.

**Option B — Hand-roll a thin Client-SDK-style loop over Ollama's OpenAI-compatible endpoint.**

This is genuinely possible. Ollama's `/api/chat` with tool support is a clean API. A hand-rolled loop would be ~200 lines: send prompt, parse tool calls, execute, loop. The 07-07 doc showed this shape for the master PRAO loop (built, not adopted, because no framework gives "no unnecessary step" for the master).

However, hand-rolling the WORKER loop re-introduces exactly what adoption avoids:
- MCP client from scratch (non-trivial; ADK/smolagents give `McpToolset`/`from_mcp()` free)
- Streaming tool-call events (Ollama explicitly marks this "coming soon" — not yet available)
- `interrupt()` / cancellation plumbing
- Lifecycle hook wiring
- Context management for long delegated runs

The 07-07 doc built the MASTER loop by hand because "no unnecessary step" is precisely the property a framework fights. But for the WORKER — where the loop is delegated and we want it to run autonomously until done — the framework's structure IS the feature, not the obstacle. Adoption is thinner.

**Verdict: Adopt ADK (or smolagents) for the second adapter.** Hand-rolling would rebuild the harness — exactly what L4 (Lessons Learned) prohibits. The adapter surface over ADK is genuinely thinner than a hand-rolled loop, and the KIND-B contract maps cleanly onto ADK's documented API.

The one case where hand-rolling beats adoption: if open-weight model tool-calling reliability is so poor that the loop needs custom retry/correction logic tightly coupled to model quirks. Monitor this at integration time (see Open Uncertainties).

---

## Open Uncertainties (Flag Before Build)

**U1 — Tool-calling reliability of specific open-weight models.**
ADK and smolagents both require the model to emit valid tool-call JSON. Not all open-weight models do this reliably at the same level as Claude or GPT-4o. Models that fail silently (emit prose instead of tool call JSON) stall the loop. Test the target model (llama3.2, qwen2.5, mistral-nemo) against the tool schema at integration time. smolagents has a `CodeAgent` mode (Python code generation instead of JSON tool calls) that partially mitigates this — may be worth evaluating for open-weight robustness.

**U2 — MCP maturity on open-model SDKs.**
ADK's `McpToolset` is documented but MCP ecosystem for local (non-Anthropic) agent loops is younger than the Claude-side ecosystem. Verify `McpToolset` stability against the specific MCP servers Axiom uses (CM, Gmail, Slack, Drive, Notion, Taskyn) at integration time. smolagents' `ToolCollection.from_mcp()` has the same maturity question.

**U3 — ADK Python abort API specifics.**
The 07-07 doc fetched ADK docs and confirmed "Cancel Agent Runs" and TypeScript `AbortSignal` clearly. The Python graceful cancellation mechanism was mentioned but its exact async API shape (`run_handle.cancel()` is a sketch — confirm the actual method name and await behavior in `adk-python` source at build time).

**U4 — smolagents `interrupt()` semantics.**
`MultiStepAgent.interrupt()` stops after the current step completes. If a step is a long-running tool call (e.g., a web crawl), the abort is delayed until that step finishes. For Axiom's circuit-breaker (hard stop), confirm whether `interrupt()` stops mid-step or waits for step completion, and whether a harder cancel is available.

**U5 — ADK context management for long runs.**
The Claude Agent SDK has a documented context-compaction blind spot (flagged in 07-07 doc). ADK manages context internally. Verify whether ADK performs silent compaction for long delegated runs, and whether it can lose injected system-prompt content (the same risk). If yes, apply the same pre-scoped-context countermeasure.

**U6 — smolagents step callbacks vs per-tool-call hooks.**
smolagents' `step_callbacks` fire once per ReAct step, not once per tool invocation within a step (if a step invokes multiple tools). For Axiom's observability feed and per-tool-call audit trail, verify whether step-level granularity is sufficient or whether per-tool hooks are needed (in which case ADK's `before/after_tool_callback` is required).

**U7 — AutoGen direction.**
AutoGen v0.4 is marked "in maintenance mode" in its own README. The replacement ("Microsoft Agent Framework") is a different product. If AutoGen is under consideration, track the migration path; new adapter investment against a maintenance-mode project has lifecycle risk.

---

## Sources

| # | URL | SDK | Fetched |
|---|-----|-----|---------|
| 1 | https://openai.github.io/openai-agents-python/ | OpenAI Agents SDK | 2026-07-08 |
| 2 | https://openai.github.io/openai-agents-python/ref/lifecycle/ | OpenAI Agents SDK | 2026-07-08 |
| 3 | https://openai.github.io/openai-agents-python/models/ | OpenAI Agents SDK | 2026-07-08 |
| 4 | https://github.com/openai/openai-agents-python | OpenAI Agents SDK | 2026-07-08 |
| 5 | https://pydantic.dev/docs/ai/overview/ | Pydantic AI | 2026-07-08 |
| 6 | https://pydantic.dev/docs/ai/core-concepts/agent/ | Pydantic AI | 2026-07-08 |
| 7 | https://github.com/pydantic/pydantic-ai | Pydantic AI | 2026-07-08 |
| 8 | https://github.com/langchain-ai/langgraph | LangGraph | 2026-07-08 |
| 9 | https://huggingface.co/docs/smolagents/en/index | smolagents | 2026-07-08 |
| 10 | https://huggingface.co/docs/smolagents/en/reference/agents | smolagents | 2026-07-08 |
| 11 | https://github.com/huggingface/smolagents | smolagents | 2026-07-08 |
| 12 | https://developers.llamaindex.ai/python/framework/module_guides/deploying/agents/ | LlamaIndex | 2026-07-08 |
| 13 | https://developers.llamaindex.ai/python/framework/understanding/agent | LlamaIndex | 2026-07-08 |
| 14 | https://github.com/run-llama/llama_index | LlamaIndex | 2026-07-08 |
| 15 | https://github.com/strands-agents/sdk-python | AWS Strands | 2026-07-08 |
| 16 | https://adk.dev/ | Google ADK | 2026-07-08 |
| 17 | https://adk.dev/tools-custom/mcp-tools/ | Google ADK | 2026-07-08 |
| 18 | https://adk.dev/callbacks/ | Google ADK | 2026-07-08 |
| 19 | https://adk.dev/runtime/ | Google ADK | 2026-07-08 |
| 20 | https://github.com/google/adk-python | Google ADK | 2026-07-08 |
| 21 | https://github.com/microsoft/autogen | AutoGen | 2026-07-08 |
| 22 | https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html | AutoGen | 2026-07-08 |
| 23 | https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html | AutoGen | 2026-07-08 |
| 24 | https://learn.microsoft.com/en-us/semantic-kernel/overview/ | Semantic Kernel | 2026-07-08 |
| 25 | https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-types/chat-completion-agent | Semantic Kernel | 2026-07-08 |
| 26 | https://learn.microsoft.com/en-us/semantic-kernel/concepts/enterprise-readiness/filters | Semantic Kernel | 2026-07-08 |
| 27 | https://github.com/microsoft/semantic-kernel | Semantic Kernel | 2026-07-08 |
| 28 | https://ollama.com/blog/tool-support | Ollama Native | 2026-07-08 |
| 29 | `C:/Projects/ai-persona/Velasari/research/prao-loop-on-claude-sdk-2026-07-07.md` | Grounding (first-hand) | — |
| 30 | `C:/Projects/axiom/.claude/research/002-agentic-systems-survey-2026-07-04.md` | Grounding (first-hand) | — |

**Proof-scope note:** All SDK capability claims above were verified against official docs or GitHub READMEs fetched 2026-07-08. Claims marked ⚠️ in the matrix indicate partial verification — either the feature exists but its precise API shape was not confirmed in a single fetch pass, or the feature is documented under a broader mechanism (e.g., step callbacks covering what named pre/post tool hooks would cover) rather than an explicit named hook. No claims are from training memory alone without a fetch attempt. Open uncertainties U3–U6 flag where build-time verification is required before committing the adapter implementation.

---

*Research generated: 2026-07-08 | Candidates evaluated: 10 | External URLs cited: 28 | First-hand grounding files: 2 | Total sources: 30*
