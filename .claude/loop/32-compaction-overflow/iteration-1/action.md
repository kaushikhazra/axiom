# Action

Bound the summary, and check the payload before sending it. Cycle 1 measured everything this
needs; nothing here should be guessed.

## AC 1 and AC 2: re-compact the summary, bounded

Today `compacted_history` appends new facts to a prior summary forever. Give the summary a
size of its own: when appending would take it past that, **re-compact the summary itself**
rather than growing it.

**AC 2 is the criterion that matters and it is the one that can silently fail.** #29's
iteration-2 found that re-summarizing an already-compacted summary alongside newer turns
dropped facts the first pass had preserved. This deliberately reintroduces that operation, so
it must be done differently:

- Re-compact the summary **alone**, not folded in with newer turns. Mixing the two is what
  lost facts before.
- Use the same `COMPACTION_INSTRUCTION` - extract every distinct fact, one per line, do not
  narrate. That instruction was written for exactly this failure.
- **Prove it with a planted fact, not a size assertion.** Cycle 1 showed a fact surviving six
  passes today; the same fact must survive a session that goes through a re-compaction. A
  summary that is bounded because it quietly drops things is worse than an unbounded one.

Pick the bound from measurement: cycle 1's session reached 2129 characters against a
700-token window. Express it as a fraction of the effective context rather than a constant,
so it scales with the model.

## AC 3: check the assembled payload

Before sending, estimate the whole thing - summary, kept pairs, and the new message - and
compare against the effective context.

Use the measured figures: **the budget is the full `num_ctx`**, not half - cycle 1 nearly
recorded that wrong. And `chars // 4` **underestimates by up to 21%**, so use a conservative
divisor of **3** for a check whose job is to be safe. Leave `estimated_tokens` as it is for
choosing a ladder rung; that is a different job and changing it would alter #29's behaviour.

If it will not fit, the user is told and it is not sent as one payload.

## AC 4: catch the silent truncation

Cycle 1 confirmed Ollama truncates without raising and reports what it actually evaluated. So
after a reply, compare `prompt_eval_count` against what was sent. A count far short of the
estimate means the prompt was cut and the answer is built on a fragment.

Treat it as a failure the user is told about, not a normal reply. **Pick the threshold from
the measurements** - a truncated 3,700-token payload reported 258, so the gap is enormous and
the check does not need to be delicate. It does need to not fire on the normal case, where
630 was reported against a 680 estimate.

## AC 5: say when the summary itself is re-compacted

Distinct from the ordinary compaction notice, in `terminal.py` beside `note_compaction`. The
user should be able to tell "I am summarizing old turns" from "the summary itself got too big",
because the second says something about the session the first does not.

## AC 6 and the transcript

AC 6 is a long session that never lets the compacted history exceed the context - the
reproduction from cycle 1, re-run against the fix, showing the summary bounded and the planted
fact still there.

The transcript gains a scenario for AC 5's message. Copy aside, regenerate, and **check the
diff by command** rather than by eye.

## Record

Full suite and the hermeticity check. `wc -l` and test count against 1246 and 179. Status for
all 6. If all six read `met-with-evidence`, **the goal is met**: follow `loop.md` exit 1 - and
#32 is the last row, so say the queue is finished rather than starting nothing silently.
