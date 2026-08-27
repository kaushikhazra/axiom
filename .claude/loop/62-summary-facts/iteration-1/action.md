# Action

**Cycle 1 reproduces the defect against a real model, changes the instruction, and covers what
can honestly be covered.** More of this row rests on a live probe than any before it - say so
plainly rather than dressing a stub test up as evidence.

## 1. Baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **521 passed**. Record it.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-62.txt`.
- `gh issue view 62`, record all 12 criteria `not-started`.

## 2. Reproduce it live, before changing anything

Call `compaction.summarised` (or whatever produces the summary) directly against the local
Ollama, with a transcript that mixes:

- a fact only the user could know - a name, a number, a preference,
- and the model explaining something general, the way it explained what RPG stands for.

**Paste the real output into the log.** If the general fact does not appear, say so - the defect
may be model-dependent, and that changes what this row can claim.

## 3. Change the instruction

Add the distinction the instruction lacks: facts the **conversation** established, not knowledge
the model brought to it. Keep the third sentence's protection - a brief early statement matters
as much as a later topic - because that is a different axis and #32 measured why it is there.

Then **run the same probe again** and paste the output. That comparison is AC 4 and AC 5's
evidence, and there is no substitute for it.

## 4. AC 3, honestly

Decide whether an honest structural signal separates "least particular", or whether keeping
general knowledge out makes the question moot. **Record the decision and the reasoning.** Do not
build a scorer that guesses importance - `assumption.md` rules that out and says why.

Whatever is decided, `bounded()` is testable directly with hand-written fact lists. Cover it.

## 5. Cover what a stub can honestly cover

- **AC 6, AC 7, AC 8** - the honesty and the bound, unchanged from #32. The existing
  `tests/test_compaction.py` largely holds these; add what is missing.
- **AC 9, AC 10** - recall across one compaction and across two, with a stub returning a summary
  the test wrote.
- **AC 12** - the transcript.
- **AC 11** - a stub can prove axiom does not *invent* a summary when the model returns nothing.
  It cannot prove the model does not invent one. Test the first, probe the second.

## 6. Then

Full suite and the hermeticity command. Break the instruction change and record what goes red -
**expect little, and say so**: an instruction has few hermetic consequences, which is itself the
finding to record rather than hide. Write cycle 2's action.

## Record

Status for all 12, and **for each, whether its evidence is a test or a live probe**. The before
and after probe output, verbatim. The AC 3 decision with reasoning. The break count and
survivors.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.
