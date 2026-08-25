# Observe

Record each cycle:

- A status token for **every one of #32's 6 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All six get a token every cycle, even "no change." Cite
  them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## What counts as evidence

This issue exists because #29's iteration-2 ran out of time before proving it, and its own
log is explicit about why: **the original bug survived a fully green suite and eleven mocked
criteria.** Mocking was not enough then and is not enough now.

- **AC 3, AC 4 and AC 6 need a real session against a real model**, driven far enough that
  the compacted history genuinely approaches the limit. `AXIOM_DEBUG_MAX_CONTEXT` exists for
  exactly this and is the right tool.
- **Natural, varied sentences only.** #29 found that repeated or near-identical filler sends
  a small model into a degenerate loop, which is a different failure that will look like this
  one. Varying the input is part of the method, not a nicety.
- **A unit test proving a mechanism is good supporting evidence and closes nothing on its
  own** for those three. Write both.
- **AC 1, 2 and 5 may be settled with stubs** - they are about what the code does with a
  history it is handed, not about what a live model returns.

## The trap this issue is named after

#29 iteration-2's finding, in its own words: re-summarizing an already-compacted summary
alongside newer turns **silently dropped facts the first pass had preserved**. The fix was to
carry a prior summary forward verbatim and only compact what is new.

**AC 1 deliberately reintroduces re-summarizing** - bounded, and only when the summary itself
has grown too large. That is the same operation that lost facts before. So:

- **AC 2 is the criterion that matters most.** Re-compacting must preserve facts the way any
  other pass does, and proving it needs a fact planted early, a session driven through a
  re-compaction, and that fact recalled afterwards. Not a size assertion.
- If a cycle cannot show a planted fact surviving, **say so plainly**. A bounded summary that
  quietly loses what it was carrying is worse than an unbounded one.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded.
- **The suite must stay green with no Ollama and no network**, and must not be changeable by
  the environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript is the behaviour record.** AC 5 adds a distinct message when the
  summary is re-compacted, so a scenario for it belongs there. Copy the baseline aside,
  regenerate deliberately, and **check the diff by command rather than by eye** - that habit
  has caught two real mistakes in this queue already.
- **#33's structure, #34's seam and #35's tools are kept.** `ollama` and `httpx` stay inside
  `backend.py`; only `terminal.py` prints; tests inject rather than patch.
- If a criterion cannot be met as written, say so plainly and say why. #35 ended with one
  criterion replaced on evidence; that is an acceptable outcome, and quietly reinterpreting
  one is not.

## Goal check

- **Met** - all 6 criteria are `met-with-evidence`, the overflow ones from a real session, and
  the suite is green and hermetic. The loop ends.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.
