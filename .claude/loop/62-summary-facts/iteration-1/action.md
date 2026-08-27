# Action

**Cold-read all 12 criteria, then take the exit.** Cycle 1 measured rather than assumed, and its
own conclusion is that two of the twelve rest on nothing a test can hold. Judge that honestly.

## 1. Read the criteria as written

`gh issue view 62` **first** - before the diff, before `logs/cycle-1.md`. That log argues for its
own conclusions and its author wrote both the wording and the case for it.

Then `git diff master...HEAD -- src/ tests/`.

## 2. The question that decides this row

**AC 4 and AC 5 do not say "on some models".**

> 4. General knowledge the model already has is not stored as though it were something learned
>    here.
> 5. Something restated in the turns that were kept is not also held in the summary.

Cycle 1 measured `qwen2.5:7b` ignoring the instruction - 3.5 general bullets before, 3.8 after,
inside the noise. On that model the criterion is **not met**, and the change did not make it met.

Decide, and say it plainly: is AC 4 met, met-in-part, or not met? `observe.md` says a criterion
that cannot be met as written is an acceptable outcome here and a likelier one than in the four
rows before. **Do not round it up to met because the code changed.**

If it is not met, the exit is still exit 1 or exit 2 - but the row's honest state goes in the
queue and, if criteria are left behind, in a follow-up issue.

**AC 5 was never separately measured at all.** "Something restated in the turns that were kept"
is a different claim from "general knowledge" - it is about duplication between the summary and
the surviving pairs. Nothing in cycle 1 tested or probed it. Do so, or mark it honestly.

## 3. Attack the rest

- **The instruction tests** assert substrings of the instruction. Intent, not effect - the exact
  shape the cold read has found in four of the last five rows. Do they earn their place, or are
  they decoration that will pass forever while the behaviour rots?
- **AC 3's decision.** Cycle 1 argues role is not a proxy for particularity because assistant
  turns carry answers as well as general knowledge. Is that right? Look for a counter-example.
- **AC 9, AC 10.** The stub returns a summary the test wrote, so these prove carrying rather
  than summarising. Is that enough for the criteria as worded?
- **AC 11.** Half is tested. The other half - a model inventing facts from small talk - was never
  probed. Probe it: a transcript of pure pleasantries, and see what comes back.

## 4. The break

Revert the instruction and record what goes red. **Expect little, and if nothing goes red, say
so** - that is the honest measure of how much of this row the suite actually holds, and it
belongs in the log rather than hidden behind a green run.

## 5. Re-run everything

- Full suite and the hermeticity command. **536 is the floor.**
- Transcript unchanged.
- No stray `.axiom/`.

## 6. Then take the exit

Whatever the verdict, hand over: mark row 15 done in `queue.md` with the PR number, cycle count,
wall-clock time **and the honest criteria state**, scaffold
`.claude/loop/60-rendered-replies/iteration-1/`, mark row 16 **running**. #60 is the last row.

**Do not touch the cron.**

## Record

Status for all 12, judged against the criteria text rather than cycle 1's table. The AC 4 and
AC 5 verdicts with reasoning. The AC 11 probe output. What the break turned red.

**Write no questions into anything.** Decide, record the decision and the reasoning, carry on.
