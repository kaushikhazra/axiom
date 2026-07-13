# M2 Observability — Fable Review, Round 1

**Reviewer:** Fable (adversarial design review)
**Doc under review:** `005-m2-observability-architecture-2026-07-13.md`
**Date:** 2026-07-13
**Verdict:** NOT spec-ready. F1 + F2 must resolve in the doc; F4 needs an explicit decision; F5 one-liners to add.

---

## F1 — KIND B span-tree fidelity is asserted, not designed — BLOCKER
The record shape is a tree (`span_id`/`parent_span_id`), but KIND B gives an ordered message/tool-call stream, not a tree with stable parent pointers. Who mints the IDs, from what signal? Options: (a) heuristic tree (fragile under parallel/nested provider tool-calls), (b) flat chain under one root (degenerate `parent_span_id` for half the providers — breaks "one normalized schema"), (c) per-event parent-attribution rules in the adapter contract. Doc picks none. This is upstream of the schema and cannot be deferred to the spec.
**Wanted:** explicit KIND B span-construction rule; whether consumers may rely on `parent_span_id` for KIND B runs.

## F2 — Durability claim contradicts the async design — BLOCKER
"Crash costs only the last line" (§3) vs "drop into in-memory queue, return immediately" (§5). On crash you lose the last line *plus every consumer buffer* — and the file sink (labeled "durable") sits behind the same lossy buffer as the TUI, deepest exactly when the agent wedges (the trace you most need). If observability is the trust layer, this loses the failure trace.
**Wanted:** file sink gets a distinct contract (bounded queue + flush-on-phase-boundary / small fsync budget), OR honestly downgrade the durability claim. Fix the false "only the last line" sentence.

## F3 — Backpressure trilemma acknowledged but not decided — CONCERN
With (no producer backpressure) + (all sinks get everything) fixed, every buffer is bounded-lossy or unbounded-leak — no fourth option. Per-consumer drop breaks span-tree integrity (orphaned children). State the invariant now; classify sinks loss-tolerant (TUI, WS) vs loss-intolerant (file).

## F4 — A2A justification for the broker is speculative coupling — CONCERN
The broker earns its keep via a tenant that doesn't exist yet. (1) Observability fan-out (fire-and-forget broadcast, loss-tolerant) is a different contract from A2A (addressing, request/reply, delivery guarantees) — designing the subject scheme now designs for ungathered requirements = premature abstraction, and re-admits the "event bus" the architecture rejected at the core, one layer down. (2) Contention: a trace burst delaying an A2A ABORT is a safety problem. Also §5 ("sink registry, not a bus") contradicts §4 ("bus with subjects").
**Wanted:** drop the A2A framing from M2 and ship the plain fan-out registry, OR defend the subject scheme with a concrete A2A requirement.

## F5 — Missing: WS security, redaction, schema versioning — CONCERN
- **WS port security:** an unauthenticated port streaming full reasoning (prompts, tool args, secrets) — the highest-value endpoint on the box, in a doc that rejected NATS *as attack surface*. Localhost-bind + token auth is one line.
- **Secret/PII redaction:** traces carry env vars, keys, personal data. Even "no redaction, trusted-local, file perms X" is a decision.
- **Schema versioning:** `gen_ai.*` is unstable (doc admits it) → add a `schema_version` field now or old JSONL becomes unparseable.

## F6 — Reuse-before-build: alternatives table skips the real competitor — CONCERN
Rejected list is all transport (NATS, MQTT, OTel collector). Nothing evaluates the **OTel SDK in-process** (`opentelemetry-sdk`, file/console exporter, NO collector — a library, same trust class as `websockets` which the doc adopts). It gives span-context propagation + the data model for free. Hand-rolling means owning span-context, schema, JSONL writer, broker, buffering, WS bridge. Maybe hand-rolled still wins (churn, weight, impedance) — but the doc never argues it against the *in-process SDK*, only the collector strawman.
**Wanted:** explicit rejection of the OTel SDK, or adopt it for the record/context layer while keeping the owned fan-out.

## F7 — Self-observation recursion undefined — NIT
When a consumer errors (WS exception, file IOError), where does that signal go? One sentence: sink-internal errors → stdlib logging, never onto the bus.

## F8 — Ordering guarantees unstated — NIT
Single producer + FIFO per-consumer queues ⇒ per-consumer order preserved — but say so; live-tree consumers depend on parent-before-child arrival.
