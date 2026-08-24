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

Loops live at `.claude/loop/{issue-id}-{slug}/iteration-{n}/` — the issue id first, so a loop is traceable to the story it serves. **The code is not the loop's artifact folder.** Source stays in `src/` and tests in `tests/`, and the loop points at them; an iteration folder holds the loop's own files and logs, nothing else.

Two rules that are load-bearing and easy to get wrong:

- **Define done by the object or the consumer — never by the producer.** "No new findings this pass" measures the agent's output and will never fire. "This number hasn't moved in N passes" measures the artifact. "The reader can act on this" measures the consumer.
- **A loop cannot be its own convergence detector.** The external check is structural, not optional. Every loop carries a fail-safe and states a reason if it stops without converging.

## Issues

Work is tracked as GitHub issues, one story each.

**Title** — the goal, as `<actor> <verb>s <what>`:

> User chats with a local Ollama model from the terminal

Not a component (*"Ollama adapter"*), not a task (*"add the CLI loop"*), not a sketch (*"input → model → output"*).

**Body** — the story, then the criteria:

```
**As a** <actor>
**I want to** <capability>
**so that** <why it is worth having>.

## Acceptance criteria

**<group>**

1. ...
```

Nothing else. No out-of-scope list, no constraints, no notes, no rationale, no design. If it is not the story or a criterion, it does not go in the issue.

**Criteria** state a condition and an observable result, in the user's terms. Every one is objectively verifiable. No sign-offs and no approvals — a gate is not a criterion, and a loop's done-condition is a separate thing that stays out of the issue.

Write enough of them to test the story thoroughly. Walk this list and write what applies:

| | |
|---|---|
| Startup | what the user sees on launch, and what happens with nothing configured |
| Happy path | the main action and its visible result, in full |
| In progress | what the user sees while waiting |
| Boundaries | empty, missing, or trivial input |
| State | what carries across actions within a run, and what resets between runs |
| Configuration | each setting's default, each override, and the precedence between them |
| Visibility | how the user confirms which configuration actually took effect |
| Failure | each distinct way it can fail, what the user is told, and what must **not** happen |
| Recovery | whether a failed action leaves things usable, or exits |
| Exit | every way out, and the status code |

Group criteria under bold headers once there are more than a handful, and number them continuously so one can be cited as "AC 12". Issue #26 is the worked example.

## Where knowledge lives

In this repo. Do not use the cognitive-memory MCP tools as a store for Axiom project knowledge, and never cite a CM memory ID in an Axiom file — anything load-bearing gets inlined here, where a fresh session, a headless run, and Kaushik reading the repo all reach it.

## Why v1 was scrapped

M1–M8 shipped and worked — 53 modules, 558 tests, 10 spec folders, ~50 dryrun reports. It was too heavy for what it does. The architecture was sound and Kaushik retains it; the process weight is what's being left behind.

**KISS, not asceticism.** "Minimal" means no unearned structure — no ports and adapters before there are two of anything, no spec ceremony around a hundred-line program. It does not mean writing things a good library already does. Reach for the library.
