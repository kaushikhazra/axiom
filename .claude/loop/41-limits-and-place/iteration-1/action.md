# Action

**Fix the harness, then write the tests.** Cycle 2 built the code and left one test red on
purpose rather than rush a second mistake. Its log has the detail; do not re-derive it.

## 0. Read this first

Cycle 2 regenerated the golden transcript after diagnosing one line of a hundred-line diff,
because pytest's summary reports the *first* differing index and reads like it is reporting
the whole difference. It destroyed two compaction scenarios. It was restored and no damage
survives.

**Before any regeneration, run `diff .tmp/transcript-baseline-41.txt tests/baseline/transcript.txt`
and read all of it.** Never regenerate off a pytest summary. If the diff contains anything
you cannot name a reason for, that is a bug in the change, not in the baseline.

## 1. Fix the two harness faults

Both are stub artifacts of the class #40 found in `given_page`, and neither is a product
problem.

- **`stub_fetch`'s neighbours report a fixed `usage=1`** whatever they were sent, so any
  growth in the payload trips `looks_truncated`. Cycle 2's diff showed twelve false
  truncation warnings from this. Make the reported `prompt_eval_count` follow the size of
  what the stub actually received. It cannot be a constant and stay honest.
- **The transcript's compaction scenarios use contexts too small to hold a system prompt.**
  Cycle 2 measured the prompt at ~163 tokens under `too_large`'s divisor of 3. Raise those
  scenarios' windows the way `test_compaction.py`'s were raised, so they exercise compaction
  rather than the refusal.

Then regenerate deliberately. **The diff should contain only `outside the working directory`
lines** — genuinely new AC 6 behaviour. Anything else means something is still wrong. Quote
the diff in the log.

## 2. Write the tests cycle 2 did not

One per criterion, asserting on what changed rather than on what was said about it.

- **AC 2** — `--command-timeout 5` and `AXIOM_COMMAND_TIMEOUT=5` each change what the prompt
  says. Same for the working directory. The point is that there is one value, not two.
- **AC 6** — a path outside is named, resolved; a path inside is not named. A *relative* name
  that lands outside is the case that matters, since that is the surprise.
- **AC 7** — the message names the limit as a rule. Assert it differs in shape from the
  ordinary failure `error: exited with status 3`, which is what it used to resemble.
- **AC 8** — the pinning test cycle 1 called for and cycle 2 did not write. Cut page names a
  count; uncut page carries no marker.
- **AC 9** — same command, same failure, twice: the third is refused. And the two negatives
  that make the criterion mean something: a command failing *differently* the second time is
  still run, and a *different* command failing the same way is still run.
- **AC 10** — a stub calling tools every round ends with the round-limit line, not silence.
  Cycle 1 recorded the before-state as `'\n\n'`.
- **AC 11** — declarations do not vary by model.
- **AC 12** — the transcript, once step 1 is honest.

## 3. The live probe, extended

AC 1, 3, 4 and 5 are not closable without it. `.tmp/probe_live_41.py` is the start; cycle 1
covered `qwen2.5:7b` only.

Working directory `C:/Projects/.tmp/axiom-tool-sandbox`, non-destructive only, never the
repo. Add:

- a relative filename lands in the working directory (AC 4),
- an explicitly named outside path is still honoured (AC 5) — **AC 5 fails if the instruction
  makes the model refuse**,
- and re-ask cycle 1's directory question. It called `read_file` instead of answering from
  the prompt; the prompt now states the directory as the place work lands rather than as a
  value in a list. Find out whether that changed anything.

Run `gemma4:e2b`, `ornith:9b` and `qwen2.5-coder:7b` too. If a model ignores the prompt,
that is the cycle's most important finding and #35 AC 12's lesson applies: make axiom do the
thing rather than ask the model to.

## 4. Carry the #42 finding into the handover

Cycle 2 established that a fixed prompt of ~163 tokens against a small context refuses every
turn — which is the state **#42 AC 4** forbids: *"A session cannot reach a state where every
message, however short, is refused."* #41 introduces the condition #42 exists to fix. This
goes in #42's scaffold whatever happens to this loop.

## Record

Status for all 12. Then write cycle 4's `action.md` — the cold check: criteria from GitHub
before the diff and before any log, attacking each rather than confirming it.

**Write no questions into it.** Decide, record the decision and the reasoning, carry on.
