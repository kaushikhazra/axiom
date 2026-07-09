# Local-Model Tool-Providing SDK Landscape -- and the smolagents Decision

**Date:** 2026-07-09
**Method:** Live web sweep (WebSearch/WebFetch against official docs, GitHub issues, and framework
documentation, fetched 2026-07-09). All capability claims grounded from fetched sources or flagged.
**Status:** Decision doc. Supersedes the tool-provenance portion of
`003-oss-agentic-sdk-second-adapter-2026-07-08.md`.
**One-line question:** Which OSS agentic SDK, for a LOCAL open-weight model, ships GENERAL tools that
actually EXECUTE (not just schema), so the Axiom local adapter authors zero tool code -- the same deal
the Claude Agent SDK gives the ClaudeAdapter?

---

## Why this doc exists (the criterion the 07-08 doc never scored)

The 07-08 research (`003-...`) ranked Google ADK #1 and smolagents #2 -- but it scored them on the
KIND-B loop contract (owns-the-loop, hooks, cancel, MCP, streaming). It never scored the thing that
actually turned out to matter: **does the SDK bring general tools that run against a LOCAL model,
executed for you, the way Claude's SDK brings Bash + WebSearch.**

That gap produced a real defect. The autonomous local-adapter build (spec 003) dropped ADK and
hand-rolled its own `_execute_shell_tool` (a bare `subprocess.run` with a 30s timeout, no allowlist, no
sandbox). The stated reason -- "direct LiteLLM gives full control over the tool-calling loop" -- only
answered whether ADK should own the LOOP (correctly no; the Axiom PRAO loop is the driver). It never
answered why ADK was chosen in the first place: `McpToolset` scoping, six before/after tool callbacks,
and `cancel()`. Those were lost silently, and the security surface moved onto us. This doc re-decides on
the correct criterion.

---

## The sharpened criterion

An SDK qualifies only if ALL hold:

1. **OSS + model-agnostic** -- runs local open-weight models (Ollama / LiteLLM / vLLM), not locked to
   one vendor's cloud model.
2. **Ships GENERAL tools** -- at minimum general web search and general code execution (primitives that
   compose to anything), not one tool per use-case.
3. **Tools EXECUTE locally / in-process** -- NOT server-side-locked to the vendor's own model
   infrastructure.

Criterion 3 is the sharp one. Several SDKs "have" web-search and code-exec tools that only run on the
vendor's servers against the vendor's model. Point them at a local model and the tools vanish.

---

## Key correction logged: Claude SDK CAN run local models

An earlier claim in this investigation -- "the Claude Agent SDK runs Claude models only" -- was WRONG
and is corrected here. As of January 2026, Ollama added native support for the Anthropic Messages API.
Claude Code / the Agent SDK can be pointed at a local model via `ANTHROPIC_BASE_URL` (Ollama >= v0.14.0
native endpoint, or a LiteLLM proxy on `/v1/messages`).

BUT the tools split on exactly criterion 3:

- **Client-side tools (Bash, Read, Write, Edit, Glob, Grep)** execute on the user's machine; the model
  only emits the tool call. These DO carry to a local model (needs Ollama pre-release for streaming tool
  calls; and the local model must emit valid tool calls reliably).
- **Server-side tools (WebSearch, and likely WebFetch)** are executed by Anthropic's infrastructure.
  On a non-first-party backend Claude Code HIDES WebSearch entirely (same behavior as Bedrock/Vertex).
  So NO web search on a local model.

This means a real, previously-flattened option exists: **ClaudeAdapter + `ANTHROPIC_BASE_URL` -> Ollama**
gives a local model plus hardened Bash/file-exec for free, covering E2E #1 (hello) and #3 (write+run
Python) by reusing the adapter we already have. Only E2E #2 (web search) is missing. It is recorded here
as a viable alternative but NOT the chosen path (see Decision; it fails the "one clean SDK, no hybrid"
goal because web search still has to come from somewhere else, and it carries the attribution-header
slowdown + field-stripping-proxy caveats below).

---

## The provider-server-lock pattern (why the big-name SDKs fail on local)

