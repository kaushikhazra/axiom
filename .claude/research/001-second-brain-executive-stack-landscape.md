# Executive Second Brain: Platform Landscape & Stack Selection

**Date**: 2026-07-02
**Context**: Discovery research to select an assembled stack (no custom build) for a CEO-grade executive augmentation "Second Brain" — Claude orchestrator on personal machine, NVIDIA DGX Spark 128GB for local cost-tiering inference, multi-user rollout to department heads, non-coder self-serve workflows, polished web app, ~2-week solo assembly.
**Status**: Research complete

---

## Hard Constraints (scored against throughout)

| Constraint | Implication for Scoring |
|---|---|
| Orchestrator = Claude (cloud), fans out to DGX Spark 128GB (local) | **TOP axis**: cloud+local model routing built-in, not bolted on |
| Cost-tier driver: ECONOMICS, not privacy (Claude may see content) | Route cheap/bulk inference local; reserve Claude for hard reasoning |
| Full exec augmentation: retrieve, draft, agent tasks, decision support | Agentic capability beyond simple RAG is required |
| Multi-user: CEO to dept heads; per-dept knowledge partitioning | RBAC + workspace isolation non-negotiable |
| Non-coder extension: dept heads build own workflows | A real no-code visual builder layer is required |
| Connectors: email/Slack/GDrive as defaults; MCP + REST + Python | Open connector architecture mandatory |
| CEO-grade polish | Web app UX must compare to Glean/Notion/Slack, not a dev tool |
| ~2 weeks, solo builder | Strongly favors mature + self-hostable over anything needing heavy custom build |

---

## Section 1 — Scored Agent-Harness / Orchestration Inventory

### Scoring Key (1 = absent/unusable, 5 = best-in-class)

Twelve axes evaluated per tool:
1. **Cloud+local model routing** — first-class support for routing between Anthropic API and local OpenAI-compatible endpoints (Ollama/vLLM)
2. **MCP-native** — Model Context Protocol support for standardized tool/integration connections
3. **Custom code / Python execution** — ability to run arbitrary code inside workflows
4. **Multi-agent orchestration** — coordinating multiple specialized agents or workflow steps
5. **Memory / state** — persistent state across sessions; knowledge base integration
6. **Multi-user + permissions / governance** — built-in RBAC, teams, org-level access control
7. **Non-coder no-code builder** — drag-and-drop or visual workflow builder usable without coding
8. **Polish / UX maturity** — web UI quality (if any); developer experience
9. **Project maturity / community** — GitHub stars, release cadence, ecosystem
10. **Claude-ecosystem fit** — native Claude support, Anthropic alignment
11. **Self-host / licensing / cost** — open license, self-deployable, no surprise commercial gates
12. **2-week assemble feasibility** — realistic MVP achievable by one person in 14 days

---

### 1.1 Claude Agent SDK / Claude Code (Headless)

**GitHub**: https://github.com/anthropics/anthropic-sdk-python | **Stars**: ~12K | **License**: MIT
**Docs**: https://docs.anthropic.com/en/docs/claude-code/sdk

Official Anthropic Python/TypeScript SDK plus Claude Code's headless/subprocess SDK. The native orchestration layer for Claude — full Anthropic Messages API, tool-use, streaming, and native MCP client support added in 2025. A **developer library**, not a platform: no web UI, no multi-user layer, no local-LLM routing.

**Verdict for this project**: Best-in-class for the agent-logic layer within a larger assembly; cannot stand alone.

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 1 | API-only; local model routing requires external proxy (LiteLLM) |
| MCP-native | **5** | Full native MCP client support, official spec implementer |
| Custom code/Python | 4 | Full SDK; arbitrary Python callable as tools |
| Multi-agent orchestration | 4 | Supports handoffs and sub-agent patterns via SDK |
| Memory/state | 2 | No built-in; requires external vector/DB |
| Multi-user+permissions | 1 | Library only; no auth or user concept |
| No-code builder | 1 | Developer-only; zero visual tooling |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 4 | Official Anthropic; actively maintained |
| Claude-ecosystem fit | **5** | Native; built by Anthropic |
| Self-host/license/cost | 5 | MIT; API costs only |
| 2-week feasibility | 2 | Needs full platform wrap around it |
| **TOTAL** | **35/60** | |

---

### 1.2 LangGraph

**GitHub**: https://github.com/langchain-ai/langgraph | **Stars**: ~8K | **License**: MIT
**Docs**: https://langchain-ai.github.io/langgraph/

State-graph orchestration engine from LangChain. Define agents as nodes and edges in a directed graph; supports cycles, branching, human-in-the-loop. Excellent for complex multi-step reasoning chains. No UI; no native MCP; multi-user requires paid LangSmith (cloud SaaS).

**Developer-facing only.** Dept heads cannot build workflows here.

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 4 | Supports Ollama, any OpenAI-compatible endpoint |
| MCP-native | 2 | Via LangChain tool integrations; not direct MCP |
| Custom code/Python | 5 | Full Python graph definition |
| Multi-agent orchestration | 5 | Core strength; stateful graph execution |
| Memory/state | 4 | Graph-native state management; integrates checkpointers |
| Multi-user+permissions | 1 | None built-in; LangSmith (paid SaaS) adds this |
| No-code builder | 1 | Code-only — developer-facing |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 4 | ~8K stars; backed by LangChain Inc. |
| Claude-ecosystem fit | 3 | Claude supported but not native |
| Self-host/license/cost | 4 | MIT; LangSmith (for multi-user) is paid |
| 2-week feasibility | 2 | Needs multi-user wrapper + UI |
| **TOTAL** | **36/60** | |

---

### 1.3 CrewAI

**GitHub**: https://github.com/crewAIInc/crewAI | **Stars**: ~9K | **License**: MIT
**Docs**: https://docs.crewai.com

Purpose-built "crew of agents" framework. Agents have roles, backstories, and goals; a Crew coordinates them via tasks. Strong for advisory-board-style multi-agent teams. No MCP, no visual builder, no multi-user.

**Developer-facing only.**

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 3 | Ollama supported; OpenAI-compatible endpoints |
| MCP-native | 1 | No MCP support |
| Custom code/Python | 5 | Python-native |
| Multi-agent orchestration | 5 | Core strength; role-based agent teams |
| Memory/state | 3 | Basic agent memory; external DB needed |
| Multi-user+permissions | 1 | Single-orchestration design; no user concept |
| No-code builder | 1 | Python only — developer-facing |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 4 | ~9K stars; active development 2025 |
| Claude-ecosystem fit | 3 | Claude models supported |
| Self-host/license/cost | 5 | MIT, free |
| 2-week feasibility | 2 | Needs UI + multi-user wrap |
| **TOTAL** | **34/60** | |

---

### 1.4 AutoGen / AG2

**GitHub**: https://github.com/microsoft/autogen | **Stars**: ~12K | **License**: Apache 2.0
**Docs**: https://ag2.ai

Microsoft's conversable-agent framework. Agents can execute code, call APIs, and converse with each other and humans. Enterprise-grade pedigree but no MCP, no visual builder, no multi-user layer.

**Developer-facing only.**

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 3 | Local endpoints supported |
| MCP-native | 1 | No MCP |
| Custom code/Python | 5 | Native code execution is a core feature |
| Multi-agent orchestration | 5 | Conversable agents; group chats |
| Memory/state | 3 | Session-based; external DB for persistence |
| Multi-user+permissions | 1 | None built-in |
| No-code builder | 2 | Configuration-based setup only |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 4 | ~12K stars; Microsoft backing |
| Claude-ecosystem fit | 3 | Claude supported |
| Self-host/license/cost | 5 | Apache 2.0, free |
| 2-week feasibility | 2 | Needs UI + multi-user |
| **TOTAL** | **35/60** | |

---

### 1.5 OpenAI Agents SDK

**GitHub**: https://github.com/openai/openai-agents-python | **License**: Proprietary API
**Docs**: https://openai.github.io/openai-agents-python/

OpenAI's first-party Python SDK for building agents on OpenAI models. No local model support. No Claude support. No MCP. Cloud-only. **Entirely wrong ecosystem for this project.**

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 1 | OpenAI-only; no local inference |
| MCP-native | 1 | No |
| Custom code/Python | 3 | Python SDK exists |
| Multi-agent orchestration | 3 | Basic handoffs |
| Memory/state | 2 | Session only |
| Multi-user+permissions | 1 | No |
| No-code builder | 1 | No |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 3 | Newer, growing, OpenAI-backed |
| Claude-ecosystem fit | 1 | Competing ecosystem |
| Self-host/license/cost | 1 | Cloud API only, proprietary |
| 2-week feasibility | 1 | Wrong ecosystem entirely |
| **TOTAL** | **19/60** | ELIMINATED |

---

### 1.6 Letta (MemGPT)

**GitHub**: https://github.com/letta-ai/letta | **Stars**: ~7K | **License**: MIT
**Docs**: https://docs.letta.com

