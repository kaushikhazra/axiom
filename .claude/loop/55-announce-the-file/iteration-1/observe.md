# Observe

Record each cycle:

- A status token for **every one of #55's 11 criteria**: `not-started` / `attempted` /
  `met-with-evidence` / `blocked`. All eleven get a token every cycle, even "no change."
  Cite them as "AC 4".
- How far that moved from the last cycle, and what moved it.
- What is still missing, and whether it can be closed from here at all.
- Any assumption that changed.

## Where this will be tempting to cheat

**AC 1 and AC 3 - the case that started this.** The old behaviour passes any test run in an
empty directory, because there the folder *is* created. The criterion that separates right from
wrong is a directory that **already has `.axiom/mcp.json` and no `model.json`**. If only one
test is written for this row, write that one.

**AC 7 - decided by the file being there, not by anything remembered.** The lazy implementation
tracks "have I said this yet" in a variable, which is true within a run and forgotten between
them - so a second run announces again. The criterion is that the *file's existence* decides.
Prove it across two separate `main()` calls, not two writes in one.

**AC 5, AC 6 - not being told twice.** A test that runs once cannot see a repeat. Two runs, and
the second must be silent.

**AC 10 - a run that writes nothing announces nothing.** Four routes settle a model without
writing: a flag, an environment variable, the single-model case, the non-terminal fallback. Each
needs its own assertion that nothing was said, and each must sit beside a positive proving the
announcement works - otherwise "said nothing" passes trivially for an implementation that never
announces at all. #48 AC 14 has exactly this shape and its four negatives are the model.

**AC 11 - a save that fails.** It must say the choice will not be remembered and **not** also
claim a file was written. Two assertions, and the second is the one a careless fix drops.

**AC 9 - the switch says it in the same words.** #49's switch path calls `_remember` too. A fix
applied only to startup meets half the criterion and looks complete.

## What counts as evidence

- **The file system, not a flag.** Assert on whether `model.json` exists before and after, and
  drive two separate runs where the criterion is about repetition.
- **A directory with `mcp.json` and no `model.json`** is the fixture this row turns on. Build it
  explicitly.
- **AC 10's four negatives** are settled the way #48's were - each paired with a positive.

## Standing checks

- **The full suite is re-run in every cycle that changes code**, and the result recorded. The
  baseline is **473 tests, green** at scaffold time, 2026-08-28 00:42 IST.
- **The suite must stay green with no Ollama running**, and must not be changeable by the
  environment:
  `env AXIOM_HOST=http://127.0.0.1:1 AXIOM_MODEL=nonsense:99b AXIOM_DEBUG_MAX_CONTEXT=7 uv run pytest -q`
- **The golden transcript may change**, since the announcement's wording and trigger both move.
  Copy it aside in cycle 1. **Fix every stub before regenerating** - #48 cycle 2 regenerated
  against a `StubClient` with no `list` and wrote a baseline in which every scenario ended in
  `AttributeError`. Then read the diff as a diff and check `grep -c "^<"` explicitly.
- **`conftest.isolate_remembered_choice` is autouse** and points the choice file at `tmp_path`.
  A test about announcing must not fight it - point at its own path, or let the fixture do it.
- **Ask whether each test could pass if the feature did nothing**, then break the feature and
  watch it go red. Record the counts.
- If a criterion cannot be met as written, say so plainly and say why.

## The cycle that writes the code never declares it done

A separate cycle checks, reading the criteria from GitHub **before** the diff and before the
previous log. **Attack each criterion rather than confirming it.**

This has found a real defect in **seven consecutive issues** - #40 AC 7, #41 AC 9, #42 AC 3,
#43 AC 6, #48 AC 33, #49 AC 25 and AC 27, #57 AC 7.

**Three of the last four were the same shape**: an assertion a *wrong* implementation also
satisfies - a substring, a count, a message that is right for the wrong reason. #57's was
`"could not be read"`, which a strict decoder produces too. **This row is unusually exposed to
it**, because most of its criteria are about something *not* being said, and "nothing was said"
is the easiest assertion in the world to satisfy by accident.

## Goal check

- **Met** - all 11 criteria `met-with-evidence`, suite green and hermetic, transcript change
  accounted for line by line.
- **Not met** - report which criteria moved and which did not, and write the next action.
- **Answer did not move** - report the flat result and stop. Do not run another variant.
