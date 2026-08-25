# Action

Fix AC 6. Three criteria remain and all three wait on it.

## The problem, precisely

`qwen2.5-coder:7b` announces a call as bare JSON in `content`, with `tool_calls` set to
`None`, streamed token by token across ~30 chunks. **No single chunk is recognisable**, so
the current loop prints each piece as it arrives and the user sees raw JSON instead of an
answer.

The fix therefore has two halves, and the second is the one that is easy to get wrong:

1. **Recognise it.** After a stream ends with no structured call, if the whole reply parses
   as JSON naming a registered tool with a dict of arguments, it is a call.
2. **Do not show it while deciding.** Withholding everything until the stream ends would
   destroy streaming for the three models that behave. Withhold only while the reply so far
   could still turn out to be a call - that is, while it is empty or starts with `{` - and
   flush the moment it cannot be.

A reply that starts with `{` and turns out to be ordinary prose must still be printed, in
full, in order. Test that case explicitly; it is the one that silently eats output.

## Where each half belongs

Recognising a call is a backend concern - it is the same translation `OllamaBackend` already
does for structured calls, just from a different form. Put the parsing there, next to `Call`.

Deciding what reaches the screen is the loop's, since the loop already accumulates the reply
and owns the turn. Keep `terminal` free of the decision - it prints what it is given.

**Do not add a per-model branch.** AC 4 and AC 5 forbid it, and this needs none: the rule is
about the shape of a reply, not the name of a model.

## Tests

Stub-driven, no model needed:

- A reply that is a JSON call runs the tool and is never printed.
- A reply that is ordinary prose starting with `{` is printed in full and runs nothing.
- A reply that is JSON but names no registered tool is printed rather than swallowed.
- A reply that is JSON, names a tool, but has malformed arguments is reported, not dropped -
  AC 6 allows "reported as one axiom could not make", but not silence.
- Streaming is unaffected for a normal reply: pieces still reach the screen as they arrive,
  not in one lump at the end. Assert on the sequence of writes, not just the final text.

## Then close AC 5 and AC 7, live

- **AC 5** - `qwen2.5-coder:7b` works with no tool edited. Show the same read as the other
  three families.
- **AC 7** - the same question streamed and not, on a model of each behaviour: one that sends
  structured calls and one that sends text. Four runs, and they must agree on the tool action.

## Safety

Read-only live requests only, in `C:/Projects/.tmp/axiom-tool-sandbox`.

## Record

Full suite and the hermeticity check. Status for all 35. If the transcript changes, diff it
and put the diff in the log - a text-announced call is a new observable path and deserves a
scenario.

If all 35 read `met-with-evidence`, **the goal is met**: follow `loop.md` exit 1, then hand
over to the next loop in `queue.md`.
