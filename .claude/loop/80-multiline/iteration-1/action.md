# Action — cycle 2

**Prove the confinement first. Then add the dependency.**

Cycle 1 recommends `prompt_toolkit` and names the one thing that could overturn it: if it
cannot be kept off the piped path, AC 30 fails, the golden transcript moves, and 876 tests
change meaning. Adding it and then finding out is the expensive order.

## Do these in order

1. **Add `prompt_toolkit` to `pyproject.toml`** and sync. One dependency of its own,
   `wcwidth`, BSD, Python >= 3.10 - all recorded in cycle 1.

2. **Prove it is confined, before writing any reader.** A test that:
   - runs a piped session, with `sys.stdout.isatty()` false, through `main()`
   - asserts the output is byte-identical to the same session before the dependency existed
   - and asserts `builtins.input` was the thing that read the line

   Then **run the whole suite and check `tests/baseline/transcript.txt` is untouched.**
   If it moved, stop and report - that is the finding, and no reader gets written until it
   is understood.

3. **Add the substitution hook.** Cycle 1's finding: every existing test supplies input by
   monkeypatching `builtins.input`, so a terminal-only reader is unreachable from all 876 of
   them. Give the composing reader its own hook, the way `use_input` is one for the timed
   path. **Without this nothing about #80 is testable**, so it comes before the feature and
   not after.

4. **Then the reader**, terminal-only, behind that hook. Bind:

       enter        c-m            accept
       ctrl+enter   escape, c-j    insert a newline

   Not `"c-enter"`, which does not exist, and not a bare `c-j`, which also catches ctrl+J.
   The mapping was read out of `prompt_toolkit/input/win32.py` and is quoted in cycle 1.

## Prove, do not claim

Take AC 30, 31, 32, 33 first - the guards. They are the ones a wrong move breaks silently,
and they are testable today without any of the new behaviour existing.

**AC 33 needs a before.** Capture a single-line session's bytes now, on this branch, before
the reader lands - otherwise there is nothing to compare against and the criterion becomes
an opinion.

## Do not

- Write the composing behaviour this cycle. Confinement, hook, reader - in that order, and
  stop when the cycle runs out rather than rushing the next step.
- Regenerate the baseline.

## Record

`logs/cycle-2.md`, per `observe.md`. Criteria met out of 36, the suite count and wall-clock,
the baseline's state, and any addition to the list of what only a person can confirm.
