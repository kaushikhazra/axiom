# Assumption

Standing inputs. These are given - do not re-derive them, and do not spend a cycle deciding
them.

## The codebase this lands in

Rows 1 to 11 merged. **473 tests, green and hermetic** at scaffold time.

- **`__init__._remember(chosen, host)` is the whole of the current behaviour:**

  ```python
  fresh = not models.DEFAULT_CHOICE_FILE.parent.exists()
  problem = models.write_choice(chosen, host)
  terminal.note_choice_saved(problem, str(...parent) if fresh and not problem else "")
  ```

  `fresh` asks about the **folder**. That is the defect, and it is one line.
- **`terminal.note_choice_saved(problem, path)`** prints the failure to stderr when there is a
  problem, the path to stdout when `path` is non-empty, and nothing otherwise. The two-argument
  shape - where an empty string means silence - is what makes AC 11 easy to get wrong.
- **`_remember` is called from exactly two places**: `_settle_model`, after a pick from the
  startup list, and `_switched_to`, after a mid-session switch. **Both must announce** (AC 8,
  AC 9), and they already share the function, so a fix there covers both by construction.
- **Four routes settle a model without writing anything** - a named model, the single-model
  case, the non-terminal fallback, and a cancelled list. None calls `_remember`, so AC 10 is
  already structurally true; it needs proving, not building.
- **`models.write_choice` creates the parent directory** with `mkdir(parents=True,
  exist_ok=True)` and returns a problem string rather than raising.
- **`models.DEFAULT_CHOICE_FILE` is `Path(".axiom") / "model.json"`**, resolved at call time
  through `_where` so a test can point it elsewhere.
- **`tests/conftest.py`'s `isolate_remembered_choice` is autouse** and repoints
  `models.DEFAULT_CHOICE_FILE` at `tmp_path/.axiom/model.json` for every test.
- **`StubBackend`** takes `models`, `capable`, `infos`, `listing`, and records `asked_about`
  and `capability_asks`.

## The defect, as observed

2026-08-27, first manual pass. A directory that already had `.axiom/` - because an earlier run
had made it - produced no announcement while still writing the file. That was **correct** under
#48 AC 30, which is about the folder. The general case is a project with `.axiom/mcp.json`,
where the announcement can never fire at all.

Confirmed both ways at the time: a genuinely empty directory announces; one with the folder
already present does not.

## Given

- **`requires-python = ">=3.12"`; the venv is 3.14.3.** `uv` and pytest. No new dependency.
- **The repo's own rules apply**: KISS over structure, one command per shell invocation,
  nothing committed under a `temp` name, project-local `.tmp/`, loop files stay in this folder
  while code stays in `src/` and `tests/`.
- **The branch is `feature/55-announce-the-file`.** Commits reference #55.
- **`master` is protected by a hook.** Everything lands on the branch and merges by PR.
- **Four rows follow this one** - #56, #61, #62, #60. On exit, hand over per the queue.
- **One cron drives the whole queue.** It reads `queue.md` for whichever row says `running`.
  Marking the next row running *is* the handover. **Never delete it.**

## Decided - do not reopen

- **The trigger moves from the folder to the file.** `not DEFAULT_CHOICE_FILE.exists()` rather
  than `not ...parent.exists()`.
- **The path named is the file.** A user told about `.axiom` and left to guess which file is
  told less than they need; the point is that they can go and look at it.
- **Existence decides, not memory.** No flag, no counter. The file being absent before the write
  is the whole condition, which is what makes it true across separate runs.
- **A failed save says only that it will not be remembered.** It never also claims a file was
  written, because none was.
- **#48 AC 30 is superseded**, and a comment saying so is already on that issue.

## Carried forward, worth not relearning

- **An assertion that a *wrong* implementation also satisfies proves nothing.** #57 AC 7,
  #48 AC 33, #49 AC 25 and AC 27. This row is full of "nothing was said" assertions, which is
  the easiest thing in the world to satisfy by accident - pair every negative with a positive.
- **Fix every stub before regenerating the transcript.** #48 wrote a golden master full of
  `AttributeError` and only the copy-aside made it recoverable.
- **Read a diff as a diff**, and check for removed lines explicitly.
- **A `sed`/`.replace()` that does not match reports success.** Grep after scripted edits.
- **The formatter is not the only thing that edits a file.** Verify what landed.
