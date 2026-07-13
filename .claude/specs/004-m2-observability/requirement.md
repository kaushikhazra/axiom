# M2 · Observability — Requirements

**Spec:** `004-m2-observability`
**Milestone:** M2 — "Watch it think"
**Author:** Velasari — 2026-07-13
**Status:** DRAFT — authored from Rev-3 research (`005-m2-observability-architecture-2026-07-13.md`)

---

## Purpose

M2 makes Axiom's reasoning **visible**: a structured trace of every PRAO loop cycle, emitted at every phase boundary, so every later milestone (Memory, Tools, Skills, Router, Orchestrator) is *judgeable against observed behavior*. It is the foundational **trust layer** — glass-box at build-time, persistent trace on every run.

Baseline before M2: only `src/axiom/observability/timing.py` — wall-clock timing via stdlib `logging` at DEBUG (the M1 stub). A run currently leaves only timing. M2 replaces that stub with a structured, provider-general, multi-sink tracing system.

---

## User Stories

---

### US-01 — Step-level PRAO trace at every phase boundary

**As** a developer running the Axiom agent,
**I want** a structured trace record emitted at every `perceive → reason → act → observe` boundary of the agent loop,
**so that** I can see exactly what happened at each loop phase — *not* a periodic health-check, but a per-phase record tied to the running cycle.

#### Acceptance criteria

- AC-01.1: A trace record is emitted at the **start and end** of each phase: Perceive, Reason, Act, Observe. No phase boundary is silent.
- AC-01.2: Each record identifies the loop cycle (run) it belongs to and the phase it represents (`perceive` | `reason` | `act` | `observe`).
- AC-01.3: The Observability RECORD call-point (as defined in `architecture.md`, firing at every phase boundary) is the **sole injection point** for trace emission — it does not live in loop control flow or in adapter code.
- AC-01.4: A record is emitted even if a phase completes with an error; the error is captured in the record, not silently swallowed.
- AC-01.5: Trace granularity is **step-level**: one record (or span) per phase boundary per cycle, not one record per run.

---

### US-02 — Provider-general span tree (KIND A + KIND B)

**As** a developer using any Agent port adapter (local KIND A or delegated KIND B),
**I want** the span tree to be rooted in the agent loop's own phase spans — regardless of provider kind —
**so that** `parent_span_id` is always meaningful and consumers always know where a span sits in the PRAO tree.

#### Acceptance criteria

