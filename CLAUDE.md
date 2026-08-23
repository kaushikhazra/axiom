# Axiom

Minimal agent. v2 — rebuilt from scratch 2026-08-23. v1 is archived at tag `archive/v1`; nothing was carried over.

## Development method — loop engineering

**Not spec-driven.** This project **overrides** the "Spec-Driven Development" section of the global `~/.claude/CLAUDE.md`.

Do not create `requirement.md` / `design.md` / `task.md`, and do not run the `/e-spec:*` or `/dryrun-*` skills here unless Kaushik asks for one by name.

Work proceeds as loops: a fixed goal, an artifact under test, and an instruction the loop rewrites each cycle from what the last cycle observed. The pattern is Kaushik's; it is implemented in the `ai-engineering:auto-iterate` plugin. Apply it — don't redesign it.

Two rules that are load-bearing and easy to get wrong:

- **Define done by the object or the consumer — never by the producer.** "No new findings this pass" measures the agent's output and will never fire. "This number hasn't moved in N passes" measures the artifact. "The reader can act on this" measures the consumer.
- **A loop cannot be its own convergence detector.** The external check is structural, not optional. Every loop carries a fail-safe and states a reason if it stops without converging.

## Why v1 was scrapped

M1–M8 shipped and worked — 53 modules, 558 tests, 10 spec folders, ~50 dryrun reports. It was too heavy for what it does. The architecture was sound and Kaushik retains it; the process weight is what's being left behind. Minimalism is the constraint, not a preference.