Memory-augmented agent platform. Agents have database-backed memory (LanceDB or Postgres), can read/write long-term memory, and are accessed via a REST server. Local-first design. MCP support was **planned for Q3 2025** — not confirmed production-ready as of research date. Multi-user auth is minimal (basic HTTP auth on the server).

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 4 | Local-first design; Ollama and local models |
| MCP-native | 2 | Planned; not confirmed production-ready |
| Custom code/Python | 4 | Python SDK; REST server |
| Multi-agent orchestration | 3 | Server mode; limited vs. LangGraph |
| Memory/state | **5** | Core strength: persistent, database-backed agent memory |
| Multi-user+permissions | 2 | Basic server mode; no enterprise RBAC |
| No-code builder | 2 | Basic web UI; no visual workflow builder |
| Polish/UX maturity | 2 | Functional UI; not CEO-grade |
| Project maturity | 3 | ~7K stars; active 2025 |
| Claude-ecosystem fit | 3 | Claude support added in recent versions |
| Self-host/license/cost | 4 | MIT; Docker deployable |
| 2-week feasibility | 2 | MCP not ready; multi-user too basic |
| **TOTAL** | **36/60** | |

---

### 1.7 Dify — TOP HARNESS PICK

**GitHub**: https://github.com/langgenius/dify | **Stars**: ~30K | **License**: MIT
**Website**: https://dify.ai | **Version**: v0.7+ (Q2 2025, rapidly evolving)

Dify is a full LLM application platform: visual workflow builder, RAG pipelines, agent framework, multi-user auth, and multi-model routing in one self-hosted Docker image. The only candidate that meets **all twelve axes** at acceptable or better levels. MCP server support added in v0.6+. First-class Claude support. 30K GitHub stars = production-proven.

**This is the recommended harness for the 2-week build.**

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | **5** | Seamless Ollama, HuggingFace, custom endpoints alongside Claude |
| MCP-native | 4 | MCP server framework added v0.6+; still maturing |
| Custom code/Python | 4 | Custom Python code nodes in workflows |
| Multi-agent orchestration | 4 | Visual branching, loops, parallel execution, agent nodes |
| Memory/state | 4 | Knowledge bases, persistent agent conversations, vector search |
| Multi-user+permissions | **5** | Built-in multi-user, teams, RBAC, API key management |
| No-code builder | **5** | Drag-and-drop visual workflow builder; CEO/PM-accessible |
| Polish/UX maturity | 4 | Clean product UI; version control for workflows |
| Project maturity | **5** | ~30K stars; most active LLM platform OSS project 2025 |
| Claude-ecosystem fit | **5** | First-class Anthropic support; native Claude routing |
| Self-host/license/cost | 5 | MIT; Docker Compose or K8s; zero cost |
| 2-week feasibility | **5** | MVP realistically achievable in 5-7 days |
| **TOTAL** | **55/60** | RECOMMENDED |

**Key Dify capabilities for this project**:
- Model router: Route between Claude and local Ollama/vLLM endpoints via config
- Workflow engine: Branches, loops, parallel execution, conditionals, agent nodes
- Knowledge base: Document ingestion to vector search to retrieval-augmented chat
- Deployment API: Any workflow becomes a REST endpoint automatically
- Org structure: Organizations, Teams, Members with granular permissions
- Observability: Built-in token counting, request tracing, cost tracking

---

### 1.8 Flowise

**GitHub**: https://github.com/FlowiseAI/Flowise | **Stars**: ~20K | **License**: Apache 2.0

Node-based visual LLM workflow builder. Excellent UI/UX; strong RAG pipeline construction; Ollama native. **Critical gap**: no MCP support (as of research date). Multi-user is limited in community edition. Similar visual builder to Dify but Dify wins on MCP, multi-user depth, and Claude ecosystem fit.

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 4 | Excellent Ollama, local endpoint integration |
| MCP-native | 1 | No MCP — significant gap for Claude ecosystem |
| Custom code/Python | 3 | Custom nodes possible |
| Multi-agent orchestration | 3 | Flow-based; less powerful than LangGraph |
| Memory/state | 3 | Basic memory nodes |
| Multi-user+permissions | 2 | Limited; basic roles only in CE |
| No-code builder | **5** | Excellent node-based builder; possibly better UX than Dify |
| Polish/UX maturity | 4 | Very polished; strong UI |
| Project maturity | 4 | ~20K stars |
| Claude-ecosystem fit | 3 | Claude supported but not native |
| Self-host/license/cost | 4 | Apache 2.0; Docker ready |
| 2-week feasibility | 3 | No MCP is a blocking gap; limited multi-user |
| **TOTAL** | **39/60** | Second choice if MCP becomes available |

---

### 1.9 n8n

**GitHub**: https://github.com/n8n-io/n8n | **Stars**: ~40K | **License**: Sustainable Use (Commons Clause)
**Website**: https://n8n.io

General-purpose visual workflow automation (1000+ integrations). Excellent multi-user, teams, RBAC. Best-in-class non-coder builder for business process automation. **Critical concerns**: (1) Not LLM-native — AI nodes call external APIs via HTTP; not designed for agent loops. (2) **Commons Clause license**: commercial self-hosting requires a paid n8n license. (3) No MCP.

Best role for this project: **connector bus / trigger layer** (email arrives -> workflow -> AI step -> action), not the agent orchestrator.

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 2 | Indirect: HTTP nodes only; not LLM-native |
| MCP-native | 1 | No MCP |
| Custom code/Python | 4 | JS code nodes; HTTP calls to any API |
| Multi-agent orchestration | 2 | Workflow automation, not LLM agent orchestration |
| Memory/state | 3 | Basic state within workflow runs |
| Multi-user+permissions | **5** | Enterprise-grade: teams, RBAC, audit |
| No-code builder | **5** | Excellent; 1000+ integrations |
| Polish/UX maturity | 4 | Very polished; mature product |
| Project maturity | **5** | ~40K stars; most stars in category |
| Claude-ecosystem fit | 2 | Claude HTTP node; not native |
| Self-host/license/cost | 3 | Commons Clause: commercial use needs paid license |
| 2-week feasibility | 3 | Licensing friction; not LLM-native |
| **TOTAL** | **39/60** | Useful as trigger/automation layer only |

---

### 1.10 Sim Studio

**GitHub**: https://github.com/simstudioai/sim | **Stars**: ~500-1K | **License**: MIT

Very early stage (Q1 2025 emergence). Minimal documentation, sparse community, unclear production readiness. **Not viable for a 2-week business-critical build.**

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 2 | Unclear |
| MCP-native | 2 | Unclear |
| Custom code/Python | 2 | Early stage |
| Multi-agent orchestration | 2 | Early stage |
| Memory/state | 2 | Early stage |
| Multi-user+permissions | 1 | Not present |
| No-code builder | 2 | Unknown |
| Polish/UX maturity | 2 | Early stage |
| Project maturity | 1 | ~500-1K stars; very new |
| Claude-ecosystem fit | 1 | Unclear |
| Self-host/license/cost | 3 | MIT |
| 2-week feasibility | 1 | Not production ready |
| **TOTAL** | **21/60** | ELIMINATED |

---

### 1.11 Mastra

**GitHub**: https://github.com/mastra-ai/mastra | **Stars**: ~500-1K | **License**: MIT

Modern TypeScript-first agent framework. Async-first design, model routing supported, Claude models work. No MCP, no multi-user, no UI, no no-code builder. API design may still change. Too immature for a production 2-week assembly.

**Developer-facing only. Too early.**

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 3 | Model routing supported |
| MCP-native | 1 | No |
| Custom code/Python | 3 | TypeScript only |
| Multi-agent orchestration | 2 | Early |
| Memory/state | 2 | Early |
| Multi-user+permissions | 1 | No |
| No-code builder | 1 | TypeScript only — developer-facing |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 1 | ~500-1K stars; API may change |
| Claude-ecosystem fit | 3 | Claude supported |
| Self-host/license/cost | 4 | MIT |
| 2-week feasibility | 1 | Too early |
| **TOTAL** | **23/60** | ELIMINATED |

---

### 1.12 Pydantic-AI

**GitHub**: https://github.com/pydantic/pydantic-ai | **Stars**: ~2K | **License**: MIT
**Docs**: https://ai.pydantic.dev

Type-safe Python agent library from the Pydantic team. Excellent Claude support; native model routing between Claude and any OpenAI-compatible endpoint is elegant and type-safe. MCP support planned but not yet released. Zero UI, zero multi-user. Best-in-class for the **agent logic layer** inside a larger assembled stack; cannot stand alone.

| Axis | Score | Notes |
|---|---|---|
| Cloud+local routing | 4 | Any OpenAI-compatible endpoint; model routing built-in |
| MCP-native | 2 | Planned; not yet released |
| Custom code/Python | **5** | Type-safe Python; best DX in category |
| Multi-agent orchestration | 3 | Agent library; no native orchestration UI |
| Memory/state | 2 | No built-in persistence |
| Multi-user+permissions | 1 | Library only |
| No-code builder | 1 | Developer-only |
| Polish/UX maturity | 1 | No UI |
| Project maturity | 3 | ~2K stars; newer but from trusted Pydantic team |
| Claude-ecosystem fit | **5** | Excellent native Claude support |
| Self-host/license/cost | 5 | MIT, free |
| 2-week feasibility | 2 | Library; needs full platform wrap |
| **TOTAL** | **34/60** | |

---

### 1.13 Harness Summary Table

