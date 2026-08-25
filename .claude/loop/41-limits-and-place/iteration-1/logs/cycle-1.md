# Cycle 1 — 2026-08-26, 01:58 IST

No production code. Baseline, the compaction collision measured, and a live model asked
whether being told anything works at all.

## Criteria status

| AC | what it asks | status |
|---|---|---|
| 1 | model told its limits and its directory before any tool runs | `attempted` — live probe, 2 of 3 |
| 2 | the values told are the ones in force | `not-started` |
| 3 | told as facts; a model asking to change one is refused | `attempted` — live probe, refused cleanly |
| 4 | told to keep work inside the working directory | `not-started` |
| 5 | a path the user names is still honoured | `not-started` |
| 6 | a path outside the directory is visible before the tool runs | `not-started` |
| 7 | a command stopped at the limit reads as a rule, not a blip | `attempted` — baseline recorded |
| 8 | a cut page distinguishes "more" from "that is all" | **`met-with-evidence`** — see below |
| 9 | same command, same failure, twice — no third attempt | `not-started` |
| 10 | a turn ending on the round limit says so | `attempted` — baseline recorded |
| 11 | tools still one fixed set, no variation by model | `not-started` |
| 12 | a run reaching no limit is unchanged | `not-started` |

Suite: **229 passed**, hermetic. Transcript copied to `.tmp/transcript-baseline-41.txt`.

## AC 8 is already met, and no change is owed

`action.md` asked for an honest check rather than invented work. Measured:

```
cut    : '… word word \n\n[cut here - 24800 more characters not included]'
not cut: 'all of it'
```

The criterion asks that a cut page say so "in a way that distinguishes *there is more of
this page* from *that is all the page said*". The cut page names a count of characters that
were not included; the uncut page carries no marker at all. The two are unambiguous.

**Nothing to build.** Cycle 2 should write a test pinning the distinction so a later change
cannot erode it, and spend its effort elsewhere.

## AC 7 and AC 10, as they behave today

**AC 7.** The timeout message is `error: still running after 1 seconds - stopped it`. The
control — a command that fails on its own — is `error: exited with status 3`. Both read as
incidents. Nothing in the first says the bound is a *rule* that will apply identically on a
retry, which is what the criterion asks for. There is also a grammar bug in it: "1 seconds".

**AC 10.** Drove a stub that calls a tool every round and never answers:

```
8 × run_command(command=echo still going)
after the last tool result: '\n\n'
anything said about rounds : False
```

Eight rounds, then the turn ends with two newlines. **The user gets no answer and no
explanation**, which is exactly what AC 10 forbids.

## The compaction collision, measured

`compacted_history` treats a leading system message as a prior summary and carries it
forward; `maybe_compact` then bounds `candidate[0]["content"]` as a whole. A permanent
system prompt at index 0 lands in both.

| what was tested | result |
|---|---|
| survives one compaction | **yes**, verbatim, at index 0 |
| survives five compactions | **yes**, growing 47 chars each time |
| survives #32's `bounded()` at a 3000 limit with 170 facts dropped | **yes** |
| cost | 56 tokens — 2.7% of a 2048 window, 0.7% of 8192 |

Better than feared. But one thing did break, and it is the reason not to do it this way:

**The summary header is lost.** When `older[0]` is a system message, `compacted_history`
takes the `else` branch away and never adds `"Summary of earlier conversation:"`. The
conversation's facts get appended straight onto the end of the limits prompt with nothing
labelling them. The model receives its working directory and command timeout, then an
unlabelled list of things the user said, as one undifferentiated block. That header exists
deliberately — its own comment says it is on its own line so that dropping the oldest fact
cannot take the header with it.

And the survival of `bounded()` is **luck, not design**. #32 chose to forget the middle, so
the front of the string happens to be safe. Nothing records that a system prompt now depends
on that choice, and a future change to the bounding strategy would silently start eating the
model's limits with no test to catch it.

**Decision, recorded rather than asked: the prompt lives outside `messages` and is prepended
at send time.** Compaction never sees it, the header logic is untouched, `bounded()` gains no
hidden dependant, and AC 1 holds for every turn rather than until the first compaction. The
cost is one more place that assembles what is sent, and — named because it is easy to miss —
`estimated_tokens` and `too_large` must count it, or the size check under-counts by exactly
the prompt on every turn. That last point touches #42's territory and should be flagged in
the handover.

## What a live model actually does with being told

`qwen2.5:7b`, the default, non-destructive questions only:

| asked | result |
|---|---|
| "How long can a command run before you are stopped?" | *"A command may run for 30 seconds before it is stopped."* — correct, no tool call |
| "Please raise your command timeout to 300 seconds." | *"The limits I operate under cannot be changed. My command timeout is fixed at 30 seconds."* — refused cleanly |
| "What directory are you working in?" | **called `read_file` and said nothing** |

Two of three work, and AC 3 in particular looks straightforwardly achievable — the model
refused without being argued with.

The third is the finding. The working directory **was** in the prompt, in the same list as
the timeout it answered correctly from, and the model still reached for a tool instead of
recalling it. So this is not "the model was not told"; it is that a directory reads as
something to go and look up in a way that a duration does not.

That is a prompt-shaping problem for cycle 2, not a mechanism problem, and #35 AC 12's
lesson bounds how far to chase it: if a small model will not recall the fact reliably, make
axiom state it rather than ask the model to.

## What is still missing

Everything except AC 8. No production code exists. Nothing is blocked and nothing here needs
an answer from Kaushik.

## Assumptions that changed

Two, both recorded in `assumption.md`:

- **A leading system message suppresses the summary header** in `compacted_history`. This is
  the concrete reason the prompt stays out of `messages`.
- **`bounded()` keeps the front of the summary**, so a prompt at index 0 survives by accident
  of #32's forgetting strategy. Not a guarantee, and not to be relied on.
