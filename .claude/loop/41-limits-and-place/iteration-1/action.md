# Action

**Cycle 1 writes no production code.** Record the baseline, and probe the two things in this
issue that can quietly break something else. A fix designed against an imagined failure is a
fix for the wrong thing.

## 1. Record the baseline

- Full suite and the hermeticity check. Confirm 229 green.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-41.txt`. **AC 12 is
  measured by this file**, so a later check must be a diff command rather than a memory.
- Record the exact strings AC 7 and AC 8 are about, as they read today, by running them -
  not by quoting the source.
- Record what a turn looks like today when it exhausts `MAX_TOOL_ROUNDS`: drive a stub that
  calls a tool every round and never answers, and write down exactly what the user sees.
  That is AC 10's before.

## 2. Probe the system prompt against compaction

This is the sharpest edge in the issue and it is cheap to measure.

`compaction.compacted_history` checks whether the older half of the history begins with a
system message and, if so, treats it as a carried-forward summary and appends to it. A
permanent system prompt would sit at index 0 forever.

Drive a session with a system prompt at index 0, past a compaction, with
`AXIOM_DEBUG_MAX_CONTEXT` small enough to force one. Record:

- Does the prompt get absorbed into the summary, duplicated, or dropped?
- Does it survive compaction at all? A model that loses its limits mid-session fails AC 1
  for every turn after the first compaction, and nothing would report it.
- What does it cost against the window? Measure the characters, and say what fraction of a
  small context it takes.

**If it breaks compaction, say so plainly and design around it in cycle 2.** The options -
keeping the prompt outside `messages` and prepending at send time, or teaching
`compacted_history` to distinguish the two kinds of system message - are both cheap. Pick on
evidence, not preference.

## 3. Probe what a real model does with being told

`observe.md` requires a live model for AC 1, 3, 4 and 5. Find out now whether the local
models comply at all, because the answer shapes the whole issue.

Working directory `C:/Projects/.tmp/axiom-tool-sandbox`, non-destructive requests only, per
`CLAUDE.md`. With a draft prompt stating the limits:

- Ask something that would exceed the command timeout. Does it say so instead of trying?
- Ask it to change the timeout. Is it refused, and does it accept that?
- Ask it to create a file with a bare relative name. Does it land in the working directory?
- Ask it to create a file at an explicit path outside. Is that still honoured? **AC 5 fails
  if the instruction makes it refuse.**

Record what each model actually did. If a model ignores the prompt entirely, that is the
most important finding in the cycle and #35 AC 12's lesson applies: make axiom do the thing
rather than ask the model to.

## 4. Check AC 8 honestly

The current cut message may already satisfy it. Read the criterion, read the message, and
say met or not met with the reasoning. **Do not invent a change to justify the criterion** -
inventing work is as wrong as skipping it.

## 5. Say what the fix will be

One paragraph per criterion group, no code. Where the prompt lives, what it says, how AC 9
compares "the same failure", and what AC 10 prints. If a probe shows the obvious approach is
wrong, say that instead.

## Record

Status for all 12 - most will read `not-started`, which is correct for this cycle. Then
write cycle 2's `action.md`.

**Write no questions into it.** Decide, record the decision and the reasoning in the log,
carry on. Nobody is reading between firings.