| Tool | Routing | MCP | Code | Multi-Agent | Memory | Multi-User | No-Code | UX | Maturity | Claude | License | 2-Wk | **TOT** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Dify** | **5** | 4 | 4 | 4 | 4 | **5** | **5** | 4 | **5** | **5** | 5 | **5** | **55** |
| n8n | 2 | 1 | 4 | 2 | 3 | **5** | **5** | 4 | **5** | 2 | 3 | 3 | 39 |
| Flowise | 4 | 1 | 3 | 3 | 3 | 2 | **5** | 4 | 4 | 3 | 4 | 3 | 39 |
| Letta | 4 | 2 | 4 | 3 | **5** | 2 | 2 | 2 | 3 | 3 | 4 | 2 | 36 |
| LangGraph | 4 | 2 | **5** | **5** | 4 | 1 | 1 | 1 | 4 | 3 | 4 | 2 | 36 |
| Claude SDK | 1 | **5** | 4 | 4 | 2 | 1 | 1 | 1 | 4 | **5** | 5 | 2 | 35 |
| AutoGen | 3 | 1 | **5** | **5** | 3 | 1 | 2 | 1 | 4 | 3 | 5 | 2 | 35 |
| Pydantic-AI | 4 | 2 | **5** | 3 | 2 | 1 | 1 | 1 | 3 | **5** | 5 | 2 | 34 |
| CrewAI | 3 | 1 | **5** | **5** | 3 | 1 | 1 | 1 | 4 | 3 | 5 | 2 | 34 |
| Mastra | 3 | 1 | 3 | 2 | 2 | 1 | 1 | 1 | 1 | 3 | 4 | 1 | 23 |
| Sim Studio | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 2 | 1 | 1 | 3 | 1 | 21 |
| OpenAI SDK | 1 | 1 | 3 | 3 | 2 | 1 | 1 | 1 | 3 | 1 | 1 | 1 | 19 |

**Note on developer-only tools**: LangGraph, CrewAI, AutoGen, Pydantic-AI, Claude SDK, Mastra, and Sim Studio have zero no-code builder capability. Dept heads cannot extend workflows without engineering help — a hard disqualifier for the self-serve extension model. These tools remain valuable as **inner-loop components** assembled inside Dify or a similar platform.

---

## Section 2 — Scored Second-Brain / Knowledge-System Inventory

### Scoring Key (1 = absent/unusable, 5 = best-in-class)

Ten axes evaluated per system:
1. **Local-LLM compatibility** — works with Ollama/vLLM/OpenAI-compatible endpoints
2. **Connector breadth** — built-in email (Gmail/Outlook), Slack, Google Drive + extensibility
3. **Retrieval/RAG quality** — hybrid search, reranking, graph reasoning, benchmarks
4. **Multi-user + per-dept partitioning** — RBAC, workspace isolation, SSO/SCIM
5. **Non-coder self-serve** — can dept heads add documents and build knowledge areas without code?
6. **Polish / web UX** — CEO-grade interface quality
7. **Agentic capability** — autonomous actions beyond retrieval (web search, code exec, scheduling)
8. **Self-host / licensing / cost** — open license, self-deployable
9. **Claude / MCP integration** — Anthropic API support; MCP for tool extensibility
10. **2-week feasibility** — realistic to fully deploy and integrate in 14 days

---

### 2.1 Khoj

**GitHub**: https://github.com/khoj-ai/khoj | **Stars**: 35K | **License**: AGPL-3.0 | **Version**: 2.0.0-beta.28 (Mar 2026)
**Website**: https://khoj.dev

Personal AI second brain with semantic search, web browsing, and custom agents. Strong agentic capabilities (scheduled automations, deep research, custom agent personas). **Designed as a personal AI first** — multi-tenant team partitioning is an afterthought. No native email/Slack/Drive connectors. AGPL-3.0 license requires source disclosure if distributed. Enterprise tier exists at khoj.dev/teams.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | 4 | Ollama, OpenAI-compatible, wide model support |
| Connector breadth | 2 | File formats only (PDF, MD, Notion, Word); no email/Slack/Drive connectors |
| RAG quality | 4 | Hybrid search, reranking, graph-based agent reasoning |
| Multi-user + partitioning | 2 | Personal-first; no department-level RBAC in CE |
| Non-coder self-serve | 3 | Good web UI for personal use; limited for team onboarding |
| Polish/web UX | 4 | Polished web app + desktop; WhatsApp access |
| Agentic capability | 4 | Custom agents, scheduled automations, web research |
| Self-host/license/cost | 3 | AGPL-3.0: source disclosure required; CE free |
| Claude/MCP integration | 2 | No explicit MCP; Claude usable as LLM backend |
| 2-week feasibility | 3 | Personal-first architecture needs significant customization for teams |
| **TOTAL** | **31/50** | |

---

### 2.2 Onyx (formerly Danswer) — TOP KB PICK

**GitHub**: https://github.com/onyx-dot-app/onyx | **Stars**: 30K | **License**: MIT (CE) | **Version**: v4.2.2 (Jun 2026)
**Website**: https://www.onyx.app

Enterprise-grade agentic RAG platform built for teams. **50+ indexing connectors** including Gmail, Slack, Google Drive, Confluence, SharePoint. Full RBAC with SSO (Google OAuth, OIDC, SAML) and SCIM provisioning (Okta, Azure AD). Agentic deep research (multi-step iterative research flows — top leaderboard Feb 2026). Custom agents with instructions, knowledge, and actions. MCP support for external integrations. White-label support. Community Edition is MIT-licensed.

**The only knowledge system meeting all ten axes at acceptable or better levels.**

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | **5** | Ollama, LiteLLM, vLLM, all major cloud providers |
| Connector breadth | **5** | 50+ connectors: Gmail, Outlook, Slack, Drive, Confluence, SharePoint |
| RAG quality | **5** | Agentic RAG, hybrid vector+keyword, benchmark-leading Feb 2026 |
| Multi-user + partitioning | **5** | RBAC, SSO, SCIM, team workspaces, audit logs, usage analytics |
| Non-coder self-serve | 4 | Comprehensive UI; connector setup is UI-driven |
| Polish/web UX | **5** | Professional, clean; whitelabeling; voice/video UI included |
| Agentic capability | **5** | Custom agents, deep research, web search, code execution, MCP actions |
| Self-host/license/cost | **5** | MIT CE; Docker + K8s + Helm/Terraform; zero licensing cost |
| Claude/MCP integration | 4 | MCP for external integrations; Anthropic models supported |
| 2-week feasibility | **5** | 5-7 days to production; all requirements met out of the box |
| **TOTAL** | **48/50** | RECOMMENDED |

**Sources**: https://github.com/onyx-dot-app/onyx, https://docs.onyx.app

---

### 2.3 AnythingLLM

**GitHub**: https://github.com/Mintplex-Labs/anything-llm | **Stars**: 62K | **License**: MIT | **Version**: v1.15.0 (Jun 2026)
**Website**: https://anythingllm.com

All-in-one AI app: chat + agents + RAG + multi-user workspaces. Highest GitHub stars in this category (62K). One-click deployments on Railway/Render. 40+ LLM providers. Dynamic model routing. No-code AI agent builder. MCP compatibility. Connectors for Gmail, Outlook, Slack, Google Drive, OneDrive. Workspace separation model.

**Fastest path to a working MVP.** Slightly less fine-grained RBAC than Onyx (workspace-level vs. group+role-level), but most teams will not hit this ceiling at CEO + dept head scale.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | **5** | 40+ providers; seamless Ollama, LM Studio, llama.cpp |
| Connector breadth | 4 | Gmail, Outlook, Slack, Drive, OneDrive — good coverage |
| RAG quality | 4 | LanceDB default; 8+ vector DBs; hybrid search; reranking |
| Multi-user + partitioning | 4 | Docker multi-user; workspace separation; less fine-grained than Onyx |
| Non-coder self-serve | **5** | One-click deploy; drag-drop document upload; UI-driven agent builder |
| Polish/web UX | 4 | Intuitive, modern; citation display; workspace organization |
| Agentic capability | 4 | Custom agents, scheduled tasks, tool selection (80% token savings), no-code builder |
| Self-host/license/cost | **5** | MIT; Railway/Render one-click; $0 |
| Claude/MCP integration | 4 | Full MCP compatibility explicit in docs |
| 2-week feasibility | **5** | 3-5 days to production; fastest path |
| **TOTAL** | **44/50** | Strong #2 pick |

---

### 2.4 Open WebUI

**GitHub**: https://github.com/open-webui/open-webui | **Stars**: 143K | **License**: Modified Open WebUI License | **Version**: v0.10.2 (Jul 2026)
**Website**: https://openwebui.com

Most feature-rich and polished self-hosted AI web interface. RBAC, user groups, channels, notes workspace, calendar, automations, voice/video calls, 9 vector databases, hybrid search, SCIM provisioning, OpenTelemetry. The **best-in-class UX** in this category — closest to Glean/Notion in polish. **Gap**: built-in email/Slack connectors do not exist; they require MCP server setup (additional glue work, ~2 days).

License note: Modified license requires branding preservation; not a standard open-source license.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | **5** | Ollama primary; any OpenAI-compatible; mix-and-match |
| Connector breadth | 3 | Google Drive/OneDrive yes; email/Slack need MCP or custom (gap) |
| RAG quality | 4 | 9 vector DBs; hybrid BM25+vector; reranking; multiple OCR engines |
| Multi-user + partitioning | **5** | RBAC, user groups, channels, SCIM, per-group model access controls |
| Non-coder self-serve | 4 | Excellent UI once deployed; some config required for email/Slack |
| Polish/web UX | **5** | Best-in-class: notes, channels, calendar, voice, artifacts — CEO-grade |
| Agentic capability | 4 | Custom agents, calendar integration, automations, code execution via plugins |
| Self-host/license/cost | 4 | Modified license (branding req); Docker-ready; $0 self-host |
| Claude/MCP integration | 4 | MCP, MCPO, OpenAPI tool servers supported |
| 2-week feasibility | 4 | 7-8 days (email/Slack connectors need custom MCP work) |
| **TOTAL** | **42/50** | Best UX; connector gap is the only downside |

