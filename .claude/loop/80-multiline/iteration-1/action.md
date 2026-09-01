# Action — cycle 1

**Read and survey. Do not write to `src/`.**

The artifact ships today and the first decision - what reads the keys - is the one that
cannot be taken back cheaply. `~/.claude/CLAUDE.md` asks for a search before a build, and
naming the library in cycle 2 without having looked is the shortcut that rule exists to
stop.

Produce `logs/cycle-1.md` holding:

1. **The starting suite.** `uv run pytest`. Count, pass, fail, wall-clock. It should be
   876 passed, 1 deselected, ~92s. If it is not, that is the finding and everything waits.

2. **Each of the 36 criteria in a bucket** — met with a proving test, true but unproved, or
   not started. Read them from `gh issue view 80`. Expect most of "Unchanged" and "Exit" to
   be already true: they are guards on behaviour that ships.

3. **The library survey.** At least three candidates, not one. `prompt_toolkit` is the
   obvious name; find the others before settling. For each, say:
   - does it read ctrl+enter separately from enter, **on Windows**
   - what it brings that would otherwise be hand-written - history, arrows, word-delete
   - what it costs: install size, dependencies of its own, and whether it takes over the
     terminal in ways that fight `Rendered`
   - whether it can be confined to the terminal path, leaving piped runs untouched
   **Recommend one, and say what would have to be true for the recommendation to be wrong.**

4. **Where the seam is.** `terminal.read_line` is the only reader for a typed line, and
   `Typed` wraps a second one for the scheduled path. Name exactly which functions change
   and which must not. `use_input` exists for tests to substitute a reader - check whether
   it is enough, because if the tests cannot swap the new reader out, nothing here is
   testable.

5. **What a test will never be able to prove**, listed by criterion number. This list is the
   manual pass's brief and it starts now, not at the end.

## Do not

- Add a dependency this cycle. Recommending one is the output; installing it is cycle 2.
- Touch `tests/baseline/transcript.txt`.

Then write `action.md` for cycle 2.
