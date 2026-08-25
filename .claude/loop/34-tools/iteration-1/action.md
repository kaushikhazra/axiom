# Action

The live model pass. Four criteria, three model loads, one cycle - attempt nothing else
alongside it.

## AC 3: the same request, three families

Drive the **real program** - `main()` through a pipe, as in cycle 2 - with the same question
against `qwen2.5:7b` (qwen2), `gemma4:e2b` (gemma4) and `ornith:9b` (qwen35), changing
nothing but `--model`.

Use a read-only question against a file in `C:/Projects/.tmp/axiom-tool-sandbox`. Record each
model's output verbatim in the log, including any that misbehave.

**What counts as the same tool action** is worth deciding before running, not after: the same
tool called with the same argument, and an answer drawn from the file. The wording of the
answer will differ between models and that is not a difference AC 3 cares about. Say so in
the log, so the judgement is visible rather than implied.

Two of the three are thinking models and will take noticeably longer. That is expected, not a
failure.

## AC 7: streamed and not

The program only ever streams. Exercise `OllamaBackend.stream()` and a non-streamed call
against the same model and the same question, and compare the tool call each produces.

If Ollama's non-streaming path returns the call differently, that is a finding worth the
cycle on its own - record it and say what it would cost to support both.

## AC 6: be honest about what was not seen

Cycle 1's probe never reproduced a model announcing a call as text. If this cycle does not
either, **do not claim the case cannot happen.** Write a synthetic test that drives the
handler with a reply containing a `<tool_call>`-style block in `content`, confirm it is
either carried out or reported, and state plainly in the log that the failure mode has not
been observed live across four models and eight runs.

That is a weaker claim than "handled" and it is the true one.

## AC 5: demonstrate, do not assert

Adding support for a further model should require no edit to any tool. `qwen2.5-coder:7b` is
already pulled and is a fourth model - use it. If it works with no code change, AC 5 is
demonstrated rather than argued.

## Safety, binding

Every live request is **read-only**. Read a file, list, echo. No deletes, no writes outside
the sandbox, no `git`, no network. `delete_file` and `write_file` stay stub-tested - they
already are.

## If the models disagree

That is the finding, and it is what AC 6 exists for. Record exactly what each emitted, and do
not paper over it with a per-model branch - AC 4 and AC 5 forbid that, and the log should say
what a general fix would look like instead.

## Record

Full suite and the hermeticity check afterwards - a live cycle must not leave the suite red.
Status for all 35. If all 35 read `met-with-evidence`, **the goal is met**: follow `loop.md`
exit 1, then hand over to the next loop in `queue.md`.
