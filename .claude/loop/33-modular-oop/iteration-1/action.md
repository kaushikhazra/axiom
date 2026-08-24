# Action

Establish the baseline. **Do not modify `src/` this cycle** - nothing in the restructure
can be judged until there is a recorded picture of what the program does today.

Start on branch `feature/33-modular-oop`, created from `master`.

Read `src/axiom/__init__.py` in full and the three test modules, then produce three things
and record all of them in `logs/cycle-1.md`:

1. **A behaviour transcript.** Drive `main()` with scripted input against a stub client and
   capture stdout, stderr and exit status for each of: startup with a model that reports its
   context; startup when the model cannot be reached; a normal exchange; a compaction notice
   firing; a `ResponseError` mid-turn; a connection dropped mid-stream with a partial reply;
   Ctrl-C during generation; Ctrl-C at an idle prompt; `/exit`; `/quit`; end-of-input.
   This is the instrument AC 1 is settled with, so capture it verbatim - not a summary of it.

   Writing a new characterization harness under `tests/` is expected and allowed: it is the
   measuring instrument, not the artifact, and it adds without removing. `src/` stays untouched.

2. **An assertion inventory.** Every assertion in `tests/`, listed by test name. AC 2 is
   settled by showing each of these still asserted after the restructure, so a bare count
   is not enough - record what each one actually asserts.

3. **A line count.** `wc -l` of `src/`, and the 447-line ceiling restated against it.

Then, without writing any of it yet, record the shape the restructure will take: which
responsibilities exist in the current file, which module each would move to, and where the
model backend seam would sit so that `ollama` and `httpx` disappear from the session module.
Name it, so the next cycle derives its move from a decision already made rather than
inventing one.

Finally, walk #33's 20 criteria and give each a status token. Almost all will be
`not-started` - that is the correct reading at cycle 1, and the point is the baseline row,
not the score.