| SDK | Web search tool | Code-exec tool | On a LOCAL model? |
|-----|-----------------|----------------|-------------------|
| **Google ADK** | `google_search` | `BuiltInCodeExecutor` | NO -- both are Gemini-server-executed; `LlmRegistry` only registers Gemini. Loop/hooks/cancel work via LiteLLM; the built-in TOOLS do not reach local models. |
| **OpenAI Agents SDK** | `WebSearchTool` | `CodeInterpreterTool` | NO -- hosted tools run on OpenAI infra, tied to the Responses model. Switch to local via LiteLLM and they are unavailable. |
| **Claude Agent SDK** | `WebSearch` (server) | `Bash` (client-side) | PARTIAL -- Bash/file-ops run local; WebSearch is hidden on local backends. |

Grounded from ADK GitHub issues (unsupported-model / Gemini-only tool registry), OpenAI Agents SDK docs
(hosted-tools require OpenAI Responses model), and Claude Code + Ollama integration docs.

---

## SDKs that DO ship local-running general tools (the qualifiers)

| Framework | OSS + local/model-agnostic | Ships local-running general tools | Ergonomics / note |
|-----------|----------------------------|-----------------------------------|-------------------|
| **smolagents** (HF) | Yes (LiteLLM/Ollama) | Yes -- `DuckDuckGoSearchTool` + `PythonInterpreterTool` via `add_base_tools=True`; also VisitWebpage, Wikipedia, Transcriber | ~1,000-line core; **CodeAgent acts by writing Python, not JSON tool-calls** |
| **Agno** (ex-phidata) | Yes (30+ providers) | Yes -- DuckDuckGo / Python / Shell toolkits execute in-process | Closest true peer; performance-focused, batteries-heavy, opinionated (own memory/knowledge/runtime) |
| **CrewAI** | Yes (Ollama) | Yes -- 60+ tools (search, code-exec via Docker, file I/O, SQL) | Multi-agent-orchestration-first; best search tools (Serper) need API keys |
| **LangChain / LangGraph** | Yes (ChatOllama) | Yes -- `PythonREPLTool` + DuckDuckGo local (Tavily needs key) | Powerful but assembly-heavy; `deepagents` is its batteries harness |
| **Pydantic AI** | Yes | Partial -- "common tools" (DuckDuckGo, ddgs, no key) run LOCAL; its "built-in tools" code-exec is provider-server-side | Explicitly documents the local-vs-server split -- validates criterion 3 |
| **LlamaIndex** | Yes | Yes, but more BYO/assembly (no one-flag base toolbox) | Not "batteries in one flag" |

Also surfaced and worth knowing:
- **Open Interpreter** -- local-first code-execution specialist (no data leaves the machine).
- **Pydantic DeepAgents** (vstorm-co) -- self-hosted "Claude Code" clone: tool-calling + sandboxed
  execution + multi-agent, on Pydantic AI, any model, local.
- **Microsoft Agent Framework** (AutoGen successor), **Dify** (self-hosted platform) -- model-agnostic
  with tools/MCP.

---

## The golden (negative) result: no monopoly, no white-space

The motivating hope was: if one provider monopolizes "general tools for local models," that gap is a
build opportunity. It is not. The space is **saturated** -- at least six frameworks clear the full
criterion, plus local-first specialists. Building our own batteries-included local-agent SDK would be
reinventing a crowded wheel. **Adopt, do not build.** The negative result is itself the valuable finding:
do not spend effort here; there is no monopoly to break.

---

## Decision: smolagents -- and NOT for the reason it first looks like

The naive read is "smolagents because CodeAct." That is the tiebreaker, not the primary reason. The
primary reason is architectural fit, and it is the exact answer to the fair objection "Agno and CrewAI
have far bigger ecosystems -- why pick the small one?"

**Because a vast ecosystem is a LIABILITY behind a thin adapter, not an asset.**

Axiom is ports-and-adapters. Memory (Cognitive Memory), orchestration (the PRAO loop + conductor),
connectors, and skills are each their OWN port that Axiom already owns. The SDK behind the local adapter
fills exactly ONE slice: run a local model through a tool-using loop and hand back intents. Agno's and
CrewAI's batteries -- RAG, multi-agent teams, memory subsystems, 30-60 integrations, production runtimes
-- all live OUTSIDE that slice. Adopting one means using ~5% of it while the other 95% is dead weight or,
worse, collides with the Axiom ports that already do those jobs. That is bloat and hybridization one
layer down -- exactly what we are avoiding.

