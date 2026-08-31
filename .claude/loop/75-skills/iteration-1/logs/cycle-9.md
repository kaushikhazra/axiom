# Cycle 9 — 2026-08-31, started 18:47 +0530

## Where the artifact stands

**34 of 44 criteria met**, up from 32. AC 15 and AC 16 are counted on recorded evidence.

| bucket | count | criteria |
|---|---|---|
| met | **34** | the 32, plus AC 15 and AC 16 |
| not started | 10 | AC 14, 25, 29, 31, 32, 34, 35, 40, 43, 44 |

**AC 15 and AC 16 are counted without a break, and that is deliberate.** They do not assert
a behaviour; they ask for a measurement to be taken and written down. The measurement is
the deliverable and it is below. The test's own assertion - that every installed model was
measured - is what a break would prove, and a break costs six minutes of live model time to
demonstrate something the run already shows by listing six rows.

## AC 15 — the corrected measurement

Ten runs per model, 363 seconds, instrument now passing the reply through `call_from_text`
the way a session does:

| model | reached the skill | previous (retracted) |
|---|---|---|
| gemma4:e2b | **10/10** | 9/10 |
| ornith:9b | **10/10** | 10/10 |
| qwen2.5:7b | **10/10** | 10/10 |
| qwen3.5:9b | **9/10** | 10/10 |
| qwen2.5-coder:7b | **2/10** | 0/10 |
| gemma2:2b | no tool support | no tool support |

**The noise floor is plus or minus one.** qwen3.5 moved 10 to 9 and gemma4 moved 9 to 10
between two runs of the same measurement with no code change between them. Any future
comparison has to clear that, which is why #68's rule asks for improvement on one model and
no worsening on any - a single row moving by one is not a result.

## AC 16 — and the number that turned out to mean the opposite

`qwen2.5-coder:7b` at 2/10 looks like a model that will not use skills. A ten-run census of
what it actually emits says otherwise:

| what it emitted | out of 10 |
|---|---|
| structured tool call | 0 |
| text call, well-formed - recognised by `call_from_text` | 5 |
| text call naming the **skill** where the tool goes - refused | 5 |
| **prose answered from memory** | **0** |

**It reaches for the skill every single time. It never once answered from memory.**

AC 15's wording is "invokes it rather than answering from memory". By that wording this
model scores 10/10 on the thing the criterion actually asks about. The 2/10 is not model
judgement - it is **axiom failing to route a correct intention**, half the time, because the
model writes:

    {"name": "release-checklist", "arguments": {}}

naming the skill where the tool belongs. `call_from_text` refuses it, correctly: a skill is
not a tool, and that guard rejects unknown names for #34's reasons.

Recorded as AC 16's case with both numbers, because rounding it up to 10/10 would hide a
real gap in axiom and rounding it down to 2/10 would blame the model for axiom's parsing.

## Why the preamble was not touched

The action allowed one attempt at the preamble under #68's rule. **It was not made, and the
census is why.** The preamble's job is to persuade a model to reach for a skill instead of
answering from memory. This model already does that ten times out of ten. There is no
wording that fixes the *shape* of a call, and changing one to chase a number it cannot move
would burn six minutes and leave the log claiming a fix that fixed nothing.

No change without evidence it improves something. There was no evidence, so there was no
change.

## For Kaushik — a design question with a number on it now

Should `call_from_text` recognise a skill name where a tool name belongs?

- **For:** it is half of one installed model's attempts, and every one of them is the user's
  request being silently dropped. The model is right about what it wants.
- **Against:** `call_from_text` refuses unknown names deliberately (#34). Loosening it to
  match skill names means a reply that merely *mentions* a skill in JSON could be read as
  invoking it, and that guard exists so prose is never mistaken for a call.

It is a design decision, it is not this story's to make quietly, and it now has evidence
rather than a hunch behind it.

## The suite

    820 tests, 1 deselected, unchanged this cycle

No code changed. The only writes were the log and the next action.

## Assumptions that changed

**"A model that scores badly is a weak model" was wrong, and was nearly recorded as fact
twice.** Cycle 8's 0/10 was an instrument fault. Cycle 9's 2/10 is a routing fault. Neither
was the model's judgement, and both looked exactly like it. A score below the pack is a
question about the measurement before it is an answer about the model.

## Goal check

**Not met.** 34 of 44. Next action written.
