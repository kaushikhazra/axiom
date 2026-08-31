# Cycle 10 — 2026-08-31, started 19:08 +0530

## Where the artifact stands

**39 of 44 break-proven**, up from 34.

| bucket | count | criteria |
|---|---|---|
| met, break-proven | **39** | the 34, plus AC 14, 34, 35, 40, 43 |
| implemented, break not run | 4 | AC 25, 31, 32, 44 |
| not started | 1 | AC 29 |

## AC 34 was false, and measuring it is what found that

The action named it as the one most likely to be quietly false. It was. Two invocations put
the instructions in twice:

    BODY-TEXT appears 2 times

Not a test to write - a change to make. `Library` now tracks what has been invoked and
answers a repeat with a pointer instead of the text. The model still learns the skill
applies and where to look; what it does not get is a second copy filling the window.

**A model that re-invokes every turn is not hypothetical.** It is the cheapest way for a
model to be sure it is still following the skill, and before this it would have filled the
window with copies of one file while nothing looked wrong.

## AC 35, and the half that only appears once AC 34 exists

The pointer is a **claim about the conversation**: "already in this conversation, above."
Compaction can make that false, and a model told that about instructions which are no longer
there has been given a wrong answer rather than a short one.

So `forgotten()` clears the belief when compaction has been through, and the skill becomes
sendable again. The user is told what went by `note_facts_forgotten`, which already names
forgotten facts - the mechanism that exists, not a second one invented for skills.

**AC 34 and AC 35 are a pair and neither is safe alone.** Adding the first without the
second would have produced a session that silently refuses to re-send instructions it has
just discarded.

## AC 43 - the weakness cycle 2 recorded is now structural

Cycle 2 broke the required-field check and `_one` raised `KeyError` rather than reporting,
because `parsed["name"]` is only safe while a guard above it happens to run first. **A whole
session's startup depended on the order of two lines in one function.**

`read()` now catches whatever `_one` does not anticipate, names the folder, and carries on.
The test injects a `fault_in` that raises and asserts the other skill still loads.

## The two routes that had to become one

`/skill` called `skills.instructions` directly, bypassing the library. That is two routes to
one behaviour, and it would have made AC 34 true for a model and false for a user typing
`/skill one` twice. It now goes through `library.invoke` like the tool does.

## The breaks — five, four narrow

| break | red |
|---|---|
| a repeat sends the instructions again | AC 34 |
| compaction does not clear the belief | AC 35 |
| the read failure loses its reason | AC 40 |
| the model's invocation is not announced | AC 14 |
| an unexpected failure escapes `read()` | AC 43 |

**AC 43's break printed no summary line on the first attempt**, and cycle 5's guard caught
it: the scripted edit replaced `try:` with `if True:` and left a dangling `except`, so the
file would not parse and pytest never ran. Re-done through the Edit tool as a `raise` inside
the handler, it turned exactly one test red.

That guard has now paid for itself twice. Without it the log would read "AC 43's break found
nothing", which is the opposite of true.

## What is not counted

AC 25, 31, 32 and 44 have passing tests and no breaks. AC 44's test is the thin one: it
drives `/exit`, `/quit` and end-of-input with a skill loaded and would catch a crash or a
hang, but it does not assert the status explicitly. Both are next cycle's work, and neither
is counted until then.

## The suite

    820 -> 829 tests, all passing, 78.54s, 1 deselected

Arithmetic: 820 + 9 = 829. Holds. Wall clock flat.

## Assumptions that changed

None, but one was confirmed the hard way: **"already true, just needs a test" is a claim to
check, not to act on.** AC 14 was that and turned out to be right. AC 34 was assumed the same
way in cycle 1's planning and was false. The difference cost one measurement to find.

## Goal check

**Not met.** 39 of 44. Next action written.
