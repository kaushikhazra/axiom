# Cycle 3 — the cold read

2026-08-27 14:40–15:05 IST. Fail-safe 16:52 IST.

Criteria read from `gh issue view 49` **before** the diff and before cycle 2's log, and
attacked rather than confirmed. **419 tests, green and hermetic** (was 413).

Not a genuinely fresh reader - no second agent - and `observe.md` asks that this be said
rather than a cold read claimed that was not cold. Every finding below came from running
something hostile, and each fix is paired with a break-and-watch.

## Five findings. Three were the criteria being read too loosely

### 1. AC 25 — a name typed at the list was refused, and the criterion says it is valid

The criterion refuses "an entry that is **not a number and not an installed name**". Cycle 2
read that as "numbers only" and wired the list to `models.picked` alone:

```
axiom: which model? (enter to keep the current one) ornith:9b
axiom: 'ornith:9b' is not a number - type a number from 1 to 3
```

The name is one of the two things the criterion says the list takes - and worse, it is the
*same string* that works at `/model ornith:9b`, so a user was being told the name they had
just used does not work here. Fixed, and the refusal widened to
`type a number from 1 to N, or a model's full name` - advice narrower than the truth is its
own defect.

### 2. AC 27 — the list was not shown at all

"`/model` with exactly one model installed **shows that model marked as current** and says
there is nothing to switch to." Two things. Cycle 2 did the second only:

```
axiom: solo:1b is the only model installed - nothing to switch to
```

Cycle 2's own test asserted `"nothing to switch to" in out.out` and
`"which model?" not in out.out` - both true of an implementation that shows nothing. **The
test was written from the implementation rather than from the criterion.** The list is now
shown first, one row, marked `(current)`.

### 3. AC 31 — the current model vanished and nothing said so

"If the model in use has been removed from the host since the session started, it is still
shown as the current one." Probed with a host that lists the model at startup and not after:

```
axiom: models on http://localhost:11434
  1. gemma2:2b
  2. ornith:9b
axiom: which model? (enter to keep the current one)
```

Nothing marked, and no way to tell what the session is talking to.

It *cannot* appear in the list - AC 2 ties this list to the startup list, which holds what the
host reports and nothing else - so the reading taken is that the fact has to be **said**:
`still on qwen2.5:7b, which <host> no longer lists`. Recorded as a reading rather than a
literal satisfaction of "shown", because the literal one contradicts AC 2.

### 4. AC 18 had no test at all

"If the conversation does not fit the new model's window, it is compacted the way a long
conversation is." Cycle 2 relied on the existing compaction machinery and never checked -
exactly the kind of thing that gets assumed.

Writing the test **also found the test wrong before it found the code right**: the first
version used a 2000-token window and a two-word conversation, which fits comfortably, so
nothing should have compacted and nothing did. A real 3000-character-per-message conversation
against a 600-token window compacts, is announced, and is announced *before* the payload goes
out. The code was correct; the absence of evidence was the defect.

### 5. AC 23 had no test either

"If a switch cannot be saved, it still takes effect and axiom says it will not be remembered."
Assumed to be `_remember` shared with #48 - true, and unverified through this path. Now
asserted on `asked_about[-1]`, so "the switch took effect" is measured rather than inferred
from a printed line.

## Break-and-watch

| broken | went red |
|---|---|
| numbers only at the list | 1 — AC 25 |
| current-model-missing line removed | 1 — AC 31 |
| history cleared on a switch *(cycle 2)* | 2 — AC 10, AC 11 |
| `start()` guard removed *(cycle 2)* | 1 — AC 14, with `RuntimeError` |
| Ctrl-C treated as Ctrl-D *(cycle 2)* | 1 — AC 26 |

## Status — all 34 criteria

| criteria | status |
|---|---|
| AC 1–34 | `met-with-evidence` |

Each has a test in `tests/test_switch.py` or `tests/test_oversized_turn.py`, cited by number in
its docstring. AC 19 is additionally evidenced by the two amended #42 tests, since it
supersedes that story's exit.

## Standing checks

- **419 passed**, hermetic. No test reaches a live Ollama.
- **Transcript unchanged since cycle 2**: two removed lines, both replacements from the AC 19
  change, each accounted for in that log. The fixes here touched no line it records.
- No orphaned processes; no `.axiom/` left in the repo.

## What this row leaves behind

- **`Running` and `_prepare` are the seam for anything else that varies per model.** A third
  story that changes models - a fallback, a per-task model - rebinds one object rather than
  hunting six locals.
- **`StubBackend` now answers per model** (`infos`, `capable`). Any future criterion about
  "the model in use" should assert on `asked_about`, `options` or `tools_sent` rather than on
  a printed line. That single blindness has now cost two rows a real defect.
- **#42 AC 6 is superseded**, recorded in the test docstrings and in cycle 2's log.

## Exit

Converged — `loop.md` exit 1. Commit, push, PR referencing #49, merge, delete the branch, mark
the row done, **say the queue is empty**, and update the handoff: manual testing is next, and
both #48 and #49 changed what starting axiom looks like.
