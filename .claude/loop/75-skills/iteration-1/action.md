# Action

**Clear the second bucket before building anything new.** Ten criteria have passing tests
and no break: AC 17, AC 20, AC 21, AC 22, AC 23, AC 24, AC 26, AC 27, AC 30, AC 42. That is
more than twice the number that are proven, and a bucket that size is where a vacuous test
hides.

Run them as a batch - most are one edit each in `skills.py`:

- **AC 42** is the one cycle 3 got wrong. Move validation to *after* the file is opened for
  writing, so a refused write truncates the good skill. It must go red for **that**, not
  because its setup stopped working. If the test passes under this break, it is testing
  nothing and needs rewriting before it counts.
- **AC 22** - make a tool-written skill differ from a hand-written one.
- **AC 17** - return the body instead of the file. **AC 20** - delete without refreshing.
- **AC 26, AC 27, AC 30** - remove each guard in `_one` and `read` in turn.
- **AC 23, AC 24** - drop the frontmatter parse; accept any file as a skill.

Any test that stays green under its own break is a defect in the test. Say so in the log
and rewrite it - that is a better outcome than a break that dutifully goes red.

**Then check the wall clock before anything else.** Cycle 4 measured 91.34s against cycle
3's 79.08s and attributed it to machine load, on the evidence that all eight slowest tests
are pre-existing MCP waits. **If this cycle adds no tests and still measures ~91s, that
attribution stands. If it is back near 79s, it also stands. If it has climbed again, it does
not** - and finding out costs one `uv run pytest` that was going to happen anyway.

**Only then start `/skill` and `/skills`.** They sit beside `MODEL_COMMAND` in
`src/axiom/__init__.py` and are handled before the turn starts, the way `/model` is. Six
criteria, AC 5 to AC 11, and AC 9 and AC 10 both say *nothing is sent to the model* - which
is the half a test will forget, because a command that prints the right thing and also
starts a turn looks correct on screen.

First thing to tackle: **the AC 42 break**, because cycle 3 recorded it as unproven for a
specific reason and a bucket that is never emptied is how eleven criteria become forty.
