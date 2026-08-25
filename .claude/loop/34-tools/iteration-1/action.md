# Action

**Find out what the three models actually do before designing anything.** Write no
production code this cycle.

#34's whole difficulty is AC 3 through AC 8 - one mechanism across models that announce tool
calls differently. Every design decision in this loop depends on facts nobody here has yet:
whether Ollama's `tool_calls` field is populated the same way by a qwen2 model, a gemma4
thinking model and a qwen35 thinking model, and what the ones that deviate actually emit.
Designing first and discovering second would mean rewriting the seam in cycle 3.

## Probe all four models

Write a throwaway probe script under `.tmp/` - not `src/`, not `tests/` - that declares one
trivial, read-only tool and asks each model to use it. Something like a `get_time` tool
taking no arguments, or `read_file` on a path in the sandbox. **Nothing destructive, and
nothing outside `C:/Projects/.tmp/axiom-tool-sandbox`.**

For each of `qwen2.5:7b`, `gemma4:e2b`, `ornith:9b`, record verbatim:

- whether `message.tool_calls` is populated at all, and its exact shape
- whether arguments arrive as a dict or as a JSON string
- whether the model emits anything in `message.content` alongside the call - the thinking
  models may, and AC 6 turns on this
- whether more than one call comes back at once
- what happens with `stream=True` versus without, since AC 7 requires both to behave

Then ask `gemma2:2b` the same thing and record exactly how Ollama refuses. That refusal is
what AC 2 and AC 8 are written against, and guessing at its shape would produce a handler
that never fires.

Create the sandbox directory first if it does not exist.

## Record the baseline

- Current `wc -l` across `src/`, and the test count, so growth is measured rather than felt.
- Confirm the suite is green and hermetic with the one-command check in `observe.md`.
- Note which of the thirteen transcript scenarios will need to change once tools exist, and
  which new observable paths #34 adds that the harness does not yet reach.

## Then name the shape

With the probe results in hand, say where tools will live and how a call travels: which
module declares them, which executes them, where a result re-enters the conversation, and
how AC 6's non-structured case is caught. Name it, so cycle 2 derives its move from a
decision already made.

Do not write it yet. If the probe shows the three families disagree more than expected, the
shape is a bigger question than one cycle and cycle 2 should still be design.

## Record

All 35 criteria get a status token. Nearly all will be `not-started` - that is the correct
reading at cycle 1, and the point is the probe results, not the score.