---

### 2.5 Morphik

**GitHub**: https://github.com/morphik-org/morphik-core | **Stars**: ~3.6K | **License**: Apache 2.0 | **Version**: v1.2.2 (Jun 2026)
**Website**: https://morphik.ai

Specialized multimodal RAG platform — exceptional at visually rich documents (PDFs with charts, tables, images) via ColPali visual embeddings. Integrations: Google Suite, Slack, Confluence. **Cloud-first design** with self-hosting as a secondary path. Multi-user documentation is sparse. Emerging platform; less battle-tested at enterprise scale.

**Recommended as a specialized supplement** (board decks, financial reports with charts) rather than the primary platform.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | 2 | Primarily cloud/API; local LLM path unclear |
| Connector breadth | 3 | Google Suite, Slack, Confluence; limited email |
| RAG quality | **5** | Exceptional multimodal/visual via ColPali; specialized strength |
| Multi-user + partitioning | 2 | Unclear documentation; cloud-first |
| Non-coder self-serve | 3 | Console UI exists; cloud-first UX |
| Polish/web UX | 3 | Console works; less polished than top tier |
| Agentic capability | 2 | Primarily Q&A; limited agentic workflows |
| Self-host/license/cost | 2 | Cloud-first; self-host less documented |
| Claude/MCP integration | 3 | MCP explicitly mentioned |
| 2-week feasibility | 2 | Emerging; cloud-first; self-host path immature |
| **TOTAL** | **27/50** | Supplement only for visual docs |

---

### 2.6 Cognee

**GitHub**: https://github.com/topoteretes/cognee | **Stars**: 26K | **License**: Apache 2.0 | **Version**: ts-v3.0.13 (Jul 2026)

Knowledge graph + vector embedding memory platform for AI agents. Research paper-backed (Markovic et al., 2025: "Optimizing the Interface Between Knowledge Graphs and LLMs for Complex Reasoning"). Entity linking across memories; cross-agent knowledge sharing; temporal reasoning. Claude Code plugin available. **No web UI**; primarily SDK/API. Best used as the memory/knowledge layer underneath Open WebUI or Dify.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | 4 | Graph approach works with local LLMs |
| Connector breadth | 2 | Memory-focused; not a data-source connector hub |
| RAG quality | **5** | Knowledge graph + vectors; research-validated; entity linking |
| Multi-user + partitioning | 3 | Agentic user/tenant isolation; less explicit team features |
| Non-coder self-serve | 2 | Python SDK primary; API-driven |
| Polish/web UX | 2 | Animated demos; programmatic focus |
| Agentic capability | **5** | Agent memory, cross-agent sharing, learning from feedback |
| Self-host/license/cost | 4 | Apache 2.0; open source |
| Claude/MCP integration | 4 | Claude Code plugin; MCP support inferred |
| 2-week feasibility | 3 | Good as a component; knowledge graph adds setup complexity |
| **TOTAL** | **34/50** | Memory layer component, not primary platform |

---

### 2.7 Mem0

**GitHub**: https://github.com/mem0ai/mem0 | **Stars**: 60K | **License**: Apache 2.0
**Website**: https://mem0.ai | YC S24

AI memory layer with a novel April 2026 algorithm: single-pass ADD-only extraction, entity linking, multi-signal retrieval (semantic + BM25 + entity), temporal reasoning. Benchmark-leading: 91.6 on LoCoMo, 94.8 on LongMemEval. Multi-level memory (User / Session / Agent state). **No web UI** — SDK + REST API only. Best used to augment agent memory inside Dify or Open WebUI.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | 4 | Works with any LLM; OpenAI-compatible endpoints |
| Connector breadth | 1 | Memory layer only; not a data-source connector |
| RAG quality | **5** | Memory algorithm best-in-class; 91.6 LoCoMo; temporal awareness |
| Multi-user + partitioning | 3 | Multi-level memory per user/session/agent; not team-focused |
| Non-coder self-serve | 2 | CLI and SDK focus; no UI |
| Polish/web UX | 1 | No web UI |
| Agentic capability | **5** | Exceptional: agent-generated facts; learning over time |
| Self-host/license/cost | 4 | Apache 2.0; managed service also available |
| Claude/MCP integration | 2 | Not explicitly documented; SDK-based integration |
| 2-week feasibility | 2 | Component only; needs primary platform |
| **TOTAL** | **29/50** | Memory component, not primary platform |

---

### 2.8 Reor

**GitHub**: https://github.com/reorproject/reor | **Stars**: 8.5K | **License**: AGPL-3.0 | **Last release**: v0.2.32 (Apr 2025 — appears dormant)

AI-powered desktop note-taking app. Semantic note linking, Q&A over notes, local Ollama. **Desktop application only** — no web server, no multi-user, no team features. Last release April 2025 suggests reduced activity. **Not applicable** for a CEO web platform with team rollout.

| Axis | Score | Notes |
|---|---|---|
| Local-LLM compatibility | 4 | Ollama-first; LanceDB embeddings |
| Connector breadth | 1 | Local filesystem only |
| RAG quality | 3 | Simple vector similarity for note linking |
| Multi-user + partitioning | 1 | Single-user desktop; no team features |
| Non-coder self-serve | 2 | Desktop install is simple; single-user paradigm |
| Polish/web UX | 2 | Desktop app; Obsidian-like UX; not web |
| Agentic capability | 1 | Q&A only; no automation |
| Self-host/license/cost | 3 | AGPL-3.0 |
| Claude/MCP integration | 1 | Not mentioned |
| 2-week feasibility | 1 | Desktop-only; not applicable |
| **TOTAL** | **19/50** | ELIMINATED |

---

### 2.9 Glean — Commercial Polish Bar

**Website**: https://www.glean.com | Pricing: ~$15-30K+/year for small orgs

Enterprise search and AI assistant. 200+ connectors, advanced RBAC, Google-scale search quality, excellent enterprise UX. Cloud-only; not self-hostable; expensive. Included to define the enterprise polish standard this platform must aspire to: (a) federated search across all connected sources, (b) team-level scoping that "just works," (c) interface that non-technical executives adopt without training.

**Not a candidate. Cited as the bar.**

---

### 2.10 Hebbia — Commercial Agentic Bar

**Website**: https://www.hebbia.ai | Pricing: Custom enterprise

AI-powered research and analysis platform targeting financial/legal/technical document workflows. Multimodal document understanding, AI-generated synthesis, code execution for data analysis. Sets the bar for **agentic knowledge work** — users expect synthesis and drafted outputs, not just retrieved chunks.

**Not a candidate. Cited as the bar.**

---

### 2.11 Knowledge System Summary Table

| System | Local LLM | Connectors | RAG | Multi-User | Self-Serve | UX | Agentic | License | Claude/MCP | 2-Wk | **TOT** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Onyx** | **5** | **5** | **5** | **5** | 4 | **5** | **5** | **5** | 4 | **5** | **48** |
| AnythingLLM | **5** | 4 | 4 | 4 | **5** | 4 | 4 | **5** | 4 | **5** | **44** |
| Open WebUI | **5** | 3 | 4 | **5** | 4 | **5** | 4 | 4 | 4 | 4 | **42** |
| Cognee | 4 | 2 | **5** | 3 | 2 | 2 | **5** | 4 | 4 | 3 | **34** |
| Khoj | 4 | 2 | 4 | 2 | 3 | 4 | 4 | 3 | 2 | 3 | **31** |
| Mem0 | 4 | 1 | **5** | 3 | 2 | 1 | **5** | 4 | 2 | 2 | **29** |
| Morphik | 2 | 3 | **5** | 2 | 3 | 3 | 2 | 2 | 3 | 2 | **27** |
| Reor | 4 | 1 | 3 | 1 | 2 | 2 | 1 | 3 | 1 | 1 | **19** |

---

## Section 3 — Gap Analysis

These are the layers that **neither inventory fully provides** in pre-assembled form. For each: is there a proven off-the-shelf answer, or is it custom glue?

---

### Gap 1: Claude to DGX Spark Model Router

**The need**: A layer that accepts calls in Claude's native API format (Anthropic Messages API), routes cheap/bulk work to the local DGX Spark (OpenAI-compatible endpoint), and sends hard reasoning to Claude cloud — transparently to the application layer.

**Off-the-shelf options**:

