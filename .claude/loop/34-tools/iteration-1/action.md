# Action

**Test what cycle 2 built, before building more.** The mechanism is proven live and has zero
tests. Adding a second tool now would grow the surface faster than the evidence for it, and
every criterion still standing needs a test rather than another live demo.

## Write `tests/test_tools.py`

Against `tools.run()` and `tools.declarations()` directly - no model, no backend.

- `declarations()` returns one entry per registered tool, shaped as Ollama expects, and takes
  no model argument (AC 4).
- `read_file` returns a file's contents (AC 10), reads an empty file as empty rather than as a
  failure (AC 25), and returns a plain explanation for a file that does not exist (AC 24).
- An unknown tool name returns a message naming it rather than raising (AC 29).
- Wrong or missing arguments return a message rather than raising (AC 29).

Use pytest's `tmp_path`. **Nothing destructive, and nothing outside it.**

## Then the loop's own behaviour, with a stub

`StubBackend` can already stream; teach it to yield a `Call` so the chat loop can be driven
without a model. Then, through `main(..., using=stub)`:

- A call is executed and its result reaches the model as a `tool`-role message carrying
  `tool_name` (AC 18, AC 19).
- Two calls in one turn both run before the model is asked again (AC 17).
- `MAX_TOOL_ROUNDS` bounds a model that never stops calling - assert it stops rather than
  looping forever.
- A failed tool leaves the session alive and the turn continuing (AC 28).
- A tool result larger than `TOOL_OUTPUT_LIMIT` is truncated on screen and says how much was
  withheld (AC 23).
- **The rollback:** a turn that fails after a tool has run leaves history with nothing from
  that turn - not the user line, not the assistant turn, not the tool result. Cycle 2 changed
  `messages.pop()` into `del messages[before:]` for exactly this, and it is untested.

## Then extend the transcript

The harness has thirteen scenarios and none of them involves a tool. Add: a tool running and
answering, a tool failing, and a model with no tool support. These are new scenarios, so the
baseline grows - that is an addition, not a regeneration, and the existing thirteen lines must
stay byte-identical. Say so in the log.

## Do not, this cycle

Add a second tool. Change the startup line. Both are cycle 4 - the startup line is where the
transcript changes deliberately, and it deserves a cycle where that is the headline rather
than a side effect.

## Record

Full suite. `wc -l` across `src/` and the test count against 66. Status token for all 35. Note
in particular whether any test proves something the live run only suggested.
