# Cycle 1 — reproduced the hole, fixed it, covered the eleven

2026-08-28 00:42–01:02 IST. Fail-safe 04:42 IST.

**487 tests, green and hermetic** (was 473). 14 new in `tests/test_announce.py`.
**Golden transcript unchanged** - see below, and it is worth knowing why.

## The failing test came first, and it proved the point about the empty directory

Five of fourteen failed before the fix. The one that matters:
`test_a_project_that_already_has_the_folder_is_still_told` - a directory holding
`.axiom/mcp.json` and no `model.json`, which is **every project that configures MCP**.

And `test_a_directory_with_nothing_in_it_is_told_too` **passed before the fix**. That is the
whole story of this row in one line: the old behaviour is correct in an empty directory, so any
test written there proves nothing, and that is why a cold read never caught it.

## The fix

`_remember`: `not models.DEFAULT_CHOICE_FILE.exists()` rather than `...parent.exists()`, and the
path named is the file rather than the folder. Two lines. `note_choice_saved`'s docstring
corrected - it described a folder condition that is no longer the one in force.

## Decision — existence decides, not memory

Recorded because the alternative is tempting and wrong. A flag saying "already announced" is
true within a run and forgotten between them, so the second run would announce again. Worse, it
could not do the thing a user would expect: **delete the file and axiom announces again**,
because the condition is the file. `test_the_file_decides_and_nothing_is_remembered_between_runs`
drives three separate `main()` calls to pin exactly that - announce, silent, delete, announce.

## The negatives are all paired

Nine of the fourteen assert that something was **not** said, which passes trivially for an
implementation that never speaks. Every one sits beside a positive, and
`test_the_negatives_are_not_vacuous` exists solely to say so out loud: same fixture, same
directory, a route that does write - and it speaks.

`observe.md` flagged this as the row's main hazard, and #57's cold read had just found the third
instance of the same shape, so it was worth the extra test rather than a comment.

## The transcript did not move, and that is not luck

Every characterization scenario runs under `conftest.isolate_remembered_choice`, which points
the choice file at a fresh `tmp_path` where neither the file nor the folder exists. Both the old
condition and the new one are true there, so both announce, and the recorded output is identical.

**Which means the transcript could never have caught this either.** Worth stating plainly: the
golden master is a good instrument for behaviour that varies with input, and blind to behaviour
that varies with what is already on disk.

## Break-and-watch

Reverting both lines to the folder turns **5 red** - the same five that failed before the fix.
Restored and verified by grep.

## Live, against the case that started it

A directory built to look like a project that configures MCP:

```
C:\Projects\.tmp\axiom-ac55\.axiom\mcp.json      (and no model.json)

run 1:  axiom: remembering this choice in .axiom\model.json
run 2:  (nothing)
```

Announced once, silent after, and it names the file. Before this row, run 1 said nothing at all
and every run after it said nothing either.

## Status — all 11 criteria

| criteria | status |
|---|---|
| AC 1–11 | `attempted` |

Not `met-with-evidence`. This is the cycle that wrote the code. Every criterion has a test, the
break turns five red, and the live case is above - and the verdict still belongs to a cycle that
has not read this log.

## Cycle 2 will

Cold-read all 11 from GitHub before the diff and before this log. Where to attack:

- **AC 10's four negatives** - could any pass for a reason other than the one claimed? The
  paired positive covers "never announces at all", but is there a route that writes without
  announcing, which these would not see?
- **AC 7** - three runs prove existence decides. Is there a fourth state - the file present but
  empty, or present but a directory?
- **AC 11** - `mkdir` is patched to fail. Does the same hold when the *write* fails rather than
  the directory creation?
- **AC 9** - the two routes are compared after stripping the prompt. Confirm that strip is not
  hiding a real difference.
- And the standing question: which of the fourteen survive the break, and is each one fine?
