# #85 — the manual pass

Settled 2026-09-08. No loop folder and no `iteration-1/`, because #85 never had a
loop: it was written, built and merged in one evening on 2026-09-03 after #74's pass
found what it is for.

**The tests cite ten of thirty criteria.** Searched across the whole suite, the only
#85 numbers any test claims are **1, 2, 7, 10, 11, 12, 14, 16, 17, 20**. Twenty are
cited by nothing, because they are about **what a thing looks like**, and looking is
all #85 changed.

## It did not need fifteen rows of typing at a model

A fifteen-row checklist was written first and then thrown away, which is worth
recording because the reasoning generalises.

Driving #74's pass on the same day left **thirty-six captured tool calls across five
tools** — `schedule_prompt` 15, `run_command` 13, `list_schedules` 5,
`cancel_schedule` 2, `fetch_page` 1 — in
`.claude/loop/74-scheduled-prompts/iteration-1/*.log`. Those transcripts are #85's
evidence. They were gathered for a different issue and they answer most of this one,
because every one of them is a call line and a result line drawn by the code under
test.

**What a transcript could not reach is the drawing**, and that is one screen rather
than fifteen turns. `sample.py` calls the same pair a real turn calls — `note_tool`
then `show_tool_result` — with realistically shaped results:

    uv run --project C:/Projects/axiom python .claude/loop/85-tool-lines/sample.py

No model, no waiting, no schedule to trip over. Resize the window and run it again.

## The rows

| AC | Verdict | Evidence |
|---|---|---|
| 1 | pass | turns that called no tool produced no tool line, throughout |
| 2 | pass | 36 call lines, each naming its tool |
| **3** | **pass** | `run_command(command=date)` at 11:18:36, its result at **11:19:06**. Thirty seconds apart — the call line demonstrably precedes the result, which is the one thing no still image can show |
| 4 | pass | `cron=*/1 * * * *, prompt=say TICK, repeating=True` |
| 5 | pass | `list_schedules()`, and a `schedule_prompt()` the model called with nothing at all |
| 6 | pass | `sample.py` — a 350-character call cut to one row ending `…` |
| 7 | pass | every result in every transcript sits under its own call |
| 8 | pass | `sample.py` — a 24-line result becomes three rows and `… 21 more lines` |
| 9 | pass | `sample.py` — `(finished with no output)` still gets a row |
| 10 | pass | `sample.py` — `×` on the error row against `·` on the success above it, same turn |
| 11, 12, 13 | pass | six `date` calls in one turn, three-round turns, all in order, none interleaved |
| 14 | pass | model → tool → model → tool seen repeatedly; every round drawn |
| 15 | pass | the count line appears **nowhere** in any log. The eleven greps that match are all the startup banner |
| 16 | pass | tools countable by counting call lines |
| 17, 20 | pass | **four times on 2026-09-08.** The tool said `next at 11:16`, the model said "01:16", and both were on screen. This is the criterion the issue exists for |
| 18 | pass | the identifier leads the first result row |
| **19** | **fails below ~90 columns** | see the open judgement |
| 21 | pass | grey `38;2;112;116;126`, against the answer's default foreground |
| 22 | pass | every line starts with two spaces and a mark. None starts with `axiom:` |
| 23 | pass | judged on screen — see below |
| 24, 25, 26, 27 | pass | golden transcript unmoved, suite green at 964 |
| 28, 29 | pass | failing tools that did not end the turn, repeatedly |
| 30 | pass | `exit status 0` on every run |

## The judgements

**A — `×` against `·`, and B — four lines a tool: answered by Kaushik, 2026-09-08.**
Shown the full sample screen: *"all the rows looks very cool to me."* The marks read
apart, and four lines a tool is a block worth reading rather than one to skim. Both
open questions from the 2026-09-04 handoff are closed.

**C — AC 19 at a narrow window. Open, and it is a real failure rather than a
judgement about taste.**

`schedule_prompt`'s first result row carries the identifier, the schedule, the prompt
and the next run time, and the prompt sits inside it — so the row's length moves with
what was scheduled. Measured with `say TICK`, an eight-character prompt, giving 89
characters:

| window | what survives |
|---|---|
| 100+ | the whole row |
| 90 | `next at 2026-09-08 22:27…` — the time lives, ` local` is gone |
| **80** | `next at 2026-0…` — **AC 19 fails outright** |

**A longer prompt fails at a wider window.** A job whose prompt is a sentence rather
than two words pushes the cut left by however long the sentence is.

It was left visible rather than half-fixed when #85 shipped, because shortening it
means changing what `_when()` returns and that is #74's tested contract. The decision
that is actually open:

- **accept it** — 80 columns is a corner, and the identifier and the seven-day notice
  both survive on rows of their own; or
- **file it** — and the fix is either a shorter `_when()` for the screen, or letting
  a result row wrap where a call row may not.

Nothing else in #85 is outstanding.
