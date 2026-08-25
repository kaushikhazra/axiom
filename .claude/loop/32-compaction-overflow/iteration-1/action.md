# Action

Decide what AC 1 and AC 6 should be, now that the obvious reading of them has been measured
and found impossible. Then implement whichever survives.

## The finding to design against

Cycle 2 established, with numbers:

- A summary is a list of distinct facts. Compacting it again returns the same facts - measured
  at 0% to -2% on a real session, once +5 characters.
- Re-compacting repeatedly **loses facts**, which is what AC 2 forbids and #29 spent an
  iteration fixing.
- Therefore **AC 1 and AC 2 cannot both hold for an unbounded session.** Facts accumulate;
  a bounded space cannot hold unbounded facts.

Do not try to be cleverer about the compaction step. The arithmetic does not move.

## Three honest options

**A. Report and stop.** Keep what cycle 2 built. When the history will not fit, the user is
told and the turn is not sent. Nothing is ever lost silently; the session eventually cannot
continue and says so. AC 1 becomes "the summary is not allowed to overflow silently" and AC 6
is amended.

**B. Forget deliberately, and say so.** When the summary passes its bound, drop the oldest
facts and **tell the user which**. Bounded, honest, and the loss is visible rather than
discovered later. AC 2 is amended - facts are preserved until the user is told they are not.

**C. Keep the oldest facts and drop the middle.** A refinement of B. Early facts are often
identity-shaped - a name, a preference - and #29's instruction already says a brief early
statement matters as much as a later topic. More complex, and the choice of what to drop is a
judgement the code would be making on the user's behalf.

**Recommend one, with the reasoning, and say what it costs.** Then implement it. If it is A,
most of the work is already done and the cycle is mostly amending the issue and its criteria.

## Whichever is chosen

- **AC 2's protection must survive it.** Whatever the summary does, a fact must not vanish
  without the user being able to know. That is the whole lesson of #29 and of cycle 2.
- **Prove it live**, with a planted fact, over a session long enough to reach the boundary.
  Cycle 2's probe is in `.tmp/probe_overflow.py` and already instrumented.
- **AC 5 needs whatever message the choice implies** - re-compaction, deliberate forgetting,
  or refusal - and a transcript scenario for it.

## Amending the issue

If a criterion cannot stand as written, **edit #32 on GitHub** to say what it is now, and note
in the log what changed and why. #35 ended this way and the record was better for it. An
amended criterion with the measurement behind it is worth more than a green tick against
wording nobody can satisfy.

## Record

Full suite and the hermeticity check. Status for all 6. If all six read `met-with-evidence`
against the criteria as they then stand, **the goal is met**: follow `loop.md` exit 1, and say
the queue is finished - #32 is the last row.
