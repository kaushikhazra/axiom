# Action

**Take the cheap remainder.** Ten criteria left, seven of them small. No live model time is
needed again - AC 15 and AC 16 are measured and recorded.

In this order:

- **AC 44** - `/exit`, `/quit` and end-of-input leave the same way with skills loaded as
  without, same status. Three ways out, asserted with a skill loaded.
- **AC 43** - no skill failure ends the session: loading, listing, reading, writing,
  deleting, invoking. **Cycle 2 found the soft spot** - `_one` raises rather than returning
  a problem if its guards are ever reordered, and nothing between it and `read()` catches
  it. Put the guard around the whole of `_one` and prove it with a skill file that cannot be
  parsed at all.
- **AC 40** - a skill file that cannot be *read* - a permission error, not a parse error -
  is reported with the reason and the session continues. Distinct from the parse case that
  already has a test.
- **AC 31, AC 32** - a skill written in one run is there in the next; deleted, gone. Two
  sessions over one directory, which the `run` helper already supports.
- **AC 25** - files beside `SKILL.md` are not loaded, and the instructions may name one by
  path for the model to read.
- **AC 14** - the model's invocation is shown the way a tool call is shown. Already true
  through `note_tool`; it needs a test, not a change.

**Then the three that touch compaction**, and only then, because each needs a session driven
far enough to compact:

- **AC 34** - invoking the same skill twice in one run leaves its instructions in the
  conversation once.
- **AC 35** - when compaction lets go of an invoked skill's instructions, that is named the
  way other forgotten facts already are.
- **AC 29** - a skill whose instructions cannot fit the model's window is not sent, and the
  user is told which skill and why.

`--debug-max-context` is how the other compaction tests force a small window; use it rather
than building a large skill.

**Narrow breaks, one thing each.** Cycles 3 and 6 both lost criteria to breaks that took
several tests down for the wrong reason.

**AC 34 is the one most likely to be quietly false.** Nothing currently prevents a second
invocation appending the same instructions again - `/skill one` twice would do it, and so
would a model that re-invokes each turn. If it is not already true, that is a change, not a
test.

First thing to tackle: **AC 43's guard around `_one`**, because cycle 2 recorded that
criterion as resting on the order of two checks rather than on structure, and it is the only
item in this list that is a known weakness rather than a missing test.
