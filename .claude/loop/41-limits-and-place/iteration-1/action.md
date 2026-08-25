# Action

Build the prompt and the three message changes. Cycle 1 measured everything this needs and
its findings are in `logs/cycle-1.md` — do not re-derive them.

## 1. The system prompt, outside `messages`

Decided in cycle 1 on measurement: the prompt is **not** stored in `messages`. It is held by
`main()` and prepended at send time, so `compaction.py` never sees it.

- Built from the resolved `Limits`, so AC 2 is true by construction rather than by a second
  copy of the values that can drift. Changing `--command-timeout` changes what the model is
  told, because it is the same object.
- **Describe the limits, not the inventory.** No tool count, no tool names — #43 makes the
  tool list vary by run and a prompt naming "seven tools" would be wrong in two loops.
- **`estimated_tokens` and `too_large` must count it.** They assemble from `messages`, which
  no longer holds the whole payload. Miss this and the size check under-counts by exactly the
  prompt, every turn. Cycle 1 measured the cost at 56 tokens for a draft; a fuller prompt
  will be larger.
- AC 4's instruction goes in the same prompt: keep work inside the working directory, go
  outside it only when the user names a path outside. **No enforcement** — `assumption.md`
  settles that, and AC 5 exists to stop a guard being built.

**The working directory needs shaping.** Cycle 1's probe: asked how long a command may run,
`qwen2.5:7b` answered from the prompt correctly; asked what directory it was working in, it
called `read_file` and said nothing — from the same list. A duration reads as a fact and a
path reads as something to go and look up. Try stating it as the place work lands rather than
as a value in a list. If a small model still will not recall it, **make axiom state it rather
than ask the model to** — that is #35 AC 12's lesson and it bounds how far to chase this.

## 2. AC 7 and AC 10, the two messages

- **AC 7.** Today: `error: still running after 1 seconds - stopped it`, which reads like the
  control failure `error: exited with status 3`. Make it say the bound is a rule that will
  apply again to the same command. Fix "1 seconds" while there.
- **AC 10.** Today the round loop falls out of `range(MAX_TOOL_ROUNDS)` and the user gets
  `'\n\n'` — no answer, no reason. Say the turn ended because it reached the round limit.
  **Not by raising the limit.** `terminal.py` owns the printing.

## 3. AC 9, and be precise about "the same"

The same command failing the same way twice in one turn is not run a third time. Both halves
are load-bearing:

- **Same command** — the exact string, and say so in the code.
- **Same failure** — say in a comment what this is compared on. A command that fails
  differently the second time is not this case; a *different* command failing the same way is
  not either.

Scope is one turn. Nothing carries between turns.

## 4. AC 8 is already met — pin it, do not rebuild it

Cycle 1 checked it honestly and it holds: `[cut here - N more characters not included]`
against a bare page with no marker. Write a test that pins the distinction so a later change
cannot erode it, and spend no further effort there.

## 5. Prove it, and prove nothing else moved

- Unit tests for each of AC 2, 6, 7, 8, 9, 10, 11, 12.
- **AC 12 is the transcript.** `diff .tmp/transcript-baseline-41.txt tests/baseline/transcript.txt`.
  A system prompt is not output, but anything leaking it to the screen is. If a scenario
  genuinely moves, regenerate deliberately and say which lines and why.
- Full suite and the hermeticity command. 229 is the floor.
- **AC 1, 3, 4 and 5 need the live probe**, extended to cover AC 4 and AC 5: a relative
  filename lands in the working directory, and an explicitly named outside path is still
  honoured. `.tmp/probe_live_41.py` is the starting point. Working directory
  `C:/Projects/.tmp/axiom-tool-sandbox`, non-destructive only, never the repo. Run more than
  one model — cycle 1 only covered `qwen2.5:7b`, and `gemma4:e2b`, `ornith:9b` and
  `qwen2.5-coder:7b` all report tool support.

## Record

Status for all 12. Then write cycle 3's `action.md`, which is the cold check: criteria from
GitHub before the diff and before this log, attacking each rather than confirming it.

**Write no questions into it.** Decide, record the decision and the reasoning in the log,
carry on. Nobody is reading between firings.
