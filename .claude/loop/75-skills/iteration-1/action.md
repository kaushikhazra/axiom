# Action

**Five criteria left. This cycle can finish the story.**

**First, AC 29** - the only one not started. A skill whose instructions cannot fit the
model's window is not sent, and the user is told which skill and why.

`--debug-max-context` is how every other compaction test forces a small window; use it
rather than building a huge skill. The check belongs where the instructions become a turn -
both routes, `/skill` and `invoke_skill`, because AC 34's cycle already found that two
routes to one behaviour is how the second one stops obeying the rule.

`compaction.what_will_not_fit` already exists and already produces this shape of message for
an oversized turn (#42). **Use it rather than inventing a second way to say the same
thing** - and check whether the existing path already covers this. If a skill too large for
the window is *already* refused by the oversized-turn check, then AC 29's remaining work is
only that the message names the skill.

**Then break the four that are unproven:** AC 25, 31, 32, 44.

- **AC 25** - load a file beside `SKILL.md` into the catalogue or the instructions.
- **AC 31** - have `write` put the file somewhere the next run does not read.
- **AC 32** - have `delete` leave the file on disk.
- **AC 44** - this one needs its test strengthened before it can be broken. It currently
  drives three exits and asserts nothing about the status. Assert it, then break it by
  making a loaded skill change the exit path.

**If all 44 are break-proven, the goal is met.** Say so, delete the cron, and stop - do not
start polishing. The loop's done-condition is the criteria and the suite, and a cycle that
finds nothing left to do is the cycle that ends it.

Before declaring it met, run the whole thing once more and check three things: the count is
44, `uv run pytest` is green with the live test deselected, and `uv run pytest -m live`
still collects exactly one test. A goal check that trusts the last cycle's numbers is not a
check.

First thing to tackle: **AC 29, and specifically whether #42's oversized-turn path already
refuses it** - because if it does, this is a message change rather than a mechanism, and the
difference is most of the cycle.
