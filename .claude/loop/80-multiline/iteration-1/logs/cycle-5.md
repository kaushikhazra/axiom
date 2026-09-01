# Cycle 5 — paste, and the half of it that was not where it looked

2026-09-01, 22:06 +0530. Branch `feature/80-multiline`. Committed.

## The measurement

**Criteria demonstrably met: 13 of 36.** Moved by 5.

| bucket | count | criteria |
|---|---|---|
| **1 — met, proved by a break** | **13** | 1, 2, 3, 5, 7, 8, 9, 10, 13, 18, 22, 23, 30 |
| 2 — implemented but not proved | 4 | 4, 12, 14, 31 |
| 3 — not started | 19 | 6, 11, 15, 16, 17, 19, 20, 21, 24–29, 32, 33, 34, 35, 36 |

**The defect #80 was filed for is fixed.** Three lines pasted are one message.

## The suite

    891 passed, 1 deselected, 83.93s     entering
    900 passed, 1 deselected, 83.84s     leaving

Arithmetic: 891 + 9 = 900. **Baseline untouched**, eleven cycles across two issues.

## The reader half was already true, and that is the dangerous kind of true

Every paste test passed **first time**, on the criterion `loop.md` calls the hardest in the
issue. That is precisely when a green test deserves suspicion.

The reason it held is worth recording, because the obvious assumption is wrong:

> **Windows consoles do not send bracketed-paste markers at all.** There is no
> `\x1b[200~` to look for. prompt_toolkit *infers* a paste - a batch of key events
> arriving together, containing at least one newline and at least one text character,
> becomes a single `BracketedPaste` event carrying the whole text.

Read out of `prompt_toolkit/input/win32.py`, `_is_paste`. Its own comment says it is "not
100% correct, but probably the best possible way", which is honest and is also a thing to
remember when a paste one day does not behave.

So AC 7, 8 and 9 held the moment the reader existed. **Four breaks say they are real**
rather than accidental: only the first line arriving, the first line being sent the instant
its newline lands, blank lines dropped, and the order reversed. Each overrides the default
binding with what a badly-handled paste would look like.

## The half that was genuinely broken was above the reader

And it was found by **reading the command matching**, not by a failing test - because
nothing could compose a multi-line message before this issue, so the hole had never been
reachable.

    line in EXIT_COMMANDS                              equality - safe
    line.startswith(MODEL_COMMAND + " ")               NOT safe
    line.startswith(SKILL_COMMAND + " ")               NOT safe

A stack trace pasted with `/model` on its first line would have been swallowed as a model
switch **and the rest of it thrown away**. Exactly what AC 10 forbids, and exactly the kind
of thing that only appears once something else changes.

A command is now a message of **one line**. Typed commands have no newline in them, so
AC 13 costs nothing - and it is asserted next to AC 10 because a fix for one that broke the
other would have met neither. Both directions are broken and both go red.

## The backslash rule, fourth time

`break_command.py` was written through a heredoc, its search string contained
`"\n" not in line`, and all three breaks reported "did not apply". Rewritten with the Write
tool and a raw string, all three go red.

Four times in one session: a docstring, two reader breaks, and now three command breaks.
Every one the same shape, every one costing a few minutes and a false "did not apply". The
rule in `~/.claude/CLAUDE.md` is not advice about being careful. **It is a rule about which
tool to use for which job**, and the cost of ignoring it is that a break-proof lies to you
in the safest-looking direction - it says a break did not run, when what it means is that
the harness was misspelt.

## Assumptions changed

None.

## What only a person can confirm — one added

Criteria 2, 3, 4, 5, **7, 8, 9**, 24. The paste criteria join the list rather than leave it:
a pipe input proves axiom does the right thing with a `BracketedPaste` event, and only a
person pasting into a real console can confirm that this console produces one. Given
`_is_paste` is a heuristic, that confirmation matters more here than anywhere else in the
issue.

## Next

The remaining nineteen are mostly boundaries and guards: an oversized paste refused rather
than truncated (AC 21), abandoning a part-composed message (AC 24-26), and the unchanged
set (AC 32-36). AC 21 is the one with a real trap in it - #42 exists because of a truncation
on the other side of the conversation.
