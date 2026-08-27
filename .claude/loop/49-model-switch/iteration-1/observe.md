# Observe

Record each cycle:

- A status token for **every one of #49's 34 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All thirty-four get a token every cycle, even "no change."
  Cite them as "AC 14".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## Where this will be tempting to cheat

**AC 10 - the conversation carries over.** The easy test asserts the model was switched and a
message still worked. The criterion is that the **new model is sent everything said before the
switch**. Measure it on the payload: `StubBackend.streamed` holds each request, and the turn
after a switch must contain the turns before it. A test that only checks a reply came back
passes for an implementation that quietly starts a fresh conversation.

**AC 11 - tool calls carry across unchanged.** Kaushik settled this deliberately: switching to
a model that cannot call tools does **not** remove them from history. The hostile input is a
conversation containing an `assistant` message with `tool_calls` and a `tool` message, then a
switch to a model with no tool support. Assert those messages are still in the payload, byte
for byte, and that the session did not end.

**AC 16 - tool availability is the new model's.** #48 AC 29 was the same class of claim and had
**no real test**, because `StubBackend` discarded the model name it was handed. It records
`asked_about` now. Use it: after a switch, `supports_tools` and `model_info` must have been
asked about the new model, not the old one. A startup-line assertion cannot tell the difference.

**AC 2 - the list matches the one shown at startup.** Same contents, same order, same
numbering. The temptation is a second list built from a second call. Prove it by giving the
host an order that is not sorted and asserting both lists agree, and prefer calling #48's
`models.sorted_models` and `models.picked` over copying them.

**AC 20 - a switch is remembered however it was made.** Two routes in, and both must write:
by number and by name. #48 AC 14's rule is "a model the user picks themselves while axiom is
running", and a name typed at `/model` is exactly that - it is *not* the same as a launch flag,
which never writes.

**AC 24 - switching to the model already in use changes nothing, including the conversation.**
The cheat is a no-op that also skips the compaction check. Assert the history is untouched
*and* that the run did not treat it as an error.

**AC 26, AC 33 - Ctrl-C cancels, Ctrl-D ends the session.** Deliberately different, and
deliberately unlike #48 where both exit. Test both, and assert the model is unchanged after
Ctrl-C *and* that the next message still works.

**AC 30 - the host cannot be reached when `/model` is typed.** Unlike #48 AC 31, this must
**not** exit. The session carries on with the model it already had. A test asserting an error
message was printed proves nothing about whether the session survived; send a message
afterwards.

## What counts as evidence

- **Every criterion is settled against a stub, not against Ollama.** The suite must pass with
  nothing running.
- **A live probe against the local Ollama is for the implementer, not for the suite.**
  `gemma2:2b` has no tool support and the other four do, which makes a real tool-availability
  switch observable by hand.
- **AC 10, AC 11, AC 12 are payload facts.** `StubBackend.streamed` is the instrument, not the
  printed output.
- **AC 16, AC 15 are `asked_about` facts.** Not printed output.
- **AC 14 - servers keep running.** The same server object must still be attached, not a new
  one. Prove identity, not merely that tools still work.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **377 tests, green** at scaffold time, 2026-08-27 13:52 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript will change** if any scenario switches models. Copy it aside in
  cycle 1. **Fix every stub before regenerating** - #48 cycle 2 regenerated against a
  `StubClient` with no `list` and wrote a baseline in which every scenario ended in
  `AttributeError`. A transcript regenerated against a broken stub is still a green suite.
- **Before regenerating, run `diff` and read all of it**, checking for removed lines
  explicitly with `grep -c "^<"`.
- **A stub that contradicts the thing under test proves nothing.** #40's `given_page`, #41's
  constant `prompt_eval_count`, #48's model-discarding `StubBackend`. Assume there is another.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. #48 recorded the counts: unsorting turned 18 red, remembering on every
  route turned 5 red. Do the same here and record the numbers.
- If a criterion cannot be met as written, say so plainly and say why.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has now found a real defect in **five consecutive issues**, every time after the
implementing cycle had written `met-with-evidence` beside it:

- #40 AC 7 - a typeless PNG returned its bytes as content and was counted as a source.
- #41 AC 9 - the retry block compared whole result strings, so a pid defeated it.
- #42 AC 3 - the fix compacted away the user's own message.
- #43 AC 6 - a server whose name contained the separator declared unreachable tools.
- #48 AC 33 - a corrupt choice file reused a different criterion's message and blamed the host
  for it; the test asserted a substring that the gibberish happened to contain.

Each was found by a hostile input. None by rereading code.

## Goal check

- **Met** - all 34 criteria `met-with-evidence`, suite green and hermetic, transcript
  accounted for.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.
