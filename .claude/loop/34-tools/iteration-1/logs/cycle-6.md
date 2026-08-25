# Cycle 6 - 2026-08-25 07:22 IST

AC 20, AC 30 and AC 31. **119 tests green, from 112.** `src/` 900 -> 949.
Transcript unchanged.

## AC 20: two real defects, found by looking rather than reasoning

The action said find out first and do not assume it is broken. It was broken, in two ways,
and a probe over a synthetic history showed both.

### A tool result kept without its call

`compacted_history` slices `messages[-kept_pairs * 2:]`. That arithmetic assumes a turn is
two messages. A turn that used tools is four - user, assistant-with-calls, tool, assistant -
so the cut landed inside one:

```
system: Summary of earlier conversation: ...
tool:   contents of file 2        <- the call that produced this was summarized away
assistant: answer 2
```

A tool result for a request the model never made. Ollama may reject that outright, and at
best the model is handed an answer to a question it cannot see.

**Fixed** by snapping the cut forward to the next `user` message - the start of a turn.
Forward rather than back, so a compaction candidate never grows, which the escalation ladder
depends on.

### What was asked never reached the summary

`compact()` rendered `f"{role}: {content}"`. An assistant message carrying only tool calls
has `content=""`, so the transcript handed to the summarizer read:

```
user: question 0
assistant:                        <- the read_file(/f0) call, gone
tool: contents of file 0
```

The summary could record *that a file said something* but not *which file*. The fact
survived and its subject did not - which is precisely the failure mode #29's whole iteration
was about.

**Fixed** by rendering calls: `assistant: called read_file({'path': '/f0'})`.

### A regression the existing suite caught immediately

The first version of the boundary fix broke
`test_compacted_history_carries_summary_forward_with_no_new_turns`. With a prior summary at
index 0 and nothing older than the kept window, snapping *forward* found a boundary at index
1 and compacted a history that had nothing to compact - turning a no-op into work.

Fixed by only snapping when there is genuinely something older. Worth recording that #29's
test caught a #34 regression in code #34 was not supposed to be touching.

### Four tests now hold it

Including `test_plain_conversations_are_sliced_exactly_as_before`, which pins that a history
with no tool use slices identically - every boundary in one is already a turn boundary, so
the new rule must be invisible there.

## AC 30: cancelling stops the work

`run_command` blocks in `communicate()`. An interrupt there unwound the turn with the child
still running - the same shape as cycle 4's timeout bug, and with the same consequence: the
user believes they cancelled, and work carries on where they cannot see it.

Now kills the tree and re-raises, so the turn still unwinds and the session returns to the
prompt.

Tested the way cycle 4 taught: the command writes a marker after the interrupt should have
killed it, and the test asserts the marker never appears. A test that only checked the
session survived would have passed against a program that leaks processes.

## AC 31: already met, now pinned

Decided against the transcript rather than the code, as the action asked. The three failures
already read differently:

| failure | where | how | turn |
|---|---|---|---|
| tool | stdout | `  \| error: ...` inside the tool's marked output | carries on |
| model refused | stderr | `error: model refused` | ends |
| connection lost | stderr | `error: cannot reach Ollama at ...` | ends |

A tool failure is not a session-level failure and does not appear on stderr at all. A test
now asserts all three, including that a refusal and a dropped connection do not produce the
same message - they carry different advice, one being wait and one being check the network.

## Criteria status

**Startup** 1-2 `met-with-evidence`

**Works across models** 3 `not-started`, 4 `met-with-evidence`, 5 `attempted`,
6 `not-started`, 7 `not-started`, 8 `met-with-evidence`

**Files** 9-12 `met-with-evidence`

**Commands** 13-16 `met-with-evidence`

**Multi-step work** 17-19 `met-with-evidence`, **20 `met-with-evidence`** - both defects
fixed, four tests, and a compacted session provably still refers to earlier tool work

**Visibility** 21-23 `met-with-evidence`

**Boundaries** 24-27 `met-with-evidence`

**Failure and recovery** 28-29 `met-with-evidence`, **30 `met-with-evidence`**,
**31 `met-with-evidence`**

**Configuration** 32-34 `met-with-evidence`

**Exit** 35 `met-with-evidence`

## Goal check

**Not met.** 31 of 35 carry evidence, from 29.

## What is left

Four criteria, and they are all the same job: **the live model pass.**

- **AC 3** - the same request producing the same tool actions on `qwen2.5:7b`, `gemma4:e2b`
  and `ornith:9b`, changing nothing but `--model`.
- **AC 5** - support for a further model added without editing any tool. Structurally true
  since cycle 2; needs demonstrating rather than asserting.
- **AC 6** - a model announcing a call as text rather than structured output. Cycle 1's probe
  never reproduced it. If three families again produce clean structured calls, the honest
  outcome is a synthetic test of the handler plus a plain statement that the failure mode was
  not observed - not a claim that it cannot happen.
- **AC 7** - tool calling behaving the same streamed and not. Only the streaming path is
  exercised today.

That is one cycle, and it wants the whole cycle: three model loads on a 16GB machine, plus
`gemma2:2b` already covered. Nothing else should be attempted alongside it.
