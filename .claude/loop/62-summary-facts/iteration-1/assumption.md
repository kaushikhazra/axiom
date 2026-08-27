# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Rows 1 to 14 merged. **521 tests, green and hermetic** at scaffold time.

- **`compaction.COMPACTION_INSTRUCTION`** is what produces the summary:

  > *Extract every distinct fact, stated preference, name, and number from the conversation
  > below as a bulleted list - one bullet per fact, in the order it was mentioned. Do not write
  > a narrative summary. Do not judge some facts as more important than others: a brief, early
  > statement (e.g. a stated preference) is exactly as important to keep as a later, longer
  > topic. Omit nothing a reader would need to answer a question about anything mentioned
  > below.*

  **"every distinct fact ... from the conversation" is why the defect exists.** The model *said*
  "RPG stands for role-playing game" during the conversation, so by this instruction it is a
  fact from the conversation and belongs in the list. The instruction never distinguishes what
  the conversation *knows* from what the model already knew.

  Note the third sentence: it forbids judging importance, and it is there for a reason - #32
  found oldest-first dropping losing "my cat is called Biscuit" from turn one. **Any change must
  not undo that.** "Not general knowledge" is a different axis from "not important".

- **`compaction.bounded(summary, limit)`** cuts the summary to its bound and returns what was
  dropped. **It drops from the middle**, keeping `KEEP_EARLIEST = 5` at the front, because early
  facts are identity-shaped and recent ones are live context. AC 3 lives here, and this docstring
  records why the obvious alternative was rejected.
- **`terminal.note_facts_forgotten(dropped)`** names each dropped fact, one per line. AC 6 is
  already true and must stay true.
- **`compaction.summary_limit`** is `SUMMARY_FRACTION = 0.5` of the window. AC 7 is that this is
  unchanged.
- **`StubBackend.complete(model, messages)`** returns a fixed `summary` string and records what
  it was asked. **It cannot demonstrate what a real summariser does.**
- **`tests/test_compaction.py`** holds #32's and #29's coverage - the ladder, the bound, the
  forgetting announcement.

## The defect, as observed

2026-08-27, first manual pass, real session:

```
axiom: the summary is full - forgetting 2:
  | - RPG stands for role-playing game
  | - The player starts in the peaceful world of Azeroth and quickly finds themselves caught up in the conflict between the Horde and the Alliance.
```

Nothing was lost that time - a car registration given before the compaction was recalled
correctly afterwards. The complaint is that a bounded store spent a slot on something the model
would reproduce on request, while the user's own details competed for the same space.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest. No new dependency.
- **The local Ollama at `http://localhost:11434`** for probes: `gemma4:e2b`, `qwen2.5:7b`,
  `qwen2.5-coder:7b`, `gemma2:2b`, and `ornith:9b` (**which crashes the server on load,
  intermittently - avoid it**).
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/62-summary-facts`.** Commits reference #62.
- **`master` is protected by a hook.** Everything lands on the branch and merges by PR.
- **One row follows this one** - #60, the largest in the queue. On exit, hand over per the queue.
- **One cron drives the whole queue.** Marking the next row running *is* the handover. **Never
  delete it.**

## Decided - do not reopen

- **The instruction is the primary lever.** It is the same reasoning Kaushik applied to the
  fabrication problem: shaping what is asked for is keepable, and a checker that second-guesses
  the output is not.
- **No fact scorer.** AC 3 must not become a heuristic that ranks bullets by guessed importance.
  If no honest structural signal separates "least particular", meet AC 3 by keeping general
  knowledge out in the first place, and say so.
- **#32's middle-drop stays** unless something better is *proved* better. Its docstring records a
  measured failure of the obvious alternative.
- **Corruption is out of scope.** "ventured" becoming "**Vented**" across a compaction boundary
  was seen in the same session. It is a different failure - a fact altered rather than dropped -
  and belongs to its own story. Do not widen this row to cover it.
- **A live probe never enters the suite.** The suite stays green with no Ollama.

## Carried forward, worth not relearning

- **A stub that contradicts the thing under test proves nothing**, and here the stub cannot
  demonstrate the thing at all. #61's AC 9 had no test whatsoever and the whole suite was blind
  to it - the same blindness is available here on AC 4 and AC 5.
- **An assertion a wrong implementation also satisfies proves nothing.** Four instances in five
  rows.
- **Name the survivors of the break**, individually. That is how #56 and #61 found theirs.
- **Read criteria literally, against states nobody had in mind.** #55.
- **Fix every stub before regenerating the transcript.**
- **A `sed`/`.replace()` that does not match reports success.** Grep after scripted edits.
