# Cycle 8 - 2026-08-25 07:52 IST

AC 6 fixed, AC 5 and AC 7 closed. **131 tests green, from 119.** `src/` 949 -> 1021.
**All 35 criteria met.**

## The fix

Two halves, as cycle 7's finding required.

**Recognising it** - `backend.call_from_text()`, next to `Call`. A reply that is JSON naming a
registered tool is a call. It refuses anything it is not sure of: JSON naming an unknown tool,
JSON that is not an object, broken JSON, and prose. Those all get printed, because swallowing
a reply is worse than printing one.

No model is named anywhere in it. The rule is the shape of the reply.

**Not showing it while deciding** - the loop withholds only while the reply *could still* turn
out to be a call, meaning it is empty or opens with a brace, and releases it the moment it
cannot. Withholding until the stream ended would have turned streaming into buffering for the
three models that behave.

`test_an_ordinary_reply_still_streams_piece_by_piece` asserts on the **sequence of writes**,
not the final text. A reply delivered in one lump at the end would pass a content check and
fail the user.

`test_prose_that_begins_with_a_brace_is_still_printed_in_full` covers the case that silently
eats an answer.

## A crash the tests caught

`terminal.note_tool` assumed `arguments` is a mapping. A call announced as text can carry
anything, and `{"name": "read_file", "arguments": "not-a-mapping"}` crashed on `.items()` -
**before** `tools.run` could report the problem. AC 6 allows reporting a call axiom cannot
make; it does not allow a traceback. Fixed in both places.

## Live

```
$ ... --model qwen2.5-coder:7b
> axiom: read_file(path=C:/Projects/.tmp/axiom-tool-sandbox/notes.txt)
  | Biscuit the cat is ginger.
Biscuit the cat is ginger.
```

The model that broke cycle 7 now works, with no tool edited and no per-model branch. That is
**AC 6 and AC 5 together** - a fourth model supported by a change to the seam alone.

## A wrong hypothesis, corrected by probing

The first live run after the fix worked but called `read_file` **four times** before
answering. The obvious explanation was that echoing back a *structured* `tool_calls` message
to a model that never speaks that way confuses it.

Probed all three ways of recording its turn. **The hypothesis was wrong:**

| what goes back into history | repeats the call |
|---|---|
| reconstructed structured `tool_calls` | **no** |
| the text it actually wrote, then the result | yes |
| the text it wrote, result as a user message | yes |

What axiom already does is the only one of the three that works. Rerunning the live case gave
a single call and a correct answer, so the repetition is **non-deterministic model behaviour,
not a defect** - and worth recording rather than fixing something that is not broken.

### One change on that evidence

`MAX_TOOL_ROUNDS` raised from 5 to 8. A single-step question consumed four of five rounds
once. A genuine multi-step request plus that behaviour would have hit the bound and returned
an empty answer. The bound exists to stop a runaway, not to ration work a model legitimately
needs.

## AC 7: streamed and not

Four runs, two models, one of each behaviour:

| model | not streamed | streamed | agree |
|---|---|---|---|
| `qwen2.5:7b` | `read_file(path=...)` | same | yes |
| `qwen2.5-coder:7b` | `read_file(path=...)` | same | yes |

The text-announced case agrees too - `call_from_text` sees the same reply either way, since
streaming only changes how the text arrives, not what it is.

## The transcript

One scenario added, diffed against the copy taken first:

```
148a149,159
> === a call the model announced as text, not as a call ===
> > axiom: read_file(path=<sandbox>/notes.txt)
>   | Biscuit the cat is ginger.
> The cat is ginger.
```

Purely additive. `_stable()` also normalises the posix form of the sandbox path now - the
announcement embeds the path with forward slashes, which the backslash replacement would have
missed and left machine-specific.

## Criteria status

All 35 `met-with-evidence`.

**Startup** 1-2 · **Works across models** 3-8 · **Files** 9-12 · **Commands** 13-16 ·
**Multi-step work** 17-20 · **Visibility** 21-23 · **Boundaries** 24-27 ·
**Failure and recovery** 28-31 · **Configuration** 32-34 · **Exit** 35

The four that closed this cycle and last:

- **3** - three families, same tool, same argument, only `--model` changed
- **5** - a fourth model works with no tool edited
- **6** - reproduced live, fixed, and verified against the model that broke it
- **7** - streamed and not agree, for both behaviours

## Goal check

**Met.** All 35 criteria carry evidence, the model-facing ones from live runs against four
models, and the suite is green and hermetic.

Following `loop.md` exit 1: merge, then hand over to the next loop in `queue.md`.
