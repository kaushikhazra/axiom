# Loop

```
Goal:                goal.md          (immutable)
Observe rules:       observe.md       (immutable)
Assumptions:         assumption.md
Action:              action.md
Document under test: src/axiom/ and tests/ on feature/95-memory-across-sessions

One cycle:
  - Action:  do what action.md asks
  - Observe: check the result against #95 using observe.md
  - If goal met:     stop
  - If goal not met: write the next action.md, then exit this cycle

Fail-safe: 2026-11-03 18:00 IST, stop and report, converged or not.
```

Cycles are run by the project agent in session, orchestrated by Velasari over crosschat;
no cron. Each cycle is written to `logs/cycle-N.md`, immutable once written.

## Where the work goes

Source in `src/axiom/`, tests in `tests/`. This folder holds only the loop's own files.
Branch `feature/95-memory-across-sessions`, cut from `master`. `gh issue view 95` is the
source of truth for what *met* means; do not work from a copy.

## Limits that bind every cycle

- **No live model use until Velasari says go** (a game-ai GPU job shares this machine).
  Anything needing Ollama is owed, not claimed.
- Synaptra belongs to another maintainer. Do not change it; report what it would need.
- A test never fetches a package or a model, and never starts a real Synaptra (CLAUDE.md,
  #43). Stub installer, in-memory transport, a script this repo owns.
