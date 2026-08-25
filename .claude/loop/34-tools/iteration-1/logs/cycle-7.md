# Cycle 7 - 2026-08-25 07:37 IST

The live model pass. **AC 3 closed. AC 6 reproduced live and is a real defect.**
No source changed; 119 tests still green.

## AC 3: three families, same tool action

The real program, through a pipe, changing nothing but `--model`.

| model | family | called | answered from the file |
|---|---|---|---|
| `qwen2.5:7b` | qwen2 | `read_file(path=...)` | yes |
| `gemma4:e2b` | gemma4 | `read_file(path=...)` | yes |
| `ornith:9b` | qwen35 | `read_file(path=...)` | yes |

**What "the same tool action" means was decided before running:** the same tool, the same
argument, and an answer drawn from the file. The wording differs between the three - one
wrapped it in a code fence, one bolded it - and AC 3 does not care about that. Stating it
here so the judgement is visible rather than implied.

**AC 3: `met-with-evidence`.**

### One incident on the way

`ornith:9b` failed on first attempt - not in axiom:

```
error: llama-server process has terminated: exit status 0xc0000409 ...
CUDA error: shared object initialization failed (status code: 500)
```

Ollama's own server crashed loading the model, immediately after `gemma4:e2b` (7.2GB) had
been resident. `ollama ps` showed nothing loaded; the retry worked. Transient GPU memory
pressure on a 16GB machine, which `assumption.md` warned about.

Worth recording for what axiom did with it: reported it on stderr, returned to the prompt,
and `/exit` still exited cleanly. That is AC 31 and AC 35 holding under a real failure nobody
designed for.

Also visible: ornith's context came out as **13829** tokens on the crashed attempt and
**43721** on the retry, against its declared 262144. That is #28's memory-safe cap doing its
job - the number moves with what the machine actually has free.

## AC 6: reproduced, and axiom fails it

The fourth model produced it immediately.

```
$ ... --model qwen2.5-coder:7b
> {"name": "read_file", "arguments": {"path": "C:/Projects/.tmp/axiom-tool-sandbox/notes.txt"}}
>
```

**axiom printed the model's tool call to the user as though it were the answer.** No tool
ran. AC 6 forbids exactly this: *never silently dropped, and never shown to the user as prose
in the middle of an answer.*

Cycle 1 probed three models and never saw it, and recorded that as absence of evidence rather
than evidence of absence. That caution was right, and one more model was enough to find it.

### The exact shape

Probed directly rather than inferred:

```json
{"stream": false,
 "content": "{\"name\": \"read_file\", \"arguments\": {\"path\": \"...\"}}",
 "tool_calls": [], "tool_calls_is_none": true}
```

- **`tool_calls` is `None`** - absent, not empty.
- **`content` is the whole call as bare JSON**, with no `<tool_call>` wrapper.
- **Streamed, it arrives in 30 chunks, token by token**: `{"`, `name`, `":`, ` "`, `read`,
  `_file`, `",`, ` "`...

That last point is the hard part, and it is why the current code prints it. **No single chunk
is recognisable as a call.** The text has to be accumulated and judged once the stream ends -
by which time every piece has already gone to the screen.

So the fix is not only "parse the JSON". It is "do not show the reply until it is known not
to be a call", and doing that without ruining streaming for the three models that behave.

## Consequences for the remaining criteria

- **AC 5** was going to be demonstrated with this fourth model. It cannot be yet: adding
  `qwen2.5-coder:7b` does not work today. Note that the fix belongs in the seam, not in any
  tool, so AC 5's actual claim - *no tool is edited* - should still hold once AC 6 is done.
  Left `attempted`, honestly.
- **AC 7** was to be checked this cycle and is now entangled: `qwen2.5-coder` behaves the
  same way streamed and not, but both are wrong. Checking that streaming and non-streaming
  agree is only meaningful once they agree on something correct. Deferred.

## Criteria status

**Startup** 1-2 `met-with-evidence`

**Works across models**
3. **`met-with-evidence`** - three families, same tool, same argument
4. `met-with-evidence`
5. `attempted` - blocked behind AC 6, and the fix is in the seam rather than a tool
6. **`not-started`** - reproduced live, exact shape captured, currently failing
7. `not-started` - deferred until AC 6 gives it something correct to compare
8. `met-with-evidence`

**Files** 9-12 `met-with-evidence`
**Commands** 13-16 `met-with-evidence`
**Multi-step work** 17-20 `met-with-evidence`
**Visibility** 21-23 `met-with-evidence`
**Boundaries** 24-27 `met-with-evidence`
**Failure and recovery** 28-31 `met-with-evidence`
**Configuration** 32-34 `met-with-evidence`
**Exit** 35 `met-with-evidence`

## Goal check

**Not met.** 32 of 35 - AC 3 gained, and AC 6 is now correctly reported as failing rather
than untested.

The count moved by one and the picture got sharper: three criteria remain and all three
depend on one fix.

## What this cycle was for

A cycle that changed no code and closed one criterion looks thin by the numbers. It found the
defect that four earlier cycles of stub testing could not, because a stub does what it was
written to do and `qwen2.5-coder` does not.

Had this been left to the end, or skipped because "the mechanism is proven", axiom would have
shipped printing raw JSON at users on a model that is already pulled on this machine.
