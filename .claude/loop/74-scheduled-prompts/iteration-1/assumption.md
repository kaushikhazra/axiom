# Assumptions

Standing inputs. May change between iterations — when one does, say so in that cycle's Observe.

- **Three tools, not a slash command.** Kaushik asked for this to play out the way Claude
  Code's cron does, and there it is three model-callable tools — create, list, delete. So
  the model can schedule work on the user's behalf, which a slash command could not do.
  `REGISTRY` in `src/axiom/tools.py` is the pattern; follow it exactly.
- **Match this contract, which was read from Claude Code's own tools rather than
  remembered:** standard 5-field cron in the user's local timezone; `recurring` defaults to
  true; a one-shot fires once then deletes itself; a recurring job auto-expires after seven
  days, firing one final time first; jobs live only in the session and nothing is written to
  disk; jobs fire only while the session is idle, never mid-turn; create returns an
  identifier that delete takes.
- **Do not copy the jitter.** Claude Code spreads fire times so a global fleet does not hit
  one API at the same instant. axiom talks to localhost. Copying it would add unexplainable
  lateness to a local tool for a reason that does not exist here. This is a deliberate
  deviation from "the same way", and it is the only one.
- **Use a library for cron parsing.** `croniter` is the one. CLAUDE.md is explicit that
  minimal does not mean rewriting what a good library already does — hand-rolled cron
  arithmetic is exactly the trap. Adding it to `pyproject.toml` is expected, not a
  deviation.
- **The clock must be injectable from the first cycle.** Every criterion here is about time,
  and a suite that waits on real time is a suite nobody runs. Design for a test-controlled
  clock before writing the first tool, not after.
- **Session-only means in memory.** A new `src/axiom/schedule.py` holding the store, and
  nothing under `.axiom/`. `.axiom/model.json` exists for other reasons and is where a
  careless implementation would put this by habit.
- **The idle point is in the REPL in `src/axiom/__init__.py`.** Cycle 1 establishes exactly
  where a due job can be dispatched such that AC 10 and AC 11 hold, and writes it down.
- **A scheduled turn is announced in axiom's own voice.** `terminal.py` is the only module
  that prints, and `VOICE` is how axiom's lines stay distinguishable from the model's.
  #60 AC 17 and AC 29 both bind here.
- **The source is `src/axiom/` and the tests are `tests/`.** This iteration folder holds the
  loop's own files and logs, nothing else. Never copy source into it.
- **Nothing here touches `_as_markdown`.** Issues #72 and #73 own that function in their own
  loops.