| Tool | Fit | Notes |
|---|---|---|
| **LiteLLM** (https://github.com/BerriAI/litellm) | Best | Proxy server + Python SDK; 100+ LLM providers; built-in cost tracking; fallback chains; YAML config; Docker-ready. Ollama v0.14.0+ (Jan 2026) added native Anthropic Messages API support on port 11434 — zero-translation routing. |
| **OpenRouter** (https://openrouter.ai) | Good | Cloud-based; routes to 400+ models; free tier includes Llama 3.3 70B. Cloud-only — cannot replace local routing but can complement. |
| **Portkey** (https://portkey.ai) | Partial | Enterprise gateway; conditional routing, caching, analytics. Self-hosted Gateway 2.0 in pre-release; not production-ready for self-hosted as of research date. |
| **RouteLLM** (https://github.com/lm-sys/RouteLLM) | Not viable | ICLR 2025 academic paper; ML-trained router. Requires workload-specific training data and ML expertise. 2/10 for 2-week timeline. |

**Verdict**: **LiteLLM is the clear off-the-shelf answer.** Setup: 2 hours. Provides unified Claude Messages API to local Ollama/vLLM routing, cost tracking per request, fallback chain (local first, then Claude cloud), Docker-native deployment.

**Illustrative LiteLLM config**:
```
model_list:
  - model_name: "local-llama"
    litellm_params:
      model: "openai/llama3.1:70b"
      api_base: "http://dgx-spark.local:8000"
  - model_name: "claude-sonnet"
    litellm_params:
      model: "claude-3-5-sonnet-20241022"
router_settings:
  fallback_models: ["claude-sonnet"]
```

**Sources**: https://docs.litellm.ai/, https://docs.ollama.com/api/anthropic-compatibility

---

### Gap 2: Non-Coder Self-Serve Builder

**The need**: Dept heads build their own AI workflows (trigger, AI step, action) without writing code.

**Off-the-shelf options**:

| Tool | Fit | Notes |
|---|---|---|
| **Dify** (workflow builder) | Best | AI-first; drag-and-drop; RAG nodes built-in; exports as REST API; non-coders report under 1 hour to first working workflow. Self-hosted MIT. |
| **n8n** | Good for triggers | 1000+ integrations; excellent for "when email arrives, AI step, then action" patterns. Not AI-native for agentic loops. Commons Clause license for commercial self-hosting. |
| **Flowise** | Good UX | Excellent node-based builder; better UX than Dify for some users. No MCP. Limited multi-user. |
| **Zapier AI** (https://zapier.com/ai) | Cloud only | 8000+ integrations; Copilot for natural-language Zap building (Sep 2025); Agents GA May 2025. Cloud-only; no data sovereignty. |
| **Make.com** | Cloud only | 3000+ integrations; AI Agents (Apr 2025); excellent visual builder. Cloud SaaS only. |

**Verdict**: **Dify for AI workflow building; n8n optionally as a trigger/automation bus**. Together they cover: (a) AI agent/RAG workflow design by non-coders (Dify) and (b) business process triggers and integrations at scale (n8n optional layer, requires paid license for commercial self-hosting).

---

### Gap 3: Auth / Permissions / Governance

**The need**: SSO, RBAC, department-level isolation, SCIM provisioning — for self-hosted AI apps with CEO + dept head user base.

**Off-the-shelf options**:

| Tool | Fit | Notes |
|---|---|---|
| **Authentik** (https://goauthentik.io) | Best for 2-week | Modern IdP; OAuth2/OIDC/SAML/LDAP; Docker-native; 30-45 min setup; 2.5x lighter than Keycloak; RBAC via groups; no XML config; actively maintained 2025. |
| **Keycloak** (https://www.keycloak.org) | Enterprise | Java-based; broadest protocol coverage; 4-8 GB RAM; 2-4 hours setup; Raft consensus for HA. Best for 2000+ users or existing Red Hat environment. |
| **Clerk** (https://clerk.com) | Cloud only | Fastest dev setup; no self-hosting; data sovereignty concern. |
| **Built-in (Open WebUI)** | For small teams | RBAC, LDAP, OIDC built in; sufficient for under 50 users without external IdP. |
| **Built-in (Onyx)** | For mid-size teams | Google OAuth, OIDC, SAML, SCIM; production-ready for dept-head rollout. |

**Verdict**:
- **Solo MVP path**: Use Onyx's built-in auth (covers CEO + up to ~10 dept heads with OIDC).
- **Scale path**: Add **Authentik** as IdP for SSO federation (Google/AD). Setup under 1 hour. Skip Keycloak unless you have DevOps headcount dedicated to it.

**Source**: https://www.cerbos.dev/blog/authentik-vs-keycloak-selfhosted-idp-comparison

---

### Gap 4: Web App Shell

**The need**: CEO-grade web interface — chat, agents, knowledge management, per-user configuration. Glean/Notion UX bar.

**Off-the-shelf options**:

| Tool | Fit | Notes |
|---|---|---|
| **Open WebUI** | Best UX | Best-in-class polish: notes, channels, calendar, voice, multi-workspace, RBAC. Deploy in under 10 min. Email/Slack connectors are the only gap. |
| **Onyx Chat** | Best integrated | Includes knowledge retrieval, agent access, deep research — all in one UI. Slightly less "productivity suite" feeling than Open WebUI. |
| **AnythingLLM** | Fastest | Most approachable UI; drag-drop document upload; workspace per dept. |
| **Chainlit** (https://github.com/Chainlit/chainlit) | Dev tool | Python chat app framework; SSO support; but community-maintained since May 2025. |
| **Custom React/Next.js** | Too slow | Adds 3-4 weeks minimum. Skip entirely. |

**Verdict**: The web shell is **included in both recommended KB systems** (Onyx and AnythingLLM both have polished chat UIs). Open WebUI can be added as an overlay if even higher UX polish is needed.

---

### Gap 5: Connector Auth Token Management

**The need**: Store and rotate OAuth tokens (Gmail, Slack, GDrive) securely; allow dept heads to authorize their own accounts without touching config files.

**Off-the-shelf options**:

| Tool | Fit | Notes |
|---|---|---|
| **Dify built-in** | Sufficient for MVP | OAuth token store per tool; dept heads click "Authorize"; tokens encrypted at rest; multi-account per provider. |
| **Onyx built-in** | Connector auth | Each connector has its own OAuth flow; tokens stored server-side. |
| **Infisical** (https://infisical.com) | Scale step-up | Modern MIT secrets platform; dashboard-driven; under 1 hour Docker deploy. Best when secrets grow beyond built-in stores. |
| **HashiCorp Vault** | Overkill | Raft consensus, HCL policies, unsealing procedures. Days to set up properly. Skip for 2-week solo build. |

**Verdict**:
- **Week 1-2**: Use **built-in token stores in Dify/Onyx** — OAuth flows handle Gmail/Slack/Drive authorization out of the box.
- **Post-MVP**: Graduate to **Infisical** if secrets grow beyond ~15 or multi-environment management is needed.

---

### Gap 6: Eval / Observability

**The need**: Trace LLM calls, track token costs, debug agent loops, measure response quality, know which requests go local vs. cloud.

**Off-the-shelf options**:

| Tool | Fit | Notes |
|---|---|---|
| **LangFuse** (https://langfuse.com, https://github.com/langfuse/langfuse) | Best self-hosted | MIT; Docker Compose in 5 min; deep tracing (nested spans, multi-turn, tool calls); prompt versioning; eval framework; cost per request; OpenTelemetry native. Integrates with LiteLLM in 3 config lines. |
| **LangSmith** | Cloud only | LangChain SaaS; excellent if stack is LangChain-based; otherwise requires manual instrumentation; paid. |
| **Helicone** (https://helicone.ai) | Cloud only | Proxy-based; 2-minute setup; good for cost visibility; shallow tracing; can reduce costs 10-30% via caching. |
| **Phoenix / Arize** (https://github.com/Arize-ai/phoenix) | Eval-heavy | Open-source (Elastic 2.0); excellent for notebook-driven evaluation; less suited for real-time ops monitoring. |

**Verdict**: **LangFuse is the clear self-hosted winner.** 5-minute Docker Compose deploy. Configure LiteLLM to emit traces to LangFuse — every local and cloud LLM call is logged with cost, latency, and token count. Evaluation framework available for week 3+ once the stack is running.

---

### Gap Summary Table

| Gap Layer | Off-the-Shelf Answer | Custom Glue? | Setup Time |
|---|---|---|---|
| Cloud to local model router | **LiteLLM** | No | 2 hours |
| No-code workflow builder | **Dify** + n8n (triggers) | No | under 1 day |
| Auth / RBAC / SSO | **Onyx built-in** (MVP) then Authentik | No | 30-45 min |
| Web app shell | Included in Onyx / AnythingLLM | No | 10 min |
| OAuth token management | Built-in (Dify/Onyx) then Infisical | No | 5 min per connector |
| Eval / observability | **LangFuse** (self-hosted, MIT) | No | 5 min |

**Key finding**: All six gaps have production-ready off-the-shelf answers. No custom glue is required for the 2-week MVP. Custom work is needed only for domain-specific agent logic and specialized data pipelines — which belong to week 3+ iteration anyway.

---

## Section 4 — DGX Spark 128GB Serving Reality

### 4.1 Hardware Profile

The NVIDIA DGX Spark ($4,699) is a 150 x 150 x 50mm desktop AI supercomputer based on the Grace Blackwell Superchip (GB10).

| Spec | Value |
|---|---|
| Unified memory | 128 GB LPDDR5X (shared CPU+GPU) |
| Memory bandwidth | 273 GB/s (16 channels, 256-bit at 4266 MHz) |
| GPU compute | 1 PFLOP FP4 (with sparsity); 1000 TOPS |
| GPU cores | 6,144 CUDA + 5th-gen Tensor Cores (FP8 native on Blackwell) |
| CPU | 20 ARM cores (10x Cortex-X925 + 10x Cortex-A725) |
| Networking | 10GbE ConnectX-7 Smart NIC + Wi-Fi 7 |
| Power | 240W TDP |

**Critical architectural note**: Unified memory means no PCIe bottleneck for weight loading. However, 273 GB/s is the **shared** bandwidth for all CPU+GPU operations. For LLM decode, each token requires reading all model weights from memory — a 70B FP8 model (70 GB weights) theoretically caps single-stream decode at ~3.9 tok/s (273 / 70 = 3.9). PagedAttention in vLLM mitigates this via continuous batching across concurrent requests.

**Sources**: https://www.nvidia.com/en-us/products/workstations/dgx-spark/, https://docs.nvidia.com/dgx/dgx-spark/hardware.html, https://www.lmsys.org/blog/2025-10-13-nvidia-dgx-spark/

---

### 4.2 Model Sizes and Quantizations

#### Recommended Models for 128GB Unified Memory

| Model | Quantization | Weight Size | KV Cache (128K ctx) | Fits? | Quality vs FP16 |
|---|---|---|---|---|---|
| Llama 3.1 70B | FP8 | 70 GB | ~42 GB | Yes (~16 GB headroom) | 99%+ |
| Llama 3.1 70B | AWQ/INT4 | 35-40 GB | ~42 GB | Yes, comfortable | 95-97% |
| Llama 3.1 70B | FP16 | 140 GB | — | No, exceeds 128 GB | — |
| Qwen 2.5 72B | FP8 | 72 GB | ~42 GB | Yes (~14 GB headroom) | 99%+ |
| Llama 3.1 8B | FP16 | 16 GB | ~1.5 GB | Yes, very comfortable | Baseline |
| Mistral Nemo 12B | FP8 | 12 GB | ~2 GB | Yes, excellent headroom | 99%+ |
| Gemma 3 27B | INT8 | 27 GB | ~5 GB | Yes, comfortable | 98-99% |
| Multi-model | Mixed | 8B+13B+27B = ~48 GB total | — | Yes, multi-model feasible | Context-dependent |

**Quantization quality guidance** (2025-2026 consensus):
- **FP8**: Natively accelerated on Blackwell (GB10); virtually indistinguishable from FP16 (99%+ quality retention). **Recommended default.**
- **INT8**: 98-99% quality; well-tested; acceptable if FP8 container unavailable.
- **AWQ/GPTQ (4-bit)**: 95-97% quality; more headroom; suitable when 70B + 128K context simultaneously exceeds memory.
- **INT4**: 92-94% quality; visible degradation on reasoning/code tasks; avoid for decision-support use cases.

**Sources**: https://vrlatech.com/llm-quantization-explained-int4-int8-fp8-awq-and-gptq-in-2026/, https://canitrun.dev/gpus/dgx-spark/, https://www.spheron.network/blog/gpu-memory-requirements-llm/

---

### 4.3 Serving Stack Comparison

| Framework | Throughput (70B FP8, single-stream) | Throughput (256 concurrent) | Setup Complexity | Best For |
|---|---|---|---|---|
| **vLLM** | 22-24 tok/s | 695 tok/s aggregate | Medium (Docker) | Multi-user serving |
| **TensorRT-LLM** | 50-55 tok/s | 550+ tok/s | High (model compilation) | Lowest latency single-stream |
| **Ollama** | 2.7 tok/s | ~41 tok/s | Very simple | Solo dev / prototyping only |
| **llama.cpp** | 60-80 tok/s (Q4_K_M) | Moderate | Simple (binary) | Edge / portability |

#### vLLM — Recommended for Multi-User

PagedAttention treats KV cache as virtual memory pages, enabling continuous batching across concurrent requests. This transforms the DGX Spark's bandwidth limitation into a throughput advantage: at 256 concurrent streams, Llama 3.1 70B FP8 achieves 695 tok/s aggregate vs. Ollama's 41 tok/s — a 17x improvement.

```
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:cu130-nightly \
  --model meta-llama/Llama-3.1-70B-Instruct \
  --dtype float8 \
  --gpu-memory-utilization 0.85
```

#### Ollama — For Initial Prototyping Only

Zero-friction setup: pull a model and serve in minutes. Throughput plateaus at ~41 tok/s under any load. For a CEO platform serving multiple concurrent users, Ollama is a **prototype tool, not a production serving stack**.

#### TensorRT-LLM — If Sub-20ms Latency Matters

Best single-stream latency (15-20 ms/token vs. vLLM's 40-50 ms/token). Requires model compilation to TensorRT engine format using `trtllm-build` (~10-20 min per model) and NVIDIA's spark single-GPU dev container. High setup cost; justified only if streaming latency for a single user is the priority over concurrent throughput.

#### llama.cpp — For Portability

Pure C++ binary; CUDA + Metal + CPU support; GGUF format models (Q4_K_M common). ~60-80 tok/s for 70B Q4_K_M. No Docker dependency. Best for laptop/edge inference or CPU fallback scenarios.

**Sources**: https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking, https://vllm.ai/blog/2026-06-01-vllm-dgx-spark, https://itecsonline.com/post/vllm-vs-ollama-vs-llama.cpp-vs-tgi-vs-tensort, https://www.sitepoint.com/ollama-vs-vllm-performance-benchmark-2026/

---

### 4.4 Networking: Laptop Orchestrator to DGX Spark

**Physical topology**: CEO MacBook (Claude orchestrator + LiteLLM proxy) connected over 10GbE local network to DGX Spark (vLLM serving on port 8000).

| Network parameter | Value |
|---|---|
| 10GbE round-trip latency | 40-80 microseconds |
| Data transfer overhead per request | ~0.1-1 ms |
| LLM inference time (70B, 1K tokens at 24 tok/s) | ~42,000 ms |
| Network fraction of total latency | Under 0.1% — negligible |

**Network latency is irrelevant relative to inference compute.** WiFi 7 is also acceptable for this workload.

**Setup options for local LAN** (simplest):
- Discover DGX Spark: `ping dgx-spark.local`
- Configure LiteLLM to point at: `http://dgx-spark.local:8000`

**Setup options for remote/off-site access**:
- **SSH tunnel**: `ssh -L 8000:localhost:8000 user@dgx-spark.local` — secure, zero config, recommended for solo use
- **Tailscale/WireGuard VPN**: Full network isolation; access as if on LAN; recommended for team rollout
- **Nginx + basic auth**: Reverse proxy with authentication in front of vLLM port for internet exposure

**Auth on vLLM/Ollama**: Neither has built-in authentication. For home/office LAN: bind to localhost and use SSH tunnel or VPN. For internet-exposed endpoints: Nginx with basic auth, or ngrok with OAuth (`ngrok http 8000 --oauth google`).

**Sources**: https://medium.com/@michael.hannecke/connecting-claude-code-to-local-llms-two-practical-approaches-faa07f474b0f, https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models, https://markaicode.com/ollama-network-exposure-secure-remote-access-guide/

---

### 4.5 DGX Spark Caveats (Flagged Issues)

| Issue | Detail | Mitigation |
|---|---|---|
| **Thermal throttling** | Early units (Oct 2025-Jan 2026) throttled at ~100W under sustained load instead of rated 240W. Feb 2026 firmware update delivers up to 2.6x perf improvement. | Verify firmware is current before production use. Source: https://docs.nvidia.com/dgx/dgx-spark/release-notes.html |
| **Page cache OOM** | Linux page cache can hold up to 64 GB, preventing CUDA allocation even with apparent free memory. | Periodically run `sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'` before large sessions. |
| **nvidia-smi reporting** | "Memory-Usage: Not Supported" on iGPU platforms is expected behavior; per-process GPU memory is listed separately. | Normal behavior; use vLLM's internal memory reporting instead. |
| **Single-stream latency** | 70B FP8 single-stream: 40-50 ms/token (vLLM); 370 ms/token (Ollama). For low-volume CEO use, Ollama may feel too slow. | Use 8B model for fast-turnaround tasks; 70B for quality reasoning. TensorRT-LLM achieves 18-20 ms/token if single-user latency is critical. |
| **Not a 24/7 production server** | DGX Spark excels at prototyping and modest concurrency, not data-center-grade continuous load. | Acceptable for CEO + dept head scale (~10-30 concurrent users); add thermal monitoring in production. |
| **OS support horizon** | DGX OS guaranteed for 2 years of updates. | Plan for hardware refresh or OS migration ~2027-2028. |

**Sources**: https://docs.nvidia.com/dgx/dgx-spark/known-issues.html, https://intuitionlabs.ai/articles/nvidia-dgx-spark-review

---

## Section 5 — Recommended Assembled Stacks

### Shared Topology (All Options)

```
CEO MacBook
  Claude Code / Claude Agent SDK  [hard reasoning]
  LiteLLM Proxy :4000
    -> Claude Anthropic API  (complex reasoning, MCP tool calls)
    -> vLLM on DGX Spark :8000  (bulk inference, drafting, retrieval)

DGX Spark 128GB (office LAN, 10GbE)
  vLLM serving Llama 3.1 70B FP8
  (optional) Llama 3.1 8B for fast/cheap tasks

Knowledge + Agent Platform (self-hosted, same or adjacent server)
  [varies by stack below]

Observability
  LangFuse (Docker, MIT, 5-min deploy)

Auth (for multi-user rollout)
  Onyx/Dify built-in (MVP) -> Authentik (scale)
```

---

### Option A — Onyx + Dify (Enterprise-Grade, Full Requirements Met)

**This is the top recommendation.**

| Layer | Tool | Role |
|---|---|---|
| Model router | LiteLLM | Claude to DGX Spark cost-tiering |
| Knowledge system | **Onyx CE** (MIT) | 50+ connectors, RBAC, agentic RAG, enterprise UX |
| Agent harness / builder | **Dify** (MIT) | No-code visual workflow builder, multi-agent orchestration |
| Observability | LangFuse (MIT) | Tracing, cost tracking, evals |
| Auth (scale) | Authentik | SSO/OIDC federation when needed |

**Integration**: Dify points its LLM nodes at the LiteLLM proxy (OpenAI-compatible endpoint). Onyx handles all knowledge retrieval (email, Slack, Drive indexed and searchable). Dify workflows call Onyx's REST API for document context, then route reasoning to Claude or local model via LiteLLM. Both have RBAC; Onyx's is more mature.

**Week 1 build plan**:
- Days 1-2: Deploy Onyx CE (Docker Compose) + configure Gmail/Slack/Drive connectors
- Days 2-3: Deploy vLLM on DGX Spark with Llama 3.1 70B FP8; verify endpoint
- Day 3: Stand up LiteLLM proxy; verify Claude to local routing
- Days 3-4: Deploy Dify; connect LLM nodes to LiteLLM; build first CEO workflow (daily briefing)
- Days 4-5: Configure Onyx RBAC (CEO workspace + 2-3 dept workspaces)
- Days 5-6: Deploy LangFuse; wire LiteLLM cost tracking; first observability dashboard
- Day 7: CEO review session

**Week 2**: Build 3-5 dept-specific workflows in Dify; connect Onyx knowledge bases per dept; non-coder dept head onboarding; refine model routing rules.

**What is proven**: Onyx connector ecosystem (50+ connectors); Dify visual builder (30K stars, 2+ years production use); LiteLLM routing; LangFuse observability. All four have thousands of validated deployments.

**What is risky**:
- Dify + Onyx running as separate services requires a clear API boundary — which platform "owns" the conversation? Decide before building: Dify as the orchestrator (calling Onyx's API for knowledge retrieval) is the recommended pattern.
- Dify's MCP support (v0.6+) is maturing; complex MCP integrations may need workarounds for the first 2 weeks.

**Biggest open question**: Will the CEO want a single chat interface (Onyx) or a workflow-builder-centric experience (Dify)? These are different UX paradigms. Settle this in Day 1.

**Confidence level**: High.

---

### Option B — AnythingLLM + LiteLLM (Speed-First, Lowest Complexity)

| Layer | Tool | Role |
|---|---|---|
| Model router | LiteLLM | Claude to DGX Spark cost-tiering |
| Everything else | **AnythingLLM** (MIT) | Chat, RAG, agents, connectors, no-code builder, multi-user — all-in-one |
| Observability | LangFuse (MIT) | Tracing, cost |

**Integration**: AnythingLLM is the single platform (knowledge + agents + UI + multi-user). LiteLLM sits in front for model routing. No separate orchestration harness needed — AnythingLLM's built-in agent framework and no-code builder handle workflow construction.

**Deploy timeline**: 3-5 days to production. One-click Railway/Render deployment. Configure LiteLLM proxy; set Ollama endpoint; done. 62K GitHub stars means maximum community support for troubleshooting.

**What is proven**: AnythingLLM connectors (Gmail, Slack, Drive); one-click deploys; multi-user workspaces; no-code agent builder. Fastest validated path to a working system.

**What is risky**:
- RBAC is workspace-level (per department) but lacks fine-grained role controls (e.g., manager can edit, member can read only). Acceptable for CEO + 5 dept heads; may not scale to 50+ users.
- Built-in agent framework is less powerful than Dify for complex multi-step agentic workflows.

**Biggest open question**: Is workspace-level isolation sufficient, or does the CEO need cross-workspace visibility with read-only scoping?

**Confidence level**: High for speed; medium for enterprise governance at scale.

---

### Option C — Open WebUI + Onyx API + LiteLLM (Best UX, More Integration Work)

| Layer | Tool | Role |
|---|---|---|
| Model router | LiteLLM | Claude to DGX Spark cost-tiering |
| Web shell / chat UI | **Open WebUI** | Best-in-class UX: channels, notes, calendar, voice |
| Knowledge / retrieval | **Onyx CE** | 50+ connectors, agentic RAG, deep research |
| Observability | LangFuse | Tracing, cost |
| Auth | Authentik (from Day 1) | Required for multi-user + modified Open WebUI license |

**Integration**: Open WebUI provides the CEO-facing interface (closest to Glean polish). Onyx runs as a backend knowledge service, accessed via API from Open WebUI's tool/MCP server layer. LiteLLM routes model calls.

**What is proven**: Open WebUI UX (143K stars; v0.10.2 July 2026 = very active); Onyx knowledge backbone.

**What is risky**:
- Email and Slack integrations in Open WebUI require MCP server configuration (custom setup, ~2 days).
- Open WebUI's modified license requires branding preservation — verify with legal before production deployment.
- Integration between Open WebUI and Onyx API is not pre-built; requires custom MCP adapter or HTTP tool configuration (~1 day of custom glue).

**Biggest open question**: Is the CEO's UX bar high enough to justify 3-4 extra days of integration work vs. Option A/B?

**Confidence level**: Medium (components are proven; end-to-end assembly requires custom bridging).

---

### Top Recommendation: Option A (Onyx + Dify + LiteLLM)

**Rationale**:

1. **Onyx is the only knowledge system that meets all connector requirements out of the box** (Gmail, Slack, Drive = all three defaults, plus 47 more). Connector setup is UI-driven with no custom MCP glue.

2. **Dify is the only agent harness with all three required capabilities simultaneously**: MCP support, multi-user RBAC, and a visual no-code builder. Dept heads can build new workflows without any engineering involvement.

3. **LiteLLM solves the model router gap** in 2 hours with zero code written — the highest-priority architectural requirement (cost-tiering). Ollama v0.14.0+'s native Anthropic Messages API makes the integration trivial.

4. **All three components are MIT-licensed** — no licensing friction, no surprise commercial gates, no vendor dependency.

5. **The UX gap** (Onyx vs. Open WebUI in polish) is real but acceptable. Onyx's UI is professional and CEO-presentable; it includes deep research and agentic capabilities that Glean does not, which may actually exceed the CEO's UX bar on features.

6. **Timeline**: 7-10 days to a working system covering all five deliverables (connectors, multi-user, workflows, model routing, observability). Remaining 4-7 days for dept-specific configuration and user onboarding.

**Fallback**: If the CEO's UX bar is non-negotiable at Open WebUI level, switch to Option C and accept 3-4 extra days for integration work plus a legal review of the Open WebUI license.

**Speed fallback**: If timeline pressure requires cutting to 3-5 days, choose Option B (AnythingLLM solo) and plan migration to Onyx in month 2 when governance requirements emerge.

---

## Relevance to This Project

This research directly informs the stack selection decision for the executive Second Brain. Key outputs:

| Decision | Chosen | Rationale |
|---|---|---|
| Agent harness | **Dify** | Only tool with MCP + multi-user RBAC + no-code builder simultaneously |
| Knowledge system | **Onyx CE** | Only system with all three default connectors + enterprise RBAC + MIT |
| Model router | **LiteLLM** | 2-hour setup; Claude to DGX Spark transparent routing; cost tracking |
| Observability | **LangFuse** | 5-minute Docker deploy; MIT; deep agent tracing |
| Auth at scale | **Authentik** | 30-minute setup; lighter than Keycloak; OIDC native |
| DGX Spark serving | **vLLM + Llama 3.1 70B FP8** | Best concurrency; FP8 native on Blackwell; Docker-ready |
| Web shell | **Onyx Chat** (or Open WebUI overlay) | Embedded in knowledge system; avoids extra integration layer |

**Scope boundary confirmed**: AI project management is explicitly out of scope (handled by Taskyn PM per CLAUDE.md). This platform handles executive knowledge work and agentic task execution only.

**Self-serve extension model**: Dify's visual workflow builder directly satisfies the "dept heads self-serve" requirement. Non-coders can build new workflows by connecting LLM nodes, knowledge base nodes, and HTTP/MCP tool nodes in the Dify canvas — without writing code. The no-code constraint is satisfied without compromise.

**Architecture risk to prototype first** (Day 1): The Dify-to-Onyx API integration seam. Validate that Dify can call Onyx's REST API for knowledge retrieval before committing to the full stack build.

---

## Sources

### Agent Harnesses / Orchestration
- [Dify GitHub](https://github.com/langgenius/dify) — Stars, license, MCP v0.6+ support, feature overview
- [Dify Official Site](https://dify.ai) — Visual workflow builder, multi-model routing, enterprise features
- [Dify Summer 2025 Highlights](https://dify.ai/blog/2025-dify-summer-highlights) — Recent feature additions
- [Flowise GitHub](https://github.com/FlowiseAI/Flowise) — Stars, license, feature comparison
- [n8n Official](https://n8n.io) — Licensing terms (Commons Clause), AI node capabilities
- [n8n Credential Docs](https://docs.n8n.io) — OAuth2 and external secrets management (see n8n.io/docs)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/) — Architecture, stateful graph execution
- [CrewAI GitHub](https://github.com/crewAIInc/crewAI) — Role-based multi-agent framework
- [AutoGen / AG2](https://ag2.ai) — Microsoft conversable agents
- [Letta GitHub](https://github.com/letta-ai/letta) — Memory-augmented agents, MCP roadmap
- [Claude Agent SDK Docs](https://docs.anthropic.com/en/docs/claude-code/sdk) — MCP native support
- [Pydantic-AI Docs](https://ai.pydantic.dev) — Type-safe agent development, model routing
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) — Feature set (eliminated)

### Second-Brain / Knowledge Systems
- [Onyx GitHub](https://github.com/onyx-dot-app/onyx) — MIT license, v4.2.2, 50+ connector list
- [Onyx Docs](https://docs.onyx.app) — RBAC, SSO, SCIM, deep research, custom agents
- [AnythingLLM GitHub](https://github.com/Mintplex-Labs/anything-llm) — 62K stars, MCP compatibility, connector list
- [AnythingLLM Docs](https://anythingllm.com) — One-click deployments, workspace model
- [Open WebUI GitHub](https://github.com/open-webui/open-webui) — 143K stars, v0.10.2, license terms
- [Open WebUI Docs](https://docs.openwebui.com/features/authentication-access/) — RBAC, SSO, SCIM features
- [Khoj GitHub](https://github.com/khoj-ai/khoj) — 35K stars, AGPL-3.0, personal-first design
- [Cognee GitHub](https://github.com/topoteretes/cognee) — Knowledge graph, Apache 2.0, Claude Code plugin
- [Mem0 GitHub](https://github.com/mem0ai/mem0) — 60K stars, April 2026 algorithm, LoCoMo benchmarks
- [Morphik GitHub](https://github.com/morphik-org/morphik-core) — ColPali multimodal RAG
- [Reor GitHub](https://github.com/reorproject/reor) — Desktop-only; eliminated

### Gap Analysis Tools
- [LiteLLM Docs](https://docs.litellm.ai/) — Proxy setup, Claude routing, costtracking
- [LiteLLM: Claude Code Integration](https://docs.litellm.ai/docs/tutorials/claude_responses_api) — Official tutorial
- [Ollama Anthropic Compatibility Docs](https://docs.ollama.com/api/anthropic-compatibility) — Native Anthropic Messages API (v0.14.0+, Jan 2026)
- [RouteLLM GitHub](https://github.com/lm-sys/RouteLLM) — ML-trained routing, ICLR 2025
- [Authentik Docs](https://goauthentik.io/) — IdP setup, OIDC, group RBAC
- [Authentik vs Keycloak Comparison](https://www.cerbos.dev/blog/authentik-vs-keycloak-selfhosted-idp-comparison) — Resource requirements, setup complexity
- [LangFuse Docs](https://langfuse.com/) — Self-hosting, LiteLLM integration
- [LangFuse GitHub](https://github.com/langfuse/langfuse) — MIT license, architecture, Docker deploy
- [Infisical](https://infisical.com) — MIT secrets management; comparison vs HashiCorp Vault
- [Zapier AI](https://www.eesel.ai/blog/zapier-ai) — Cloud no-code AI agent features (Sep 2025)
- [Make.com](https://www.make.com/en) — Cloud workflow automation, AI Agents (Apr 2025)
- [Chainlit GitHub](https://github.com/Chainlit/chainlit) — Python chat app framework; community-maintained note

### DGX Spark Serving
- [NVIDIA DGX Spark Product Page](https://www.nvidia.com/en-us/products/workstations/dgx-spark/) — Official specs and pricing
- [NVIDIA DGX Spark Hardware Docs](https://docs.nvidia.com/dgx/dgx-spark/hardware.html) — Memory bandwidth, compute specs
- [NVIDIA DGX Spark Known Issues](https://docs.nvidia.com/dgx/dgx-spark/known-issues.html) — Thermal, OOM, power adapter issues
- [NVIDIA DGX Spark Release Notes](https://docs.nvidia.com/dgx/dgx-spark/release-notes.html) — Feb 2026 firmware (2.6x perf improvement)
- [LMSYS: DGX Spark In-Depth Review](https://www.lmsys.org/blog/2025-10-13-nvidia-dgx-spark/) — 695 tok/s at 256 concurrent; 2.7 tok/s Ollama decode; benchmarks
- [IntuitionLabs DGX Spark Review](https://intuitionlabs.ai/articles/nvidia-dgx-spark-review) — Thermal throttling, practical recommendations
- [CanIRun.dev: DGX Spark 128GB](https://canitrun.dev/gpus/dgx-spark/) — Model size compatibility calculator
- [Fungies.io: DGX Spark Setup Guide 2026](https://fungies.io/nvidia-dgx-spark-local-llm-setup-guide-2026/) — Practical LLM setup instructions
- [Red Hat: Ollama vs vLLM Deep Dive](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking) — 793 tok/s (vLLM batch) vs 41 tok/s (Ollama)
- [vLLM Blog: DGX Spark Configuration](https://vllm.ai/blog/2026-06-01-vllm-dgx-spark) — Official vLLM DGX Spark guide and CUDA 13 nightly
- [ITECS: Inference Engine Comparison 2025](https://itecsonline.com/post/vllm-vs-ollama-vs-llama.cpp-vs-tgi-vs-tensort) — vLLM vs Ollama vs TRT-LLM vs llama.cpp
- [SitePoint: Ollama vs vLLM Benchmark 2026](https://www.sitepoint.com/ollama-vs-vllm-performance-benchmark-2026/) — Updated throughput numbers
- [Medium: Four Inference Engines on DGX Spark](https://medium.com/@michael.hannecke/four-inference-engines-one-box-when-to-use-which-on-the-dgx-spark-6b32a53db768) — Per-engine DGX Spark recommendations

---

## Design Decisions — Locked (K + V session, 2026-07-02)

Decisions taken interactively after reviewing this research. These override any ambiguity above.

### D1 — Direction: commodity assemble (Option A)
**Locked: Onyx + Dify + LiteLLM**, with LangFuse (observability), Authentik (auth at scale), and DGX Spark serving **Llama 3.1 70B FP8 via vLLM**. Rationale: the SB here is an **internal tool, not a product that needs a moat** — commodity assembly is the *right* fit here, not a compromise. Everything needed is assemble-able; no from-scratch build.

### D2 — Front door: chat-first
The user **lives in the chat** (Onyx as the primary surface). The visual workflow builder is **not** the front door.

### D3 — Workflow authoring is conversational, not canvas-drawn
Workflows are **built automatically from the conversation** — the "like Kaushik and Velasari talk" model. A **conversational orchestrator (Claude Agent SDK)** sits behind the chat: when it hears a durable, recurring task, it **writes a workflow into Dify via Dify's API** and runs it. Dify becomes the **runtime the agent writes to**, not a canvas humans draw on.

> **Honest scope flag:** this conversation → reliable-saved-workflow **synthesis layer is the real custom build** — the "harness engineering." The research's "no custom glue needed" verdict (Section 3) applied to the *drag-drop* interpretation of the no-code requirement. The **chat-builds-workflows** interpretation chosen here needs this intelligence layer built on top of the assembled parts. Timeline reality: the assembled plumbing (knowledge / runtime / routing) is ~2 weeks; **the synthesis layer is the real work and where the value sits.**

### D4 — Cognitive Memory (CM) is OUT of scope
Considered: replicating the **Velasari substrate** (CM as the living memory layer in place of Onyx's vanilla vector store). **Rejected.** CM is open-source in Kaushik's repo, so the reason is **positioning, not legal**: CM is Kaushik's crown-jewel asset that should distinguish **his own product seeds** — not power an employer's internal tool (IP-conduit risk). The commodity stack stays; **CM stays Kaushik's.**

### D5 — Borrow the *open* memory + governance patterns
Instead of CM, adopt the **open** patterns surfaced from Nate B. Jones's ecosystem (evaluated but not adopted wholesale — both are personal/prosumer scale, no exec polish):
- **From Open Brain (OB1):** provenance / derivation chains, **recall-trace** records ("what did the AI actually use to answer this"), use-policy metadata, audit trails, and the **rebuild-safe embedding schema** (source content and vectors in separate tables, tagged by which model produced them → re-embed without data loss).
- **From Open Engine:** **receipts** (AGENT CLAIMED / DONE / BLOCKED / HUMAN HOLD), **human-review holds**, and explicit review states — the agent-execution legibility layer.

These feed the **accountability layer** the org rollout needs, which the base Onyx/Dify stack under-emphasizes. They are open patterns — adopt freely.

**Net line:** Kaushik's crown jewel (CM) distinguishes *his* seeds; the result is a strong assembled tool with an open governance layer grafted on.
- [NVIDIA Build: TensorRT-LLM for DGX Spark](https://build.nvidia.com/spark/trt-llm) — Official TensorRT-LLM build guide
- [Ollama Remote Access Guide](https://markaicode.com/ollama-network-exposure-secure-remote-access-guide/) — Network exposure patterns, Nginx reverse proxy
- [ngrok: Expose Ollama Securely](https://ngrok.com/docs/universal-gateway/examples/ollama/) — Public HTTPS with OAuth for remote access
- [VRLA Tech: LLM Quantization 2026](https://vrlatech.com/llm-quantization-explained-int4-int8-fp8-awq-and-gptq-in-2026/) — FP8 vs INT8 vs INT4 quality trade-offs
- [Spheron: GPU Memory Requirements 2026](https://www.spheron.network/blog/gpu-memory-requirements-llm/) — VRAM by model size and quantization level
- [MindStudio: Local AI with Claude Code](https://www.mindstudio.ai/blog/run-local-ai-models-with-claude-code-cut-costs) — 10x cost reduction with hybrid architecture
- [DEV: Hybrid LLM Routing (Ollama + Claude)](https://dev.to/lokyfour/hybrid-llm-routing-ollama-claude-api-without-quality-degradation-5e5b) — Practical routing patterns with LiteLLM
- [Medium: Connecting Claude Code to Local LLMs](https://medium.com/@michael.hannecke/connecting-claude-code-to-local-llms-two-practical-approaches-faa07f474b0f) — LiteLLM proxy setup walkthrough
- [Red Hat: llama.cpp vs vLLM (Jun 2026)](https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine) — Latest framework comparison
