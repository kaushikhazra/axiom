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

## Testing tools before security exists

Issue #34 gives the model file CRUD and command execution with **no list of permitted
programs** (AC 14). The security stories are separate and none of them has landed, so
nothing between the model and the machine inspects what a tool is about to do. Three
different local models, each with its own tool template, will be improvising commands
in an unattended loop. Assume one of them will eventually emit something destructive.

The split that makes this safe is **who is driving**, not which command it is:

- **A live model is only ever asked for non-destructive work.** Read a file, list a
  directory, echo a string, run `python -c "print(...)"`, create a file in the sandbox.
  Never a request that deletes, moves, or overwrites; never `git`; never the network.
- **Destructive criteria are verified with a stub client**, which emits a fixed tool
  call the test wrote itself. AC 12 - deleting a file - is settled this way: a
  deterministic call inside pytest's `tmp_path`. A live model is never asked to
  improvise its way to a destructive command, because the point of the test is the
  tool's behaviour, not the model's judgement.
- **Every live-model tool test runs with its working directory set to
  `C:/Projects/.tmp/axiom-tool-sandbox`** - outside the repo, and never the repo root
  or the `C:\` root. A model that improvises a recursive delete of its working
  directory hits an empty scratch tree instead of source history.
- **The sandbox is the only thing a test may destroy.** If a test needs to assert that
  something was removed, it removes something it created inside the sandbox.

**Issue #43 adds a second exposure, different in kind.** An MCP server is not axiom's
code and does not wait to be called: it is a third-party executable, launched at startup
from a path in a config file, before the model has said anything. The sandbox rule above
does not reach it - that rule bounds the working directory of a command axiom runs, and a
server subprocess brings its own working directory, its own network access and its own
lifetime.

- **A test never fetches a server.** No `npx -y`, no `uvx`, no package downloaded at test
  time. That dependency is someone else's release, pulled over the network, running as
  whoever ran pytest.
- **Prefer the in-memory transport.** The SDK connects a `Client` straight to a server
  object in the same process - no subprocess, no port, no network. Nearly every criterion
  in #43 should be settled that way, and it keeps the suite green with nothing installed
  and nothing running.
- **Where a criterion genuinely needs a real process** - AC 26 and AC 27 are about
  processes outliving axiom, and cannot be proved in-memory - the server is a script this
  repo owns, under `tests/`, run by the same interpreter, with its working directory set
  to the sandbox. It is our own code, reviewed like any other file here.
- **No test contacts a hosted server or needs a real secret.** #43 is stdio-only, so
  nothing legitimate requires one. AC 14 to AC 16 are about substitution and redaction,
  and a made-up variable holding a made-up value proves both.

AC 26 and AC 27 are where the shortcut will be tempting, because pointing at a real
server is the fastest way to get a process to kill. That is the moment to write the
script instead.

**Issue #75 adds a third exposure, and it is the one that persists.** A skill is
instructions written to disk that a model will later follow, and #75 lets the model write
them. The first two exposures are bounded by the turn: a command runs and finishes, a
server dies when axiom exits. A skill outlives both - written in one run, loaded at the
start of the next, before anyone has typed anything.

The path that matters is `fetch_page` to `write_file` to a skill invoked tomorrow. Nothing
in axiom inspects what a skill says, the catalogue is built by reading the folder, and a
skill's instructions can ask for `run_command`. A page that talks a model into writing a
skill has written a standing instruction, not a one-off.

- **A test never lets a live model write a skill from fetched content.** Live models are
  asked to write skills only from text the test supplied inline. AC 18 to AC 22 are about
  the writing path working, not about where the words came from.
- **Skills a test creates live under the sandbox**, the same
  `C:/Projects/.tmp/axiom-tool-sandbox` the tool tests use - never `.axiom/skills/` in this
  repo. A loop that improvises its way to `write_skill` must not be able to leave something
  behind that the next session loads.
- **AC 21 and AC 42 - a refused write leaving the previous version untouched - are settled
  with a stub client**, like AC 12. A deterministic malformed skill, written by the test,
  inside `tmp_path`. A live model is not asked to improvise its way to a bad file.
- **Deleting is stub-only too.** AC 20 and AC 32 remove a skill the test created in the
  sandbox, and nothing else.

The tempting shortcut here is pointing the loop at this repo's own `.axiom/skills/` because
that is where the feature actually reads from. That is the moment to set the working
directory instead.

This holds until the security stories land. When they do, revisit it - do not delete
it silently.
