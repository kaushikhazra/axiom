# Cycle 3 — 2026-08-26, 02:28 IST

Harness fixed, transcript regenerated **with the whole diff read**, 24 tests written, and the
live probe run across all four tool-capable models. All twelve criteria now have evidence.
**Convergence is not declared** — cycle 4 is the cold check.

## Criteria status

| AC | status | evidence |
|---|---|---|
| 1 | `met-with-evidence` | 4 models answered both the timeout and the directory from the prompt |
| 2 | `met-with-evidence` | command line, environment and direct `Limits` each change what is said |
| 3 | `met-with-evidence` | 4 models refused cleanly; `limits` appears in no schema and `run()` rejects it |
| 4 | `met-with-evidence` | 4 models chose a relative path; it lands in the working directory |
| 5 | `met-with-evidence` | 4 models used a named absolute path exactly; unit test |
| 6 | `met-with-evidence` | resolved, not echoed; the escaping-relative case tested |
| 7 | `met-with-evidence` | reads as a rule, and stays distinguishable from an ordinary failure |
| 8 | `met-with-evidence` | pinned by test, per cycle 1's finding that it was already met |
| 9 | `met-with-evidence` | both negatives tested, plus turn scoping |
| 10 | `met-with-evidence` | the round-limit line replaces cycle 1's `'\n\n'` |
| 11 | `met-with-evidence` | declarations do not vary |
| 12 | `met-with-evidence` | transcript regenerated; every hunk accounted for below |

**Suite: 253 passed** (229 + 24), hermetic.

## The transcript, and how it was done this time

Cycle 2's mistake was regenerating off pytest's summary, which reports the *first* differing
index and reads like it reports the whole difference. This time the whole diff was read as a
diff before anything was accepted. Every hunk, accounted for:

| hunk | what | why it is legitimate |
|---|---|---|
| lines 36, 151 | `context: 200 tokens` → `1000 tokens` | deliberate harness change — 200 can no longer hold a system prompt |
| lines 122, 134, 217 | `outside the working directory: <sandbox>\...` | genuinely new AC 6 behaviour; the transcript's tool scenarios use a temp sandbox, which really is outside |
| line 154 | `forgetting 34` → `forgetting 7` | `summary_limit` scales with the context, so a 1000-token window forgets fewer facts per pass |
| 164-166, 189-231 | compaction blocks reordered, 27 fact lines fewer | same cause — the scenario now reaches its bound later and drops less |

**Both compaction scenarios are intact.** `compacting older history` and `the summary is
full - forgetting N` are still there, doing what they are named for, with different numbers.
Nothing was destroyed. That is the difference between this regeneration and cycle 2's.

## The two harness faults

Both were stubs contradicting the thing under test — the same class as #40's `given_page`
announcing `text/plain` over HTML, and neither is a product problem.

- **`StubClient` reported a fixed `prompt_eval_count=1`** whatever it was sent.
  `looks_truncated` compares the estimate against exactly that, so once #41 put a prompt in
  every request the stub was claiming every request had been cut — twelve false warnings in
  cycle 2's diff. It now derives the count from the payload it actually received. An
  explicit count still wins, for the two scenarios that set one to drive compaction.
- **The two transcript compaction scenarios used 200-token windows.** At ~163 tokens for the
  prompt that leaves nothing for a conversation, so they were exercising the refusal rather
  than compaction. Scaled to 1000 with their triggers, exactly as `test_compaction.py`'s were.

## What a real model does, all four

`qwen2.5:7b`, `qwen2.5-coder:7b`, `gemma4:e2b`, `ornith:9b`. Sandbox working directory,
non-destructive requests only.

| | timeout | directory | refuses change | relative by default | honours named path |
|---|---|---|---|---|---|
| qwen2.5:7b | ✓ | ✓ * | ✓ | ✓ `notes.txt` | ✓ |
| qwen2.5-coder:7b | ✓ | ✓ | ✓ | ✓ | ✓ |
| gemma4:e2b | ✓ | ✓ | ✓ | ✓ | ✓ |
| ornith:9b | ✓ | ✓ | ✓ | ✓ | ✓ |

**Cycle 1's problem is fixed.** Asked which directory it was working in, `qwen2.5:7b` called
`read_file` and said nothing. The prompt now states the directory as the place work lands
rather than as a value in a list, and all four answer it directly.

`*` One honest blemish: `qwen2.5:7b` answered `C:\Projects\tmp\axiom-tool-sandbox`, dropping
the dot from `.tmp`. It recalled the fact and mis-transcribed one character. It does not
affect behaviour — the same model uses relative paths for its own work, and AC 4 passed —
but it is recorded rather than rounded up to a tick.

**AC 5 is the one that could have failed quietly** and did not. An instruction to stay inside
the working directory is exactly the kind of thing that makes a model refuse work the user
actually asked for. All four used the named absolute path exactly as written.

## Nothing here needs an answer from Kaushik

## Why this cycle does not declare convergence

`observe.md`: the cycle that writes the code never declares it done, and in #40 that check
found a criterion outright broken after the implementing cycle had marked it met.

Cycle 2 and cycle 3 wrote all of this. Cycle 4 reads #41's criteria from GitHub before the
diff and before these logs, attacks each one rather than confirming it, and merges only if
they hold.

## Carried to the handover

**#41 creates the state #42 AC 4 forbids.** A fixed ~163-token prompt against a small context
refuses every turn, however short. #42's scaffold must carry this.
