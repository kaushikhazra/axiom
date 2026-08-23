# Axiom

Minimal agent. v2 — rebuilt from scratch 2026-08-23. v1 is archived at tag `archive/v1`; nothing was carried over.

## Development method — loop engineering

**Not spec-driven.** This project **overrides** the "Spec-Driven Development" section of the global `~/.claude/CLAUDE.md`.

Do not create `requirement.md` / `design.md` / `task.md`, and do not run the `/e-spec:*` or `/dryrun-*` skills here unless Kaushik asks for one by name.

Work proceeds as loops. The pattern is Kaushik's; it is implemented in the `ai-engineering:auto-iterate` plugin. Apply it — don't redesign it.

```
goal.md         fixed, never rewritten
observe.md      how to check the artifact against the goal — fixed
assumption.md   standing inputs that must survive a rewrite
action.md       rewritten each cycle BY THE LOOP
artifact/       the thing under test
```

One cycle = generate the artifact as `action.md` asks → check it against the goal → if met, stop; if not, write the next `action.md` and exit. The scheduler is the loop; each run is one body, and a hung run costs one cycle.

The artifact is what's under test — never the prompt. `action.md` is the instrument. Getting this backwards has the loop tuning its own wording instead of the deliverable.

Each cycle derives its next move from the last cycle's constraint. It does not generate a fresh idea — generation has no natural stop.

Assume every run starts in a fresh context. Only the files exist.

Two rules that are load-bearing and easy to get wrong:

- **Define done by the object or the consumer — never by the producer.** "No new findings this pass" measures the agent's output and will never fire. "This number hasn't moved in N passes" measures the artifact. "The reader can act on this" measures the consumer.
- **A loop cannot be its own convergence detector.** The external check is structural, not optional. Every loop carries a fail-safe and states a reason if it stops without converging.

## Issues

Work is tracked as GitHub issues. The title states the goal as `<actor> <verb>s <what>` — "User chats with a local Ollama model from the terminal", not a component name or a task. The body is a user story followed by acceptance criteria:

```
As a <who>
I want to <what>
so that <why>.

## Acceptance criteria
1. ...
```

Nothing else. No "out of scope", no "constraints", no notes, no rationale. Story and criteria.

Criteria are verifiable, and where the work has a reader, at least one is written in terms of that reader rather than the code.

## Where knowledge lives

In this repo. Do not use the cognitive-memory MCP tools as a store for Axiom project knowledge, and never cite a CM memory ID in an Axiom file — anything load-bearing gets inlined here, where a fresh session, a headless run, and Kaushik reading the repo all reach it.

## Why v1 was scrapped

M1–M8 shipped and worked — 53 modules, 558 tests, 10 spec folders, ~50 dryrun reports. It was too heavy for what it does. The architecture was sound and Kaushik retains it; the process weight is what's being left behind. Minimalism is the constraint, not a preference.
