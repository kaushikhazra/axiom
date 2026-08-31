# Cycle 8 — 2026-08-31, started 18:27 +0530

## Where the artifact stands

**32 of 44 criteria demonstrably met.** Unchanged, deliberately: AC 15 and AC 16 were
measured, the measurement was found to be wrong, and a wrong number is not evidence.

| bucket | count |
|---|---|
| met, break-proven | 32 |
| measured, measurement retracted | AC 15, AC 16 |
| not started | AC 14, 25, 29, 31, 32, 34, 35, 40, 43, 44 |

## The lane exists and is deselected

`live` marker in `pyproject.toml`, `addopts = "-m 'not live'"`. Proven before the
measurement was written, as the action asked:

    820/821 tests collected (1 deselected)

The default suite ran green at 79.86s with the live test present and excluded. Nothing
acquired a network dependency.

**Nothing in the live test executes a tool call.** The model is asked a question, the call
it makes is counted, and the call is dropped. No file written, no command run.

## What was installed, and what was measured

    qwen3.5:9b        gemma2:2b        qwen2.5-coder:7b
    gemma4:e2b        ornith:9b        qwen2.5:7b

`gemma2:2b` reports no tool support, so it cannot invoke anything. Recorded as
"no tool support" rather than 0/10 - zero implies it tried.

First measurement, ten runs per model, 426 seconds:

| model | score |
|---|---|
| qwen3.5:9b | 10/10 |
| gemma4:e2b | 9/10 |
| ornith:9b | 10/10 |
| qwen2.5:7b | 10/10 |
| **qwen2.5-coder:7b** | **0/10** |
| gemma2:2b | no tool support |

## The measurement was wrong, and 0/10 is why it got caught

A single model at 0/10 against four at 9 or 10 is not a result, it is a question. Three
diagnostic runs against `qwen2.5-coder:7b` answered it:

    calls=[]  text: {"name": "invoke_skill", "arguments": {"name": "release-checklist"}}
    calls=[]  text: {"name": "release-checklist", "arguments": {}}
    calls=[]  text: {   "name": "release-checklist",   "arguments": {} }

**It does reach for the skill. It announces the call as text rather than as a structured
call**, which is precisely what #34 was built to handle and what the session already does
through `backend.call_from_text`.

The test drove `backend.stream` directly and counted only structured `Call` objects -
**measuring below the seam where axiom solves this.** It scored a model zero for asking
correctly in the other shape.

Had 0/10 been a little higher - 3/10, say - it would have looked like a plausibly weak model
and gone into the log as AC 16's case. The number was extreme enough to be implausible, and
that is the only reason the method was questioned rather than the model.

**AC 15 and AC 16 are not counted. The first four scores are probably right and are not
being kept either**, because they came from the same instrument and an instrument found
wrong on one input is not trusted on the others.

## What changed

`_asked_for_the_skill` now accumulates the reply and passes it through `call_from_text`
with the real tool names, the way a session does. The two shapes it will now see:

- `{"name": "invoke_skill", "arguments": {"name": "release-checklist"}}` - recognised.
- `{"name": "release-checklist", "arguments": {}}` - **not** recognised, and correctly so:
  `release-checklist` is a skill, not a tool, and `call_from_text` refuses names it does not
  have. This is a real miss and should count as one.

So `qwen2.5-coder:7b` will not come out at 10/10. It will come out at roughly the rate it
uses the well-formed shape, which on three runs was one in three.

**That second shape is worth Kaushik's eye.** A model naming the skill where the tool goes
is reaching for the right thing through the wrong door. Whether axiom should recognise it is
a design question, not a bug - #34's `call_from_text` deliberately refuses names it does not
have, and loosening that to match skill names would weaken a guard that exists for a reason.

## The suite

    820 tests, all passing, 79.86s, 1 deselected

Arithmetic: 820 + 0 in the default suite. The live test is the 821st and does not run there.

## Assumptions that changed

**"Live-model tests are separate from the hermetic suite" is no longer an assumption** - it
is enforced by the marker, and the enforcement was proven before it was relied on.

## Goal check

**Not met.** 32 of 44, with AC 15 and AC 16 measured and retracted. Next action written.
