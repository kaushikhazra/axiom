# M2 · Observability — Architecture Research

**Project:** Axiom (agent-core)
**Milestone:** M2 — Observability ("watch it think")
**Author:** Velasari — 2026-07-13
**Status:** DESIGN RESEARCH — pre-spec. **Rev 3** — incorporates Fable Round-1 **and Round-2** review resolutions (see §10 changelog + `005-...-review-fable-r1.md`). Fable Round-2 verdict: both R1 blockers genuinely closed; spec-ready after the R2 edits folded in here.

---

## 1. Purpose

M2 makes the agent's reasoning **visible** — a structured trace of every loop cycle, so every later milestone (Memory, Tools, Skills, Router) is *judgeable against observed behavior*, and so the system is trustworthy by inspection. It is the foundational **trust layer**: glass-box at build-time, persistent trace on every run.

**Baseline today (shipped code):** only `src/axiom/observability/timing.py` — wall-clock timing via stdlib `logging` at DEBUG (the M1 stub). Adapters: `claude_adapter.py` (KIND B — provider owns loop) and `local_adapter.py` (KIND A — we own loop, spec `003-local-adapter`). A run currently leaves only timing — a black box on *why*.

---

## 2. The four design axes

1. **Generalize** — observation is defined at the **Agent-port level**; works for any provider. The provider-specific part is the adapter translating native trace into the standard span shape.
2. **Standardize (what)** — one normalized schema. Depth-asymmetry is explicit (KIND A = every step; KIND B = streamed messages only) → **common core + provider-specific extensions bag**.
3. **Emit (how/where)** — file, TUI, stream-to-web, under **single-producer / multiple-consumer**.
4. **Async** — non-blocking emit; trace-writing never locks the agent process (a latency invariant).

---

## 3. Data model & instrumentation — reuse the OTel SDK, own the transport

**How the field does it:** the space has converged on **OpenTelemetry GenAI semantic conventions** (v1.41): agent/workflow/tool/model **spans** in a **span tree** (run = root span; each reason/act/tool call = a nested child span with duration), plus token/latency metrics and `gen_ai.*` attributes. Minimum viable signal: **step-level tracing**.

**Decision (reuse over build — maintenance argument):**
- **Adopt the OpenTelemetry *SDK* in-process** (`opentelemetry-sdk`) — a library, same trust class as `websockets`; **no collector, no external process**. It gives us, for free and battle-tested: **span creation, context propagation (parent/child ID minting), and the attribute model**. Hand-rolling span-context propagation is subtle infra we would own forever.
- **Confine OTel to the observability faculty.** The core loop stays framework-free (roadmap invariant); OTel lives behind the Observability call-point, never in loop control flow.
- **Emit via a custom `SpanProcessor`/exporter** that serializes each finished span to **JSONL** and publishes it to our **owned in-process fan-out** (§4–5). OTel's processor hook is the emit seam; the transport downstream is ours.
- **Reject the OTel *stack*** (collector + backend service) — external-install infra Axiom avoids. (This is the distinction Round-1 F6 flagged: SDK ≠ infra.)
- **`gen_ai.*` caveat:** those attributes are "Development" stability — names churn. Mirror the shape; carry OTel's `schema_url` **and** a local `schema_version` field on every JSONL record so old files stay parseable (F5).

**Wire format:** **JSONL** — one span-serialization per line. Append-only; each line independently parseable; neutral (web wraps as SSE/WS; a future analytics sink loads lines into sqlite). JSONL is the *producer's* format, never a consumer's storage — consumer storage stays **deferred**.

**Verify (spike before spec) — OTel impedance is more than batching:**
1. **`contextvars` propagation across asyncio task boundaries — HIGHEST RISK.** OTel span context lives in a `contextvars.Context`. It follows `await` *within* a task but does **not** auto-propagate across `asyncio.create_task` / `run_in_executor` / callbacks. The KIND B adapter streams (likely a task per stream), so a child span opened in a different task than its parent orphans or mis-parents — reintroducing F1 at the implementation layer. The spike must exercise `context.attach` / `copy_context` across our actual task boundaries, not just "confirm interaction with the loop."
2. **Live sinks may need span-lifecycle events, not finished-span serialization.** A custom `SpanProcessor` sees a fully-populated span only on `on_end` — which for a 30 s Act fires exactly when you no longer need "Act in progress." Live TUI/WS likely need **span-open / span-close** events; that is a schema + processor decision, made now or reworked later.
3. **Batch-vs-live latency.** `BatchSpanProcessor` is off-hot-path (good) but adds delivery latency — wrong for live sinks; use a low-latency `SimpleSpanProcessor`-style path for them.
4. **Dependency pinning.** `opentelemetry-sdk` pulls a small tree (`-api`, `-semantic-conventions`) with its own cadence — pin it. ("Same trust class as `websockets`" understates the dep count, not the trust.)

