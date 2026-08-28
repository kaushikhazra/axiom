# Action

Twelve of thirty-three. The dispatch is live and inert: nothing can create a job, because
there are no tools. That is the next thing, and one piece of housekeeping comes before it.

1. **Make `terminal._typed` injectable.** It is a module-level singleton, so an end-to-end
   test through `main` with a schedule would leak a reader thread between tests. Cycle 3's
   tests sidestep it by patching `read_line`, which is honest for a unit test and not enough
   for the tool tests coming next. Fix it before writing them, not after.
2. **Add the three tools**, following `REGISTRY` in `src/axiom/tools.py` exactly: schedule a
   prompt, list what is scheduled, cancel one by identifier. `Limits` is not where the store
   goes - it is frozen and holds settings that belong to the user. Mirror the pattern with a
   `needs_schedule` flag and a second injected argument on `run()`, as cycle 1 established.
3. **Say what was scheduled** (AC 3, AC 4, AC 5): what, when it next runs, and its identifier.
   And the two things the user is told once - that schedules last only as long as the session
   (AC 7) and that a repeating job stops after seven days (AC 8).
4. **Listing and cancelling** (AC 14 to AC 18), including the empty listing saying so rather
   than printing nothing, and cancelling an identifier that is not there.
5. **Break every one.** Three of eleven of loop 73's own tests were vacuous a cycle after
   being written. Assume the same rate here.
6. `uv run pytest` - 665 on this branch, green, and the wall-clock must not climb.

Leave the seven-day expiry (AC 21) and AC 27 for a later cycle. AC 27 is still the one known
to be harder than it looks: croniter cannot express "in the past", so a one-shot at 09:00
asked for at 18:47 resolves to next year rather than being refused, and telling those apart
needs the pinned fields rather than the resolved time.

First thing to tackle: **the singleton.** It is small, it is in the way of everything after
it, and leaving it until the tool tests exist means discovering it as flakiness rather than
as a decision.
