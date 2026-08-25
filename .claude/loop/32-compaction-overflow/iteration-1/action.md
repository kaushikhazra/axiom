# Action

**Reproduce the overflow before fixing anything.** Write no production code this cycle.

#29's iteration-2 ran out of time here and its scope note says why it matters: the original
compaction bug survived a green suite and eleven mocked criteria. This issue is the same
shape - a failure that only appears in a long real session - and designing against an
imagined version of it would produce a fix for the wrong thing.

## Drive a session to the boundary

Small `AXIOM_DEBUG_MAX_CONTEXT`, many turns, **natural and varied sentences**. #29 found that
repeated filler sends a small model into a degenerate loop, which will look like this bug and
is not.

Run it far enough that compaction fires repeatedly and the **summary itself** becomes the
thing that no longer fits - not a single oversized message. Record, per compaction pass:

- how long the carried-forward summary is
- how many facts it still names
- what the real `prompt_eval_count` was on the following turn

**The number that matters is whether the summary grows without bound.** Three passes showing
it climbing is the reproduction; a plateau would mean #32 is not real as written and that is
worth knowing before building anything.

## Then find out what happens at the limit

If the summary does reach the effective context, what does Ollama actually do? #29 found
silent truncation with a raw oversized message. Confirm whether the same happens here, and
whether `prompt_eval_count` on the reply reveals it - **AC 4 depends on that count being
usable as a signal**, and if it is not, AC 4 needs rethinking rather than implementing.

## Probe the token question

AC 3 wants a check against the real assembled payload, and `estimated_tokens` is characters
divided by four. Find out what better is available:

- Does the `ollama` client expose a tokenize or count endpoint?
- Does `show()` carry anything usable?
- If nothing does, say so, and say what the estimate's error actually is - measure it against
  a real `prompt_eval_count` on a payload of known character length, rather than assuming
  four is wrong.

An honest error bar on the estimate may be enough for AC 3. A guess is not.

## Record

Baseline: `wc -l` across `src/`, the test count, the hermeticity check. Status for all 6
criteria - most will be `not-started`, and the point is the reproduction.

**If the overflow does not reproduce**, that is the finding. Say what was tried, how far the
session was driven, and what the summary length actually did.
