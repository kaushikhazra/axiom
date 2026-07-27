# M9 · Connectors — Requirements

**Spec:** `011-m9-connectors`
**Milestone:** M9 — "Connectors. Email / Slack / Drive knowledge intake." (`001-agent-core-roadmap.md`)
**Status:** DRAFT — scoping only, blocked on an open question before user stories are written

---

## Purpose

`architecture.md` names Connectors as "knowledge-intake adapters (email, Slack, Drive, meeting transcripts)" — a new port, structurally the same class of component as Tools (M4) and Skills (M5): an external-facing adapter surface the core never imports directly. `001-agent-core/requirement.md`'s own component list frames it as "ingest the user's world... the knowledge intake" — content flows in, presumably landing in Memory (M3) the same way a conversational turn does today.

**Why this milestone is scoped differently from M6/M7/M8.** Every open question resolved in M6 (Router), M7 (Orchestrator), and M8 (Self-correction) was answerable by reasoning from `architecture.md`, existing code, and precedent already in this repo — no external dependency stood between "decide" and "build." M9 is different: a real email/Slack/Drive connector needs credentials for a real external account (an OAuth app registration, an API token) that only a human can provision. That is not a design ambiguity this milestone can reason its way through overnight; it is a hard external dependency. Per the standing "Kaushik asleep, co-think and proceed" authorization already exercised for M6–M8, this milestone stops short of writing user stories / acceptance criteria until the scoping question below is answered — proceeding to build against an undecided architecture would risk the same failure class this project's own DoD philosophy exists to catch: something that looks "done" (tests green, a connector class exists) without actually delivering "ingest the user's world."

**A relevant fact this scoping question turns on:** the Claude Code session this milestone would be built in already has authenticated MCP tools for Gmail, Slack, and Google Drive (`mcp__claude_ai_Gmail__*`, `mcp__claude_ai_Slack__*`, `mcp__claude_ai_Google_Drive__*`) — these are the *user's own* claude.ai connectors, available in this interactive session. That changes the shape of the real question:

## Open Question — OQ-1: MCP-wrapped vs. direct-API connectors

**The question:** Does `ConnectorPort`'s first real adapter (a) wrap the already-authenticated `mcp__claude_ai_*` MCP tools available in this session, or (b) integrate directly against Gmail/Slack/Drive's own REST APIs with Axiom-owned credentials?

**Why it matters — these are genuinely different architectures, not an implementation detail:**

| | (a) MCP-wrapped | (b) Direct API |
|---|---|---|
| Auth | Reuses the user's existing claude.ai connector session — zero new credential provisioning to unblock M9's build/verify loop *now*. | Needs a human to register an OAuth app / API token for Axiom's own standalone runtime before any code can be verified live. |
| Portability | Only works inside a Claude Code / claude.ai session with those connectors enabled — **not present in Axiom's own headless runtime** (`axiom-cli` run standalone, or any future daemon/scheduled-run mode) per this project's own MCP-instructions caveat: "interactively-authenticated MCP servers... may be absent in headless/cron runs." | Works anywhere Axiom itself runs, including fully autonomous/headless — matches the "Second Brain" vision of an agent that ingests the user's world on its own schedule, not just inside an interactive coding session. |
| Build-now feasibility | Can be prototyped and live-verified *tonight*, no blocker. | Blocked until credentials exist — genuinely blocked, not a guessable default. |
| Fit with `architecture.md`'s "core never imports an adapter; adapters import port contracts" | Still fits — the adapter would import the MCP tool-call surface instead of a REST SDK. Same port shape either way. | Same fit. |

**This is a real fork, not a false choice** — (a) is fast to prove but wrong for the system's actual long-term shape (an autonomous agent, not an interactive-session dependent one); (b) is architecturally correct for the vision but has a hard external blocker no amount of design reasoning removes tonight.

**Recommendation (not a decision — velasari/Kaushik's call):** build `ConnectorPort`'s contract now (independent of (a) vs (b) — a `list_recent(source, since) -> list[ConnectorItem]` / `fetch(source, item_id) -> ConnectorItem` shape works for either), and prototype the *first* concrete adapter against (a) MCP-wrapped Gmail specifically because it's provable tonight with zero new external dependency — but do **not** mark M9 "done" on that basis. A connector whose only implementation depends on an interactive session's ambient MCP tools is a structural proxy for "ingest the user's world," not the real thing (the exact Pass 10 / M3-incident trap this project's own dryrun-design process exists to catch) — it would need to be explicitly flagged as "prototype only, not the shipped connector" rather than counted as delivering M9's Purpose. The real, autonomous-capable connector (b) is follow-up work requiring Kaushik to provision credentials for Axiom's own runtime.

**Status:** Flagged to velasari via crosstalk (2026-07-27, overnight session). Genuine wait observed; proceeding with scoping-only documentation (this file) rather than committing to user stories or implementation pending a reply, per the reasoning above.

---

## Out of Scope (for now — pending OQ-1)

- User stories, acceptance criteria, and `design.md` — deliberately not written yet. Writing ACs against an undecided architecture (MCP-wrapped vs. direct-API) would produce criteria that don't survive whichever way OQ-1 resolves.
- Any actual OAuth app registration, API token provisioning, or write access to a real Gmail/Slack/Drive account — not attempted without explicit authorization, regardless of how OQ-1 resolves.
- Meeting-transcript ingestion (named in `architecture.md`'s Connectors line but not elaborated anywhere) — deferred to a later requirement pass once the email/Slack/Drive shape is settled, per the roadmap's own component ordering.
