# Action

Settle the seam, then build the smallest thing that proves it. Cycle 1 showed the three
families agree on the structured path, so the design question is no longer "how do we
reconcile them" - it is "what does `stream()` yield now that a turn can produce text, a tool
call, and thinking."

## First: what the backend yields

Today `stream()` yields `Piece(text, usage)`. A tool call is not text and thinking is neither.
Decide and write it down before touching the chat loop:

- A second event type alongside `Piece` - a `Call(name, arguments)` - so the loop tells them
  apart by type rather than by inspecting strings.
- Thinking: **discard it** unless Kaushik has said otherwise. Cycle 1's open question offers
  three options and takes option 1 by default, because it preserves current behaviour and no
  criterion requires more. If a `thinking` field arrives, drop it and note in the log that it
  was dropped deliberately, not overlooked.
- `stream()` takes the tool declarations. When none are passed it must behave exactly as it
  does today - that is what keeps the existing transcript honest for the non-tool paths.

## Then: tool support detection, cheaply

AC 2 needs to know at startup whether the model can call tools. Cycle 1 found the only
observed signal is a `ResponseError` at generation time, which is too late and costs a call.

**Check whether the Python client exposes capabilities on `show()`** - the CLI reports a
`Capabilities` list containing `tools`, so the data exists somewhere. Confirm it directly
against `gemma2:2b` and one tool-capable model before building on it. If it is not exposed,
say so and fall back to catching the 400 on the first tool-bearing request, and note what that
costs the user.

`gemma2:2b` is the model for this, and its exact refusal string is in the cycle-1 log.

## Then: one tool, end to end

**`read_file` only.** Not the file suite, not commands. One tool through the whole path:
declared, called by a live model, executed, result returned, model answers from it.

That closes the mechanism for AC 4, AC 17, AC 18 and AC 19, and everything after it is
additional tools rather than new machinery. Adding four tools before the first one runs would
mean debugging the machinery through four surfaces at once.

Keep #33's structure: `ollama` and `httpx` stay inside `backend.py`, no module both talks to a
backend and writes to the terminal, tests inject rather than patch. Check by grep before
committing.

## Watch for

**Streaming accumulates.** Cycle 1 saw the call arrive inside the stream - qwen in 2 chunks,
gemma4 in 175. The loop cannot assume a call is complete on the chunk it first appears in.

**The existing transcript must still pass** until the startup line legitimately changes. If it
breaks for any other reason this cycle, that is a regression, not a legitimate change.

## Record

Full suite plus characterization. Live evidence for the one tool against **at least one**
model - all three is AC 3's job and can wait until the mechanism works on one. `wc -l` across
`src/` against the 442 baseline. Status token for all 35.
