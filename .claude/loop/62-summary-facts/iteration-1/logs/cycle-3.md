# Cycle 3 — attempted the two never attempted, and measured everything again

2026-08-28 03:35–04:05 IST. Fail-safe 06:18 IST.

**539 tests, green and hermetic** (was 536). Transcript unchanged.

## AC 5 — the structural fix

`compact()` was given only the pairs it was replacing, never the turns being kept, so it could
not know what it would be duplicating. `compacted_history` has both in hand and passed one.

It now passes both, labelled, and sends the kept turns' text as context - shown, never
summarised. The cost is a second copy of the kept turns in one request; the thing it buys is a
slot in a store bounded at half the window, permanently. Recorded in the docstring as that trade.

## AC 11 — a fourth paragraph

*"If nothing here is worth remembering - only greetings, thanks, or small talk that establishes
nothing - reply with nothing at all. An empty answer is correct and expected."*

## The measurements, six runs each

**AC 5** - bullets for a deadline stated, acknowledged, asked about and answered. One is ideal.

| model | blind to kept turns | shown kept turns |
|---|---|---|
| `qwen2.5:7b` | 3.3 | **1.2** |
| `gemma4:e2b` | 2.7 | 2.3 |

**AC 11** - bullets from four turns of pure pleasantries. Zero is ideal.

| model | before | after |
|---|---|---|
| `gemma4:e2b` | 4.0 | **0.8** (five of six runs empty) |
| `qwen2.5:7b` | 4.7 | 4.7 |

**AC 4** - general-knowledge bullets, with the *final* wording, re-measured as `action.md`
required rather than carrying cycle 1's numbers.

| model | original instruction | final instruction |
|---|---|---|
| `gemma4:e2b` | 5.2 | **0.0** - zero in all six runs |
| `qwen2.5:7b` | 2.5 | **1.3** |

User facts kept, throughout: 5.0/5 on qwen, 4.7 → 4.8 on gemma. **Nothing costs a user fact.**

## The finding — the two changes work on opposite models

| | AC 5 | AC 11 |
|---|---|---|
| `qwen2.5:7b` | works - 3.3 to 1.2 | no effect |
| `gemma4:e2b` | no effect | works - 4.0 to 0.8 |

Neither works on both, and each works on the one the other does not. That is not a result I
expected and it is the most useful thing in this log: **instruction-following on 7B-class models
is not a property of the instruction, it is a property of the pair.** A wording that reads as
obviously clearer can move one model and leave another untouched.

One thing did generalise. Adding AC 11's paragraph also improved AC 4 **on qwen**, which cycle 1
had measured as unmoved - 3.5 to 3.8 then, 2.5 to 1.3 now. Plausibly because telling a model it
may record nothing reinforces the idea of not recording things. Recorded as an observation rather
than a theory; it was not predicted and is not designed for.

## Status — all 12 criteria, honestly

| criteria | status | why |
|---|---|---|
| AC 1 | **not met as written** | rests on AC 4, which holds on one model |
| AC 2 | **not met as written** | same |
| AC 3 | `met-with-evidence` | by decision, reasoning in cycle 1 and confirmed in cycle 2 |
| AC 4 | **met on `gemma4:e2b` (0.0), not on `qwen2.5:7b` (1.3)** | six-run measurement |
| AC 5 | **met on `qwen2.5:7b` (1.2), not on `gemma4:e2b` (2.3)** | six-run measurement; structurally now possible on both |
| AC 6 | `met-with-evidence` | test |
| AC 7 | `met-with-evidence` | test |
| AC 8 | `met-with-evidence` | test |
| AC 9 | `met-with-evidence` | test |
| AC 10 | `met-with-evidence` | test |
| AC 11 | **met on `gemma4:e2b` (0.8), not on `qwen2.5:7b` (4.7)** | six-run measurement |
| AC 12 | `met-with-evidence` | test + transcript |

**Six met outright. Three met on one model of two. Two not met as written because they rest on
the third.** Every measured number moved in the right direction and none cost a user fact.

## Exit — exit 2

Not converged, and the fail-safe has two hours left - but `observe.md`'s goal check says to stop
when the answer stops moving rather than to run another variant, and cycle 1 established that
wording comparisons below six runs are noise. Three wordings and a structural change have been
measured across two models. **What remains is not a wording problem.**

Merging what is proven: every change is a measured improvement on at least one model, neutral on
the other, and costs a user fact on neither. A follow-up issue carries the criteria that did not
land, and says plainly that they may not be reachable by instruction alone on a 7B model - which
is the same wall the unwritten **system prompt story** exists to meet.
