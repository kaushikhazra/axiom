# Action

Read `gh issue view 75` cold, then record the baseline: 0 of 44, the suite at 775 tests,
and its wall-clock time. That is the first row of the measurement and every later cycle is
read against it.

Then build the one thing everything else hangs off — **the catalogue, and the boundary that
keeps the body out of it.** A loader that walks `.axiom/skills/`, parses each `SKILL.md`'s
frontmatter with a library, and yields name and description with the instructions left on
disk. Not the tools, not the commands, not the token line: those all read from this, and
each one built before it exists is a guess about its shape.

Two things get settled in the same cycle, because both get harder later:

- **A test that inspects what is actually sent to the model** and asserts no skill's body is
  in it. Written now, this test governs every cycle after it. Written at the end, it is
  written against whatever was built and proves nothing.
- **Where a live-model test lives**, separate from the hermetic suite. AC 15 and AC 16 are
  the criteria most likely to be deferred and then not fit. Pick the lane now, even if
  nothing runs in it yet.

First thing to tackle: **the loader and its catalogue** — because the four tools, both
commands, the token line and the off switch are all views onto it, and none of them can be
shaped correctly until it exists.
