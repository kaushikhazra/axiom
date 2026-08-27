# Action

**Cycle 1 records the baseline, reproduces the hole, fixes it, and covers the criteria.** The
fix is one line. The work is proving the eleven, and most of them are about something *not*
being said - which is the easiest thing to assert by accident.

## 1. Baseline

- `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
  Expect **473 passed**. Record it.
- Copy `tests/baseline/transcript.txt` to `.tmp/transcript-baseline-55.txt`.
- `gh issue view 55`, record all 11 criteria `not-started`.

## 2. Reproduce the hole first

The failing test, before touching `src/`: a directory that **already contains
`.axiom/mcp.json`** and no `model.json`. Pick a model from the list. Today nothing is announced
and the file is written anyway. **Watch it fail.**

An empty directory is not this test. The old behaviour passes there, which is precisely why the
hole survived a cold read.

## 3. Fix

`_remember`: `fresh = not models.DEFAULT_CHOICE_FILE.exists()`, and name the file rather than
its parent. Nothing else changes.

## 4. Cover the eleven, negatives paired with positives

- **AC 1, AC 3, AC 4** - announced in a directory with the folder already there, and in one
  without.
- **AC 2** - the path named is the file. Assert `model.json` appears in it.
- **AC 5, AC 6, AC 7** - two separate `main()` calls. The second is silent, and it is silent
  because the file is there rather than because anything was remembered. A third run after
  deleting the file announces again - that is what proves existence decides.
- **AC 8, AC 9** - both routes, same words: a startup pick, and a `/model` switch.
- **AC 10** - four negatives, one each for a named model, an environment variable, the
  single-model case and the non-terminal fallback. **Each beside a positive**, or "said
  nothing" passes for an implementation that never speaks.
- **AC 11** - a save that fails says it will not be remembered and does **not** claim a file was
  written. Both assertions.

## 5. The transcript

It may move - the wording and the trigger both change. **Fix every stub first**, then regenerate
deliberately, then read the whole diff and check `grep -c "^<"`. Account for every changed line.

## 6. Then

Full suite and the hermeticity command. Break the fix - revert to `.parent.exists()` - and
record how many go red. Write cycle 2's action: a cold read of all 11 from GitHub, before the
diff and before this log.

## Record

Status for all 11. The failing-test-first evidence. The break count. Every transcript line that
changed and why.

**Write no questions into anything.** Decide, record the decision and the reasoning under a
heading that says so, carry on. The exception is safety, not uncertainty.