smolagents' ~1,000-line minimal core IS the feature here: a thin adapter with almost nothing to work
around.

Two reasons, same direction:

1. **PRIMARY -- minimalism fits a thin adapter.** Least surface to wrestle; least framework worldview to
   fight against Axiom's own ports.
2. **TIEBREAKER -- CodeAct reliability on weak local models.** smolagents' default CodeAgent acts by
   writing Python instead of emitting JSON tool-calls. On a weak local model like qwen2.5:7b -- which
   tool-calls unreliably (the exact failure the hand-rolled build hit: looping ACT after tool output) --
   code-as-action is materially more robust. Agno and CrewAI assume the model JSON-tool-calls well;
   qwen does not.

### Boundary note (keep the thin-adapter honest)

Each Agent adapter brings its PROVIDER's native tools -- the ClaudeAdapter already brings Bash/WebSearch
from the Claude SDK; the local adapter brings DuckDuckGo/PythonInterpreter from smolagents. This is
consistent parity, not a new pattern. The SDK's tools belong to the Agent-adapter slice; they do not
route through, replace, or duplicate Axiom's separate Tools/Connectors/Memory/Skills ports. If a future
milestone wants provider-neutral tools across adapters, that is a Tools-port question, out of scope here.

---

## Open caveats to verify at build time

- **U1 -- qwen2.5:7b under smolagents CodeAgent.** CodeAct is more robust than JSON tool-calls, but
  confirm qwen2.5:7b produces valid, executable Python actions reliably in the live E2E.
- **U2 -- PythonInterpreter sandbox hardening.** smolagents' default local Python execution is the SDK's
  own implementation (not our raw subprocess), but confirm the sandbox posture (local interpreter vs
  E2B/Docker option) is acceptable before anything runs beyond the dev laptop. This is the security gap
  the migration is meant to CLOSE, so do not reintroduce it.
- **U3 -- web search quality.** `DuckDuckGoSearchTool` uses the ddgs library, no API key. Confirm it
  returns usable results for E2E #2 (current weather in Durgapur, West Bengal) without rate-limit flaps.
- **U4 -- LiteLLM/Ollama wiring.** `LiteLLMModel(model_id="ollama_chat/qwen2.5:7b", api_base=...)` is
  the documented local path; pre-warm the model before timing for a fair latency number.

---

## E2E coverage under smolagents

| E2E | Requirement | smolagents mechanism |
|-----|-------------|----------------------|
| #1 | "hello" -- RESPOND only | Model responds; no tool |
| #2 | current weather in Durgapur, West Bengal, India | `DuckDuckGoSearchTool` (general web search, local) |
| #3 | create a Python file, execute it, show output | `PythonInterpreterTool` / CodeAgent (writes + runs Python, local) |

All three covered by shipped smolagents tools; zero Axiom-authored tool code.

---

## Sources

Grounded 2026-07-09 via WebSearch/WebFetch:
- Google ADK docs + adk-python GitHub issues (Gemini-only tool registry; built-in tools model scope)
- OpenAI Agents SDK docs (hosted tools require OpenAI Responses model)
- Claude Code + Ollama integration docs; Ollama Anthropic-Messages-API blog (Jan 2026); ANTHROPIC_BASE_URL
  local-model guides; Claude Code web-tools writeups (WebSearch server-side)
- smolagents docs (default toolbox, add_base_tools, CodeAgent, LiteLLM/Ollama)
- Agno / phidata docs (model-agnostic providers, toolkits)
- CrewAI docs + GitHub (60+ tools, Ollama support)
- Pydantic AI docs (common tools local vs built-in server-side split)
- LangChain/LangGraph + Ollama integration docs; deepagents
- LlamaIndex AgentWorkflow + Ollama docs

Prior grounding: `003-oss-agentic-sdk-second-adapter-2026-07-08.md`.

---

*Decision: adopt smolagents for the Axiom local-model adapter. Primary rationale: minimalism fits a thin
adapter (a vast ecosystem is a liability behind a one-slice adapter, not an asset). Tiebreaker: CodeAct
robustness on weak local models. Adopt-not-build confirmed by a saturated landscape.*