---

## 4. Transport — in-process fan-out with a subject seam

**Constraint (Kaushik):** no **external** queue system — an external broker is an installation failure point + attack surface; in-process is simpler and more secure. Holds even though NATS runs on kh-legion (requiring it when Axiom ships is the failure point).

**Round-1 F4 resolution — seam yes, taxonomy no.** M2 ships a **sink registry with per-consumer queues** — the minimal thing observability needs. Its publish interface is **subject-addressable by shape** (`publish(subject, record)`), so the future A2A tenant (roadmap **M7 Orchestrator** — a committed milestone, not vapor) can add subjects **without rework**. But M2 uses a **single `trace` channel only**; the **subject taxonomy / addressing scheme is deferred to M7**, when A2A's real requirements (addressing, request/reply, delivery guarantees) exist. We do not design the namespace blind now.

This removes the earlier §4/§5 contradiction: it **is** a sink registry, subject-addressable by interface — not a fully-specified bus. It respects the architecture's rejection of an event-bus-in-the-core, because this is downstream of the producer, minimal, and taxonomy-deferred.

**Honest scope of the seam (F4a):** the seam spares **publishers** from rework — M7 adds subjects without touching publish call-sites. It does **not** make the whole bus M7-free: today's fan-out is broadcast-all (every sink gets everything, §5), whereas A2A needs **addressed** delivery (a message for agent-X routes to agent-X). That is a *routing* change in the fan-out core at M7 — known, deferred, not "no rework." So: no rework **to publishers**; the fan-out **gains routing** at M7.

**Contention note (for M7, not M2):** when A2A lands, control-plane messages (e.g. a mid-run ABORT) must not sit behind a trace burst. That is an M7 design constraint recorded here, not solved now — another reason not to fuse the contracts prematurely.

**Rejected alternatives:** external NATS (install/attack surface); MQTT/amqtt (overkill — full protocol surface, alpha-versioned); OTel collector/backend (external infra).

---

## 5. Fan-out, buffering, async, durability

- **Single producer** — the OTel `SpanProcessor` emit hook, fed by the Observability RECORD call-point at every `perceive → reason → act → observe` boundary.
- **All sinks get everything** — broadcast; no producer-side filtering. Filtering is consumer-side.
- **The backpressure invariant (F3, stated):** with *no producer backpressure* + *all sinks get everything* fixed, each consumer buffer is necessarily **bounded-and-lossy** or **unbounded-and-a-leak**. There is no third option. We choose per sink:

