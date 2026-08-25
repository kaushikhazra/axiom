# Action

Build the size-driven compaction and the three refusal messages. Cycle 1 measured everything
this needs; the plan is in `logs/cycle-1.md` and is not to be re-derived.

## 1. Compact because of the size, not only because of the usage

Today `too_large` refuses and the turn is dropped with nothing after it. Cycle 1's
measurement: a turn was refused at 287 tokens over while a compaction that would have taken
the payload from 1939 tokens to 226 — against a 2000 context — was never attempted, because
the *previous* turn's usage happened to sit 50 tokens under a threshold.

- When the payload will not fit, walk the same `KEPT_PAIRS_LADDER` driven by the measurement
  rather than by `running_usage`, and re-check after each rung. That is **AC 1**, and it must
  work when `running_usage` is `None`, when it is low, and when it is high.
- The refusal can then only happen after compaction has had its turn, which is **AC 2**.
  Ordering, not wording — a refusal that happens first fails this however well it reads.
- **Report it through the existing `note_compaction` and `note_facts_forgotten`.** That is
  **AC 8**. A second compaction path that forgot silently would undo what #32 spent three
  cycles building, and it would pass any size assertion.
- Reuse `compacted_history` and the ladder. Do not write a second compaction.

## 2. Three refusals, because three things can be too large

**AC 5** asks the message to name what is actually too large and suggest only something that
would help. Cycle 1 established the three cases are distinguishable and the floor is
computable — 205 tokens for the current prompt, and derivable rather than hard-coded.

- **The message itself is the bulk**, with little or no history — a shorter message genuinely
  helps. This is today's wording and it is correct here.
- **The conversation is the bulk**, and compaction has already run — say the conversation is
  what will not fit, and that a new session is the way out. Do not advise a shorter message:
  cycle 1 watched the overage stop falling at 5 tokens while the message shrank to one
  character.
- **Prompt plus a minimal summary plus the message still exceeds the context** — nothing the
  user types will help. **AC 6**: say so plainly, once, rather than let them discover it by
  retrying.

## 3. AC 3 and AC 4 are about the session, not the message

- **AC 3** — after a refusal, a following turn is not refused for the same reason. The refused
  turn is already rolled back with `del messages[before:]`; what must also be true is that
  whatever compaction achieved is *kept*, or the next turn starts from the same oversized
  history and hits the same wall.
- **AC 4** — no state where every message, however short, is refused. In the sub-floor case
  that is met by AC 6's message, not by making the impossible fit. Everywhere else it is met
  by compaction actually running.

## 4. Prove it

- **AC 3 and AC 4 need a real session driven in and back out.** Drive the AC 1 scenario from
  cycle 1 — usage pinned just under the trigger, history grown past the context — and show
  the session continuing afterwards. `.tmp/ac1_case_42.py` is the starting point.
- **AC 5 and AC 6 need the messages to differ between the three cases.** A test asserting one
  message contains "conversation" proves a string was built. Set up all three and assert they
  are different from each other and each names its own cause.
- **AC 7 is the transcript.** `diff .tmp/transcript-baseline-42.txt tests/baseline/transcript.txt`.
  A turn that fits must be byte-identical: no extra compaction, no extra output.
  **Read the whole diff as a diff before regenerating anything.**
- **AC 8** — a planted fact, a size-triggered compaction, and the fact still recalled
  afterwards; plus `the summary is full - forgetting N` appearing when it applies.
- Full suite and the hermeticity command. **255 is the floor.**

## 5. Do not over-build for the sub-floor case

Cycle 1 measured every real model at 32,768 tokens or more against a 205-token floor — at
least 160× headroom. The sub-floor case is reachable only through `AXIOM_DEBUG_MAX_CONTEXT`.
It still needs AC 6's message, because the criterion asks for it and the debug override is a
real path. It does not need a recovery mechanism built around it.

## Record

Status for all 8. Then write cycle 3's `action.md` — the cold check: criteria from GitHub
before the diff and before this log, attacking each rather than confirming it. That pass has
found a real defect in each of the last two issues.

**Write no questions into it.** Decide, record the decision and the reasoning, carry on.
