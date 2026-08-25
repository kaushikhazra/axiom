# Cycle 1 - 2026-08-25 06:07 IST

Probe cycle. **No production code.** Two throwaway scripts under `.tmp/`, four models asked
what they actually do.

## The probe

One read-only `read_file` tool, one question about a seeded file in
`C:/Projects/.tmp/axiom-tool-sandbox`. Each model asked with `stream=False` and `stream=True`.
Nothing destructive, nothing outside the sandbox.

### All three tool-capable families agree

| model | architecture | `tool_calls` | count | arguments | `content` |
|---|---|---|---|---|---|
| `qwen2.5:7b` | qwen2 | populated | 1 | **dict** | empty |
| `gemma4:e2b` | gemma4 | populated | 1 | **dict** | empty |
| `ornith:9b` | qwen35 | populated | 1 | **dict** | empty |

Every one produced a correctly-formed call with the right path. **Arguments arrive as a
`dict`, not a JSON string** - that was an open question and it is now closed. Streaming works
on all three; the call arrives inside the stream.

**This is a much better position than #34 assumed.** The worry behind AC 3 through AC 5 was
per-model divergence forcing per-model code. Ollama normalizes it, and the three families do
not disagree on anything the design has to care about.

### Thinking is a separate field, and it is not in the criteria

`gemma4:e2b` and `ornith:9b` both populate `message.thinking` and leave `content` empty:

> gemma4: "1. **Analyze the Request:** The user wants to know the content of the file..."
> ornith: "The user wants me to read a specific file using the read_file tool."

Chunk counts differ enormously under streaming - qwen 2, ornith 26, gemma4 **175** - with
`content` empty throughout. The thinking models are streaming their reasoning through a
channel `content` never sees.

**#34 has no criterion about this.** AC 16 says the user can tell a tool's output from the
model's own words; thinking is a third category, and two of the three default-eligible models
produce it. Flagged for Kaushik - see the open question at the bottom.

### The tool-less model refuses precisely

```
ollama.ResponseError: registry.ollama.ai/library/gemma2:2b does not support tools
(status code: 400)
```

Identical with and without streaming. This is what AC 2 and AC 8 are written against, and it
is a `ResponseError` - which `backend.py` currently translates into a plain `BackendError`.
Distinguishing "cannot do tools" from "refused this request" will need more than the current
translation.

**Note the timing problem:** this error only appears when tools are *sent*. Detecting tool
support at startup, as AC 2 requires, cannot rely on it without burning a generation call.
`ollama show` reports a `Capabilities` list containing `tools` - cycle 2 should check whether
the Python client exposes that on `show()`, because it is the cheap answer.

### The round trip

A second probe executed the call and fed the result back:

```
user      -> "What does the file ... say?"
assistant -> content="", tool_calls=[read_file(path=...)]
tool      -> {"role": "tool", "content": "Biscuit the cat is ginger.\n",
              "tool_name": "read_file"}
assistant -> "The file ... contains the following text: "Biscuit the cat is ginger.""
```

The assistant message goes back into history **as the object Ollama returned**, not
reconstructed. The result goes back as a `tool`-role message carrying `tool_name`. The model
then answered from the file's real contents, and made no second call.

That is AC 4, AC 11 and AC 12's mechanism confirmed end to end before a line of it is written.

## AC 6 did not reproduce - and that is not proof

No model announced its call as text in `content`. AC 6 exists for that case and still needs a
handler, but **there is no live example to design against**, so the handler will have to be
driven by a synthetic reply in tests. Recorded here so a later cycle does not mistake "we
never saw it" for "it cannot happen" - one probe, one prompt, one tool is thin evidence about
a failure mode that depends on template edge cases.

## Baseline

- `src/` - **442 lines** across six modules. #33's 447 ceiling does **not** apply to this
  loop; growth is expected and will be reported, not squeezed.
- **66 tests**, green and hermetic:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  -> `66 passed in 0.19s`
- `.gitignore` gained `.tmp/`, which it was missing - the repo rule forbids committing temp
  folders and nothing was enforcing it.

**Transcript scenarios that will need to change:** all thirteen begin with the startup line,
which AC 1 adds tool availability to. That is a legitimate, deliberate regeneration when it
happens. **New paths the harness does not yet reach:** a tool running and reporting, a tool
failing, a tool cancelled mid-run, a command timing out, output truncated on screen, and a
model that cannot call tools at all.

## The shape

Named now so cycle 2 derives rather than invents.

| module | gains |
|---|---|
| `tools.py` (new) | the declarations Ollama is sent, and the execution of each call - one registry, no per-model variation |
| `backend.py` | `stream()` takes `tools`; yields a call as well as text; and reports whether a model supports tools at all |
| `terminal.py` | the before-and-after visibility lines, and the truncation rule |
| `__init__.py` | the turn becomes a small loop: stream, execute any calls, append results, stream again, bounded |
| `config.py` | tools on/off, the working directory, the command time limit |

The seam question is what `stream()` yields. Today it is `Piece(text, usage)`. A tool call is
not text, and thinking is neither. The likely answer is a second event type alongside `Piece`,
so the chat loop can tell them apart without inspecting strings - but that is cycle 2's
decision, and it should be made with the recorded shapes above in hand.

## Protocol note

One shell invocation this cycle chained `cd` and `uv run` with `&&`, against the repo's
one-command rule. It then did exactly what that rule exists to prevent: the working directory
persisted into the next invocation, and a `find src` came back "No such file or directory"
from the wrong folder. No harm - both commands were read-only - but recorded, because the
rule earned itself the expensive way and a clean-looking violation is how it comes back.

## Criteria status

All 35 `not-started`. Nothing is built; this cycle bought facts, not criteria. The probe
bears directly on AC 3, 4, 5, 6, 7 and 8, and none of them can be *met* until there is code.

**Startup** 1-2 `not-started`
**Works across models** 3-8 `not-started` - mechanism confirmed for 3/4/5/7; 6 has no live
example; 8 has a verified tool-less model and a recorded refusal
**Files** 9-12 `not-started`
**Commands** 13-16 `not-started`
**Multi-step work** 17-20 `not-started` - round trip confirmed
**Visibility** 21-23 `not-started`
**Boundaries** 24-27 `not-started`
**Failure and recovery** 28-31 `not-started`
**Configuration** 32-34 `not-started`
**Exit** 35 `not-started`

## Goal check

**Not met.** Correct for a probe cycle.

## Open question for Kaushik

**Thinking output has no criterion.** `gemma4:e2b` and `ornith:9b` stream reasoning through
`message.thinking`; `gemma4` produced 175 chunks of it for a one-line question. Three options,
and this is a product decision rather than a loop decision:

1. **Discard it** - simplest, and matches today's behaviour where only `content` is printed.
2. **Show it, marked** - visible as reasoning, distinct from both the answer and tool output.
   AC 16's spirit, extended to a category the issue does not mention.
3. **Show it while waiting, then clear it** - it is the only thing on screen during a long
   thinking pause, which is what AC 21's "before a tool runs, the user sees what is about to
   happen" is reaching for.

The loop will take option 1 by default, since it preserves current behaviour and no criterion
requires otherwise. Say the word if you want 2 or 3 - it is a criterion change on #34, not a
loop change.