| Sink | Loss class | Buffer contract |
|------|-----------|-----------------|
| **File** | **bounded-durable** | Drains on **its own thread** (never the producer's), with a **deep** bounded queue + **aggressive periodic fsync**. Guarantee: durable up to queue depth *D*; beyond sustained rate *R* it drops with a gap-marker like the others. It is the *most* durable sink, not an absolutely durable one. |
| **TUI** | loss-tolerant | Bounded, **drop-oldest**, emit a gap-marker |
| **WS/web** | loss-tolerant | Bounded, **drop-oldest**, emit a gap-marker |

- **No sink taxes the producer (F2a).** All three, file included, drain on their own consumer threads; the producer hands off and returns. The file sink differs only by *queue depth* and *flush aggressiveness*, not by back-pressuring the loop — so §2's non-blocking latency invariant holds without exception. (A synchronous "forensic durable" mode that fsyncs on the producer thread is a possible *future opt-in config*, explicitly not M2 — it would trade the latency invariant for absolute durability.)
- **F2 durability fix:** the earlier "a crash costs only the last line" was **false** for the async pipeline (buffered records die with the process). Corrected: the file sink is **bounded-durable** (above), not absolutely durable; TUI/WS are best-effort. The false sentence is removed and the §7 box reads "durable (bounded)".
- **Async / non-blocking emit** — producer returns immediately after handing off; consumers drain independently at their own pace. No sink — WS, TUI, or file — can back-pressure the producer.
- **Dropped-record honesty:** a lossy sink that drops emits an explicit **gap-marker (dropped-count)** so its consumer knows data was lost — and, because a dropped record can orphan a child span, the marker lets a tree-renderer choose tolerate-orphans vs drop-whole-span (F3).
- **Ordering (F8):** single producer + FIFO per-consumer queue ⇒ **per-consumer record order preserved**. Live-tree consumers can rely on parent-before-child arrival within a consumer.

---

## 6. Provider generality & the span tree (F1 resolution)

**The loop owns the tree.** `perceive / reason / act / observe` are the real parent spans, minted via OTel context — **KIND-agnostic**. So `parent_span_id` is **always meaningful**: it points at a real loop-level span for every provider.

- **KIND A (we own the loop** — local vLLM / direct API): nested child spans per internal step; full depth.
- **KIND B (provider owns the loop** — Claude/Codex): the adapter opens a span for the delegated **Act**, and maps the streamed events (tool-calls / messages) to child spans **under that Act span** — best-effort depth, **not** a claim to reconstruct the provider's internal tree. This is the F1 answer: *flat-ish under the Act span, but the parent pointer is always valid.*
- **`span_source` attribute** (`core-minted` | `provider-streamed`) tags each span so consumers know its fidelity.
- **Consumer contract:** you MAY rely on `parent_span_id` being meaningful for all providers; you may NOT assume provider-internal depth for KIND B.
- The **extensions bag** absorbs *attribute* asymmetry (missing token counts, etc.) — separate from the structural tree question above.

---

## 7. Architecture (vertical)

```
╔════════════════════════════════════════════════════╗
║                    AGENT LOOP                      ║
║               (the single producer)                ║
║      Perceive ─▶ Reason ─▶ Act ─▶ Observe ─▶ …     ║
║   loop owns the span tree (OTel context = parents) ║
╚═══════════════════════┬════════════════════════════╝
                        │  adapters feed spans:
                        │   KIND A → nested child spans (full)
                        │   KIND B → children under Act (best-effort)
                        ▼
┌────────────────────────────────────────────────────┐
│  OTel SDK  (in-process, no collector)              │
│  spans + context propagation + gen_ai.* attrs      │
│  custom SpanProcessor → JSONL (+ schema_version)   │
└───────────────────────┬────────────────────────────┘
                        │  async · non-blocking
                        ▼
┌────────────────────────────────────────────────────┐
│  IN-PROCESS FAN-OUT  (sink registry)               │
│  publish(subject, record); M2 = 'trace' only       │
│  subject seam ready for agent.* at M7 (taxonomy TBD)│
│  dumb + complete → every sink gets EVERYTHING       │
└───────────────────────┬────────────────────────────┘
                        │  fan-out (each drains own pace)
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   [bounded+flush]  [bounded,drop]  [bounded,drop]
        ▼               ▼               ▼
   ┌─────────┐     ┌──────────┐    ┌──────────────┐
   │ FILE    │     │  TUI     │    │ WEBSOCKETS   │
   │ .jsonl  │     │ live     │    │ localhost +  │
   │ durable │     │ (lossy)  │    │ token auth   │
   │(bounded;│     │          │    │ (lossy)      │
   │ own thrd)│    └──────────┘    └──────┬───────┘
   └─────────┘                            ▼
                                 filtering consumer-side
```

---

## 8. Security, redaction, versioning (F5), recursion (F7)

- **WS port security:** the bridge **binds localhost-only + requires a token**. It streams full reasoning (prompts, tool args, possibly secrets) — the highest-value endpoint on the box; leaving it open would contradict rejecting NATS *as attack surface*.
- **Redaction policy (M2 decision, stated):** **no redaction in M2** — traces are trusted-local; file sink written `0600`. A redaction hook is deferred to when Connectors / untrusted input arrive (roadmap M9 / Guardrails), where it belongs. Silence would have been the bug; this is the decision.
- **Schema versioning:** every JSONL record carries `schema_version` (+ OTel `schema_url`). Given `gen_ai.*` churn, this keeps old traces parseable.
- **Self-observation recursion (F7):** a sink's *own* errors (WS exception, file IOError) go to **stdlib logging, never onto the bus** — no trace-of-the-trace loop.

---

## 9. Open questions / for the spec to lock

- Exact **core-vs-extensions attribute boundary** (which `gen_ai.*` fields are core).
- **File sink** storage location + rotation policy; concrete queue depth *D* and drain/fsync cadence.
- **Gap-marker format** for dropped records (F3).
- **OTel async-impedance spike** (§3 verify) — must cover, in priority order: (1) `contextvars` propagation across our asyncio task boundaries; (2) span-lifecycle events vs finished-span serialization for live sinks; (3) batch-vs-live processor choice; (4) dep pinning.
- **KIND-B stream→span mapping** contract detail (which stream-event types open/close child spans). **Note (F1a):** *concurrent* provider stream events (parallel tool calls, subagents) collapse to **sequential siblings** under the Act span — the spec must not attempt to reconstruct provider concurrency (that would revive the internal-depth fidelity claim §6 disclaims).

### Spec-author priorities (Fable Round-3, non-blocking)

1. **The `contextvars` spike is a true gate, not a formality — run it FIRST.** If OTel context won't cleanly follow the KIND-B streaming task boundaries even with `copy_context`, the §6 "`parent_span_id` always valid" guarantee weakens at the implementation layer. Run it **before the schema is frozen**, because span-lifecycle-vs-finished-span (spike item 2) also feeds the schema shape.
2. **Spec the gap-marker early — it is load-bearing across three mechanisms:** F2a (file-sink rate-*R* drops), F3 (orphan-span signaling), and TUI/WS drop-oldest all depend on it. It is a small schema object, not a late detail.
3. **M7 name — verified.** The roadmap (`001-agent-core-roadmap.md`) names **M7 — Orchestrator** ("multi-provider consortium — the committee; Velhari-pattern"), a committed milestone. The §4 forward-reference is exact; F4's deferral defense holds.

---

## 10. Changelog — Round-1 (Fable) resolutions

- **F1 (BLOCKER)** → §6: loop owns the tree; `parent_span_id` always valid; KIND B = best-effort children under Act; `span_source` tag. OTel context propagation mints IDs.
- **F2 (BLOCKER)** → §5: false durability sentence removed; file sink alone gets a durability contract (bounded flush-on-boundary); TUI/WS best-effort.
- **F3** → §5: backpressure invariant stated; per-sink loss classes; gap-markers.
- **F4** → §4: pub/sub *seam* kept (A2A = roadmap M7), subject *taxonomy deferred*; §4/§5 contradiction removed.
- **F5** → §8: WS localhost+token; redaction policy stated; `schema_version` added.
- **F6** → §3: adopt OTel **SDK** in-process (reuse over build); reject only the collector/stack.
- **F7** → §8: sink errors → stdlib logging, never the bus.
- **F8** → §5: per-consumer FIFO ordering stated.

**Round-2 (Fable) resolutions:**
- **F2a (CONCERN)** → §5: file sink drains on its **own thread** (never taxes the producer — invariant contradiction removed); guarantee restated as **bounded-durable** (depth *D* / rate *R*, drops with gap-marker beyond); synchronous "forensic durable" mode noted as future opt-in, not M2; §7 box now "durable (bounded)".
- **F6a (CONCERN)** → §3 + §9: OTel spike expanded — `contextvars`-across-asyncio-tasks named as **highest** risk (can revive F1 at impl layer), plus span-lifecycle-vs-finished-span for live sinks, plus dep pinning.
- **F4a (NIT)** → §4: honesty clause — seam spares **publishers**; the fan-out **gains routing** at M7 (broadcast-all → addressed delivery).
- **F1a (NIT)** → §9: concurrent KIND-B stream events collapse to sequential siblings; spec must not reconstruct provider concurrency.

---

## 11. Non-goals (fenced)

No external broker. No MQTT. No OTel collector/backend (SDK yes, infra no). No subject taxonomy in M2. No redaction in M2. No web dashboard (CLI + read-back + raw authenticated WS stream only). No consumer storage decision. No self-correction (M8).
