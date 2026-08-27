# Goal

Let the summary of a long conversation hold what only that conversation knows - meeting every
one of the 12 acceptance criteria on GitHub issue #62.

#32 gave the summary a hard bound and made it honest: when it fills, what goes is named one by
one rather than counted. That part works. What it never decided is **what deserves a slot**.

Observed 2026-08-27, first manual pass. A conversation about a career history and then World of
Warcraft compacted twice, and when the bound was reached axiom said:

```
axiom: the summary is full - forgetting 2:
  | - RPG stands for role-playing game
  | - The player starts in the peaceful world of Azeroth and quickly finds themselves caught up in the conflict between the Horde and the Alliance.
```

**"RPG stands for role-playing game" is not a fact about the conversation.** It is general
knowledge the model already has and would produce again on request. It occupied a slot in a
bounded store meant for things the model cannot recover any other way - and the user's own
details were competing with it.

Nothing was lost that time. The car registration survived, and was recalled correctly after two
compactions. But the bound is small, and every slot spent on something the model already knows
is a slot not holding a name, a number, or a decision.

A second observation from the same session, and **not in scope here**: "ventured into Python"
became "**Vented** into Python" across a compaction boundary. That is corruption rather than
loss, it is a different failure from what #32 or this row promises, and it belongs to its own
story. Recorded so a later cycle does not quietly widen this one to cover it.

Done when: all 12 criteria of #62 are met, each with evidence recorded in a cycle log; the suite
is green and hermetic; and the golden transcript's change is accounted for line by line.