- AC-02.1: The agent loop **owns the root span tree**: the four PRAO spans (Perceive / Reason / Act / Observe) are minted by the loop itself, not by the adapter.
- AC-02.2: For **KIND A adapters** (we own the loop — e.g. local vLLM via LiteLLM): adapters produce **nested child spans** under the relevant PRAO span, giving full internal depth.
- AC-02.3: For **KIND B adapters** (provider owns the loop — e.g. Claude via Agent SDK): the adapter maps streamed events (tool-calls / messages) to child spans **under the Act span only**, at best-effort depth. The implementation MUST NOT attempt to reconstruct the provider's internal loop or claim provider-internal depth.
- AC-02.4: For KIND B, concurrent provider stream events (e.g. parallel tool calls) are represented as **sequential siblings** under the Act span. The requirement explicitly does not demand concurrency reconstruction.
- AC-02.5: `parent_span_id` is **always a valid, non-null reference** for every span in the tree, for both KIND A and KIND B. A span with no logical parent points to the run's root span, not to null (except the run root itself).
- AC-02.6: Every span carries a `span_source` attribute with value `core-minted` (emitted by the loop's Observability call-point) or `provider-streamed` (emitted by a KIND B adapter from streamed events). Consumers MUST be able to distinguish these.
- AC-02.7: Consumer contract (stated in the spec, testable in integration): consumers MAY rely on `parent_span_id` being valid for all providers; consumers MUST NOT assume provider-internal depth for KIND B.

---

### US-03 — Normalized span schema: common core + extensions bag

**As** a consumer reading trace records (file, TUI, or WebSocket),
**I want** every record to conform to a documented common-core schema and carry a schema version,
**so that** I can reliably parse records from any provider without provider-specific parsing logic, while still accessing provider-specific attributes when present.

#### Acceptance criteria

- AC-03.1: Every JSONL record carries these **mandatory common-core fields** (minimum set; exact attribute boundary is an open question — see OQ-01):
  - `run_id` — unique identifier for the agent run (root span)
  - `span_id` — unique identifier for this span/record
  - `parent_span_id` — id of the logical parent span (see AC-02.5)
  - `trace_id` — OTel trace identifier propagated via OTel context
  - `span_source` — `core-minted` | `provider-streamed` (see AC-02.6)
  - `phase` — `perceive` | `reason` | `act` | `observe`
  - `provider_kind` — `KIND_A` | `KIND_B`
  - `schema_version` — local schema version string (see AC-03.4)
  - `otel_schema_url` — OTel `gen_ai.*` schema URL in effect at emit time
  - `start_time_unix_nano`, `end_time_unix_nano` — span timing in nanoseconds
  - `status` — `OK` | `ERROR`; when `ERROR`, an accompanying `error_message` field is present
- AC-03.2: Every record carries `gen_ai.*`-shaped attributes (following the OpenTelemetry GenAI semantic conventions shape) in the common-core, where those attributes are available. **Exact boundary between core and extensions bag is an open question** (see OQ-01).
- AC-03.3: Provider-specific or adapter-specific attributes that do not belong to the common core are placed in an **`extensions` object** (a freeform attribute bag) inside the record. No common-core field may be absent because "it isn't available for this provider" — if unavailable, it MUST be `null`, not omitted.
- AC-03.4: `schema_version` is a local version string (e.g. `"1.0"`) incremented on every backward-incompatible schema change. It is **independent** of `otel_schema_url` (which tracks OTel GenAI convention churn separately). Both fields are present on every record.
- AC-03.5: Records produced by KIND A and KIND B adapters are parseable by the same schema parser; the difference in depth/fidelity is encoded in `span_source` and `provider_kind`, not in structural schema divergence.

---

### US-04 — JSONL wire format with single-producer fan-out

**As** any trace consumer (file archiver, TUI renderer, WebSocket client),
**I want** trace records delivered as JSONL (one JSON object per line) via a single-producer fan-out,
**so that** every consumer receives every record without any consumer needing to query a central store.

#### Acceptance criteria

- AC-04.1: The producer serializes each finished span into **one JSONL line** (one valid JSON object, no embedded newlines, terminated by `\n`). Each line is independently parseable.
- AC-04.2: **All sinks receive all records.** The fan-out is broadcast — no producer-side filtering. Filtering (e.g. "only Act spans") is **consumer-side only**.
- AC-04.3: There is **exactly one producer**: the OTel custom `SpanProcessor` emit hook, invoked by the Observability RECORD call-point. No other code path publishes to the fan-out.
- AC-04.4: JSONL is the **producer's wire format**. Consumer storage (e.g. sqlite, indexed store) is deferred and out of scope for M2. Sinks receive JSONL; what they do with it internally is their concern.
- AC-04.5: The fan-out is an **in-process component** (a sink registry). There is no external message broker, queue service, or OTel collector. The in-process fan-out is the only transport between producer and sinks.

---

### US-05 — Async non-blocking emit with per-consumer buffering and drop-gap honesty

**As** the agent loop (the producer),
**I want** to hand off a trace record and return immediately, with zero possibility of any sink back-pressuring or blocking the loop,
**so that** the observability layer has zero latency impact on the agent's PRAO cycle time — a hard invariant, not a best-effort goal.

#### Acceptance criteria

- AC-05.1: The producer (`SpanProcessor` emit call) returns **immediately** after placing the record in each consumer's buffer. No sink's write speed, flush rate, or connectivity state can cause the producer to block, sleep, or wait.
- AC-05.2: Each consumer has its own **bounded, independent buffer queue**. The buffer sizes may differ per sink (file sink carries a deeper queue than TUI/WS sinks). Buffer sizes are **configurable**.
- AC-05.3: **Lossy sinks** (TUI, WS bridge): when the consumer buffer is full, the **oldest** record is dropped (drop-oldest policy). A **gap-marker record** is immediately appended to the consumer's queue in place of the dropped record (see AC-05.4). The producer is NOT involved in the drop decision — it is the consumer's own buffer logic.
- AC-05.4: The **gap-marker** is a first-class JSONL record. Its exact schema is an open question (see OQ-02), but it MUST carry at minimum: `"record_type": "gap_marker"`, a count of dropped records, the `run_id`, and approximate `drop_start_time_unix_nano`. Gap-markers allow consumers to detect data loss without silent holes.
- AC-05.5: A consumer that receives a gap-marker knows that child spans may be missing from the tree. Consumer implementations MAY choose to tolerate orphaned spans or drop the whole subtree — but the gap-marker signal MUST be present so they can make that choice.
- AC-05.6: Per-consumer FIFO ordering is preserved: within each consumer's buffer queue, records arrive in producer emit order. Live-tree consumers may rely on parent-before-child arrival order within their own queue.

---

### US-06 — File sink: bounded-durable, drains on its own thread

**As** a developer who wants a persistent record of every agent run,
**I want** a file sink that writes JSONL to a `.jsonl` file and is the most durable of the three sinks,
**so that** runs are inspectable after the fact and recoverable from restarts, within the bounded-durable contract.

#### Acceptance criteria

- AC-06.1: The file sink writes a **`.jsonl` file** (location and rotation policy configurable — see OQ-03). Each completed span appends one line.
- AC-06.2: The file sink has a **deep, bounded** consumer buffer queue (depth *D* — see OQ-03). Within that depth, records are durable. Records beyond the sustained rate *R* drop with a gap-marker (same gap-marker contract as AC-05.4). The file sink is **bounded-durable, not absolutely durable**.
- AC-06.3: The file sink drains its queue and writes to disk on **its own dedicated thread** — not the producer's thread, not the asyncio event loop. The producer never waits for a file write.
- AC-06.4: The file sink performs **periodic fsync** on its own thread to reduce crash-loss exposure. The fsync cadence is configurable (see OQ-03) but must not block the producer.
- AC-06.5: The output file is written with **permissions `0600`** (owner read/write only) — traces contain full reasoning, tool arguments, and potentially sensitive data.
- AC-06.6: File storage path and rotation policy (max size, max age, max file count) are configurable. The defaults are an open question at requirement time (see OQ-03).
- AC-06.7: A file sink error (IOError, disk-full) MUST be reported via **stdlib logging**, never onto the trace bus (see US-11).

---

### US-07 — TUI sink: live terminal view, lossy

**As** a developer running the agent interactively in a terminal,
**I want** a live TUI display of the trace as the agent runs,
**so that** I can watch the agent think in real time without opening a separate browser or file reader.

#### Acceptance criteria

- AC-07.1: The TUI sink renders incoming JSONL trace records as a **live terminal display** during an agent run.
- AC-07.2: The TUI sink uses a **bounded drop-oldest buffer** (capacity configurable). It is explicitly loss-tolerant: display frames may be dropped to keep the view live; the TUI will show gap-markers when drops occur.
- AC-07.3: The TUI sink drains on its **own thread or async task**, independent of the producer.
- AC-07.4: TUI sink errors (render exception, terminal resize fault) MUST go to stdlib logging, never the bus (see US-11).
- AC-07.5: The TUI sink is **optional at run-time** — it must be possible to run the agent without activating the TUI sink (e.g. non-interactive runs, CI).

---

### US-08 — WebSocket bridge sink: localhost-only, token-authenticated, lossy

**As** an external tool or developer dashboard consuming the trace,
**I want** a WebSocket endpoint that streams trace records in real time,
**so that** I can connect a browser devtool, custom visualizer, or other local consumer without coupling them to the agent's in-process state.

#### Acceptance criteria

- AC-08.1: The WS bridge **binds to localhost only** (`127.0.0.1`). It MUST NOT bind to `0.0.0.0` or any external interface. This is a security requirement — traces may contain prompts, tool arguments, and secrets.
- AC-08.2: The WS bridge requires **token authentication** on every connection. Unauthenticated connections are rejected. The token is configurable (generated at startup or provided via config).
- AC-08.3: Connected clients receive a **stream of JSONL lines** over WebSocket. Each message is one JSONL record (or a gap-marker record).
- AC-08.4: The WS bridge uses a **bounded drop-oldest buffer** (capacity configurable). It is loss-tolerant; clients receive gap-markers when drops occur (AC-05.4).
- AC-08.5: Client disconnection, WS handshake failure, or send error MUST go to stdlib logging, never the bus (see US-11).
- AC-08.6: The WS bridge sink is **optional at run-time** — the agent starts without it if no WS consumer is configured.
- AC-08.7: There is **no web dashboard** served from this port — raw authenticated WS stream only. A future rendering layer (browser UI) is out of scope for M2.

---

### US-09 — In-process pub/sub seam: subject-addressable, `trace` channel only in M2

**As** the Observability system (and the future M7 Orchestrator),
**I want** the fan-out to accept records via a subject-addressable publish interface (`publish(subject, record)`),
**so that** M7 can add new subjects (e.g. `agent.*`) without modifying publisher call-sites, while M2 operates on a single `trace` channel with no unnecessary complexity.

#### Acceptance criteria

- AC-09.1: The fan-out exposes a `publish(subject: str, record: dict)` interface. Publishers call this interface; the fan-out dispatches to registered sinks.
- AC-09.2: In M2, the Observability RECORD call-point publishes **only to the `trace` subject**. No other subjects are defined, created, or routed in M2.
- AC-09.3: The subject taxonomy (the naming scheme for `agent.*`, `system.*`, etc.) is **explicitly deferred to M7 (Orchestrator)**. The M2 spec does not define or constrain future subject names.
- AC-09.4: The honest scope of the seam: it **protects publishers** from rework when M7 adds subjects. It does NOT protect the fan-out internals from rework — M7 will add per-subject routing (replacing broadcast-all with addressed delivery). This is a known, recorded deferred change.
- AC-09.5: All three sinks (file, TUI, WS bridge) are registered against the `trace` subject in M2. All receive all `trace` records (broadcast-all, no filtering).
- AC-09.6: The fan-out is purely **in-process**. No external broker (NATS, MQTT, Redis Pub/Sub, or equivalent) is used or depended on.

---

### US-10 — OTel SDK in-process: span creation, context propagation, attributes

**As** the Observability implementation,
**I want** to use the OpenTelemetry Python SDK (`opentelemetry-sdk`) in-process for span creation, context propagation, and `gen_ai.*` attribute modeling,
**so that** Axiom inherits battle-tested span-ID minting and asyncio context propagation without hand-rolling that infrastructure, while keeping the OTel *stack* (collector, backend) entirely absent.

#### Acceptance criteria

- AC-10.1: The Observability faculty uses `opentelemetry-sdk` as an **in-process library** — same trust class as `websockets`. No OTel collector, no OTel backend, no external OTel process.
- AC-10.2: OTel is **confined to the Observability faculty**. The core loop (`loop.py`, `interfaces.py`) imports nothing from `opentelemetry`. OTel lives behind the Observability call-point.
- AC-10.3: Span IDs and parent/child linkage are minted via **OTel context propagation** (`opentelemetry.context`, `contextvars`). The loop does not hand-roll span-ID generation or parent-pointer tracking.
- AC-10.4: A custom `SpanProcessor` (or equivalent OTel hook) is the **emit seam** — it serializes each finished span to JSONL and publishes to the fan-out. The transport (fan-out, sinks) is Axiom's own code.
- AC-10.5: `gen_ai.*` attributes (OpenTelemetry GenAI semantic conventions) are applied where applicable. Their "Development" stability status is acknowledged — the schema versioning (AC-03.4) is the mitigation for churn.
- AC-10.6: `opentelemetry-sdk` and its transitive dependencies (`-api`, `-semantic-conventions`) are **pinned** in the project dependency manifest. They are treated as first-class versioned dependencies.
- AC-10.7: The OTel `BatchSpanProcessor` is **not used** for live sinks — its delivery latency is incompatible with real-time TUI/WS display. A low-latency (SimpleSpanProcessor-equivalent) path is used for live sinks.

#### Design-phase gates (must NOT be assumed away — run before schema is frozen)

- **DG-10.A — `contextvars` across asyncio boundaries (HIGHEST RISK):** OTel span context lives in a `contextvars.Context`. It propagates within a single asyncio task but does **not** auto-propagate across `asyncio.create_task` / `run_in_executor` / callbacks. The KIND B adapter likely uses a task-per-stream, meaning a child span opened in a different task than its parent can orphan or mis-parent — potentially re-introducing the F1 flat-tree problem at the implementation layer. A spike exercising `context.attach` / `copy_context` across Axiom's actual asyncio task boundaries (particularly the KIND B streaming task) MUST be run and its results verified **before the schema is frozen** at design time. If the spike reveals that `parent_span_id` cannot be reliably propagated, the AC-02.5 guarantee weakens and the design must be revised. **This is a GATE, not a formality.**
- **DG-10.B — Span-lifecycle events for live sinks:** A custom `SpanProcessor` receives a fully-populated span only on `on_end` — which for a 30-second Act span fires when "Act in progress" is no longer useful to live consumers. The TUI and WS sinks may need **span-open** and **span-close** events separately, not just span-end. Whether to emit span-lifecycle events vs finished-span records is a schema and processor decision that affects AC-03 (schema shape) and AC-07/AC-08 (sink contracts). MUST be resolved at design time before schema is frozen.

---

### US-11 — Sink self-error isolation: no trace-of-trace recursion

**As** the Axiom system,
**I want** sink errors (file IOError, WS exception, TUI render failure) to be reported via stdlib logging and NEVER published back onto the trace bus,
**so that** a sink failure never creates a recursive trace loop that could degrade system stability.

#### Acceptance criteria

- AC-11.1: All sink error handlers (file, TUI, WS bridge) use **`logging.getLogger(__name__).error(...)`** or equivalent for error reporting.
- AC-11.2: No sink error handler calls `publish(...)` on the fan-out, directly or indirectly.
- AC-11.3: A sink failure does not propagate an exception to the producer or to other sinks. Sinks fail independently.
- AC-11.4: The OTel `SpanProcessor` itself (if it encounters a serialization error) also goes to stdlib logging, not the bus.

---

### US-12 — Schema versioning and parseable old traces

**As** a developer or tool reading trace files after a schema update,
**I want** every trace record to carry a schema version,
**so that** I can parse records written by older versions of Axiom without ambiguity, even as the `gen_ai.*` attribute names change over time.

#### Acceptance criteria

- AC-12.1: Every JSONL record carries `schema_version` (a local version string, e.g. `"1.0"`) and `otel_schema_url` (the OTel GenAI conventions schema URL in effect at emit time).
- AC-12.2: `schema_version` is incremented on every backward-incompatible change to the common-core schema. Additive changes (new optional fields, new `extensions` keys) do not require a version bump.
- AC-12.3: The `schema_version` field appears in **every** record, including gap-marker records.
- AC-12.4: Trace files written under an older `schema_version` remain parseable by a parser that knows the version — no field is removed or type-changed silently between versions.

---

## Non-Goals (M2 scope fence)

These are explicitly **out of scope** for M2. Mentioning them here prevents scope creep at design and implementation time.

| Non-Goal | Notes |
|----------|-------|
| External message broker | No NATS, no MQTT, no Redis Pub/Sub — in-process fan-out only |
| OTel collector or backend | OTel SDK yes; OTel infra no |
| Subject taxonomy / addressing | Deferred to M7 (Orchestrator); M2 uses `trace` channel only |
| Redaction / PII scrubbing | Deferred to M9 (Connectors / Guardrails), where untrusted input first arrives |
| Web dashboard | Raw WS stream only; no browser UI, no HTTP server |
| Consumer storage decisions | Consumers receive JSONL; what they persist is their concern, not M2's |
| Self-correction | M8 |
| Multi-user / permissions | Later phase |
| Synchronous "forensic durable" file mode | A possible future opt-in; explicitly not M2 (would violate the non-blocking emit invariant) |
| A2A / inter-agent message routing | M7; M2's fan-out is broadcast-all |

---

## Open Questions

These MUST be resolved at design time (before `design.md` is marked complete). They are not optional — they are load-bearing for implementation.

| ID | Question | Why it's load-bearing |
|----|----------|----------------------|
| **OQ-01** | Exact boundary between common-core attributes and the `extensions` bag. Which `gen_ai.*` fields are core vs optional? What is the minimum common-core field set beyond the list in AC-03.1? | Defines what every consumer can rely on without provider-conditional parsing logic |
| **OQ-02** | Exact gap-marker schema (field names, types, required vs optional). | Used by file sink (rate-overflow drops), TUI, WS, AND span-tree renderers for orphan-span handling. A late-defined format propagates rework across all three sinks and consumers. Spec it early. |
| **OQ-03** | File sink storage location, rotation policy (max size, max age, max file count), concrete queue depth *D*, and drain/fsync cadence. | Determines the bounded-durability contract consumers can rely on; wrong defaults cause silent data loss |
| **OQ-04** | KIND-B stream-to-span mapping contract: which streamed event types (tool-call-start, tool-call-end, message-start, message-end, etc.) open/close child spans under the Act span? | Necessary to implement AC-02.3 and AC-02.4 correctly. Concurrent events collapse to sequential siblings (AC-02.4), but the mapping of event type to span boundary must be specified |
| **OQ-05** | OTel `contextvars`-across-asyncio spike result (DG-10.A). Does OTel context cleanly follow KIND B streaming task boundaries with `copy_context` / `context.attach`? | If the spike fails, the AC-02.5 guarantee (`parent_span_id` always valid) weakens and the schema design changes |
| **OQ-06** | Span-lifecycle-events-vs-finished-span decision (DG-10.B). Do live sinks need span-open / span-close events, or only span-end records? | Affects schema shape (adds `record_type` field variants) and the SpanProcessor design. Must be decided before schema is frozen. |

---

## Constraints and Invariants

Hard constraints from `architecture.md` and the Rev-3 research doc — may not be relaxed in design or implementation without updating this document.

1. **Non-blocking emit is a hard invariant.** No sink — file, TUI, or WS — may back-pressure the agent loop producer under any condition, including disk-full, terminal hang, or WS client disconnect.
2. **Loop sovereignty over span tree.** The agent loop mints the root PRAO spans. Adapters add children. No adapter may reparent or replace loop-level spans.
3. **OTel confined to Observability.** The core loop imports nothing from `opentelemetry`. This is the core-stays-framework-free roadmap invariant.
4. **In-process only.** The fan-out and all sinks operate in-process. No external queue, no external infra.
5. **Single producer.** There is exactly one code path that publishes to the fan-out: the Observability RECORD call-point via the OTel `SpanProcessor` hook. Other code MUST NOT publish directly.
6. **`parent_span_id` always valid.** For every emitted span (except the run-root span). Null parent is only legal for the run-root span. This guarantee is subject to OQ-05 / DG-10.A.
7. **WS localhost-only + token auth.** The WS bridge MUST NOT bind to external interfaces. It streams full reasoning traces.
8. **File sink `0600` permissions.** Traces are trusted-local and may contain secrets.
9. **Sink errors go to stdlib logging only.** Never onto the fan-out bus.
