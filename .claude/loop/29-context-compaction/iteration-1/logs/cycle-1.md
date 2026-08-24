# Cycle 1 — 2026-08-24 14:15 IST

## Where the artifact stood before this cycle

`src/axiom/__init__.py` was #26+#28's merged state — chat loop, streaming, interrupts, effective context sizing. No compaction, no token-usage tracking.

## Unknown 1 — measuring usage against the effective context

Checked what Ollama's own streamed response actually carries before assuming a tokenizer library was needed:

```
final chunk fields:
  ...
  prompt_eval_count = 35
  eval_count = 4
  ...
```

`prompt_eval_count` is the number of tokens the model actually processed as input for that request — the real, exact size of everything sent, measured by Ollama's own tokenizer. `eval_count` is the reply's own token count. Since axiom sends the full `messages` history on every call (no server-side session), `prompt_eval_count + eval_count` after any turn *is* the current conversation's real token size — no separate tokenizer needed, no approximation. This becomes the running total to check against #28's `effective_context` before the next send.

Not wired into `main()` yet — that's the trigger logic, out of scope for this cycle per the action's own instruction.

## Unknown 2 — a compaction mechanism, proven standalone

`compact(client, model, pairs)` asks the model itself to summarize a run of `{role, content}` messages into shorter text, as a single non-streamed request — using the same client already in `main()`, no new dependency.

**Evidence — a real fact survives, and the text genuinely shrinks:**

```
$ axiom.compact(client, 'qwen2.5:7b', pairs) on a real 4-message exchange
  ("teal" and "a cat named Biscuit")
original: 157 chars
compacted: 73 chars
"The user's favorite color is teal. The user also has a cat named Biscuit."
```

**Evidence — the model can answer from the compacted text alone** (earlier probe, before the function was moved into `src/`, same mechanism):

```
--- recall check: ask the model using ONLY the compacted text ---
Based on the summary, your cat's name is Biscuit, and your favorite color is teal.
```

Both facts recalled correctly from summary text alone, no access to the original messages.

## A finding worth carrying forward

The compacted summary contained mojibake in one probe run — `sauté` rendered as `saut�`, the same class of issue #26 cycle 3 hit with a `·` in the startup line. This is the *model's own generated content*, not something axiom controls directly. It doesn't block this cycle (nothing requires printing the compacted text to the user — AC 8 only requires the *fact* of compaction to be visible, not the text itself), but if a later criterion ever needs to display the compacted content, this will need the same ASCII-safety treatment #26 applied to its own output.

## Criteria

Re-read from the live issue this cycle (not from memory) to get the numbering right — a first draft of this table mis-numbered from AC 6 onward by dropping AC 6 (the "still compacts even when kept pairs dominate" rule) while transcribing. Corrected before commit.

| AC | State | Evidence |
|---|---|---|
| 1 90% trigger, compact to 10 pairs | **not met** | measurement mechanism proven, not wired to a trigger |
| 2 below threshold, no compaction | **not met** | same — no trigger exists yet |
| 3 escalate to 5 pairs | **not met** | ladder not written |
| 4 escalate to 2 pairs | **not met** | same |
| 5 escalate to 0 (compact everything) | **not met** | same |
| 6 still compacts even when kept pairs dominate the space | **not met** | ladder not written |
| 7 model can answer from compacted portion | **met — new** | live recall transcript above |
| 8 compacted history uses fewer tokens | **met — new** | 157 -> 73 chars, real reduction (token-level, not just character-level, is worth confirming later via `prompt_eval_count` rather than `len()`) |
| 9 visibility when compaction happens | **not met** | no trigger, nothing to be visible about yet |
| 10 compacted stays compacted for the session | **not met** | no state management wired yet |
| 11 fewer than 10 pairs, nothing to compact | **not met** | no ladder logic yet |

**2 met, 9 not met, 0 untested.**

## Movement

From nothing to two proven building blocks. Both were genuine unknowns — neither the token-measurement approach nor the compaction mechanism existed anywhere in the codebase or in prior cycles' patterns, unlike #28's cycle 1 which extended an established `model_info` inspection pattern.

## What is still missing, and is it closable

AC 1-6, 9-11 — the trigger, the ladder, and wiring both into `main()`. All closable: the two hard unknowns (how to measure, how to compact) are solved; what remains is control flow using pieces that already work.

## Assumptions that changed

None. Both assumptions flagged as "genuine design surface, not locked" in `assumption.md` are now resolved and documented above.

## Goal check

**Not met.** 2 of 11. Next action written.
